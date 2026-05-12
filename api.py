import os
import re
from typing import List, Dict, Any, Set, Tuple

from dotenv import load_dotenv
from chromadb.utils import embedding_functions
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
from chroma_store import (
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

load_dotenv()

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

SAINT_ALIAS_GROUPS: Dict[str, List[str]] = {
    "St. Thomas the Apostle": [
        "St. Thomas the Apostle",
        "Saint Thomas",
        "Thomas the Apostle",
        "Apostle Thomas",
        "Didymus",
        "Doubting Thomas",
    ],
}

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


def _canonicalize_saint_text(value: str) -> str:
    return (
        (value or "")
        .strip()
        .replace("Kyrillos", "Cyril")
        .replace("kyrillos", "cyril")
        .replace("Cyrillus", "Cyril")
        .replace("cyrillus", "cyril")
    )


def _normalize_saint_match_key(value: str) -> str:
    text = _canonicalize_saint_text(value).lower()
    text = re.sub(r"\bmarys\b", "mary", text)
    text = re.sub(r"['’`]", "", text)
    text = re.sub(r"[-_/]", " ", text)
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\b(?:st|saint|saints)\b", " ", text)
    text = re.sub(r"\bthe\b", " ", text)
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
    name_keys = _saint_match_keys(name)
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
    for canonical, values in SAINT_ALIAS_GROUPS.items():
        group_keys = set()
        for value in [canonical] + values:
            group_keys.update(_saint_match_keys(value))
        if name_keys & group_keys:
            add(canonical)
            for value in values:
                add(value)

    return aliases


def _find_saint_index_matches(query: str, limit: int = 12) -> List[str]:
    saint_index = _build_saint_name_index()
    query_keys = _saint_match_keys(query)
    if not query_keys:
        return []

    scored: List[Tuple[int, int, str]] = []
    for name in saint_index:
        name_keys = set()
        for alias in _saint_aliases_for_name(name):
            name_keys.update(_saint_match_keys(alias))
        if not name_keys:
            continue

        score: int | None = None
        for query_key in query_keys:
            query_tokens = set(query_key.split())
            for name_key in name_keys:
                name_tokens = set(name_key.split())
                if query_key == name_key:
                    score = 0 if name.lower() == query.lower() else 1
                elif name_key.startswith(query_key):
                    score = 2 if score is None else min(score, 2)
                elif query_key in name_key:
                    score = 3 if score is None else min(score, 3)
                elif query_tokens and query_tokens.issubset(name_tokens):
                    score = 4 if score is None else min(score, 4)
                elif name_tokens and name_tokens.issubset(query_tokens):
                    score = 5 if score is None else min(score, 5)

        if score is not None:
            scored.append((score, len(name), name))

    scored.sort(key=lambda item: (item[0], item[1], item[2].lower()))
    matches = []
    seen = set()
    for _, _, name in scored:
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        matches.append(name)
        if len(matches) >= max(1, min(limit, 400)):
            break
    return matches


def _log_saint_query(raw: str, normalized: str, matches: List[str]) -> None:
    print(f"SAINT_QUERY_RAW: {raw}")
    print(f"SAINT_QUERY_NORMALIZED: {normalized}")
    print(f"SAINT_MATCH_COUNT: {len(matches)}")
    print(f"SAINT_MATCH_NAMES: {matches[:12]}")


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


def _retrieve_documents(queries: List[str], top_k: int, entity: str | None = None):
    global collection

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

    aggregated: List[tuple[str, Dict[str, Any]]] = []
    seen_docs = set()

    for query in deduped_queries[:4]:
        retrieved = collection.query(query_texts=[query], n_results=top_k)
        docs = retrieved.get("documents", [[]])[0]
        metas = retrieved.get("metadatas", [[]])[0]

        for doc, meta in zip(docs, metas):
            if not doc or not meta:
                continue
            key = (
                meta.get("source_type", "pdf"),
                meta.get("pdf"),
                meta.get("page"),
                meta.get("url"),
                meta.get("chunk_index"),
                doc[:120],
            )
            if key in seen_docs:
                continue
            seen_docs.add(key)
            aggregated.append((doc, meta))

    if entity:
        saint_docs = [
            (doc, meta)
            for doc, meta in aggregated
            if str((meta or {}).get("pdf", "")).startswith("saints")
        ]
        if saint_docs:
            aggregated = saint_docs + [
                (doc, meta) for doc, meta in aggregated if not str((meta or {}).get("pdf", "")).startswith("saints")
            ]

    docs = [doc for doc, _ in aggregated[:top_k]]
    metas = [meta for _, meta in aggregated[:top_k]]
    return docs, metas


class ChatRequest(BaseModel):
    question: str
    history: list = []
    top_k: int = 8


class Source(BaseModel):
    source_type: str = "pdf"
    pdf: str | None = None
    page: int | None = None
    url: str | None = None
    title: str | None = None


class ChatResponse(BaseModel):
    answer: str
    sources: List[Source]
    entities: List[str] = []
    options: List[str] = []


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
    global collection
    query = _canonicalize_saint_text(query)
    normalized_query = _normalize_saint_search_query(query)

    index_matches = _find_saint_index_matches(query, limit=max(12, limit))
    if normalized_query:
        exact_index_match = any(
            _saint_match_keys(query) & set().union(*[_saint_match_keys(alias) for alias in _saint_aliases_for_name(name)])
            for name in index_matches[:1]
        )
        if len(index_matches) >= 2 or exact_index_match:
            return index_matches[: max(1, min(limit, 12))]

    if collection is None:
        return index_matches[: max(1, min(limit, 12))]

    retrieved = collection.query(
        query_texts=[f"{query} Orthodox saint names list"],
        n_results=12,
    )
    docs = retrieved.get("documents", [[]])[0]

    candidates = []
    core_word = _core_name_from_query(query)
    for doc in docs:
        candidates.extend(_extract_saint_mentions(doc))
        candidates.extend(_extract_core_name_mentions(doc, core_word))

    q_lower = query.lower()
    unique = []
    seen = set()
    for name in candidates:
        normalized_name = _normalize_suggestion_name(name)
        if not normalized_name:
            continue
        replacement = MANUAL_SAINT_NAME_REPLACEMENTS.get(normalized_name)
        if replacement == "":
            continue
        normalized_name = replacement or normalized_name
        if normalized_name in MANUAL_SAINT_NAME_EXCLUSIONS:
            continue
        key = normalized_name.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(normalized_name)

    q_no_prefix = _normalize_saint_search_query(q_lower)
    filtered = [name for name in unique if q_no_prefix in _normalize_saint_search_query(name)]
    filtered.sort(key=lambda name: (not _normalize_saint_search_query(name).startswith(q_no_prefix), len(name), name.lower()))

    if index_matches:
        filtered = list(dict.fromkeys(index_matches + filtered))

    if len(filtered) < 2 and core_word in AMBIGUOUS_SAINT_FALLBACKS:
        fallback = AMBIGUOUS_SAINT_FALLBACKS[core_word]
        filtered = list(dict.fromkeys(filtered + fallback))

    return filtered[: max(1, min(limit, 12))]


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
        # Treat short saint names as ambiguous (e.g. St. John / St. Mary)
        if len(name_only.split()) <= 2:
            return candidate
    return ""


app = FastAPI(title="Orthodox PDF Chat API")

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
oai_client = None
last_list = {}
saint_name_index: List[str] = []


def _collect_chroma_debug_info() -> Dict[str, Any]:
    resolved_dir = get_resolved_chroma_dir()
    resolved_path = str(resolved_dir)
    path_exists = resolved_dir.exists()

    info: Dict[str, Any] = {
        "chroma_dir_env": get_chroma_dir_env(),
        "resolved_chroma_dir": resolved_path,
        "directory_exists": path_exists,
        "collection_name": COLLECTION_NAME,
        "collection_ready": collection is not None,
        "document_count": 0,
        "source_type_counts": {},
        "pdf_counts": {},
        "sample_items": [],
    }

    if collection is None:
        return info

    try:
        info["document_count"] = int(collection.count())
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
            metadata_batch = collection.get(include=["metadatas"], limit=page_size, offset=offset)
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
        batch = collection.get(include=["documents", "metadatas"], limit=3, offset=0)
        docs = batch.get("documents", []) or []
        metas = batch.get("metadatas", []) or []
        sample_items = []
        for doc, metadata in zip(docs[:3], metas[:3]):
            sample_items.append(
                {
                    "metadata": metadata or {},
                    "document_preview": (doc or "")[:240],
                }
            )
        info["sample_items"] = sample_items
    except Exception as exc:
        info["sample_error"] = str(exc)

    return info


@app.on_event("startup")
def startup():
    global chroma_client, collection, oai_client

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("OPENAI_API_KEY missing at startup")
        return

    print("Starting up API...")
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
    print(f"CHROMA_DIR env: {get_chroma_dir_env()}")
    print(f"Collection name: {COLLECTION_NAME}")
    print(f"Ingest start; resolved_chroma_dir: {get_resolved_chroma_dir()}")
    print(f"Collection count before ingest: {int(collection.count())}")

    oai_client = OpenAI(api_key=api_key)
    debug_info = _collect_chroma_debug_info()
    print(f"Resolved Chroma dir: {debug_info['resolved_chroma_dir']}")
    print(f"Chroma dir exists: {debug_info['directory_exists']}")
    print(f"Chroma document count: {debug_info['document_count']}")
    try:
        print(f"SAINTS_LOADED_COUNT: {len(_build_saint_name_index())}")
    except Exception as exc:
        print(f"SAINTS_LOADED_COUNT_ERROR: {repr(exc)}")
    print("Startup complete.")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "collection_ready": collection is not None,
        "openai_ready": oai_client is not None,
    }


@app.get("/")
def root():
    return {
        "status": "alive",
        "service": "orthodox-api",
        "routes": ["/", "/health", "/debug/chroma", "/debug/saints", "/chat", "/saints", "/saint-suggestions"],
    }


@app.get("/debug/chroma")
def debug_chroma():
    global collection, oai_client

    if collection is None or oai_client is None:
        startup()

    return _collect_chroma_debug_info()


def _collect_saint_debug_info() -> Dict[str, Any]:
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

    return {
        "total_saint_records_loaded": len(saints),
        "sample_saint_names": saints[:20],
        "thomas_matches": thomas_matches,
        "record_fields": ["name"],
        "source_metadata_fields": sorted(metadata_fields),
        "saint_source_files": dict(sorted(saint_source_counts.items())),
        "records_failed_to_parse": 0,
        "loading_note": "Saint records are derived from saint-name mentions in Chroma documents whose pdf metadata starts with 'saints'.",
    }


@app.get("/debug/saints")
def debug_saints():
    global collection, oai_client

    if collection is None or oai_client is None:
        startup()
        if collection is None:
            raise HTTPException(status_code=500, detail="Server not initialized")

    return _collect_saint_debug_info()


def _build_saint_name_index() -> List[str]:
    global saint_name_index, collection

    if saint_name_index:
        return saint_name_index
    if collection is None:
        return []

    all_mentions = []
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
            pdf_name = str((metadata or {}).get("pdf", ""))
            if not pdf_name.startswith("saints"):
                continue
            all_mentions.extend(_extract_saint_mentions(doc or ""))

        if len(docs) < page_size:
            break
        offset += len(docs)

    normalized = []
    seen = set()
    for mention in all_mentions:
        name = _normalize_suggestion_name(mention)
        if not name:
            continue
        replacement = MANUAL_SAINT_NAME_REPLACEMENTS.get(name)
        if replacement == "":
            continue
        name = replacement or name
        if name in MANUAL_SAINT_NAME_EXCLUSIONS:
            continue
        if not _is_plausible_saint_index_name(name):
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(name)

    sourced_keys = set(seen)
    for names in AMBIGUOUS_SAINT_FALLBACKS.values():
        for name in names:
            key = name.lower()
            if key not in sourced_keys:
                continue
            if key in seen:
                continue
            seen.add(key)
            normalized.append(name)

    saint_name_index = sorted(normalized, key=lambda value: value.lower())
    return saint_name_index


def _heading_variants_for_saint_name(name: str) -> Set[str]:
    variants = set()
    base = re.sub(r"^(?:st\.?|saint)\s+", "", name or "", flags=re.IGNORECASE).strip()
    if base:
        variants.add(base.upper())
        no_the = re.sub(r"\bthe\b\s+", "", base, flags=re.IGNORECASE).strip()
        if no_the:
            variants.add(no_the.upper())

        parts = base.split()
        if len(parts) > 1:
            variants.add(f"{parts[0]}, {' '.join(parts[1:])}".upper())

    for replacement_source, replacement_target in MANUAL_SAINT_NAME_REPLACEMENTS.items():
        if replacement_target and replacement_target.lower() == name.lower():
            source_base = re.sub(r"^(?:st\.?|saint)\s+", "", replacement_source, flags=re.IGNORECASE).strip()
            if source_base:
                variants.add(source_base.upper())

    return {re.sub(r"\s+", " ", item).strip() for item in variants if item.strip()}


def _saint_dedicated_entry_exists(name: str) -> bool:
    if collection is None:
        return False

    heading_variants = _heading_variants_for_saint_name(name)
    if not heading_variants:
        return False

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
            text = doc or ""
            for heading in heading_variants:
                if re.search(rf"\b{re.escape(heading)}(?:\s*,?\s*ST\.?)?\b", text):
                    return True

        if len(docs) < page_size:
            break
        offset += len(docs)

    return False


def _find_saint_source_documents(name: str, limit: int = 6) -> tuple[List[str], List[Dict[str, Any]]]:
    if collection is None:
        return [], []

    alias_keys = set()
    for alias in _saint_aliases_for_name(name):
        alias_keys.update(_saint_match_keys(alias))
    specific_alias_keys = {key for key in alias_keys if len(key.split()) >= 2}
    alias_keys = specific_alias_keys or alias_keys
    if not alias_keys:
        return [], []

    exact_scored: List[Tuple[int, str, Dict[str, Any]]] = []
    broad_scored: List[Tuple[int, str, Dict[str, Any]]] = []
    offset = 0
    page_size = 500
    while True:
        batch = collection.get(include=["documents", "metadatas"], limit=page_size, offset=offset)
        docs = batch.get("documents", []) or []
        metadatas = batch.get("metadatas", []) or []
        if not docs:
            break

        for doc, metadata in zip(docs, metadatas):
            metadata = metadata or {}
            pdf_name = str(metadata.get("pdf", "") or "")
            if not pdf_name.startswith("saints"):
                continue

            doc_key = _normalize_saint_match_key(doc or "")
            if not doc_key:
                continue

            exact_match = False
            broad_match = False
            doc_tokens = set(doc_key.split())
            for alias_key in alias_keys:
                alias_tokens = set(alias_key.split())
                if alias_key and alias_key in doc_key:
                    exact_match = True
                elif alias_tokens and alias_tokens.issubset(doc_tokens):
                    broad_match = True

            page = int(metadata.get("page", 0) or 0)
            if exact_match:
                exact_scored.append((page, doc or "", metadata))
            elif broad_match:
                broad_scored.append((page, doc or "", metadata))

        if len(docs) < page_size:
            break
        offset += len(docs)

    scored = exact_scored if exact_scored else broad_scored
    scored.sort(key=lambda item: item[0])
    docs = [doc for _, doc, _ in scored[:limit]]
    metas = [metadata for _, _, metadata in scored[:limit]]
    return docs, metas


def _extract_saint_chat_intent(question: str) -> Dict[str, str] | None:
    q = re.sub(r"\s+", " ", (question or "").strip()).rstrip("?!. ")
    if not q:
        return None

    patterns = [
        ("lookup", r"^search\s+saints?\s*:\s*(.+)$"),
        ("lookup", r"^(?:look\s+up|lookup|find)\s+(.+)$"),
        ("lookup", r"^(?:who\s+is|who\s+was|tell\s+me\s+about|about)\s+(.+)$"),
        ("list", r"^(?:list|show)\s+saints?\s+named\s+(.+)$"),
        ("list", r"^(?:give\s+me|show\s+me)\s+(?:a\s+)?list\s+of\s+(?:saints?\s+named\s+)?(.+)$"),
        ("list", r"^list\s+(?:of\s+)?(.+)$"),
    ]

    for mode, pattern in patterns:
        match = re.match(pattern, q, flags=re.IGNORECASE)
        if not match:
            continue
        candidate = re.sub(r"\s+", " ", match.group(1)).strip()
        if not candidate:
            continue
        has_marker = re.search(r"\b(?:st\.?|saint|saints|marys)\b", candidate, flags=re.IGNORECASE)
        if mode == "list" or has_marker or _find_saint_index_matches(candidate, limit=1):
            return {"mode": mode, "query": candidate}

    return None


def _saint_options_response(raw_query: str, matches: List[str], mode: str) -> Dict[str, Any]:
    last_options = matches[:12]
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
    }


def _saint_missing_response(raw_query: str) -> Dict[str, Any]:
    return {
        "answer": f"I could not find '{raw_query}' in the loaded saint dataset.",
        "sources": [],
        "entities": [],
        "options": [],
    }


def _saint_no_dedicated_entry_response(name: str, docs: List[str], metas: List[Dict[str, Any]]) -> Dict[str, Any]:
    sources = [_source_from_metadata(metadata) for metadata in metas]
    unique_sources = []
    seen = set()
    for source in sources:
        key = _source_key(source)
        if key in seen:
            continue
        seen.add(key)
        unique_sources.append(source)

    return {
        "answer": (
            f"I found {name} in the saint dataset, but the loaded saint sources do not include "
            "a dedicated biography entry for this saint. The available matches are limited mentions, "
            "so I cannot give a fuller biography from the provided saint sources."
        ),
        "sources": unique_sources[:6],
        "entities": [name],
        "options": [],
    }


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    global last_list, collection, oai_client

    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="Missing OPENAI_API_KEY env var on server")

        if collection is None or oai_client is None:
            startup()
            if collection is None or oai_client is None:
                raise HTTPException(status_code=500, detail="Server not initialized")

        question = (req.question or "").strip()
        question = _canonicalize_saint_text(question)
        if not question:
            raise HTTPException(status_code=400, detail="Question cannot be empty")

        entity = None
        clean_entities = []

        print("\n--- NEW REQUEST ---")
        print("Original question:", question)
        print("History:", req.history)

        saint_intent = _extract_saint_chat_intent(question)
        if saint_intent:
            raw_saint_query = saint_intent["query"]
            saint_matches = _find_saint_index_matches(raw_saint_query, limit=12)
            _log_saint_query(raw_saint_query, _normalize_saint_search_query(raw_saint_query), saint_matches)

            if not saint_matches:
                return _saint_missing_response(raw_saint_query)

            if saint_intent["mode"] == "list" or len(saint_matches) > 1:
                last_list = {str(i + 1): name for i, name in enumerate(saint_matches[:12])}
                return _saint_options_response(raw_saint_query, saint_matches, saint_intent["mode"])

            entity = saint_matches[0]
            exact_docs, exact_metas = _find_saint_source_documents(entity, limit=6)
            if exact_docs and not _saint_dedicated_entry_exists(entity):
                return _saint_no_dedicated_entry_response(entity, exact_docs, exact_metas)

            question = f"{entity} Orthodox saint biography life feast teachings martyr monk bishop"

        # Numbered follow-up resolution
        q_lower = question.lower()
        match = re.search(r"(?:the\s*)?(\d+)(?:st|nd|rd|th)?\s*(?:one|saint|mary|john)?", q_lower)
        if match and match.group(1) in last_list:
            entity = last_list[match.group(1)]
            question = f"{entity} Orthodox saint biography life feast teachings martyr monk bishop"

        print("Rewritten question:", question)
        print("Resolved entity:", entity)
        print("Current last_list:", last_list)

        ambiguous_query = _extract_ambiguous_saint_query(question)
        if ambiguous_query and entity is None:
            core_name = _core_name_from_query(ambiguous_query)
            if core_name in AMBIGUOUS_SAINT_FALLBACKS:
                clean_entities = _filter_sourced_saint_options(AMBIGUOUS_SAINT_FALLBACKS[core_name])
                if len(clean_entities) > 1:
                    last_list = {str(i + 1): name for i, name in enumerate(clean_entities)}
                    return {
                        "answer": (
                            f"I found multiple saints matching '{ambiguous_query}'. "
                            "Choose one option below."
                        ),
                        "sources": [],
                        "entities": [],
                        "options": clean_entities,
                    }

            suggestion_options = _find_saint_suggestions(ambiguous_query, limit=10)
            if len(suggestion_options) > 1:
                clean_entities = suggestion_options
                last_list = {str(i + 1): name for i, name in enumerate(clean_entities)}
                return {
                    "answer": (
                        f"I found multiple saints matching '{ambiguous_query}'. "
                        "Choose one option below."
                    ),
                    "sources": [],
                    "entities": [],
                    "options": clean_entities,
                }

        top_k = max(1, min(req.top_k, 12))

        # Retrieval
        retrieval_queries = [question]
        if entity:
            retrieval_queries.extend(
                f"{variant} Orthodox saint biography life feast teachings martyr monk bishop"
                for variant in _saint_query_variants(entity)
            )
            retrieval_queries.extend(_saint_query_variants(entity))

        docs, metas = _retrieve_documents(retrieval_queries, top_k=top_k, entity=entity)

        if not docs or not metas:
            return {
                "answer": "I don't know based on the provided sources.",
                "sources": [],
                "entities": []
            }

        sources = [_source_from_metadata(m) for m in metas]

        seen = set()
        unique_sources = []
        for s in sources:
            key = _source_key(s)
            if key not in seen:
                seen.add(key)
                unique_sources.append(s)

        context_blocks = []
        for d, m in zip(docs, metas):
            context_blocks.append(f"[Source: {_source_context_label(m)}]\n{d}")

        context = "\n\n".join(context_blocks)

        history_text = "\n".join(
            f"{m['role'].upper()}: {m['content']}"
            for m in req.history[-6:]
            if isinstance(m, dict) and "role" in m and "content" in m
        )

        system_prompt = """
You are an Orthodox theology assistant.

Rules:
- Answer ONLY using the provided sources.
- If the sources do not contain the answer, say:
  "I don't know based on the provided sources."
- Do not include inline citations in the answer body.
- When listing items, ALWAYS use numbered format exactly like:
  1. Name
  2. Name
  3. Name
- Do not invent facts not found in the sources.
"""

        user_prompt = f"""
CONVERSATION SO FAR:
{history_text}

SELECTED ENTITY:
{entity if entity else "None"}

NEW QUESTION:
{question}

SOURCES:
{context}
"""

        resp = oai_client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.2,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        answer = resp.choices[0].message.content or ""

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

                last_list = {str(i + 1): item for i, item in enumerate(clean_entities)}

        print("Answer generated successfully.")
        print("Extracted entities:", clean_entities)

        return {
            "answer": answer,
            "sources": unique_sources[:6],
            "entities": clean_entities,
            "options": []
        }

    except HTTPException:
        raise
    except Exception as e:
        print("ERROR IN /chat:", repr(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/saint-suggestions", response_model=SaintSuggestionResponse)
def saint_suggestions(q: str, limit: int = 8):
    global collection, oai_client

    query = (q or "").strip()
    if len(query) < 2:
        return {"suggestions": []}

    if collection is None or oai_client is None:
        startup()
        if collection is None or oai_client is None:
            raise HTTPException(status_code=500, detail="Server not initialized")

    try:
        suggestions = _find_saint_suggestions(query, limit=limit)
        _log_saint_query(query, _normalize_saint_search_query(query), suggestions)
        return {"suggestions": suggestions}
    except Exception as e:
        print("ERROR IN /saint-suggestions:", repr(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/saints", response_model=SaintsListResponse)
def saints_list(q: str = "", search: str = "", limit: int = 400, offset: int = 0):
    global collection, oai_client

    if collection is None or oai_client is None:
        startup()
        if collection is None or oai_client is None:
            raise HTTPException(status_code=500, detail="Server not initialized")

    try:
        saints = _build_saint_name_index()
        raw_query = q or search
        query = _normalize_saint_search_query(raw_query)
        if query:
            saints = _find_saint_index_matches(raw_query, limit=400)
            _log_saint_query(raw_query, query, saints)
        safe_limit = max(1, min(limit, 400))
        safe_offset = max(0, offset)
        paged_saints = saints[safe_offset:safe_offset + safe_limit]
        return {
            "saints": paged_saints,
            "total": len(saints),
            "offset": safe_offset,
            "limit": safe_limit,
        }
    except Exception as e:
        print("ERROR IN /saints:", repr(e))
        raise HTTPException(status_code=500, detail=str(e))
