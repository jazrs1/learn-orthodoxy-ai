import os
import re
from typing import List, Dict, Any

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


def _canonicalize_saint_text(value: str) -> str:
    return (
        (value or "")
        .strip()
        .replace("Kyrillos", "Cyril")
        .replace("kyrillos", "cyril")
        .replace("Cyrillus", "Cyril")
        .replace("cyrillus", "cyril")
    )


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
    return re.sub(
        SAINT_QUERY_PREFIX_PATTERN,
        "",
        _canonicalize_saint_text(query),
        flags=re.IGNORECASE,
    ).lower()


def _find_saint_suggestions(query: str, limit: int = 12) -> List[str]:
    global collection
    query = _canonicalize_saint_text(query)
    saint_index = _build_saint_name_index()
    normalized_query = _normalize_saint_search_query(query)

    index_matches = []
    if normalized_query:
        for name in saint_index:
            normalized_name = _normalize_saint_search_query(name)
            if normalized_query in normalized_name:
                index_matches.append(name)
        index_matches.sort(key=lambda name: (not _normalize_saint_search_query(name).startswith(normalized_query), len(name), name.lower()))
        if len(index_matches) >= 2:
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
    filtered = [name for name in unique if q_no_prefix in name.lower()]
    filtered.sort(key=lambda name: (not name.lower().startswith(f"st. {q_no_prefix}"), len(name), name.lower()))

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
        "routes": ["/", "/health", "/debug/chroma", "/chat", "/saints", "/saint-suggestions"],
    }


@app.get("/debug/chroma")
def debug_chroma():
    global collection, oai_client

    if collection is None or oai_client is None:
        startup()

    return _collect_chroma_debug_info()


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

    for names in AMBIGUOUS_SAINT_FALLBACKS.values():
        for name in names:
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            normalized.append(name)

    saint_name_index = sorted(normalized, key=lambda value: value.lower())
    return saint_name_index


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

        # Direct saint search
        if question.lower().startswith("search saint:"):
            saint_name = question[len("search saint:"):].strip()
            if saint_name:
                saint_name = _canonicalize_saint_text(saint_name)
                entity = saint_name
                question = f"{saint_name} Orthodox saint biography life feast teachings martyr monk bishop"

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
                clean_entities = AMBIGUOUS_SAINT_FALLBACKS[core_name][:]
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
        return {"suggestions": _find_saint_suggestions(query, limit=limit)}
    except Exception as e:
        print("ERROR IN /saint-suggestions:", repr(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/saints", response_model=SaintsListResponse)
def saints_list(q: str = "", limit: int = 400, offset: int = 0):
    global collection, oai_client

    if collection is None or oai_client is None:
        startup()
        if collection is None or oai_client is None:
            raise HTTPException(status_code=500, detail="Server not initialized")

    try:
        saints = _build_saint_name_index()
        query = _normalize_saint_search_query(q)
        if query:
            saints = [
                name for name in saints
                if query in _normalize_saint_search_query(name)
            ]
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
