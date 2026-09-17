import hmac
import json
import logging
import os
import re
import threading
import time
import unicodedata
from collections import deque
from pathlib import Path
from typing import List, Dict, Any, Deque, Set, Tuple

from dotenv import load_dotenv
from chromadb.utils import embedding_functions
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from openai import OpenAI, APIConnectionError, APIStatusError, APITimeoutError, RateLimitError
from request_log import RequestTrace, chunk_id_from_metadata, configure_request_logging, current_trace
from chroma_store import (
    ARABIC_COLLECTION_NAME,
    COLLECTION_NAME,
    get_chroma_client,
    get_chroma_collection,
    get_chroma_dir_env,
    get_resolved_chroma_dir,
    log_chroma_configuration,
)
from saint_index_overrides import (
    MANUAL_SAINT_NAME_EXCLUSIONS,
    MANUAL_SAINT_NAME_REPLACEMENTS,
)
from arabic_saints_index import ARABIC_SAINTS_INDEX
from task_analysis import TaskAnalysis, analyze_request

load_dotenv()

logger = logging.getLogger("orthodox.api")
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
configure_request_logging()
# httpx logs every OpenAI HTTP call at INFO; the request trace already records them.
logging.getLogger("httpx").setLevel(logging.WARNING)

TRUTHY_VALUES = {"1", "true", "yes", "on"}


def _env_flag(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in TRUTHY_VALUES


def _env_int(name: str, default: int, minimum: int = 0) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default)).strip()))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)).strip())
    except ValueError:
        return default


# --- Hardening configuration (see DECISIONS.md, Security section) ---
# Shared secret that the Next.js server routes must send as X-Internal-Key.
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "").strip()
INTERNAL_KEY_HEADER = "x-internal-key"
# Header the Next.js proxy uses to forward the end user's IP for rate limiting.
CLIENT_IP_HEADER = "x-client-ip"
# Paths that never require the internal key (platform health checks).
AUTH_EXEMPT_PATHS = {"/health"}
ENABLE_DEBUG = _env_flag("ENABLE_DEBUG")

MAX_QUESTION_CHARS = _env_int("MAX_QUESTION_CHARS", 1000, minimum=1)
MAX_TOP_K = 12
MAX_HISTORY_MESSAGES = 12
MAX_HISTORY_MESSAGE_CHARS = 4000
ANSWER_MAX_TOKENS = _env_int("ANSWER_MAX_TOKENS", 1200, minimum=64)
# Tables, lists, study guides and broad requests need more room (GEN-004): a 40-row saint
# list was cut off at 1200 tokens in phase 4 step 3.
ANSWER_MAX_TOKENS_TASK = _env_int("ANSWER_MAX_TOKENS_TASK", 2400, minimum=64)
OPENAI_TIMEOUT_SECONDS = _env_float("OPENAI_TIMEOUT_SECONDS", 25.0)
OPENAI_MAX_RETRIES = _env_int("OPENAI_MAX_RETRIES", 1)
CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
CHAT_TEMPERATURE = _env_float("OPENAI_CHAT_TEMPERATURE", 0.2)

# --- Retrieval scoring (DECISIONS.md RET-002/RET-003) ---
# Chroma returns squared L2 distance between unit-length embeddings (0 = identical,
# 2 = opposite). If the best chunk across all queries is farther than this, the
# question is treated as having no relevant source. 1.0 was chosen from the eval
# data: every answerable English question had a best distance <= 0.971 and every
# out-of-corpus question >= 1.053. 0 disables the check.
VECTOR_DISTANCE_THRESHOLD = _env_float("VECTOR_DISTANCE_THRESHOLD", 1.0)
# Arabic embeddings were built from un-normalised glyph text (AUDIT C2); their
# distances do not separate relevant from irrelevant, so the check is off by default.
ARABIC_VECTOR_DISTANCE_THRESHOLD = _env_float("ARABIC_VECTOR_DISTANCE_THRESHOLD", 0.0)
# Number of prior conversation turns passed to the model as real messages.
HISTORY_TURNS_FOR_MODEL = _env_int("HISTORY_TURNS_FOR_MODEL", 6)

# --- Request analysis (DECISIONS.md RET-006) ---
# One cheap call separates the retrieval query from the requested format before retrieval.
TASK_ANALYSIS_ENABLED = _env_flag("TASK_ANALYSIS_ENABLED", "1")
TASK_ANALYSIS_MODEL = os.getenv("TASK_ANALYSIS_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
TASK_ANALYSIS_TIMEOUT_SECONDS = _env_float("TASK_ANALYSIS_TIMEOUT_SECONDS", 8.0)

# --- Broad and list requests (DECISIONS.md RET-007) ---
# Broad requests retrieve more chunks, from the main query plus the analysis sub-queries.
BROAD_RETRIEVAL_TOP_K = _env_int("BROAD_RETRIEVAL_TOP_K", 16, minimum=1)
BROAD_PER_QUERY_MIN = _env_int("BROAD_PER_QUERY_MIN", 2)
# "Saints whose names start with G": entries come from the saint index, not from vector search.
# 30 keeps a described table under ~10 s; 40 took 12 s, too close to the 20 s proxy timeout (GEN-004).
SAINT_LIST_MAX_ENTRIES = _env_int("SAINT_LIST_MAX_ENTRIES", 30, minimum=1)
SAINT_LIST_EXCERPT_CHARS = 600
# Comparisons with another church: extra chunks that contain its name (RET-008).
TRADITION_RETRIEVAL_TOP_K = _env_int("TRADITION_RETRIEVAL_TOP_K", 6, minimum=1)
# (pattern in the request, case-sensitive substrings to require in a chunk)
TRADITION_TERMS = (
    (r"catholic|roman church|church of rome|pope of rome|latin church", ("Catholic", "Roman")),
    (r"protestant|lutheran|evangelical|reformation", ("Protestant",)),
    (r"anglican|church of england", ("Anglican",)),
    (r"byzantine|greek orthodox|eastern orthodox|russian orthodox|chalcedonian", ("Byzantine", "Chalcedonian")),
)
COMPARISON_CUE = re.compile(r"differ|compar|contrast|versus|\bvs\.?\b|\bthan\b|\bbetween\b", re.IGNORECASE)

# --- Prompts are versioned files under prompts/ (DECISIONS.md GEN-001) ---
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
PROMPT_VERSION = os.getenv("PROMPT_VERSION", "v3").strip() or "v3"


def _load_prompt(name: str) -> str:
    path = PROMPTS_DIR / f"{name}_{PROMPT_VERSION}.md"
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise RuntimeError(f"Prompt file missing: {path}") from exc


ENGLISH_SYSTEM_PROMPT = _load_prompt("english")
ARABIC_SYSTEM_PROMPT = _load_prompt("arabic")

# Human-readable titles for the source files, used in the numbered context blocks and
# in the `label` of each returned source.
SOURCE_TITLES = {
    "catechism1.pdf": "Catechism of the Coptic Orthodox Church, Volume 1",
    "catechism2.pdf": "Catechism of the Coptic Orthodox Church, Volume 2",
    "saints1.pdf": "Encyclopedia of the Saints and Fathers of the Church, Volume 1",
    "saints2.pdf": "Encyclopedia of the Saints and Fathers of the Church, Volume 2",
    "saints3.pdf": "Encyclopedia of the Saints and Fathers of the Church, Volume 3",
    "saints4.pdf": "Encyclopedia of the Saints and Fathers of the Church, Volume 4",
    "full arabic catechism.pdf": "كاتيكيزم الكنيسة القبطية الأرثوذكسية",
    "full saints arabic.pdf": "قاموس آباء الكنيسة وقديسيها",
}
CITATION_RE = re.compile(r"\[(\d+(?:\s*[,;]\s*\d+)*)\]")

CHAT_RATE_LIMIT_PER_MINUTE = _env_int("CHAT_RATE_LIMIT_PER_MINUTE", 20)
CHAT_GLOBAL_RATE_LIMIT_PER_MINUTE = _env_int("CHAT_GLOBAL_RATE_LIMIT_PER_MINUTE", 300)
RATE_LIMIT_WINDOW_SECONDS = 60

GENERIC_SERVER_ERROR = "The assistant could not generate a response right now. Please try again."
GENERIC_BUSY_ERROR = "The assistant is busy right now. Please try again in a moment."
GENERIC_TIMEOUT_ERROR = "The assistant took too long to respond. Please try again."


class SlidingWindowRateLimiter:
    """In-memory sliding-window counter keyed by an arbitrary string (usually an IP).

    Good enough for a single-process backend; not shared across processes or hosts.
    """

    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit
        self.window_seconds = window_seconds
        self._events: Dict[str, Deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> Tuple[bool, int]:
        """Record one hit for `key`. Returns (allowed, retry_after_seconds)."""
        if self.limit <= 0:
            return True, 0
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            events = self._events.setdefault(key, deque())
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= self.limit:
                retry_after = int(events[0] + self.window_seconds - now) + 1
                return False, max(1, retry_after)
            events.append(now)
            # Opportunistic cleanup so idle keys do not accumulate forever.
            if len(self._events) > 10000:
                for stale_key in [k for k, v in self._events.items() if not v or v[-1] <= cutoff]:
                    self._events.pop(stale_key, None)
        return True, 0


chat_ip_limiter = SlidingWindowRateLimiter(CHAT_RATE_LIMIT_PER_MINUTE, RATE_LIMIT_WINDOW_SECONDS)
chat_global_limiter = SlidingWindowRateLimiter(CHAT_GLOBAL_RATE_LIMIT_PER_MINUTE, RATE_LIMIT_WINDOW_SECONDS)


def _client_ip(request: Request) -> str:
    """Best-effort end-user IP.

    Requests reach this service through the Next.js server on Vercel, so the socket
    peer is Vercel, not the user. The Next.js proxy forwards the user's IP in
    X-Client-IP; that header is only trusted because every non-health request has
    already presented the internal key.
    """
    forwarded = (request.headers.get(CLIENT_IP_HEADER) or "").strip()
    if forwarded:
        return forwarded.split(",")[0].strip()
    xff = (request.headers.get("x-forwarded-for") or "").strip()
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _enforce_chat_rate_limit(request: Request) -> None:
    ip = _client_ip(request)
    allowed, retry_after = chat_ip_limiter.check(ip)
    if not allowed:
        logger.warning("rate_limited scope=ip ip=%s retry_after=%s", ip, retry_after)
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please wait a moment and try again.",
            headers={"Retry-After": str(retry_after)},
        )
    allowed, retry_after = chat_global_limiter.check("global")
    if not allowed:
        logger.warning("rate_limited scope=global retry_after=%s", retry_after)
        raise HTTPException(
            status_code=429,
            detail=GENERIC_BUSY_ERROR,
            headers={"Retry-After": str(retry_after)},
        )


def _require_debug_enabled() -> None:
    if not ENABLE_DEBUG:
        # 404 rather than 403 so the endpoints are not discoverable in production.
        raise HTTPException(status_code=404, detail="Not found")


def _sanitize_history(history: Any) -> List[Dict[str, str]]:
    """Keep only well-formed {role, content} messages, bounded in count and size."""
    if not isinstance(history, list):
        return []
    cleaned: List[Dict[str, str]] = []
    for item in history:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "")).strip().lower()
        if role not in {"user", "assistant"}:
            continue
        content = str(item.get("content", "") or "").strip()
        if not content:
            continue
        cleaned.append({"role": role, "content": content[:MAX_HISTORY_MESSAGE_CHARS]})
    return cleaned[-MAX_HISTORY_MESSAGES:]


def _openai_error_to_http(error: Exception) -> HTTPException:
    """Map OpenAI SDK failures to generic client-safe HTTP errors. Details go to the log only."""
    if isinstance(error, RateLimitError):
        return HTTPException(status_code=503, detail=GENERIC_BUSY_ERROR, headers={"Retry-After": "10"})
    if isinstance(error, APITimeoutError):
        return HTTPException(status_code=504, detail=GENERIC_TIMEOUT_ERROR)
    if isinstance(error, APIConnectionError):
        return HTTPException(status_code=503, detail=GENERIC_BUSY_ERROR, headers={"Retry-After": "10"})
    if isinstance(error, APIStatusError) and error.status_code >= 500:
        return HTTPException(status_code=503, detail=GENERIC_BUSY_ERROR, headers={"Retry-After": "10"})
    return HTTPException(status_code=500, detail=GENERIC_SERVER_ERROR)


ARABIC_SAINTS_PDF_PATH = Path("data/pdfs/full saints arabic.pdf")
GENERATED_ARABIC_SAINTS_PATH = Path("data/saints_ar_generated.json")

NON_PERSON_ENTITY_TERMS = {
    "birth",
    "early life",
    "temple service",
    "betrothal to joseph",
    "annunciation",
    "life with christ",
    "assumption",
    "feast days",
    "feast day",
}

AMBIGUOUS_SAINT_FALLBACKS = {
    "john": [
        "St. John the Baptist",
        "St. John the Theologian",
        "St. John Chrysostom",
        "St. John of Damascus",
        "St. John Climacus",
    ],
    "thomas": [
        "St. Thomas the Apostle",
        "St. Thomas Aquinas",
    ],
    "mary": [
        "St. Mary Theotokos",
        "St. Mary Magdalene",
        "St. Mary of Egypt",
        "St. Mary the Armenian",
    ],
    "cyril": [
        "St. Cyril of Alexandria",
        "St. Cyril of Jerusalem",
        "St. Cyril IV",
        "St. Cyril VI",
    ],
}

SAINT_QUERY_PREFIX_PATTERN = r"^(?:(?:who is|tell me about|about)\s+)?(?:(?:st\.?|saint|pope|patriarch|abba|anba)\s+)*"

SAINT_ALIAS_RECORDS: List[Dict[str, Any]] = [
    {
        "canonical": "St. Mary",
        "english_aliases": [
            "Saint Mary",
            "St. Mary Theotokos",
            "St. Mary, the Virgin Theotokos",
            "St. Mary the Virgin",
            "Virgin Mary",
            "Holy Virgin Mary",
            "Theotokos",
            "Mother of God",
        ],
        "arabic_aliases": [
            "السيدة العذراء مريم",
            "العذراء مريم",
        ],
    },
    {
        "canonical": "St. Mark",
        "english_aliases": [
            "Saint Mark",
            "St. Mark the Evangelist",
            "Saint Mark the Evangelist",
            "Mark the Evangelist",
            "St. Mark the Apostle",
            "Saint Mark the Apostle",
        ],
        "arabic_aliases": [
            "مارمرقس",
            "القديس مارمرقس الرسول",
        ],
    },
    {
        "canonical": "St. Anthony the Great",
        "english_aliases": [
            "Saint Anthony the Great",
            "St. Anthony, Father of the Monks",
            "Saint Anthony, Father of the Monks",
            "St. Abba Anthony the Great",
            "St. Abba Anthony",
            "Abba Anthony",
            "Anthony the Great",
        ],
        "arabic_aliases": [
            "الأنبا أنطونيوس",
            "الأنبا أنطونيوس الكبير",
        ],
    },
    {
        "canonical": "St. Athanasius",
        "english_aliases": [
            "Saint Athanasius",
            "St. Athanasius the Apostolic",
            "Saint Athanasius the Apostolic",
            "St. Athanasius of Alexandria",
            "Athanasius the Apostolic",
        ],
        "arabic_aliases": [
            "أثناسيوس الرسولي",
            "البابا أثناسيوس",
        ],
    },
    {
        "canonical": "St. Cyril",
        "english_aliases": [
            "Saint Cyril",
            "St. Cyril of Alexandria",
            "Saint Cyril of Alexandria",
            "St. Cyril the Great",
            "Pope Cyril",
        ],
        "arabic_aliases": [
            "كيرلس",
            "البابا كيرلس",
        ],
    },
]

ARABIC_SAINT_INDEX_ALIASES: List[Dict[str, Any]] = ARABIC_SAINTS_INDEX

SAINT_ORDERING_TITLES = {
    "apostle",
    "disciple",
    "martyr",
    "bishop",
    "pope",
    "patriarch",
    "hermit",
    "virgin",
    "theologian",
}

SAINT_HEADING_EXCLUSIONS = {
    "encyclopedia",
    "history",
    "biographies",
    "volume",
    "preparatory",
    "index",
    "contents",
}


def _canonicalize_saint_text(value: str) -> str:
    return (
        (value or "")
        .strip()
        .replace("Kyrillos", "Cyril")
        .replace("kyrillos", "cyril")
        .replace("Cyrillus", "Cyril")
        .replace("cyrillus", "cyril")
    )


def _manual_saint_alias_values(record: Dict[str, Any]) -> List[str]:
    return [
        str(record.get("canonical", "")),
        *[str(value) for value in record.get("english_aliases", [])],
        *[str(value) for value in record.get("arabic_aliases", [])],
    ]


def _normalize_saint_match_key(value: str) -> str:
    text = _canonicalize_saint_text(value).lower()
    text = re.sub(r"\bmarys\b", "mary", text)
    text = re.sub(r"['`\u2019]", "", text)
    text = re.sub(r"[-_/]", " ", text)
    text = re.sub(r"[^\w\s]", " ", text)
    text = text.replace("\u2019", "").replace("'", "").replace("`", "")
    text = re.sub(r"\b(?:st|saint|saints|abba|anba)\b", " ", text)
    text = re.sub(r"\bthe\b", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _normalize_arabic_alias_key(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "")
    text = text.replace("ی", "ي").replace("ى", "ي")
    text = text.replace("ک", "ك")
    text = text.replace("ھ", "ه").replace("ة", "ه")
    text = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    text = re.sub(r"[\u064b-\u065f\u0670\u0640]", "", text)
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def _saint_match_keys(value: str) -> Set[str]:
    key = _normalize_saint_match_key(value)
    if not key:
        return set()

    keys = {key}
    words = key.split()
    if len(words) >= 2:
        if words[0] in SAINT_ORDERING_TITLES:
            keys.add(" ".join(words[1:] + [words[0]]))
        if words[-1] in SAINT_ORDERING_TITLES:
            keys.add(" ".join([words[-1]] + words[:-1]))
    return {item for item in keys if item}


def _saint_aliases_for_name(name: str) -> List[str]:
    aliases: List[str] = []
    seen = set()

    def add(value: str):
        normalized = re.sub(r"\s+", " ", (value or "").strip())
        if not normalized:
            return
        lowered = normalized.lower()
        if lowered in seen:
            return
        seen.add(lowered)
        aliases.append(normalized)

    add(name)
    name_key = _normalize_saint_match_key(name)
    for record in SAINT_ALIAS_RECORDS:
        english_keys = {
            _normalize_saint_match_key(str(record.get("canonical", ""))),
            *[
                _normalize_saint_match_key(str(value))
                for value in record.get("english_aliases", [])
            ],
        }
        if name_key and name_key in {key for key in english_keys if key}:
            for value in _manual_saint_alias_values(record):
                add(value)

    return aliases


def _matched_manual_arabic_alias(query: str) -> Dict[str, str] | None:
    query_key = _normalize_arabic_alias_key(query)
    if not query_key:
        return None

    best: Dict[str, str] | None = None
    best_length = 0
    for record in SAINT_ALIAS_RECORDS:
        for alias in record.get("arabic_aliases", []):
            alias_text = str(alias)
            alias_key = _normalize_arabic_alias_key(alias_text)
            if not alias_key:
                continue
            if query_key == alias_key or alias_key in query_key:
                if len(alias_key) > best_length:
                    best_length = len(alias_key)
                    best = {
                        "canonical": str(record.get("canonical", "")),
                        "alias": alias_text,
                    }
    return best


def _manual_saint_record_names(manual_canonical: str) -> List[str]:
    manual_key = _normalize_saint_match_key(manual_canonical)
    manual_record = next(
        (
            record
            for record in SAINT_ALIAS_RECORDS
            if _normalize_saint_match_key(str(record.get("canonical", ""))) == manual_key
        ),
        None,
    )
    if not manual_record:
        return []

    candidate_keys = {
        _normalize_saint_match_key(value)
        for value in _manual_saint_alias_values(manual_record)
    }
    candidate_keys = {key for key in candidate_keys if key}
    matches = []
    for record in _build_saint_record_index():
        record_keys = set()
        for alias in record.get("aliases", []):
            record_keys.update(_saint_match_keys(str(alias)))
        if candidate_keys.intersection(record_keys):
            matches.append(str(record.get("name", "")))
    return matches


def _resolve_manual_saint_alias(query: str) -> Dict[str, str] | None:
    matched = _matched_manual_arabic_alias(query)
    if not matched:
        return None

    record_names = _manual_saint_record_names(matched["canonical"])
    if not record_names:
        return None

    return {
        "alias": matched["alias"],
        "manual_canonical": matched["canonical"],
        "record_name": record_names[0],
    }


def _find_saint_record_matches(query: str, limit: int = 12) -> List[Dict[str, Any]]:
    saint_records = _build_saint_record_index()
    manual_match = _matched_manual_arabic_alias(query)
    if manual_match:
        manual_names = _manual_saint_record_names(manual_match["canonical"])
        if manual_names:
            manual_name_keys = {_normalize_saint_match_key(name) for name in manual_names}
            manual_records = [
                record
                for record in saint_records
                if _normalize_saint_match_key(str(record.get("name", ""))) in manual_name_keys
            ]
            if manual_records:
                return manual_records[:max(1, min(limit, 400))]

    query_keys = _saint_match_keys(query)
    if not query_keys:
        return []

    scored: List[Tuple[int, int, str, Dict[str, Any]]] = []
    for record in saint_records:
        name = str(record.get("name", ""))
        name_keys = set()
        for alias in record.get("aliases", []):
            name_keys.update(_saint_match_keys(alias))
        if not name_keys:
            continue

        score: int | None = None
        for query_key in query_keys:
            query_tokens = set(query_key.split())
            query_first = query_key.split()[0] if query_key else ""
            for name_key in name_keys:
                name_tokens = set(name_key.split())
                name_first = name_key.split()[0] if name_key else ""
                if query_key == name_key:
                    score = 0 if query_key in _saint_match_keys(name) else 1
                elif name_key.startswith(query_key):
                    score = 2 if score is None else min(score, 2)
                elif (
                    query_first
                    and query_first == name_first
                    and len(query_tokens) > 1
                    and query_first not in SAINT_ORDERING_TITLES
                ):
                    # "barbara martyr" vs indexed "barbara": the user's descriptor is not in the
                    # index name, but the core name is. Medium confidence.
                    score = 2 if score is None else min(score, 2)
                elif query_key in name_key:
                    score = 3 if score is None else min(score, 3)
                elif query_tokens and query_tokens.issubset(name_tokens):
                    score = 4 if score is None else min(score, 4)

        if score is not None:
            scored.append((score, len(name), name, record))

    scored.sort(key=lambda item: (item[0], item[1], item[2].lower()))
    if scored and scored[0][0] <= 1:
        core_name = _normalize_saint_match_key(_core_name_from_query(query))
        if core_name not in {"mary", "john", "cyril"}:
            scored = [item for item in scored if item[0] <= 1]
    elif scored and scored[0][0] <= 2:
        scored = [item for item in scored if item[0] <= 2]

    matches: List[Dict[str, Any]] = []
    seen = set()
    for score, _, _, record in scored:
        key = str(record.get("id", ""))
        if key in seen:
            continue
        seen.add(key)
        # Attach the match strength so callers can decide between "use it", "ask which one"
        # and "not confident, fall through to retrieval" (DECISIONS.md RET-001).
        matches.append({**record, "match_score": score})
        if len(matches) >= max(1, min(limit, 400)):
            break
    return matches


# Match-score bands for `_find_saint_record_matches` (lower is better):
#   0-1  strong: the query equals an indexed name or alias
#   2    medium: the indexed name starts with the query, or shares its core (first) name token
#   3-4  weak:   substring / token-subset only
SAINT_STRONG_MAX_SCORE = 1
SAINT_MEDIUM_SCORE = 2


def _split_saint_matches(records: List[Dict[str, Any]]) -> Tuple[List[str], List[str]]:
    strong = [str(r.get("name", "")) for r in records if int(r.get("match_score", 9)) <= SAINT_STRONG_MAX_SCORE]
    medium = [str(r.get("name", "")) for r in records if int(r.get("match_score", 9)) == SAINT_MEDIUM_SCORE]
    return strong, medium


def _find_saint_index_matches(query: str, limit: int = 12) -> List[str]:
    return [str(record.get("name", "")) for record in _find_saint_record_matches(query, limit=limit)]


def _log_saint_query(raw: str, normalized: str, matches: List[str]) -> None:
    trace = current_trace()
    if trace is not None:
        trace.set(
            saint_query=(raw or "")[:120],
            saint_query_normalized=(normalized or "")[:120],
            saint_match_count=len(matches),
            saint_matches=matches[:12],
        )
    else:
        logger.debug("saint_query raw=%r normalized=%r matches=%d", raw, normalized, len(matches))


def _saint_query_variants(saint_name: str) -> List[str]:
    canonical = _canonicalize_saint_text(saint_name).strip()
    variants: List[str] = []

    def add_variant(value: str):
        normalized = re.sub(r"\s+", " ", (value or "").strip())
        if not normalized:
            return
        if normalized.lower() in {item.lower() for item in variants}:
            return
        variants.append(normalized)

    base = re.sub(r"^(?:st\.?|saint)\s+", "", canonical, flags=re.IGNORECASE).strip()
    add_variant(canonical)
    add_variant(base)
    add_variant(f"St. {base}")

    if "cyril" in base.lower():
        kyrillos_base = re.sub(r"\bCyril\b", "Kyrillos", base, flags=re.IGNORECASE)
        add_variant(kyrillos_base)
        add_variant(f"Pope {kyrillos_base}")
        add_variant(f"St. {kyrillos_base}")
        add_variant(f"Pope {base}")

    if re.search(r"\b[IVX]+\b", base):
        add_variant(f"{base} Coptic Orthodox Pope")
        add_variant(f"{base} biography miracles sayings")

    lowered_base = base.lower()
    if "theotokos" in lowered_base:
        add_variant("St. Mary the Virgin")
        add_variant("Mary the Virgin")
        add_variant("Virgin Mary")
        add_variant("Holy Virgin Mary")

    if "thomas" in lowered_base and "apostle" in lowered_base:
        add_variant("Apostle Thomas")
        add_variant("Thomas the Disciple")
        add_variant("St. Thomas the Disciple")

    return variants


def _retrieve_documents(
    queries: List[str],
    top_k: int,
    entity: str | None = None,
    target_collection: Any | None = None,
    metadata_filter: Dict[str, Any] | None = None,
    per_query_min: int = 0,
    where_document: Dict[str, Any] | None = None,
):
    """Vector search for several queries, merged by best distance (RET-002).

    All queries go to Chroma in one call, so their embeddings are computed in a single
    OpenAI request (RET-007). `per_query_min` guarantees that each query's best few
    chunks survive the merge, so a sub-query about a narrower aspect of a broad request
    is not crowded out by the main query's neighbours.
    """
    global collection
    search_collection = target_collection or collection
    if search_collection is None:
        return [], [], []

    deduped_queries = []
    seen_queries = set()
    for query in queries:
        normalized = re.sub(r"\s+", " ", (query or "").strip())
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen_queries:
            continue
        seen_queries.add(key)
        deduped_queries.append(normalized)
    deduped_queries = deduped_queries[:8]
    if not deduped_queries:
        return [], [], []

    trace = current_trace()
    collection_label = None
    if trace is not None:
        try:
            collection_label = str(getattr(search_collection, "name", "") or "")
        except Exception:
            collection_label = None

    query_kwargs: Dict[str, Any] = {"query_texts": deduped_queries, "n_results": top_k}
    if metadata_filter:
        query_kwargs["where"] = metadata_filter
    if where_document:
        query_kwargs["where_document"] = where_document
    retrieved = search_collection.query(**query_kwargs)

    # Best (smallest) distance per unique chunk across all queries; the final list is
    # ordered by that distance, not by which query happened to run first (RET-002).
    best: Dict[tuple, Tuple[float, str, Dict[str, Any]]] = {}
    quota_keys: List[tuple] = []
    for index, query in enumerate(deduped_queries):
        docs = (retrieved.get("documents") or [])[index] if index < len(retrieved.get("documents") or []) else []
        metas = (retrieved.get("metadatas") or [])[index] if index < len(retrieved.get("metadatas") or []) else []
        ids = (retrieved.get("ids") or [])[index] if index < len(retrieved.get("ids") or []) else []
        distances = (retrieved.get("distances") or [])[index] if index < len(retrieved.get("distances") or []) else []

        if trace is not None:
            trace.add_retrieval(
                "vector",
                query,
                [{"id": chunk_id, "distance": dist} for chunk_id, dist in zip(ids, distances)],
                collection=collection_label,
                where=metadata_filter,
                n_results=top_k,
            )

        taken = 0
        for position, (doc, meta) in enumerate(zip(docs, metas)):
            if not doc or not meta:
                continue
            distance = float(distances[position]) if position < len(distances) and distances[position] is not None else float("inf")
            key = (
                meta.get("source_type", "pdf"),
                meta.get("pdf"),
                meta.get("page"),
                meta.get("url"),
                meta.get("chunk_index"),
                doc[:120],
            )
            current = best.get(key)
            if current is None or distance < current[0]:
                best[key] = (distance, doc, meta)
            if taken < per_query_min:
                if key not in quota_keys:
                    quota_keys.append(key)
                taken += 1

    chosen = list(quota_keys[:top_k])
    for key, _ in sorted(best.items(), key=lambda item: item[1][0]):
        if len(chosen) >= top_k:
            break
        if key not in chosen:
            chosen.append(key)
    ranked = sorted((best[key] for key in chosen), key=lambda item: item[0])
    docs = [doc for _, doc, _ in ranked]
    metas = [meta for _, _, meta in ranked]
    distances_out = [dist for dist, _, _ in ranked]
    return docs, metas, distances_out


def _normalize_chat_mode(value: str | None) -> str:
    mode = re.sub(r"\s+", " ", (value or "chat").strip().lower())
    return mode if mode in {"chat", "saints", "catechism"} else "chat"


def _contains_arabic(value: str) -> bool:
    return bool(re.search(r"[\u0600-\u06ff]", value or ""))


def _detect_language(selected_language: str | None, question: str) -> str:
    selected = (selected_language or "").strip().lower()
    if selected == "ar":
        return "ar"
    if selected == "en":
        return "en"
    if _contains_arabic(question):
        return "ar"
    return "en"


def _no_source_answer(language: str) -> str:
    """Reply when retrieval found nothing related (GEN-004): say so, and say what the sources are for."""
    if language == "ar":
        return (
            "لم أجد معلومات كافية عن هذا في المصادر العربية المتاحة. "
            "تغطي المصادر تعليم الكنيسة القبطية الأرثوذكسية (الإيمان والأسرار والصلاة والصوم والسنة الكنسية) "
            "وسير القديسين وآباء الكنيسة، فجرّب أن تسأل عن أحد هذه الموضوعات."
        )
    return (
        "I could not find anything about that in the loaded sources. They cover the teaching of the Coptic Orthodox "
        "Church (faith, the sacraments, prayer, fasting, the Church year) and the lives of the saints and Church Fathers, "
        "so try asking about one of those."
    )


ARABIC_LEXICAL_STOPWORDS = {
    "من",
    "ما",
    "ماذا",
    "هو",
    "هي",
    "هم",
    "عن",
    "في",
    "على",
    "الى",
    "إلى",
    "هذا",
    "هذه",
    "ذلك",
    "التي",
    "الذي",
    "الذين",
    "كيف",
    "هل",
    "معنى",
    "معني",
    "شرح",
    "القديس",
    "القديسه",
    "القديسة",
    "شهيد",
    "شهيده",
    "شهيدة",
    "الشهيد",
    "الشهيده",
    "الشهيدة",
    "الانبا",
    "البابا",
    "السيده",
    "السيدة",
    "مار",
    "الكنيسه",
    "الكنيسة",
    "القبطيه",
    "القبطية",
    "الارثوذكسيه",
    "الأرثوذكسية",
}


def _normalize_arabic_context_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "")
    text = text.replace("ی", "ي").replace("ک", "ك").replace("ھ", "ه")
    text = text.replace("\u0640", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _arabic_search_text(value: str) -> str:
    return _normalize_arabic_alias_key(_normalize_arabic_context_text(value))


def _strip_arabic_query_titles(value: str) -> str:
    removable = {
        *ARABIC_LEXICAL_STOPWORDS,
        "انبا",
        "الانبا",
        "قديس",
        "القديس",
        "قديسه",
        "قديسة",
        "القديسه",
        "القديسة",
        "بابا",
        "البابا",
        "سيده",
        "السيده",
        "السيدة",
        "مار",
    }
    cleaned_words: List[str] = []
    for word in _arabic_search_text(value).split():
        if not _contains_arabic(word):
            continue
        if word in removable:
            continue
        if word.startswith("مار") and len(word) > 3:
            word = word[3:]
        if word and word not in removable:
            cleaned_words.append(word)
    return " ".join(cleaned_words)


def _arabic_query_terms(question: str) -> List[str]:
    key = _arabic_search_text(question)
    terms: List[str] = []

    def add(value: str):
        normalized = " ".join(
            word for word in _arabic_search_text(value).split() if _contains_arabic(word)
        )
        if len(normalized) >= 3 and normalized not in ARABIC_LEXICAL_STOPWORDS and normalized not in terms:
            terms.append(normalized)

    for word in key.split():
        add(word)

    if "معمود" in key:
        for value in ["معموديه", "المعموديه", "المعمودية", "عماد", "الميرون", "ولاده جديده"]:
            add(value)
    if "ميرون" in key:
        for value in ["الميرون", "المسحه", "مسحه", "الروح القدس"]:
            add(value)
    if "رسول" in key or "الاباء" in key:
        for value in ["الاباء", "الرسل", "رسولي", "رسوليون", "رسوليين", "تلاميذ الرسل"]:
            add(value)
    if "ارثوذكس" in key and re.search(r"(اتحول|انضم|اصبح|ادخل|اكون)", key):
        for value in ["الموعوظ", "الموعوظين", "الايمان", "المعموديه", "الميرون", "الكنيسه"]:
            add(value)

    try:
        for saint_name in _find_arabic_saint_index_matches(question, limit=3):
            for word in _arabic_search_text(saint_name).split():
                add(word)
    except Exception:
        logger.warning("Arabic saint term expansion failed", exc_info=True)

    return terms


def _arabic_query_phrases(question: str) -> List[str]:
    phrases: List[str] = []

    def add(value: str):
        normalized = " ".join(
            word for word in _arabic_search_text(value).split() if _contains_arabic(word)
        )
        if len(normalized) >= 3 and normalized not in ARABIC_LEXICAL_STOPWORDS and normalized not in phrases:
            phrases.append(normalized)

    add(question)
    add(_strip_arabic_query_titles(question))
    try:
        for saint_name in _find_arabic_saint_index_matches(question, limit=4):
            add(saint_name)
    except Exception:
        logger.warning("Arabic saint phrase expansion failed", exc_info=True)

    return phrases


def _retrieve_arabic_lexical_documents(
    question: str,
    top_k: int,
    metadata_filter: Dict[str, Any] | None = None,
) -> Tuple[List[str], List[Dict[str, Any]]]:
    if arabic_collection is None:
        return [], []

    terms = _arabic_query_terms(question)
    phrases = _arabic_query_phrases(question)
    if not terms:
        return [], []

    scored: List[Tuple[int, int, str, Dict[str, Any]]] = []
    offset = 0
    page_size = 500

    while True:
        get_kwargs: Dict[str, Any] = {
            "include": ["documents", "metadatas"],
            "limit": page_size,
            "offset": offset,
        }
        if metadata_filter:
            get_kwargs["where"] = metadata_filter
        batch = arabic_collection.get(**get_kwargs)
        docs = batch.get("documents", []) or []
        metadatas = batch.get("metadatas", []) or []
        if not docs:
            break

        for doc, meta in zip(docs, metadatas):
            metadata = meta or {}
            searchable = _arabic_search_text(
                " ".join(
                    [
                        doc or "",
                        str(metadata.get("title", "") or ""),
                        str(metadata.get("pdf", "") or ""),
                    ]
                )
            )
            if not searchable:
                continue
            hits = sum(1 for term in terms if term in searchable)
            phrase_hits = sum(1 for phrase in phrases if phrase in searchable)
            if hits <= 0 and phrase_hits <= 0:
                continue
            score = hits * 10 + phrase_hits * 120
            if len(terms) >= 2 and all(term in searchable for term in terms[:2]):
                score += 25
            if " ".join(terms[:2]) and " ".join(terms[:2]) in searchable:
                score += 40
            scored.append((score, int(metadata.get("page") or 0), doc or "", metadata))

        if len(docs) < page_size:
            break
        offset += len(docs)

    scored.sort(key=lambda item: (-item[0], item[1]))
    docs: List[str] = []
    metas: List[Dict[str, Any]] = []
    hit_scores: List[int] = []
    seen: Set[Tuple[Any, ...]] = set()
    for score, _, doc, meta in scored:
        key = (
            meta.get("title"),
            meta.get("pdf"),
            meta.get("page"),
            meta.get("chunk_index"),
            doc[:80],
        )
        if key in seen:
            continue
        seen.add(key)
        docs.append(doc)
        metas.append(meta)
        hit_scores.append(score)
        if len(docs) >= max(1, min(top_k, 16)):
            break

    trace = current_trace()
    if trace is not None:
        trace.add_retrieval(
            "lexical",
            question,
            [{"id": chunk_id_from_metadata(meta), "score": score} for meta, score in zip(metas, hit_scores)],
            collection=ARABIC_COLLECTION_NAME,
            where=metadata_filter,
            terms=terms[:12],
            phrase_count=len(phrases),
            candidates_scored=len(scored),
        )
    return docs, metas


def _merge_document_batches(
    primary_docs: List[str],
    primary_metas: List[Dict[str, Any]],
    secondary_docs: List[str],
    secondary_metas: List[Dict[str, Any]],
    top_k: int,
) -> Tuple[List[str], List[Dict[str, Any]]]:
    merged_docs: List[str] = []
    merged_metas: List[Dict[str, Any]] = []
    seen: Set[Tuple[Any, ...]] = set()

    for doc, meta in [*zip(primary_docs, primary_metas), *zip(secondary_docs, secondary_metas)]:
        metadata = meta or {}
        key = (
            metadata.get("source_type"),
            metadata.get("title"),
            metadata.get("pdf"),
            metadata.get("page"),
            metadata.get("chunk_index"),
            (doc or "")[:100],
        )
        if key in seen:
            continue
        seen.add(key)
        merged_docs.append(doc or "")
        merged_metas.append(metadata)
        if len(merged_docs) >= top_k:
            break

    return merged_docs, merged_metas


def _is_broad_list_question(question: str) -> bool:
    q = question.lower()
    if not re.search(r"\b(?:list|show|name|what are|which are|give me)\b", q):
        return False
    return bool(
        re.search(
            r"\b(?:monasteries|monastery|churches|church|places|saints|fathers|disciples|items)\b",
            q,
        )
    )


def _is_definition_question(question: str) -> bool:
    return bool(re.match(r"^\s*(?:who|what)\s+(?:is|are|were|was)\b", question, flags=re.IGNORECASE))


def _build_retrieval_queries(question: str, entity: str | None = None) -> List[str]:
    queries = [question]
    q_lower = question.lower()

    if "apostolic father" in q_lower or "apostolic fathers" in q_lower:
        queries.extend(
            [
                "apostolic fathers",
                "early Christian writers connected to the apostles",
                "Ignatius Polycarp Clement Barnabas Hermas",
                "early church fathers",
                "disciples of the apostles",
                "disciples of the apostles early church fathers",
                "first generations after the apostles",
            ]
        )

    if "upper egypt" in q_lower and re.search(r"\bmonaster", q_lower):
        queries.extend(
            [
                "Upper Egypt monasteries",
                "monasteries in Upper Egypt",
                "Egyptian monasteries Upper Egypt",
                "monastery in Upper Egypt",
            ]
        )

    if entity:
        if re.search(r"\bchurch\b", q_lower):
            queries.extend(
                [
                    f"{entity} church",
                    f"church named after {entity}",
                    f"{entity} monastery",
                    entity,
                ]
            )
        queries.extend(
            f"{variant} Orthodox saint biography life feast teachings martyr monk bishop"
            for variant in _saint_query_variants(entity)
        )
        queries.extend(_saint_query_variants(entity))

    return queries


def _prepend_saint_record_context(
    docs: List[str],
    metas: List[Dict[str, Any]],
    entity: str | None,
) -> Tuple[List[str], List[Dict[str, Any]]]:
    if not entity:
        return docs, metas

    record = _find_saint_record_by_name(entity)
    body = str((record or {}).get("body", "") or "").strip()
    metadata = (record or {}).get("metadata") or {}
    if not body or not metadata:
        return docs, metas

    source_key = _source_key(_source_from_metadata(metadata))
    merged_docs = [body]
    merged_metas = [metadata]

    for doc, meta in zip(docs, metas):
        if _source_key(_source_from_metadata(meta or {})) == source_key and (doc or "").strip() == body:
            continue
        merged_docs.append(doc)
        merged_metas.append(meta)

    return merged_docs, merged_metas


def _saint_list_entries(name_filter: Dict[str, str]) -> Tuple[List[Dict[str, Any]], int]:
    """Saint-index records selected by name (RET-007): ({name, heading, body, metadata}, total matches).

    `starts_with` compares the start of the name without "St."; `contains` matches whole words.
    The index is built from ALL-CAPS headings (RET-001), so joint entries such as
    "GERVASE AND PROTASE" can be missing; callers must say the list may be incomplete.
    """
    starts = _normalize_saint_match_key(name_filter.get("starts_with", ""))
    contains = _normalize_saint_match_key(name_filter.get("contains", ""))
    if not starts and not contains:
        return [], 0
    matched = []
    for record in _build_saint_record_index():
        key = _normalize_saint_match_key(str(record.get("name", "")))
        if starts and not key.startswith(starts):
            continue
        if contains and not re.search(rf"\b{re.escape(contains)}\b", key):
            continue
        matched.append(record)
    return matched[:SAINT_LIST_MAX_ENTRIES], len(matched)


def _saint_list_context(records: List[Dict[str, Any]]) -> Tuple[List[str], List[Dict[str, Any]]]:
    """One passage per entry: the book's heading and the opening of the entry, with its page."""
    docs, metas = [], []
    for record in records:
        body = str(record.get("body", "") or "")
        excerpt = body[:SAINT_LIST_EXCERPT_CHARS].rsplit(" ", 1)[0] + (" …" if len(body) > SAINT_LIST_EXCERPT_CHARS else "")
        docs.append(f"{record.get('name')} (entry heading: {record.get('raw_heading') or record.get('name')})\n{excerpt}")
        metas.append(record.get("metadata") or {})
    return docs, metas


def _saint_list_note(name_filter: Dict[str, str], shown: int, total: int) -> str:
    if "starts_with" in name_filter:
        criterion = f"names starting with “{name_filter['starts_with']}”"
    else:
        criterion = f"names containing “{name_filter['contains']}”"
    note = (
        f"The passages below are the Encyclopedia entries whose headings an automatic index matched for {criterion}: "
        f"{shown} shown"
    )
    note += f" of {total} matched." if total > shown else "."
    note += (
        " The index cannot read every heading (for example some joint entries), so tell the reader the list may be "
        "incomplete. Describe each saint only from its passage, in one short sentence."
    )
    return note


def _collection_count_safe(target_collection: Any | None) -> int:
    if target_collection is None:
        return 0
    try:
        return int(target_collection.count())
    except Exception:
        return 0


def _arabic_metadata_filter_for_mode(mode: str) -> Dict[str, Any] | None:
    if mode == "catechism":
        return {"title": "full arabic catechism"}
    if mode == "saints":
        return {"title": "full saints arabic"}
    return None


ARABIC_REFUSAL_MARKERS = (
    "لم أجد معلومات كافية",
    "لم اجد معلومات كافية",
)


# "The sources do not mention X" opens a decline; "the sources do not give a full comparison"
# inside or at the start of an answer does not (it is a partial answer).
REFUSAL_OPENINGS = (
    "i could not find",
    "i couldn't find",
    "the sources do not mention",
    "the passages do not mention",
    "the loaded sources do not mention",
    "the provided passages do not mention",
)
PARTIAL_MARKERS = (
    "do not cover",
    "does not cover",
    "don't cover",
    "do not describe",
    "do not say",
    "does not say",
    "do not contain",
    "do not give a full",
    "may be incomplete",
    "may not be complete",
    "may not be exhaustive",
    "not exhaustive",
    "the sources mention",
)


def _response_grounding_status(answer: str, docs: List[str]) -> str:
    """no-source | partial | full.

    Prompt v3 (GEN-004) opens a decline with a fixed phrase, and states gaps inside an otherwise
    useful answer with other wording, so only the *opening* decides a refusal. Before v3, any
    "does not say" anywhere turned a partial answer into a logged refusal.
    """
    if not docs:
        return "no-source"
    text = (answer or "").strip()
    lowered = text.lower()
    if lowered.startswith(REFUSAL_OPENINGS) or any(text.startswith(marker) for marker in ARABIC_REFUSAL_MARKERS):
        return "no-source"
    if any(marker in lowered for marker in PARTIAL_MARKERS) or "غير كاملة" in text or "لا تغطي" in text:
        return "partial"
    return "full"


def _compared_tradition_terms(question: str, analysis: TaskAnalysis) -> List[str]:
    """Names of other traditions a comparison request is about, as they appear in the books."""
    text = f"{question} {analysis.retrieval_query}"
    if analysis.output_format != "comparison" and not COMPARISON_CUE.search(text):
        return []
    terms: List[str] = []
    for pattern, substrings in TRADITION_TERMS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            terms.extend(term for term in substrings if term not in terms)
    return terms[:3]


def _answer_max_tokens(analysis: TaskAnalysis, broad: bool) -> int:
    if broad or analysis.output_format in {"table", "list", "comparison", "study_guide"}:
        return max(ANSWER_MAX_TOKENS, ANSWER_MAX_TOKENS_TASK)
    return ANSWER_MAX_TOKENS


def _format_note(analysis: TaskAnalysis, language: str) -> str | None:
    """Tell the model which presentation the analysis detected (GEN-004)."""
    if analysis.output_format in {"prose", "other"}:
        return None
    label = analysis.output_format.replace("_", " ")
    if language == "ar":
        return f"الشكل المطلوب: {label}"
    return f"Requested format: {label}."


def _has_viable_saint_learn_more(answer: str, docs: List[str], metas: List[Dict[str, Any]], mode: str) -> bool:
    if mode != "saints":
        return False
    if not answer.strip() or not docs or not metas:
        return False
    if _response_grounding_status(answer, docs) == "no-source":
        return False

    answer_words = len(re.findall(r"\w+", answer))
    context_words = sum(len(re.findall(r"\w+", doc or "")) for doc in docs)
    source_keys = {_source_key(_source_from_metadata(meta or {})) for meta in metas}

    return (
        len(docs) >= 2
        or len(source_keys) >= 2
        or (context_words >= 180 and context_words >= max(120, answer_words + 60))
    )


def _build_catechism_followups(question: str, answer: str, language: str = "en") -> List[str]:
    if language == "ar":
        text = f"{question} {answer}"
        if "معمود" in text or "ميرون" in text:
            return [
                "هل تريد شرحًا عن المعمودية والميرون؟",
                "هل تريد أن تعرف كيف يستعد الموعوظ للمعمودية؟",
            ]
        if re.search(r"(أتحول|اتحول|التحول|أصبح|اصبح|أنضم|انضم|موعوظ)", text):
            return [
                "هل تريد أن تعرف أكثر عن فترة الموعوظين؟",
                "هل تريد شرحًا عن المعمودية والميرون؟",
            ]
        if "صوم" in text:
            return [
                "هل تريد أن تعرف كيف يرتبط الصوم بالصلاة؟",
                "هل تريد أن تسأل عن التوبة أثناء الصوم؟",
            ]
        if "صلاة" in text:
            return [
                "هل تريد أن تسأل عن الصلاة اليومية؟",
                "هل تريد أن تعرف كيف ترتبط الصلاة بالتوبة؟",
            ]
        return [
            "هل تريد أن تعرف كيف يُمارَس هذا في حياة الكنيسة؟",
            "هل تريد شرحًا أبسط للمصطلحات في هذه الإجابة؟",
        ]

    q = question.lower()
    text = f"{q} {answer.lower()}"
    followups: List[str]

    if re.search(r"\bconvert|conversion|become orthodox|join\b", text):
        followups = [
            "Would you like to know what a catechumen is?",
            "Would you like to know what baptism and chrismation mean?",
            "Would you like help with how to start attending an Orthodox church?",
        ]
    elif re.search(r"\bbaptism|chrismation\b", text):
        followups = [
            "Would you like to know why baptism is part of entering the Church?",
            "Would you like to know what chrismation means?",
            "Would you like to ask how a catechumen prepares for baptism?",
        ]
    elif re.search(r"\bfast|fasting\b", text):
        followups = [
            "Would you like to know how fasting is joined to prayer?",
            "Would you like to ask about repentance during fasting?",
            "Would you like to know why the Church has fasting seasons?",
        ]
    elif re.search(r"\bprayer|pray\b", text):
        followups = [
            "Would you like to ask about daily prayer?",
            "Would you like to know how prayer connects with repentance?",
            "Would you like to ask about praying with the Church?",
        ]
    else:
        followups = [
            "Would you like to ask how this is practiced in Church life?",
            "Would you like to know which catechism topic this connects to?",
            "Would you like to ask what terms in this answer mean?",
        ]

    return followups[:2]


def _catechism_followup_options(answer: str, question: str, language: str = "en") -> List[str]:
    followups = _build_catechism_followups(question, answer, language=language)
    return followups[:2]


class ChatRequest(BaseModel):
    question: str
    history: list = []
    top_k: int = 8
    mode: str | None = None
    language: str | None = None
    # When true, the response carries a `debug` object with retrieval ids/distances
    # (used by eval/run_eval.py). Only reachable by callers holding the internal key.
    debug: bool = False


class Source(BaseModel):
    source_type: str = "pdf"
    pdf: str | None = None
    page: int | None = None
    url: str | None = None
    title: str | None = None
    # Citation number used in the answer text ([n]) and a human-readable label.
    n: int | None = None
    label: str | None = None


class ChatResponse(BaseModel):
    answer: str
    sources: List[Source]
    entities: List[str] = []
    options: List[str] = []
    can_learn_more: bool = False
    debug: Dict[str, Any] | None = None


class SaintSuggestionResponse(BaseModel):
    suggestions: List[str]


class SaintsListResponse(BaseModel):
    saints: List[str]
    total: int = 0
    offset: int = 0
    limit: int = 0


def _split_env_list(value: str) -> List[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def _allowed_origins() -> List[str]:
    configured = _split_env_list(os.getenv("ALLOWED_ORIGINS", ""))
    if configured:
        return configured
    return [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]


def _allow_origin_regex() -> str | None:
    value = os.getenv("CORS_ALLOW_ORIGIN_REGEX", "").strip()
    return value or None


def _normalize_entity_label(value: str) -> str:
    cleaned = (value or "").strip()
    cleaned = re.sub(r"^\d+[\.)]\s*", "", cleaned)
    cleaned = cleaned.replace("**", "").strip()
    return cleaned


def _source_from_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    source_type = str((metadata or {}).get("source_type", "pdf"))
    if source_type == "website":
        return {
            "source_type": "website",
            "url": str((metadata or {}).get("url", "")).strip() or None,
            "title": str((metadata or {}).get("title", "")).strip() or None,
        }

    pdf_name = str((metadata or {}).get("pdf", "unknown.pdf"))
    page_num = int((metadata or {}).get("page", 0) or 0)
    return {
        "source_type": "pdf",
        "pdf": pdf_name,
        "page": page_num,
    }


def _source_key(source: Dict[str, Any]) -> tuple[Any, ...]:
    if source.get("source_type") == "website":
        return ("website", source.get("url"), source.get("title"))
    return ("pdf", source.get("pdf"), source.get("page"))


def _source_context_label(metadata: Dict[str, Any]) -> str:
    source_type = str((metadata or {}).get("source_type", "pdf"))
    if source_type == "website":
        title = str((metadata or {}).get("title", "")).strip()
        url = str((metadata or {}).get("url", "")).strip()
        if title and url:
            return f"{title} ({url})"
        return title or url or "website source"

    pdf_name = str((metadata or {}).get("pdf", "unknown.pdf"))
    page_num = (metadata or {}).get("page", 0)
    return f"{pdf_name} p.{page_num}"


def _friendly_source_label(metadata: Dict[str, Any]) -> str:
    """Citation label shown to the model and returned to the client, e.g.
    'Catechism of the Coptic Orthodox Church, Volume 2, p. 31'."""
    source_type = str((metadata or {}).get("source_type", "pdf"))
    if source_type == "website":
        return _source_context_label(metadata)
    pdf_name = str((metadata or {}).get("pdf", "unknown.pdf"))
    page_num = (metadata or {}).get("page", 0)
    title = SOURCE_TITLES.get(pdf_name, pdf_name)
    return f"{title}, p. {page_num}"


def _build_numbered_context(
    docs: List[str],
    metas: List[Dict[str, Any]],
    normalize=None,
) -> Tuple[str, List[Dict[str, Any]]]:
    """Format the retrieved chunks as numbered passages the model can cite as [n].

    Returns the context text and the per-passage source dicts (with `n` and `label`).
    """
    blocks: List[str] = []
    numbered: List[Dict[str, Any]] = []
    passages: List[Dict[str, Any]] = []
    for index, (doc, meta) in enumerate(zip(docs, metas), start=1):
        text = (normalize(doc) if normalize else (doc or "")).strip()
        label = _friendly_source_label(meta or {})
        blocks.append(f"[{index}] {label}\n{text}")
        numbered.append({**_source_from_metadata(meta or {}), "n": index, "label": label})
        passages.append({"n": index, "id": chunk_id_from_metadata(meta or {}), "label": label, "text": text})
    trace = current_trace()
    if trace is not None:
        # Kept out of the log line (LOG-002); surfaced only to authenticated debug callers so
        # the eval harness can check each claim against the passage it cites (EVAL-011).
        trace.debug_passages = passages
    return "\n\n".join(blocks), numbered


def _parse_citations(answer: str) -> List[int]:
    """Ordered, de-duplicated passage numbers cited as [n], [n, m] or [n][m]."""
    seen: List[int] = []
    for group in CITATION_RE.findall(answer or ""):
        for token in re.split(r"[,;]", group):
            token = token.strip()
            if token.isdigit():
                number = int(token)
                if number not in seen:
                    seen.append(number)
    return seen


def _cited_sources(answer: str, numbered: List[Dict[str, Any]], fallback_limit: int = 6) -> Tuple[List[Dict[str, Any]], int]:
    """Sources the answer actually cited, in first-citation order, one per page/url.

    If the model cited nothing (or cited only numbers that do not exist) fall back to
    the first `fallback_limit` distinct retrieved sources so the UI still shows where
    the context came from. Returns (sources, cited_count).
    """
    by_number = {source["n"]: source for source in numbered}
    chosen: List[Dict[str, Any]] = []
    seen_keys: Set[Tuple[Any, ...]] = set()
    for number in _parse_citations(answer):
        source = by_number.get(number)
        if not source:
            continue
        key = _source_key(source)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        chosen.append(source)
    cited_count = len(chosen)
    if not chosen and fallback_limit > 0:
        for source in numbered:
            key = _source_key(source)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            chosen.append(source)
            if len(chosen) >= fallback_limit:
                break
    return chosen, cited_count


def _analyze_request(question: str, history: List[Dict[str, str]]) -> TaskAnalysis:
    """Standalone retrieval query + requested format for this turn (RET-006), logged in the trace."""
    trace = current_trace()
    if not TASK_ANALYSIS_ENABLED or re.match(r"^\s*search\s+saints?\s*:", question, flags=re.IGNORECASE):
        analysis = TaskAnalysis(retrieval_query=question, error="skipped")
    else:
        analysis = analyze_request(
            oai_client, question, history, model=TASK_ANALYSIS_MODEL, timeout_seconds=TASK_ANALYSIS_TIMEOUT_SECONDS
        )
        if analysis.error:
            logger.warning("task analysis failed, using the raw question: %s", analysis.error)
    if trace is not None:
        trace.set(task_analysis=analysis.log_dict(), analysis_tokens=analysis.prompt_tokens and (analysis.prompt_tokens + (analysis.completion_tokens or 0)))
    return analysis


def _decline_or_cited_sources(
    answer: str, numbered: List[Dict[str, Any]], refused: bool
) -> Tuple[List[Dict[str, Any]], int]:
    """A decline shows only the passages it cites for nearby material (GEN-004), never a fallback list."""
    if not refused:
        return _cited_sources(answer, numbered)
    if not _parse_citations(answer):
        return [], 0
    return _cited_sources(answer, numbered, fallback_limit=0)


def _build_chat_messages(
    system_prompt: str,
    history: List[Dict[str, str]],
    question: str,
    context: str,
    language: str,
    note: str | None = None,
) -> List[Dict[str, str]]:
    """System prompt, then the last few real turns, then the question with its numbered passages.

    `note` is a short pipeline remark placed before the passages (e.g. how a saint list was built)."""
    messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
    for turn in history[-HISTORY_TURNS_FOR_MODEL:]:
        messages.append({"role": turn["role"], "content": turn["content"]})
    if language == "ar":
        user_content = f"المقاطع المصدرية\n\n{context}\n\nالسؤال\n{question}"
    else:
        user_content = f"SOURCE PASSAGES\n\n{context}\n\nQUESTION\n{question}"
    if note:
        user_content = f"NOTE\n{note}\n\n{user_content}"
    messages.append({"role": "user", "content": user_content})
    return messages


def _extract_entity_candidate(list_item: str) -> str:
    item = _normalize_entity_label(list_item)
    if not item:
        return ""

    # Prefer the explicit bold label from model output, e.g. "**St. Mary of Egypt** - ..."
    bold_match = re.search(r"\*\*([^*]+)\*\*", list_item)
    if bold_match:
        item = _normalize_entity_label(bold_match.group(1))
    else:
        item = re.split(r"\s[-:\u2014]\s", item, maxsplit=1)[0].strip()
        item = re.sub(r"\s*\(.*?\)\s*$", "", item).strip()

    return item


def _looks_like_person_entity(value: str) -> bool:
    candidate = _normalize_entity_label(value)
    if not candidate:
        return False

    lower = candidate.lower()
    if lower in NON_PERSON_ENTITY_TERMS:
        return False

    saint_markers = ("st.", "saint", "theotokos", "virgin mary")
    if any(marker in lower for marker in saint_markers):
        return True

    # Keep proper-name labels (2+ capitalized words), drop topical single-word terms.
    words = [w for w in re.split(r"\s+", candidate) if w]
    if len(words) < 2:
        return False

    capitalized_count = sum(1 for w in words if w[:1].isupper())
    return capitalized_count >= 2


def _extract_saint_mentions(text: str) -> List[str]:
    if not text:
        return []

    patterns = [
        r"\bSt\.?\s+[A-Z][A-Za-z'\-]+(?:\s+(?:of|the|[A-Z][A-Za-z'\-]+)){0,5}",
        r"\bSaint\s+[A-Z][A-Za-z'\-]+(?:\s+(?:of|the|[A-Z][A-Za-z'\-]+)){0,5}",
    ]
    results = []
    for pattern in patterns:
        results.extend(re.findall(pattern, text))

    return [item.strip() for item in results if item.strip()]


def _extract_core_name_mentions(text: str, core_word: str) -> List[str]:
    if not text or not core_word:
        return []

    cleaned_text = re.sub(r"\s+", " ", text)
    pattern = re.compile(
        rf"\b{re.escape(core_word)}(?:\s+(?:the|of|[A-Z][A-Za-z'\-]+)){{0,4}}",
        flags=re.IGNORECASE,
    )
    results = []
    for match in pattern.finditer(cleaned_text):
        value = re.sub(r"[^\w\s\.'\-]", "", match.group(0)).strip()
        if value:
            results.append(value)
    return results


def _normalize_suggestion_name(value: str) -> str:
    name = re.sub(r"\s+", " ", (value or "").strip())
    name = re.sub(r"^(?:st\.?|saint)\s+", "", name, flags=re.IGNORECASE)
    if not name:
        return ""

    words = [w for w in name.split() if w]
    if len(words) < 2:
        return ""

    bad_tokens = {"was", "is", "and", "or", "in", "on", "to", "for", "with", "from"}
    if any(token.lower() in bad_tokens for token in words):
        return ""

    allowed_lower = {"the", "of"}
    roman_numerals = {"i", "ii", "iii", "iv", "v", "vi"}
    for token in words:
        lower = token.lower()
        if lower in allowed_lower or lower in roman_numerals:
            continue
        if len(token) <= 2:
            return ""
        if not token[0].isupper():
            return ""

    return f"St. {name}"


def _is_plausible_saint_index_name(value: str) -> bool:
    normalized = _normalize_suggestion_name(value)
    if not normalized:
        return False
    replacement = MANUAL_SAINT_NAME_REPLACEMENTS.get(normalized)
    if replacement == "":
        return False
    normalized = replacement or normalized
    if normalized in MANUAL_SAINT_NAME_EXCLUSIONS:
        return False

    stripped = normalized.removeprefix("St. ").strip()
    lower = stripped.lower()
    if "'" in lower:
        return False

    banned_terms = {
        "church",
        "cathedral",
        "convent",
        "monastery",
        "gospel",
        "school",
        "study",
        "group",
        "institute",
        "research",
        "theological",
        "book",
        "books",
        "volume",
        "testimony",
        "attacked",
        "gets",
        "apos",
        "alexa",
        "conference",
        "tractate",
        "letter",
        "testament",
        "part",
        "square",
        "seat",
        "see",
        "support",
        "help",
        "reconciliation",
        "testified",
        "wrote",
        "debates",
        "violent",
        "seeks",
        "seeks his",
        "old",
        "december",
        "coptic",
        "orthodox",
        "prophesied",
        "prophesized",
        "prophecies",
        "prophecy",
        "who",
        "whose",
    }
    tokens = re.split(r"\s+", lower)
    if any(token in banned_terms for token in tokens):
        return False
    if any(token.endswith("-") for token in tokens):
        return False
    if lower.endswith(" the") or lower.endswith(" of"):
        return False

    allowed_lower = {"of", "the"}
    roman_numerals = {"i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x"}
    for token in stripped.split():
        token_clean = token.strip(".,;:()[]")
        lower_token = token_clean.lower()
        if lower_token in allowed_lower or lower_token in roman_numerals:
            continue
        if len(token_clean) < 3:
            return False
    return True


def _core_name_from_query(query: str) -> str:
    name = re.sub(SAINT_QUERY_PREFIX_PATTERN, "", _canonicalize_saint_text(query), flags=re.IGNORECASE)
    parts = [p for p in re.split(r"\s+", name) if p]
    return parts[0].lower() if parts else ""


def _normalize_saint_search_query(query: str) -> str:
    stripped = re.sub(
        SAINT_QUERY_PREFIX_PATTERN,
        "",
        _canonicalize_saint_text(query),
        flags=re.IGNORECASE,
    )
    return _normalize_saint_match_key(stripped)


def _filter_sourced_saint_options(options: List[str]) -> List[str]:
    saint_index = _build_saint_name_index()
    sourced_keys = {name.lower() for name in saint_index}
    return [name for name in options if name.lower() in sourced_keys]


def _find_saint_suggestions(query: str, limit: int = 12) -> List[str]:
    query = _canonicalize_saint_text(query)
    return _find_saint_index_matches(query, limit=max(1, min(limit, 12)))


def _extract_ambiguous_saint_query(question: str) -> str:
    q = (question or "").strip().rstrip("?")
    if not q:
        return ""

    patterns = [
        r"^(?:who is|tell me about|about)\s+(st\.?\s+.+)$",
        r"^(?:who is|tell me about|about)\s+(saint\s+.+)$",
        r"^(?:who is|tell me about|about)\s+(pope\s+.+)$",
        r"^(?:who is|tell me about|about)\s+(patriarch\s+.+)$",
        r"^(st\.?\s+.+)$",
        r"^(saint\s+.+)$",
        r"^(pope\s+.+)$",
        r"^(patriarch\s+.+)$",
    ]
    for pattern in patterns:
        match = re.match(pattern, q, flags=re.IGNORECASE)
        if not match:
            continue
        candidate = re.sub(r"\s+", " ", match.group(1)).strip()
        name_only = re.sub(r"^(?:st\.?|saint|pope|patriarch|abba|anba)\s+", "", candidate, flags=re.IGNORECASE).strip()
        # Only a bare single name is treated as possibly ambiguous (e.g. "St. John", "St. Mary").
        # "St. Mary Magdalene" or "St. John Chrysostom" are specific and go straight to retrieval.
        if len(name_only.split()) == 1:
            return candidate
    return ""


SAINT_CANDIDATE_CLAUSE_SPLIT = re.compile(
    r",|;|\?|\s+-\s+|\s+(?:and|who|what|how|when|where|why|which|whose|that)\s+",
    flags=re.IGNORECASE,
)


def _trim_saint_candidate(candidate: str) -> str:
    """Cut a captured name at the first clause boundary.

    "St. Demiana and how was she martyred" -> "St. Demiana"; "St. Abanoub, and how old ..." -> "St. Abanoub".
    """
    head = SAINT_CANDIDATE_CLAUSE_SPLIT.split(candidate, maxsplit=1)[0]
    return re.sub(r"\s+", " ", head).strip(" .")


app = FastAPI(title="Orthodox PDF Chat API")


@app.middleware("http")
async def require_internal_key(request: Request, call_next):
    """Reject every request that does not carry the shared internal key.

    Only /health (platform health checks) and CORS preflights are exempt. If the key
    is not configured at all we fail closed: a misconfigured deployment should be
    visibly broken rather than silently open to the internet.
    """
    if request.method == "OPTIONS" or request.url.path in AUTH_EXEMPT_PATHS:
        return await call_next(request)

    if not INTERNAL_API_KEY:
        logger.error("INTERNAL_API_KEY is not set; refusing request to %s", request.url.path)
        return JSONResponse(status_code=503, content={"detail": "Server is not configured."})

    presented = (request.headers.get(INTERNAL_KEY_HEADER) or "").strip()
    if not presented or not hmac.compare_digest(presented, INTERNAL_API_KEY):
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_origin_regex=_allow_origin_regex(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

chroma_client = None
collection = None
arabic_collection = None
oai_client = None
saint_name_index: List[str] = []
saint_record_index: List[Dict[str, Any]] = []
arabic_saint_name_index: List[str] = []
generated_arabic_saint_records: List[Dict[str, Any]] | None = None
generated_arabic_saint_stats: Dict[str, Any] | None = None


def _collect_collection_debug_info(target_collection: Any, collection_name: str) -> Dict[str, Any]:
    info: Dict[str, Any] = {
        "collection_name": collection_name,
        "collection_ready": target_collection is not None,
        "document_count": 0,
        "source_type_counts": {},
        "pdf_counts": {},
        "sample_items": [],
    }

    if target_collection is None:
        return info

    try:
        info["document_count"] = int(target_collection.count())
    except Exception as exc:
        info["count_error"] = str(exc)
        return info

    if info["document_count"] <= 0:
        return info

    try:
        source_type_counts: Dict[str, int] = {}
        pdf_counts: Dict[str, int] = {}
        offset = 0
        page_size = 500

        while True:
            metadata_batch = target_collection.get(include=["metadatas"], limit=page_size, offset=offset)
            metadatas = metadata_batch.get("metadatas", []) or []
            if not metadatas:
                break

            for metadata in metadatas:
                metadata = metadata or {}
                source_type = str(metadata.get("source_type", "pdf") or "pdf")
                source_type_counts[source_type] = source_type_counts.get(source_type, 0) + 1

                pdf_name = str(metadata.get("pdf", "") or "")
                if pdf_name:
                    pdf_counts[pdf_name] = pdf_counts.get(pdf_name, 0) + 1

            if len(metadatas) < page_size:
                break
            offset += len(metadatas)

        info["source_type_counts"] = dict(sorted(source_type_counts.items()))
        info["pdf_counts"] = dict(sorted(pdf_counts.items()))
    except Exception as exc:
        info["metadata_count_error"] = str(exc)

    try:
        batch = target_collection.get(include=["documents", "metadatas"], limit=3, offset=0)
        docs = batch.get("documents", []) or []
        metas = batch.get("metadatas", []) or []
        sample_items = []
        for doc, metadata in zip(docs[:3], metas[:3]):
            sample_items.append(
                {
                    "metadata": metadata or {},
                    "document_preview": re.sub(r"\s+", " ", (doc or "")[:240]).strip(),
                }
            )
        info["sample_items"] = sample_items
    except Exception as exc:
        info["sample_error"] = str(exc)

    return info


def _arabic_source_files_found() -> List[str]:
    pdf_dir = Path("data/pdfs")
    expected = ["full arabic catechism.pdf", "full saints arabic.pdf"]
    return [name for name in expected if (pdf_dir / name).exists()]


def _collect_chroma_debug_info() -> Dict[str, Any]:
    resolved_dir = get_resolved_chroma_dir()
    resolved_path = str(resolved_dir)
    path_exists = resolved_dir.exists()

    return {
        "chroma_dir_env": get_chroma_dir_env(),
        "resolved_chroma_dir": resolved_path,
        "directory_exists": path_exists,
        "english": _collect_collection_debug_info(collection, COLLECTION_NAME),
        "arabic": {
            **_collect_collection_debug_info(arabic_collection, ARABIC_COLLECTION_NAME),
            "source_files_found": _arabic_source_files_found(),
        },
    }


@app.on_event("startup")
def startup():
    global chroma_client, collection, arabic_collection, oai_client

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY missing at startup")
        return

    logger.info("Starting up API...")
    log_chroma_configuration("api.startup")

    embed_fn = embedding_functions.OpenAIEmbeddingFunction(
        api_key=api_key,
        model_name="text-embedding-3-small",
    )

    chroma_client = get_chroma_client()
    collection = get_chroma_collection(
        client=chroma_client,
        embedding_function=embed_fn,
        metadata={"source": COLLECTION_NAME},
    )
    arabic_collection = get_chroma_collection(
        client=chroma_client,
        embedding_function=embed_fn,
        collection_name=ARABIC_COLLECTION_NAME,
        metadata={"source": ARABIC_COLLECTION_NAME, "language": "ar"},
    )
    logger.info(
        "chroma_dir=%s resolved=%s english_collection=%s (%d docs) arabic_collection=%s (%d docs)",
        get_chroma_dir_env(),
        get_resolved_chroma_dir(),
        COLLECTION_NAME,
        int(collection.count()),
        ARABIC_COLLECTION_NAME,
        int(arabic_collection.count()),
    )

    # timeout + max_retries: the SDK retries once on 408/409/429/5xx/connection errors
    # and timeouts, with backoff, so a transient OpenAI blip does not become a 500.
    oai_client = OpenAI(api_key=api_key, timeout=OPENAI_TIMEOUT_SECONDS, max_retries=OPENAI_MAX_RETRIES)
    if not INTERNAL_API_KEY:
        logger.error("INTERNAL_API_KEY is not set. All endpoints except /health will return 503.")
    if ENABLE_DEBUG:
        logger.warning("ENABLE_DEBUG is on: /debug/* endpoints are exposed.")
    try:
        logger.info("saints_loaded_count=%d", len(_build_saint_name_index()))
    except Exception:
        logger.exception("Failed to build saint name index at startup")
    logger.info("Startup complete. model=%s", CHAT_MODEL)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "collection_ready": collection is not None,
        "arabic_collection_ready": arabic_collection is not None,
        "openai_ready": oai_client is not None,
    }


@app.get("/")
def root():
    return {
        "status": "alive",
        "service": "orthodox-api",
        "routes": ["/", "/health", "/debug/chroma", "/debug/chroma/en", "/debug/chroma/ar", "/debug/saints", "/chat", "/saints", "/saint-suggestions"],
    }


@app.get("/debug/chroma")
def debug_chroma():
    global collection, arabic_collection, oai_client
    _require_debug_enabled()

    if collection is None or arabic_collection is None or oai_client is None:
        startup()

    return _collect_chroma_debug_info()


@app.get("/debug/chroma/en")
def debug_chroma_en():
    global collection, oai_client
    _require_debug_enabled()

    if collection is None or oai_client is None:
        startup()

    return _collect_collection_debug_info(collection, COLLECTION_NAME)


@app.get("/debug/chroma/ar")
def debug_chroma_ar():
    global arabic_collection, oai_client
    _require_debug_enabled()

    if arabic_collection is None or oai_client is None:
        startup()

    return {
        **_collect_collection_debug_info(arabic_collection, ARABIC_COLLECTION_NAME),
        "source_files_found": _arabic_source_files_found(),
    }


def _is_probable_saint_heading_line(value: str) -> bool:
    heading = re.sub(r"\s+", " ", (value or "").strip())
    if not (3 <= len(heading) <= 100):
        return False
    if heading.isdigit() or "..." in heading:
        return False

    heading_core = re.sub(r"\([^)]*\)", "", heading).strip(" .:")
    letters = [char for char in heading_core if char.isalpha()]
    if len(letters) < 3:
        return False
    uppercase_ratio = sum(1 for char in letters if char.isupper()) / len(letters)
    if uppercase_ratio < 0.72:
        return False

    lower = heading_core.lower()
    if any(term in lower for term in SAINT_HEADING_EXCLUSIONS):
        return False
    if lower.startswith("[") or lower.startswith("the "):
        return False
    return True


def _title_case_saint_part(value: str) -> str:
    particles = {"and", "of", "the", "in", "on", "de", "al", "el"}
    roman_numerals = {"i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x"}
    words = []
    for raw_word in re.split(r"\s+", value.strip()):
        if not raw_word:
            continue
        lower = raw_word.lower()
        if lower in particles:
            words.append(lower)
        elif lower in roman_numerals:
            words.append(lower.upper())
        else:
            words.append(raw_word[:1].upper() + raw_word[1:].lower())
    return " ".join(words)


def _saint_name_from_heading(value: str) -> str:
    heading = re.sub(r"\s+", " ", (value or "").strip())
    heading = re.sub(r"\([^)]*\)", "", heading)
    heading = re.sub(r"(?<=\w)\d+\b", "", heading)
    heading = heading.strip(" .:")
    if not heading:
        return ""

    if heading.upper() == "THOMAS OF AQUINAS":
        return "St. Thomas Aquinas"

    parts = [part.strip(" .") for part in heading.split(",") if part.strip(" .")]
    markers = {"ST", "ST.", "SS", "SS.", "FR", "FR."}
    if len(parts) > 1:
        primary = parts[0]
        descriptors = [part for part in parts[1:] if part.upper() not in markers]
        name = _title_case_saint_part(primary)
        if descriptors:
            descriptor = ", ".join(_title_case_saint_part(part) for part in descriptors)
            return f"St. {name}, {descriptor}"
        return f"St. {name}"

    return f"St. {_title_case_saint_part(heading)}"


def _saint_record_id(name: str) -> str:
    return _normalize_saint_match_key(name)


def _is_plausible_saint_record_name(name: str) -> bool:
    if _is_plausible_saint_index_name(name):
        return True
    stripped = re.sub(r"^(?:st\.?|saint)\s+", "", name or "", flags=re.IGNORECASE).strip()
    if re.fullmatch(r"[A-Z][A-Za-z'\-]{2,}", stripped):
        return True
    return False


def _extract_record_body(lines: List[str], start_index: int) -> str:
    body_lines = []
    for line in lines[start_index + 1:]:
        stripped = line.strip()
        if _is_probable_saint_heading_line(stripped):
            break
        if stripped and not stripped.isdigit():
            body_lines.append(stripped)
    return re.sub(r"\s+", " ", " ".join(body_lines)).strip()


def _build_saint_record_index() -> List[Dict[str, Any]]:
    global saint_record_index, saint_name_index, collection

    if saint_record_index:
        return saint_record_index
    if collection is None:
        return []

    records_by_id: Dict[str, Dict[str, Any]] = {}
    offset = 0
    page_size = 500

    while True:
        batch = collection.get(
            include=["documents", "metadatas"],
            limit=page_size,
            offset=offset,
        )
        docs = batch.get("documents", []) or []
        metadatas = batch.get("metadatas", []) or []
        if not docs:
            break

        for doc, metadata in zip(docs, metadatas):
            metadata = metadata or {}
            pdf_name = str(metadata.get("pdf", "") or "")
            if not pdf_name.startswith("saints"):
                continue

            lines = (doc or "").splitlines()
            for index, line in enumerate(lines):
                heading = line.strip()
                if not _is_probable_saint_heading_line(heading):
                    continue
                body = _extract_record_body(lines, index)
                if len(body.split()) < 20:
                    continue

                name = _saint_name_from_heading(heading)
                if not name or not _is_plausible_saint_record_name(name):
                    continue
                replacement = MANUAL_SAINT_NAME_REPLACEMENTS.get(name)
                if replacement == "":
                    continue
                name = replacement or name
                if name in MANUAL_SAINT_NAME_EXCLUSIONS:
                    continue

                record_id = _saint_record_id(name)
                if not record_id or record_id in records_by_id:
                    continue

                aliases = _saint_aliases_for_name(name)
                records_by_id[record_id] = {
                    "id": record_id,
                    "name": name,
                    "aliases": aliases,
                    "raw_heading": heading,
                    "is_real_record": True,
                    "body": body,
                    "body_preview": body[:300],
                    "metadata": metadata,
                    "source": _source_from_metadata(metadata),
                }

        if len(docs) < page_size:
            break
        offset += len(docs)

    saint_record_index = sorted(records_by_id.values(), key=lambda record: str(record["name"]).lower())
    saint_name_index = [str(record["name"]) for record in saint_record_index]
    return saint_record_index


def _build_saint_name_index() -> List[str]:
    global saint_name_index

    if saint_name_index:
        return saint_name_index
    return [str(record.get("name", "")) for record in _build_saint_record_index()]


def _find_saint_record_by_name(name: str) -> Dict[str, Any] | None:
    target_keys = _saint_match_keys(name)
    if not target_keys:
        return None

    for record in _build_saint_record_index():
        record_keys = _saint_match_keys(str(record.get("name", "")))
        for alias in record.get("aliases") or []:
            record_keys.update(_saint_match_keys(str(alias)))
        if target_keys & record_keys:
            return record

    return None


def _normalize_arabic_display_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "")
    text = text.replace("ی", "ي").replace("ک", "ك").replace("ھ", "ه")
    text = text.replace("\u0640", "")
    return re.sub(r"\s+", " ", text).strip()


def _is_plausible_arabic_saint_heading(value: str) -> bool:
    text = _normalize_arabic_display_text(value)
    if not text or not _contains_arabic(text):
        return False
    if len(text) < 2 or len(text) > 90:
        return False
    if re.search(r"[.!؟:؛]", text):
        return False
    if re.match(r"^(?:كان|كانت|عاش|عاشت|ولد|ولدت|وُلد|تنيح)\b", text):
        return False
    return True


def _extract_arabic_saint_headings(document: str) -> List[str]:
    normalized = unicodedata.normalize("NFKC", document or "")
    headings: List[str] = []

    for segment in normalized.split("\u271e")[1:]:
        segment = segment.strip()
        if not segment:
            continue

        heading = re.split(r"\s{2,}", segment, maxsplit=1)[0]
        heading = re.split(r"\s+(?:St\.|SS\.)\b", heading, maxsplit=1)[0]
        heading = _normalize_arabic_display_text(heading)
        heading = re.split(
            r"\s+(?:نشأته|نشأتها|حياته|حياتها|سيرته|سيرتها|طفولته|كان|كانت|عاش|عاشت|ولد|ولدت|وُلد|قال|سأل|يروي|روى|لما|إذ|القتل|لقاء)\b",
            heading,
            maxsplit=1,
        )[0]
        heading = re.sub(r"\s*\d+\s*$", "", heading).strip()
        if _is_plausible_arabic_saint_heading(heading):
            headings.append(heading)

    return headings


def _seed_arabic_saint_names() -> List[str]:
    names: List[str] = []
    seen: Set[str] = set()
    for record in ARABIC_SAINTS_INDEX:
        name = _normalize_arabic_display_text(str(record.get("name_ar", "")))
        key = _normalize_arabic_alias_key(name)
        if not name or not key or key in seen:
            continue
        seen.add(key)
        names.append(name)
    return names


def _load_generated_arabic_saint_records() -> List[Dict[str, Any]]:
    global generated_arabic_saint_records, generated_arabic_saint_stats

    if generated_arabic_saint_records is not None:
        return generated_arabic_saint_records

    generated_arabic_saint_records = []
    generated_arabic_saint_stats = {}
    if not GENERATED_ARABIC_SAINTS_PATH.exists():
        return generated_arabic_saint_records

    try:
        payload = json.loads(GENERATED_ARABIC_SAINTS_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        generated_arabic_saint_stats = {"warnings": [f"Failed to load generated Arabic saints index: {exc!r}"]}
        return generated_arabic_saint_records

    generated_arabic_saint_stats = dict(payload.get("stats") or {})
    records = payload.get("saints") or []
    if isinstance(records, list):
        generated_arabic_saint_records = [
            record for record in records if isinstance(record, dict) and str(record.get("name_ar", "")).strip()
        ]
    return generated_arabic_saint_records


def _generated_arabic_saint_names() -> List[str]:
    names: List[str] = []
    seen: Set[str] = set()
    for record in _load_generated_arabic_saint_records():
        name = _normalize_arabic_display_text(str(record.get("name_ar", "")))
        key = _normalize_arabic_alias_key(name)
        if not name or not key or key in seen:
            continue
        seen.add(key)
        names.append(name)
    return names


def _build_arabic_saint_name_index() -> List[str]:
    global arabic_saint_name_index, arabic_collection

    if arabic_saint_name_index:
        return arabic_saint_name_index

    names: List[str] = _seed_arabic_saint_names()
    seen: Set[str] = {_normalize_arabic_alias_key(name) for name in names}
    for generated_name in _generated_arabic_saint_names():
        generated_key = _normalize_arabic_alias_key(generated_name)
        if not generated_key or generated_key in seen:
            continue
        seen.add(generated_key)
        names.append(generated_name)

    if arabic_collection is None or _collection_count_safe(arabic_collection) == 0:
        arabic_saint_name_index = names
        logger.info("arabic_saint_index_count=%d source=seed+generated", len(arabic_saint_name_index))
        return arabic_saint_name_index

    offset = 0
    page_size = 500

    while True:
        batch = arabic_collection.get(
            include=["documents", "metadatas"],
            where={"title": "full saints arabic"},
            limit=page_size,
            offset=offset,
        )
        docs = batch.get("documents", []) or []
        if not docs:
            break

        for doc in docs:
            for heading in _extract_arabic_saint_headings(doc or ""):
                key = _normalize_arabic_alias_key(heading)
                if not key or key in seen:
                    continue
                seen.add(key)
                names.append(heading)

        if len(docs) < page_size:
            break
        offset += len(docs)

    arabic_saint_name_index = names
    logger.info("arabic_saint_index_count=%d source=seed+generated+chroma", len(arabic_saint_name_index))
    return arabic_saint_name_index


def _arabic_saint_query_keys(query: str) -> List[str]:
    keys: List[str] = []

    def add(value: str):
        key = _normalize_arabic_alias_key(value)
        if key and key not in keys:
            keys.append(key)

    add(query)
    add(_strip_arabic_query_titles(query))

    if "العذراء" in _normalize_arabic_alias_key(query):
        add("مريم العذراء")

    return keys


def _arabic_saint_descriptor_rank(query_key: str, name_key: str) -> int:
    preferred_descriptors = ["العذراء", "الرسول", "الرسولي", "الكبير"]
    if any(descriptor in query_key for descriptor in preferred_descriptors):
        return 0 if any(descriptor in name_key for descriptor in preferred_descriptors) else 1
    if query_key in {"مريم", "مرقس", "اثناسيوس"}:
        return 0 if any(descriptor in name_key for descriptor in preferred_descriptors) else 1
    if query_key in {"انطونيوس", "بولا"}:
        return 0 if "القديس" in name_key else 1
    if query_key == "شنوده":
        return 0 if "رئيس المتوحدين" in name_key else 1
    return 0


def _manual_arabic_saint_index_matches(query: str) -> List[str]:
    query_keys = set(_arabic_saint_query_keys(query))
    query_latin = (query or "").strip().lower()
    if not query_keys:
        return []

    available_names = {
        _normalize_arabic_alias_key(name): name
        for name in _build_arabic_saint_name_index()
    }
    matches: List[str] = []
    for record in [*ARABIC_SAINT_INDEX_ALIASES, *_load_generated_arabic_saint_records()]:
        alias_keys = {
            _normalize_arabic_alias_key(str(record.get("name_ar", ""))),
            *[
                _normalize_arabic_alias_key(str(alias))
                for alias in record.get("aliases_ar", [])
            ],
        }
        alias_keys = {key for key in alias_keys if key}
        name_en = str(record.get("name_en", "") or "").strip().lower()
        latin_match = bool(query_latin and name_en and (query_latin == name_en or query_latin in name_en))
        arabic_match = any(
            query_key == alias_key or alias_key in query_key or query_key in alias_key
            for query_key in query_keys
            for alias_key in alias_keys
        )
        if not latin_match and not arabic_match:
            continue
        source_name_key = _normalize_arabic_alias_key(str(record.get("name_ar", "")))
        source_name = available_names.get(source_name_key)
        if source_name and source_name not in matches:
            matches.append(source_name)
    return matches


def _find_arabic_saint_index_matches(query: str, limit: int = 12) -> List[str]:
    query_keys = _arabic_saint_query_keys(query)
    if not query_keys:
        return []

    manual_matches = _manual_arabic_saint_index_matches(query)
    matches: List[Tuple[int, int, int, str]] = []
    for name in _build_arabic_saint_name_index():
        if name in manual_matches:
            continue
        name_key = _normalize_arabic_alias_key(name)
        if not name_key:
            continue
        name_tokens = set(name_key.split())
        best: Tuple[int, int] | None = None
        for query_key in query_keys:
            query_tokens = set(query_key.split())
            score: int | None = None
            if query_key == name_key:
                score = 0
            elif name_key.startswith(query_key):
                score = 1
            elif query_key in name_key:
                score = 2
            elif query_tokens and query_tokens.issubset(name_tokens):
                score = 3
            if score is not None:
                rank = _arabic_saint_descriptor_rank(query_key, name_key)
                candidate = (score, rank)
                best = candidate if best is None else min(best, candidate)
        if best is not None:
            matches.append((best[0], best[1], len(name), name))

    matches.sort(key=lambda item: (item[0], item[1], item[2], item[3]))
    limit = max(1, min(limit, 400))
    return [*manual_matches, *[name for _, _, _, name in matches if name not in manual_matches]][:limit]


def _find_weak_saint_mentions(query: str, limit: int = 12) -> List[Dict[str, Any]]:
    if collection is None:
        return []

    query_key = _normalize_saint_search_query(query)
    if not query_key:
        return []

    real_keys = {_normalize_saint_match_key(name) for name in _build_saint_name_index()}
    weak: List[Dict[str, Any]] = []
    seen = set()
    offset = 0
    page_size = 500

    while True:
        batch = collection.get(include=["documents", "metadatas"], limit=page_size, offset=offset)
        docs = batch.get("documents", []) or []
        metadatas = batch.get("metadatas", []) or []
        if not docs:
            break

        for doc, metadata in zip(docs, metadatas):
            pdf_name = str((metadata or {}).get("pdf", "") or "")
            if not pdf_name.startswith("saints"):
                continue
            for mention in _extract_saint_mentions(doc or ""):
                name = _normalize_suggestion_name(mention)
                if not name:
                    continue
                key = _normalize_saint_match_key(name)
                if key in real_keys or query_key not in key or key in seen:
                    continue
                seen.add(key)
                weak.append({
                    "name": name,
                    "canonical_id": key,
                    "is_real_record": False,
                    "source": _source_from_metadata(metadata or {}),
                })
                if len(weak) >= limit:
                    return weak

        if len(docs) < page_size:
            break
        offset += len(docs)

    return weak


def _collect_saint_debug_info(q: str = "") -> Dict[str, Any]:
    saints = _build_saint_name_index()
    thomas_matches = _find_saint_index_matches("Thomas", limit=20)
    metadata_fields: Set[str] = set()
    saint_source_counts: Dict[str, int] = {}

    if collection is not None:
        offset = 0
        page_size = 500
        while True:
            batch = collection.get(include=["metadatas"], limit=page_size, offset=offset)
            metadatas = batch.get("metadatas", []) or []
            if not metadatas:
                break

            for metadata in metadatas:
                metadata = metadata or {}
                metadata_fields.update(metadata.keys())
                pdf_name = str(metadata.get("pdf", "") or "")
                if pdf_name.startswith("saints"):
                    saint_source_counts[pdf_name] = saint_source_counts.get(pdf_name, 0) + 1

            if len(metadatas) < page_size:
                break
            offset += len(metadatas)

    info: Dict[str, Any] = {
        "total_saint_records_loaded": len(saints),
        "sample_saint_names": saints[:20],
        "thomas_matches": thomas_matches,
        "record_fields": ["name"],
        "source_metadata_fields": sorted(metadata_fields),
        "saint_source_files": dict(sorted(saint_source_counts.items())),
        "records_failed_to_parse": 0,
        "loading_note": "Saint records are derived from dedicated heading-style entries in Chroma documents whose pdf metadata starts with 'saints'. Passing mentions are ignored for search results.",
    }

    if q:
        record_matches = _find_saint_record_matches(q, limit=20)
        weak_mentions = _find_weak_saint_mentions(q, limit=20)
        info["query"] = q
        info["raw_matches"] = [
            {
                "name": str(record.get("name", "")),
                "canonical_id": str(record.get("id", "")),
                "aliases": record.get("aliases", []),
                "is_real_record": True,
                "raw_heading": record.get("raw_heading", ""),
                "source": record.get("source", {}),
            }
            for record in record_matches
        ] + weak_mentions
        info["deduped_final_results"] = [
            {
                "name": str(record.get("name", "")),
                "canonical_id": str(record.get("id", "")),
                "is_real_record": True,
                "source": record.get("source", {}),
            }
            for record in record_matches
        ]

    return info


def _arabic_saints_chroma_chunk_count() -> int:
    if arabic_collection is None:
        return 0
    count = 0
    offset = 0
    page_size = 500
    while True:
        batch = arabic_collection.get(
            include=["metadatas"],
            where={"title": "full saints arabic"},
            limit=page_size,
            offset=offset,
        )
        metadatas = batch.get("metadatas", []) or []
        count += len(metadatas)
        if len(metadatas) < page_size:
            break
        offset += len(metadatas)
    return count


def _arabic_saints_pdf_diagnostics(generated_stats: Dict[str, Any]) -> Dict[str, Any]:
    diagnostics: Dict[str, Any] = {
        "expected_path": str(ARABIC_SAINTS_PDF_PATH),
        "file_exists": ARABIC_SAINTS_PDF_PATH.exists(),
        "file_size_bytes": ARABIC_SAINTS_PDF_PATH.stat().st_size if ARABIC_SAINTS_PDF_PATH.exists() else 0,
        "page_count": generated_stats.get("page_count"),
        "pages_with_extracted_arabic_text": generated_stats.get("pages_with_arabic_text"),
        "arabic_character_count": generated_stats.get("arabic_character_count"),
        "safe_previews": generated_stats.get("previews", []),
    }
    if not diagnostics["file_exists"]:
        diagnostics["warning"] = "full saints arabic PDF is not present in the deployed source files."
    elif not generated_stats:
        diagnostics["warning"] = "Generated Arabic saints index stats are missing. Run python build_arabic_saints_index.py."
    return diagnostics


def _collect_arabic_saint_debug_info(q: str = "") -> Dict[str, Any]:
    saints = _build_arabic_saint_name_index()
    arabic_doc_count = _collection_count_safe(arabic_collection)
    source_files_found = _arabic_source_files_found()
    generated_records = _load_generated_arabic_saint_records()
    generated_stats = generated_arabic_saint_stats or {}
    pdf_diagnostics = _arabic_saints_pdf_diagnostics(generated_stats)
    arabic_saints_chunk_count = _arabic_saints_chroma_chunk_count()
    source_parts = ["seed"]
    if generated_records:
        source_parts.append("generated_pdf_index")
    if arabic_saints_chunk_count:
        source_parts.append("chroma_headings")
    info: Dict[str, Any] = {
        "language": "ar",
        "arabic_seed_count": len(ARABIC_SAINTS_INDEX),
        "arabic_generated_count": len(generated_records),
        "arabic_extracted_count": len(generated_records),
        "arabic_total_count": len(saints),
        "total_arabic_saint_index_count": len(saints),
        "source_used_for_arabic_saints_list": "+".join(source_parts),
        "sample_arabic_saint_names": saints[:20],
        "seed_index_count": len(ARABIC_SAINTS_INDEX),
        "full_saints_arabic_ingested": arabic_doc_count > 0 and "full saints arabic.pdf" in source_files_found,
        "arabic_chroma_document_count": arabic_doc_count,
        "arabic_saints_pdf_chunk_count": arabic_saints_chunk_count,
        "source_files_found": source_files_found,
        "source_title": "full saints arabic",
        "full_saints_arabic_pdf": pdf_diagnostics,
        "full_saints_arabic_was_parsed": bool(generated_records),
        "parse_extraction_warnings": generated_stats.get("warnings", []),
        "loading_note": "Arabic saint list uses the reviewed seed index first, then the generated index built from full saints arabic.pdf, then optional headings extracted from the Arabic saints Chroma collection.",
    }

    if q:
        info["query"] = q
        info["matches"] = _find_arabic_saint_index_matches(q, limit=20)

    return info


@app.get("/debug/saints")
def debug_saints(q: str = "", language: str = "en"):
    global collection, arabic_collection, oai_client
    _require_debug_enabled()

    if collection is None or arabic_collection is None or oai_client is None:
        startup()
        if collection is None or arabic_collection is None:
            raise HTTPException(status_code=500, detail="Server not initialized")

    if _detect_language(language, q) == "ar":
        return _collect_arabic_saint_debug_info(q=q)

    return _collect_saint_debug_info(q=q)


def _extract_saint_chat_intent(question: str) -> Dict[str, str] | None:
    q = re.sub(r"\s+", " ", (question or "").strip()).rstrip("?!. ")
    if not q:
        return None

    # `explicit` marks phrasings where the user typed only a name to look up (the Saints tab
    # sends "search saint: X"); natural questions keep their wording for retrieval.
    patterns = [
        ("lookup", True, r"^search\s+saints?\s*:\s*(.+)$"),
        ("lookup", True, r"^(?:i\s+(?:want|would\s+like)\s+to\s+)?learn\s+more\s+about\s+(.+)$"),
        ("lookup", True, r"^(?:tell\s+me\s+)?more\s+about\s+(.+)$"),
        ("lookup", True, r"^(?:look\s+up|lookup|find)\s+(.+)$"),
        ("lookup", False, r"^(?:who\s+is|who\s+was|tell\s+me\s+about|about)\s+(.+)$"),
        ("list", True, r"^(?:list|show)\s+saints?\s+named\s+(.+)$"),
        ("list", True, r"^(?:give\s+me|show\s+me)\s+(?:a\s+)?list\s+of\s+(?:saints?\s+named\s+)?(.+)$"),
        ("list", True, r"^list\s+(?:of\s+)?(.+)$"),
    ]

    for mode, explicit, pattern in patterns:
        match = re.match(pattern, q, flags=re.IGNORECASE)
        if not match:
            continue
        candidate = _trim_saint_candidate(re.sub(r"\s+", " ", match.group(1)).strip())
        if not candidate:
            continue
        has_marker = re.search(r"\b(?:st\.?|saint|saints|marys)\b", candidate, flags=re.IGNORECASE)
        if has_marker or _find_saint_index_matches(candidate, limit=1):
            return {"mode": mode, "query": candidate, "explicit": explicit}

    return None


def _saint_options_response(raw_query: str, matches: List[str], mode: str, language: str = "en") -> Dict[str, Any]:
    last_options = matches[:12]
    if language == "ar":
        answer = (
            f"وجدت {len(last_options)} نتيجة لقديسين تطابق '{raw_query}'."
            if mode == "list"
            else f"وجدت أكثر من قديس يطابق '{raw_query}'. اختر واحدًا من الخيارات أدناه."
        )
    else:
        answer = (
            f"I found {len(last_options)} saint matches for '{raw_query}'."
            if mode == "list"
            else f"I found multiple saints matching '{raw_query}'. Choose one option below."
        )
    return {
        "answer": answer,
        "sources": [],
        "entities": [],
        "options": last_options,
        "can_learn_more": False,
    }


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, request: Request, response: Response):
    """Entry point: opens a request trace, applies rate limiting, delegates to `_chat_impl`.

    The trace context manager emits exactly one JSON log line when the request ends,
    whether it returned normally or raised (see request_log.py / DECISIONS.md LOG-*).
    """
    with RequestTrace("chat") as trace:
        response.headers["X-Request-ID"] = trace.request_id
        trace.set(
            language_requested=req.language,
            mode_requested=req.mode,
            history_messages=len(req.history) if isinstance(req.history, list) else 0,
            client_ip=_client_ip(request),
        )
        _enforce_chat_rate_limit(request)
        payload = _chat_impl(req, trace)
        if req.debug:
            payload = {**payload, "debug": trace.debug_payload()}
        return payload


def _chat_impl(req: ChatRequest, trace: RequestTrace):
    global collection, arabic_collection, oai_client

    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.error("OPENAI_API_KEY is missing; cannot serve /chat")
            raise HTTPException(status_code=503, detail="Server is not configured.")

        if collection is None or arabic_collection is None or oai_client is None:
            startup()
            if collection is None or arabic_collection is None or oai_client is None:
                logger.error("Server not initialized (collections or OpenAI client missing)")
                raise HTTPException(status_code=503, detail="Server is not configured.")

        original_question = (req.question or "").strip()
        if not original_question:
            raise HTTPException(status_code=400, detail="Question cannot be empty")
        if len(original_question) > MAX_QUESTION_CHARS:
            raise HTTPException(
                status_code=400,
                detail=f"Question is too long. Please keep it under {MAX_QUESTION_CHARS} characters.",
            )
        original_question = _canonicalize_saint_text(original_question)
        history = _sanitize_history(req.history)
        requested_top_k = max(1, min(int(req.top_k or 8), MAX_TOP_K))

        mode = _normalize_chat_mode(req.mode)
        detected_language = _detect_language(req.language, original_question)
        manual_saint_match = (
            _resolve_manual_saint_alias(original_question)
            if detected_language == "ar"
            else None
        )
        matched_saint_alias = (
            f"{manual_saint_match['alias']} -> {manual_saint_match['record_name']}"
            if manual_saint_match
            else ""
        )
        trace.set_question(original_question)
        trace.set(
            language=detected_language,
            mode=mode,
            matched_saint_alias=matched_saint_alias or None,
            history_messages_used=len(history),
        )

        # Separate WHAT to retrieve from HOW to present it (RET-006). Saint-tab lookups
        # ("search saint: X") are already a bare name and skip the call.
        analysis = _analyze_request(original_question, history)
        trace.lap("analysis")
        # `question` keeps the user's words for the saint-intent patterns below; retrieval
        # uses the standalone query (pronouns resolved, formatting words removed).
        question = original_question
        retrieval_question = _canonicalize_saint_text(analysis.retrieval_query)
        entity = manual_saint_match["record_name"] if manual_saint_match else None
        clean_entities = []

        if detected_language == "ar":
            metadata_filter = _arabic_metadata_filter_for_mode(mode)
            top_k = requested_top_k
            retrieval_top_k = min(16, max(top_k, 10))
            arabic_selected_saint = ""
            if mode == "saints":
                try:
                    saint_matches = _find_arabic_saint_index_matches(original_question, limit=1)
                    arabic_selected_saint = saint_matches[0] if saint_matches else ""
                except Exception:
                    logger.warning("Arabic saint index match failed", exc_info=True)
                if arabic_selected_saint:
                    retrieval_question = arabic_selected_saint
            retrieval_queries = [retrieval_question]
            trace.set(
                collection=ARABIC_COLLECTION_NAME,
                metadata_filter=metadata_filter,
                retrieval_top_k=retrieval_top_k,
                retrieval_queries=retrieval_queries,
                arabic_selected_saint=arabic_selected_saint or None,
            )
            trace.lap("prepare")

            docs, metas, distances = _retrieve_documents(
                retrieval_queries,
                top_k=retrieval_top_k,
                target_collection=arabic_collection,
                metadata_filter=metadata_filter,
            )
            best_distance = min(distances) if distances else None
            lexical_docs, lexical_metas = _retrieve_arabic_lexical_documents(
                retrieval_question,
                top_k=retrieval_top_k,
                metadata_filter=metadata_filter,
            )
            if lexical_docs:
                docs, metas = _merge_document_batches(
                    lexical_docs,
                    lexical_metas,
                    docs,
                    metas,
                    retrieval_top_k,
                )
            trace.lap("retrieval")
            trace.set(
                retrieved_count=len(docs),
                merged_ids=[chunk_id_from_metadata(m) for m in metas],
                best_distance=best_distance,
                distance_threshold=ARABIC_VECTOR_DISTANCE_THRESHOLD or None,
                lexical_hits=len(lexical_docs),
            )
            trace.set_kept(metas, 0)

            # No keyword filter any more (RET-002). Refuse only when nothing came back, or
            # when the lexical search found nothing and the vector distance check is on and fails.
            no_relevant_source = not docs or (
                not lexical_docs
                and ARABIC_VECTOR_DISTANCE_THRESHOLD > 0
                and (best_distance is None or best_distance > ARABIC_VECTOR_DISTANCE_THRESHOLD)
            )
            if no_relevant_source:
                trace.set(outcome="refused", refusal=True, refusal_reason="no_relevant_source")
                answer = (
                    "وجدت اسم القديس في فهرس القديسين، لكن لم أجد معلومات كافية عنه في المصادر العربية المتاحة."
                    if mode == "saints" and arabic_selected_saint
                    else _no_source_answer("ar")
                )
                return {
                    "answer": answer,
                    "sources": [],
                    "entities": [],
                    "options": [],
                    "can_learn_more": False,
                }

            context, numbered_sources = _build_numbered_context(docs, metas, normalize=_normalize_arabic_context_text)
            messages = _build_chat_messages(
                ARABIC_SYSTEM_PROMPT, history, original_question, context, "ar", note=_format_note(analysis, "ar")
            )
            trace.set(
                context_chunks=len(docs),
                context_chars=len(context),
                prompt_chars=sum(len(m["content"]) for m in messages),
                prompt_version=PROMPT_VERSION,
                history_turns_sent=min(len(history), HISTORY_TURNS_FOR_MODEL),
            )

            resp = oai_client.chat.completions.create(
                model=CHAT_MODEL,
                temperature=CHAT_TEMPERATURE,
                max_tokens=_answer_max_tokens(analysis, broad=analysis.broad),
                messages=messages,
            )
            trace.set_generation(resp, CHAT_MODEL)
            trace.lap("generation")

            answer = resp.choices[0].message.content or ""
            followup_options: List[str] = []
            if mode == "catechism":
                followup_options = _catechism_followup_options(answer, original_question, language="ar")

            grounding = _response_grounding_status(answer, docs)
            refused = grounding == "no-source"
            response_sources, cited_count = _decline_or_cited_sources(answer, numbered_sources, refused)
            trace.set(
                outcome="refused" if refused else "answered",
                refusal=refused,
                refusal_reason="model_refusal" if refused else None,
                grounding=grounding,
                answer_chars=len(answer),
                citations=cited_count,
                sources_returned=len(response_sources),
            )
            trace.lap("postprocess")

            return {
                "answer": answer,
                "sources": response_sources,
                "entities": [],
                "options": followup_options,
                "can_learn_more": _has_viable_saint_learn_more(answer, docs, metas, mode),
            }

        saint_intent = _extract_saint_chat_intent(question) if mode != "catechism" else None
        if saint_intent:
            raw_saint_query = saint_intent["query"]
            saint_records = _find_saint_record_matches(raw_saint_query, limit=12)
            saint_matches = [str(r.get("name", "")) for r in saint_records]
            strong_matches, medium_matches = _split_saint_matches(saint_records)
            single_bare_name = len(_normalize_saint_match_key(raw_saint_query).split()) == 1
            _log_saint_query(raw_saint_query, _normalize_saint_search_query(raw_saint_query), saint_matches)
            trace.set(
                saint_intent=saint_intent["mode"],
                saint_intent_explicit=saint_intent.get("explicit", False),
                saint_strong_matches=len(strong_matches),
                saint_medium_matches=len(medium_matches),
            )

            # A saint-index miss must never end the request (AUDIT C17, DECISIONS RET-001):
            # the index is built from heading heuristics and misses real entries, so an
            # unconfident lookup falls through to ordinary retrieval on the user's own words.
            if saint_intent["mode"] == "list" and saint_matches:
                trace.set(outcome="options", refusal=False, options_count=min(12, len(saint_matches)))
                return _saint_options_response(raw_saint_query, saint_matches, "list", language=detected_language)

            # A menu is only justified by several genuinely matching saints: two or more exact
            # matches, or a bare first name ("St. John") that several indexed saints share.
            many_bare_candidates = single_bare_name and len(strong_matches) + len(medium_matches) >= 3
            if len(strong_matches) >= 2 or many_bare_candidates:
                option_names = strong_matches + medium_matches if many_bare_candidates else strong_matches
                trace.set(outcome="options", refusal=False, options_count=min(12, len(option_names)))
                return _saint_options_response(raw_saint_query, option_names, "lookup", language=detected_language)

            confident = strong_matches[:1] or (medium_matches[:1] if len(medium_matches) == 1 else [])
            if confident:
                entity = confident[0]
                if saint_intent.get("explicit"):
                    # The user typed only a name; a descriptive query retrieves better than "search saint: X".
                    question = f"{entity} Orthodox saint biography life feast teachings martyr monk bishop"
                    retrieval_question = question
                # Otherwise keep the user's question; `_build_retrieval_queries` adds entity variants.
            else:
                trace.set(saint_intent_fallthrough=True)
                # Only a name lookup ("search saint: X") is rewritten into a biography query. A
                # "list ..." request with no index match ("list saints who were martyred in Egypt")
                # keeps the analysed query; the canned biography string used to replace it (RET-006).
                if saint_intent.get("explicit") and saint_intent["mode"] == "lookup":
                    question = f"{raw_saint_query} Orthodox saint biography life feast teachings martyr monk bishop"
                    retrieval_question = question

        # TODO(per-conversation follow-ups): numbered follow-ups ("the 2nd one") used to be
        # resolved against a process-global `last_list` shared by every user, keyed off any
        # digit in the question (AUDIT.md C16). That was removed. When rebuilt, resolve
        # against the *previous assistant message of this conversation* (the frontend already
        # stores `options`/`entities` per message) and only when the question is clearly an
        # ordinal selection, not any question that happens to contain a number.

        trace.set(rewritten_question=retrieval_question[:300], entity=entity)

        ambiguous_query = _extract_ambiguous_saint_query(question) if mode != "catechism" else ""
        if ambiguous_query and entity is None:
            core_name = _core_name_from_query(ambiguous_query)
            if core_name in AMBIGUOUS_SAINT_FALLBACKS:
                clean_entities = _filter_sourced_saint_options(AMBIGUOUS_SAINT_FALLBACKS[core_name])
                if len(clean_entities) > 1:
                    trace.set(outcome="options", refusal=False, options_count=len(clean_entities), ambiguous_query=ambiguous_query)
                    ambiguous_answer = (
                        f"وجدت أكثر من قديس يطابق '{ambiguous_query}'. اختر واحدًا من الخيارات أدناه."
                        if detected_language == "ar"
                        else f"I found multiple saints matching '{ambiguous_query}'. Choose one option below."
                    )
                    return {
                        "answer": ambiguous_answer,
                        "sources": [],
                        "entities": [],
                        "options": clean_entities,
                    }

            if detected_language == "ar":
                suggestion_options = _find_arabic_saint_index_matches(ambiguous_query, limit=10)
            else:
                # Only strong/medium matches count as "several saints match"; weak substring
                # hits are not a reason to interrupt the user with a menu.
                strong_opts, medium_opts = _split_saint_matches(
                    _find_saint_record_matches(_canonicalize_saint_text(ambiguous_query), limit=10)
                )
                suggestion_options = strong_opts if len(strong_opts) >= 2 else (strong_opts + medium_opts)
            if len(suggestion_options) > 1:
                clean_entities = suggestion_options
                trace.set(outcome="options", refusal=False, options_count=len(clean_entities), ambiguous_query=ambiguous_query)
                ambiguous_answer = (
                    f"وجدت أكثر من قديس يطابق '{ambiguous_query}'. اختر واحدًا من الخيارات أدناه."
                    if detected_language == "ar"
                    else f"I found multiple saints matching '{ambiguous_query}'. Choose one option below."
                )
                return {
                    "answer": ambiguous_answer,
                    "sources": [],
                    "entities": [],
                    "options": clean_entities,
                }

        broad_list = _is_broad_list_question(retrieval_question)
        definition_question = _is_definition_question(retrieval_question)
        top_k = requested_top_k
        retrieval_top_k = min(16, max(top_k, 12 if broad_list else 10 if definition_question else top_k))

        # Retrieval plan (RET-007): a saint list selected by name comes from the saint index;
        # a broad request searches with the sub-queries too and keeps more chunks.
        retrieval_plan = "default"
        list_note = None
        saint_list_records: List[Dict[str, Any]] = []
        saint_list_total = 0
        if analysis.saint_name_filter and entity is None:
            saint_list_records, saint_list_total = _saint_list_entries(analysis.saint_name_filter)
            if saint_list_records:
                retrieval_plan = "saint_list"
        if retrieval_plan == "default" and analysis.broad:
            retrieval_plan = "broad"
            retrieval_top_k = max(retrieval_top_k, BROAD_RETRIEVAL_TOP_K)

        retrieval_queries = _build_retrieval_queries(retrieval_question, entity=entity)
        if retrieval_plan == "broad":
            retrieval_queries = retrieval_queries[:1] + analysis.sub_queries + retrieval_queries[1:]
        trace.set(
            collection=COLLECTION_NAME,
            metadata_filter=None,
            retrieval_top_k=retrieval_top_k,
            retrieval_queries=[q[:300] for q in retrieval_queries],
            broad_list=broad_list,
            definition_question=definition_question,
            retrieval_plan=retrieval_plan,
        )
        trace.lap("prepare")
        if retrieval_plan == "saint_list":
            docs, metas = _saint_list_context(saint_list_records)
            distances = []
            best_distance = None
            list_note = _saint_list_note(analysis.saint_name_filter, len(saint_list_records), saint_list_total)
            trace.set(saint_list={"filter": analysis.saint_name_filter, "shown": len(saint_list_records), "matched": saint_list_total})
        else:
            docs, metas, distances = _retrieve_documents(
                retrieval_queries,
                top_k=retrieval_top_k,
                entity=entity,
                per_query_min=BROAD_PER_QUERY_MIN if retrieval_plan == "broad" else 0,
            )
            best_distance = min(distances) if distances else None
            # Comparisons with another tradition: the Coptic books mention it only in passing,
            # so similarity search rarely surfaces those pages. Rank again among chunks that
            # contain the tradition's name (RET-008).
            tradition_terms = _compared_tradition_terms(original_question, analysis)
            if tradition_terms and docs:
                seen_ids = {chunk_id_from_metadata(m) for m in metas}
                for term in tradition_terms:
                    extra_docs, extra_metas, extra_distances = _retrieve_documents(
                        [retrieval_question],
                        top_k=TRADITION_RETRIEVAL_TOP_K,
                        where_document={"$contains": term},
                    )
                    for doc, meta, dist in zip(extra_docs, extra_metas, extra_distances):
                        chunk_id = chunk_id_from_metadata(meta)
                        if chunk_id in seen_ids:
                            continue
                        seen_ids.add(chunk_id)
                        docs.append(doc)
                        metas.append(meta)
                        distances.append(dist)
                trace.set(tradition_terms=tradition_terms)
        if mode == "saints":
            docs, metas = _prepend_saint_record_context(docs, metas, entity)
        trace.lap("retrieval")
        trace.set(
            retrieved_count=len(docs),
            merged_ids=[chunk_id_from_metadata(m) for m in metas],
            best_distance=best_distance,
            distance_threshold=VECTOR_DISTANCE_THRESHOLD or None,
        )
        # The keyword relevance filter is gone (RET-002); every retrieved chunk is kept and the
        # model is trusted to cite only what it uses. "No relevant source" is decided by the
        # best vector distance across all queries (RET-003).
        trace.set_kept(metas, 0)

        # A saint list is selected by exact name match, not by similarity, so the distance
        # check does not apply to it.
        no_relevant_source = not docs or (
            retrieval_plan != "saint_list"
            and VECTOR_DISTANCE_THRESHOLD > 0
            and (best_distance is None or best_distance > VECTOR_DISTANCE_THRESHOLD)
        )
        if no_relevant_source:
            trace.set(outcome="refused", refusal=True, refusal_reason="nothing_retrieved" if not docs else "distance_above_threshold")
            return {
                "answer": _no_source_answer(detected_language),
                "sources": [],
                "entities": [],
                "options": [],
                "can_learn_more": False,
            }

        # Numbered passages the model cites as [n]; the last few turns go in as real messages
        # so pronouns and follow-ups resolve naturally (DECISIONS.md GEN-001..003).
        context, numbered_sources = _build_numbered_context(docs, metas)
        note = "\n".join(part for part in (list_note, _format_note(analysis, "en")) if part) or None
        messages = _build_chat_messages(ENGLISH_SYSTEM_PROMPT, history, original_question, context, "en", note=note)
        trace.set(
            context_chunks=len(docs),
            context_chars=len(context),
            prompt_chars=sum(len(m["content"]) for m in messages),
            prompt_version=PROMPT_VERSION,
            history_turns_sent=min(len(history), HISTORY_TURNS_FOR_MODEL),
        )

        resp = oai_client.chat.completions.create(
            model=CHAT_MODEL,
            temperature=CHAT_TEMPERATURE,
            max_tokens=_answer_max_tokens(analysis, broad=retrieval_plan != "default"),
            messages=messages,
        )
        trace.set_generation(resp, CHAT_MODEL)
        trace.lap("generation")

        answer = resp.choices[0].message.content or ""
        followup_options: List[str] = []
        if mode == "catechism":
            followup_options = _catechism_followup_options(answer, original_question, language=detected_language)

        items = re.findall(r"(?:\d+[\.\)]\s*)(.+)", answer)

        if items:
            candidate_entities = []
            for item in items:
                entity_candidate = _extract_entity_candidate(item)
                if not entity_candidate:
                    continue
                if len(entity_candidate) > 80:
                    continue
                if not _looks_like_person_entity(entity_candidate):
                    continue
                candidate_entities.append(entity_candidate)

            if candidate_entities:
                # Preserve order but deduplicate exact matches.
                seen_entities = set()
                clean_entities = []
                for item in candidate_entities:
                    if item in seen_entities:
                        continue
                    seen_entities.add(item)
                    clean_entities.append(item)

        grounding = _response_grounding_status(answer, docs)
        refused = grounding == "no-source"
        response_sources, cited_count = _decline_or_cited_sources(answer, numbered_sources, refused)
        trace.set(
            outcome="refused" if refused else "answered",
            refusal=refused,
            refusal_reason="model_refusal" if refused else None,
            grounding=grounding,
            answer_chars=len(answer),
            entities_extracted=len(clean_entities),
            citations=cited_count,
            sources_returned=len(response_sources),
        )
        trace.lap("postprocess")

        return {
            "answer": answer,
            "sources": response_sources,
            "entities": clean_entities,
            "options": followup_options,
            "can_learn_more": _has_viable_saint_learn_more(answer, docs, metas, mode),
        }

    except HTTPException:
        raise
    except (RateLimitError, APITimeoutError, APIConnectionError, APIStatusError) as e:
        logger.exception("OpenAI call failed in /chat request_id=%s", trace.request_id)
        trace.set(error_type=type(e).__name__)
        raise _openai_error_to_http(e) from e
    except Exception as e:
        logger.exception("Unhandled error in /chat request_id=%s", trace.request_id)
        trace.set(error_type=type(e).__name__)
        raise HTTPException(status_code=500, detail=GENERIC_SERVER_ERROR)


@app.get("/saint-suggestions", response_model=SaintSuggestionResponse)
def saint_suggestions(q: str, limit: int = 8, language: str = "en"):
    global collection, arabic_collection, oai_client

    with RequestTrace("saint-suggestions") as trace:
        query = (q or "").strip()
        trace.set(language_requested=language, query_chars=len(query), limit=limit)
        if len(query) < 2:
            trace.set(outcome="empty", result_count=0)
            return {"suggestions": []}

        if collection is None or arabic_collection is None or oai_client is None:
            startup()
            if collection is None or arabic_collection is None or oai_client is None:
                raise HTTPException(status_code=503, detail="Server is not configured.")

        try:
            detected = _detect_language(language, query)
            trace.set(language=detected)
            if detected == "ar":
                suggestions = _find_arabic_saint_index_matches(query, limit=limit)
                _log_saint_query(query, _normalize_arabic_alias_key(query), suggestions)
            else:
                suggestions = _find_saint_suggestions(query, limit=limit)
                _log_saint_query(query, _normalize_saint_search_query(query), suggestions)
            trace.set(outcome="answered", result_count=len(suggestions))
            return {"suggestions": suggestions}
        except Exception as e:
            logger.exception("Unhandled error in /saint-suggestions request_id=%s", trace.request_id)
            trace.set(error_type=type(e).__name__)
            raise HTTPException(status_code=500, detail=GENERIC_SERVER_ERROR)


@app.get("/saints", response_model=SaintsListResponse)
def saints_list(q: str = "", search: str = "", limit: int = 400, offset: int = 0, language: str = "en"):
    global collection, arabic_collection, oai_client

    with RequestTrace("saints") as trace:
        if collection is None or arabic_collection is None or oai_client is None:
            startup()
            if collection is None or arabic_collection is None or oai_client is None:
                raise HTTPException(status_code=503, detail="Server is not configured.")

        try:
            raw_query = q or search
            detected = _detect_language(language, raw_query)
            trace.set(language_requested=language, language=detected, query_chars=len(raw_query), limit=limit, offset=offset)
            if detected == "ar":
                saints = _build_arabic_saint_name_index()
                query = _normalize_arabic_alias_key(raw_query)
                if query:
                    saints = _find_arabic_saint_index_matches(raw_query, limit=400)
                    _log_saint_query(raw_query, query, saints)
            else:
                saints = _build_saint_name_index()
                query = _normalize_saint_search_query(raw_query)
                if query:
                    saints = _find_saint_index_matches(raw_query, limit=400)
                    _log_saint_query(raw_query, query, saints)
            safe_limit = max(1, min(limit, 400))
            safe_offset = max(0, offset)
            paged_saints = saints[safe_offset:safe_offset + safe_limit]
            trace.set(outcome="answered", result_count=len(paged_saints), total=len(saints))
            return {
                "saints": paged_saints,
                "total": len(saints),
                "offset": safe_offset,
                "limit": safe_limit,
            }
        except Exception as e:
            logger.exception("Unhandled error in /saints request_id=%s", trace.request_id)
            trace.set(error_type=type(e).__name__)
            raise HTTPException(status_code=500, detail=GENERIC_SERVER_ERROR)
