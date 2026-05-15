import os
import re
import unicodedata
from pathlib import Path
from typing import List, Dict, Any, Set, Tuple

from dotenv import load_dotenv
from chromadb.utils import embedding_functions
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
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
            for name_key in name_keys:
                name_tokens = set(name_key.split())
                if query_key == name_key:
                    score = 0 if query_key in _saint_match_keys(name) else 1
                elif name_key.startswith(query_key):
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
    for _, _, _, record in scored:
        key = str(record.get("id", ""))
        if key in seen:
            continue
        seen.add(key)
        matches.append(record)
        if len(matches) >= max(1, min(limit, 400)):
            break
    return matches


def _find_saint_index_matches(query: str, limit: int = 12) -> List[str]:
    return [str(record.get("name", "")) for record in _find_saint_record_matches(query, limit=limit)]


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


def _retrieve_documents(
    queries: List[str],
    top_k: int,
    entity: str | None = None,
    target_collection: Any | None = None,
    metadata_filter: Dict[str, Any] | None = None,
):
    global collection
    search_collection = target_collection or collection
    if search_collection is None:
        return [], []

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

    for query in deduped_queries[:8]:
        query_kwargs: Dict[str, Any] = {"query_texts": [query], "n_results": top_k}
        if metadata_filter:
            query_kwargs["where"] = metadata_filter
        retrieved = search_collection.query(**query_kwargs)
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
    if language == "ar":
        return "لم أجد معلومات كافية عن هذا في المصادر العربية المتاحة."
    return "I could not find enough about that in the loaded sources."


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
    return " ".join(word for word in _arabic_search_text(value).split() if word not in removable)


def _arabic_query_terms(question: str) -> List[str]:
    key = _arabic_search_text(question)
    terms: List[str] = []

    def add(value: str):
        normalized = _arabic_search_text(value)
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
    except Exception as exc:
        print("ARABIC_SAINT_TERM_EXPANSION_FAILED:", repr(exc))

    return terms


def _arabic_query_phrases(question: str) -> List[str]:
    phrases: List[str] = []

    def add(value: str):
        normalized = _arabic_search_text(value)
        if len(normalized) >= 3 and normalized not in ARABIC_LEXICAL_STOPWORDS and normalized not in phrases:
            phrases.append(normalized)

    add(question)
    add(_strip_arabic_query_titles(question))
    try:
        for saint_name in _find_arabic_saint_index_matches(question, limit=4):
            add(saint_name)
    except Exception as exc:
        print("ARABIC_SAINT_PHRASE_EXPANSION_FAILED:", repr(exc))

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
    seen: Set[Tuple[Any, ...]] = set()
    for _, _, doc, meta in scored:
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
        if len(docs) >= max(1, min(top_k, 16)):
            break

    print("ARABIC_LEXICAL_TERMS:", terms[:12])
    print("ARABIC_LEXICAL_PHRASES:", phrases[:8])
    print("ARABIC_LEXICAL_MATCH_COUNT:", len(docs))
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


def _arabic_retrieval_hints(question: str) -> List[str]:
    hints: List[str] = []
    q = question or ""

    manual_match = _matched_manual_arabic_alias(q)
    if manual_match:
        manual_names = _manual_saint_record_names(manual_match["canonical"])
        saint_name = manual_names[0] if manual_names else manual_match["canonical"]
        hints.append(f"{saint_name} Orthodox saint biography life feast teachings")

    if "الآباء الرسول" in q or "اباء رسول" in q:
        hints.append(
            "apostolic fathers early Christian writers connected to the apostles Ignatius Polycarp Clement Barnabas Hermas"
        )
    if "العذراء" in q or "مريم" in q:
        hints.append("Virgin Mary Theotokos Saint Mary Mother of God")
    if "المعمودية" in q or "معمودية" in q:
        hints.append("baptism sacrament Coptic Orthodox Church born again water Holy Spirit chrismation")
    if "الميرون" in q:
        hints.append("chrismation holy myron sacrament Coptic Orthodox Church")
    if re.search(r"(أتحول|اتحول|التحول|أصبح|اصبح|أنضم|انضم)", q) and "الأرثوذكس" in q:
        hints.append("become Orthodox convert to Coptic Orthodox Church catechumen baptism chrismation")

    return hints


def _fallback_english_retrieval_query(question: str) -> str:
    hints = _arabic_retrieval_hints(question)
    if hints:
        return " ".join(hints)
    return question


def _manual_arabic_saint_alias_prompt() -> str:
    lines = []
    for record in SAINT_ALIAS_RECORDS:
        canonical = str(record.get("canonical", "")).strip()
        aliases = [str(alias).strip() for alias in record.get("arabic_aliases", []) if str(alias).strip()]
        if canonical and aliases:
            lines.append(f"- {canonical}: {', '.join(aliases)}")
    return "\n".join(lines)


def _build_english_retrieval_query(question: str, mode: str) -> str:
    fallback = _fallback_english_retrieval_query(question)

    try:
        resp = oai_client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            max_tokens=90,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Rewrite the user's Arabic or mixed-language Orthodox Christian question "
                        "as one concise English retrieval query for searching English Coptic Orthodox source chunks. "
                        "Include important Orthodox, Coptic, saint, sacrament, and catechism terms in English. "
                        "Return only the query, with no quotes or explanation."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Mode: {mode}\nQuestion: {question}",
                },
            ],
        )
        query = (resp.choices[0].message.content or "").strip()
    except Exception as error:
        print("ENGLISH_RETRIEVAL_QUERY_REWRITE_FAILED:", repr(error))
        query = ""

    if not query:
        query = fallback

    for hint in _arabic_retrieval_hints(question):
        if hint.lower() not in query.lower():
            query = f"{query} {hint}".strip()

    query = re.sub(r"\s+", " ", query).strip()
    return query or fallback or question


def _recent_history_text(history: list, limit: int = 6) -> str:
    return "\n".join(
        f"{m['role'].upper()}: {m['content']}"
        for m in history[-limit:]
        if isinstance(m, dict) and "role" in m and "content" in m
    )


def _history_messages(history: list, role: str | None = None) -> List[str]:
    messages: List[str] = []
    for item in history:
        if not isinstance(item, dict):
            continue
        if role and item.get("role") != role:
            continue
        content = str(item.get("content", "") or "").strip()
        if content:
            messages.append(content)
    return messages


def _extract_entity_from_history(history: list) -> str | None:
    for content in reversed(_history_messages(history, role="assistant")):
        bold_match = re.search(r"\*\*([^*\n]{2,80})\*\*", content)
        if bold_match:
            candidate = _normalize_entity_label(bold_match.group(1))
            if candidate:
                return candidate

        name_match = re.search(
            r"\b(?:St\.|Saint|Abba|Anba)\s+([A-Z][A-Za-z]*(?:\s+[A-Z][A-Za-z]*){0,4})",
            content,
        )
        if name_match:
            return _normalize_entity_label(name_match.group(0))

    for content in reversed(_history_messages(history, role="user")):
        match = re.match(
            r"^(?:who\s+is|who\s+was|tell\s+me\s+about|about)\s+(.+?)\s*[?.!]*$",
            content.strip(),
            flags=re.IGNORECASE,
        )
        if not match:
            continue
        candidate = re.sub(r"\s+", " ", match.group(1)).strip()
        if not candidate:
            continue
        saint_matches = _find_saint_index_matches(candidate, limit=1)
        return saint_matches[0] if saint_matches else _canonicalize_saint_text(candidate)

    return None


def _question_has_followup_reference(question: str) -> bool:
    q = f" {question.lower()} "
    return bool(
        re.search(
            r"\b(?:he|his|him|she|her|hers|it|its|they|their|them|that|this)\b",
            q,
        )
        or re.search(r"\b(?:that|this|the same)\s+(?:saint|church|monastery|one|person|place)\b", q)
    )


def _rewrite_question_with_history(question: str, history: list) -> Tuple[str, str | None]:
    resolved_entity = _extract_entity_from_history(history)
    if not resolved_entity or not _question_has_followup_reference(question):
        return question, None

    q_lower = question.lower()
    if re.search(r"\bchurch\b", q_lower) and re.search(r"\b(?:name|named|called|dedicated)\b", q_lower):
        return (
            f"Is there a church, monastery, or place named after {resolved_entity}? "
            f"{resolved_entity} church named after {resolved_entity} monastery",
            resolved_entity,
        )

    if re.search(r"\bmonaster", q_lower):
        return f"{question} {resolved_entity} monastery {resolved_entity}", resolved_entity

    return f"{question} {resolved_entity}", resolved_entity


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


RELEVANCE_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "give",
    "how",
    "in",
    "is",
    "it",
    "list",
    "me",
    "of",
    "on",
    "or",
    "show",
    "tell",
    "that",
    "the",
    "there",
    "these",
    "this",
    "to",
    "was",
    "were",
    "what",
    "which",
    "who",
    "with",
}


def _normalized_match_text(value: str) -> str:
    text = (value or "").lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _question_keywords(question: str) -> List[str]:
    normalized = _normalized_match_text(question)
    words = [
        word
        for word in normalized.split()
        if len(word) >= 3 and word not in RELEVANCE_STOPWORDS
    ]
    seen = set()
    keywords: List[str] = []
    for word in words:
        if word in seen:
            continue
        seen.add(word)
        keywords.append(word)
    return keywords


def _relevance_terms(question: str, entity: str | None = None) -> Tuple[List[str], List[str]]:
    q_lower = question.lower()
    phrases: List[str] = []
    keywords = _question_keywords(question)

    if entity:
        phrases.append(entity)
        keywords.extend(_question_keywords(entity))

    if "apostolic father" in q_lower or "apostolic fathers" in q_lower:
        phrases.extend(
            [
                "apostolic fathers",
                "apostolic father",
                "disciples of the apostles",
                "early church fathers",
                "first generations after the apostles",
                "early christian writers",
            ]
        )
        keywords.extend(["apostolic", "ignatius", "polycarp", "clement", "barnabas", "hermas"])

    if "upper egypt" in q_lower and re.search(r"\bmonaster", q_lower):
        phrases.extend(["upper egypt", "monasteries in upper egypt", "monastery in upper egypt"])
        keywords.extend(["upper", "egypt", "monastery", "monasteries"])

    seen_phrases = set()
    clean_phrases: List[str] = []
    for phrase in phrases:
        normalized = _normalized_match_text(phrase)
        if not normalized or normalized in seen_phrases:
            continue
        seen_phrases.add(normalized)
        clean_phrases.append(normalized)

    seen_keywords = set()
    clean_keywords: List[str] = []
    for keyword in keywords:
        normalized = _normalized_match_text(keyword)
        if not normalized or normalized in seen_keywords:
            continue
        seen_keywords.add(normalized)
        clean_keywords.append(normalized)

    return clean_phrases, clean_keywords


def _is_relevant_chunk(doc: str, metadata: Dict[str, Any], question: str, entity: str | None = None) -> bool:
    text = _normalized_match_text(
        " ".join(
            [
                doc or "",
                str((metadata or {}).get("title", "") or ""),
                str((metadata or {}).get("pdf", "") or ""),
            ]
        )
    )
    if not text:
        return False

    phrases, keywords = _relevance_terms(question, entity=entity)
    if any(phrase and phrase in text for phrase in phrases):
        return True

    q_lower = question.lower()
    if "apostolic father" in q_lower or "apostolic fathers" in q_lower:
        apostolic_hits = sum(1 for term in ["ignatius", "polycarp", "clement", "barnabas", "hermas"] if term in text)
        return apostolic_hits >= 1 or ("apostolic" in text and "father" in text)

    if "upper egypt" in q_lower and re.search(r"\bmonaster", q_lower):
        return ("monaster" in text) and ("egypt" in text or "upper" in text)

    if "abu fana" in q_lower:
        return "abu fana" in text or "abu fam" in text or ("epiphanius" in text and "theodosius" in text)

    if not keywords:
        return True

    hits = sum(1 for keyword in keywords if keyword in text)
    required_hits = 1 if len(keywords) == 1 else 2
    return hits >= required_hits


def _filter_relevant_documents(
    docs: List[str],
    metas: List[Dict[str, Any]],
    question: str,
    entity: str | None = None,
) -> Tuple[List[str], List[Dict[str, Any]], int]:
    accepted_docs: List[str] = []
    accepted_metas: List[Dict[str, Any]] = []
    rejected_count = 0

    for doc, meta in zip(docs, metas):
        if _is_relevant_chunk(doc, meta, question, entity=entity):
            accepted_docs.append(doc)
            accepted_metas.append(meta)
        else:
            rejected_count += 1

    return accepted_docs, accepted_metas, rejected_count


def _log_retrieval_debug(
    original_question: str,
    rewritten_question: str,
    detected_language: str,
    english_retrieval_query: str,
    matched_saint_alias: str,
    entity: str | None,
    docs: List[str],
    metas: List[Dict[str, Any]],
    accepted_count: int,
    rejected_count: int,
) -> None:
    print("ORIGINAL_QUESTION:", original_question)
    print("DETECTED_LANGUAGE:", detected_language)
    print("ENGLISH_RETRIEVAL_QUERY:", english_retrieval_query)
    print("MATCHED_SAINT_ALIAS:", matched_saint_alias)
    print("REWRITTEN_QUESTION:", rewritten_question)
    print("RESOLVED_ENTITY:", entity)
    print("RETRIEVED_CHUNK_COUNT:", len(docs))
    top_sources = [_source_context_label(meta) for meta in metas[:3]]
    print("TOP_CHUNK_TITLES_OR_SOURCES:", top_sources)
    previews = [re.sub(r"\s+", " ", (doc or "")[:180]).strip() for doc in docs[:3]]
    print("TOP_CHUNK_PREVIEWS:", previews)
    print("RELEVANCE_ACCEPTED_COUNT:", accepted_count)
    print("RELEVANCE_REJECTED_COUNT:", rejected_count)


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


def _response_grounding_status(answer: str, docs: List[str]) -> str:
    if not docs:
        return "no-source"
    lowered = (answer or "").lower()
    if (
        "could not find" in lowered
        or "do not contain" in lowered
        or "does not say" in lowered
        or "no relevant" in lowered
    ):
        return "no-source"
    if (
        "from the loaded sources" in lowered
        or "the sources mention" in lowered
        or "do not give a full" in lowered
        or "may not be exhaustive" in lowered
        or "not exhaustive" in lowered
        or "partial" in lowered
    ):
        return "partial"
    return "full"


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
arabic_collection = None
oai_client = None
last_list = {}
saint_name_index: List[str] = []
saint_record_index: List[Dict[str, Any]] = []
arabic_saint_name_index: List[str] = []


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
    arabic_collection = get_chroma_collection(
        client=chroma_client,
        embedding_function=embed_fn,
        collection_name=ARABIC_COLLECTION_NAME,
        metadata={"source": ARABIC_COLLECTION_NAME, "language": "ar"},
    )
    print(f"CHROMA_DIR env: {get_chroma_dir_env()}")
    print(f"Collection name: {COLLECTION_NAME}")
    print(f"Arabic collection name: {ARABIC_COLLECTION_NAME}")
    print(f"Ingest start; resolved_chroma_dir: {get_resolved_chroma_dir()}")
    print(f"Collection count before ingest: {int(collection.count())}")
    print(f"Arabic collection count: {int(arabic_collection.count())}")

    oai_client = OpenAI(api_key=api_key)
    debug_info = _collect_chroma_debug_info()
    print(f"Resolved Chroma dir: {debug_info['resolved_chroma_dir']}")
    print(f"Chroma dir exists: {debug_info['directory_exists']}")
    print(f"English Chroma document count: {debug_info['english']['document_count']}")
    print(f"Arabic Chroma document count: {debug_info['arabic']['document_count']}")
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

    if collection is None or arabic_collection is None or oai_client is None:
        startup()

    return _collect_chroma_debug_info()


@app.get("/debug/chroma/en")
def debug_chroma_en():
    global collection, oai_client

    if collection is None or oai_client is None:
        startup()

    return _collect_collection_debug_info(collection, COLLECTION_NAME)


@app.get("/debug/chroma/ar")
def debug_chroma_ar():
    global arabic_collection, oai_client

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
                    "body_preview": body[:300],
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


def _build_arabic_saint_name_index() -> List[str]:
    global arabic_saint_name_index, arabic_collection

    if arabic_saint_name_index:
        return arabic_saint_name_index
    if arabic_collection is None:
        return []

    names: List[str] = []
    seen: Set[str] = set()
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
    print(f"ARABIC_SAINT_INDEX_COUNT: {len(arabic_saint_name_index)}")
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
    return 0


def _find_arabic_saint_index_matches(query: str, limit: int = 12) -> List[str]:
    query_keys = _arabic_saint_query_keys(query)
    if not query_keys:
        return []

    matches: List[Tuple[int, int, int, str]] = []
    for name in _build_arabic_saint_name_index():
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
    return [name for _, _, _, name in matches[:max(1, min(limit, 400))]]


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


@app.get("/debug/saints")
def debug_saints(q: str = ""):
    global collection, oai_client

    if collection is None or oai_client is None:
        startup()
        if collection is None:
            raise HTTPException(status_code=500, detail="Server not initialized")

    return _collect_saint_debug_info(q=q)


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
        if has_marker or _find_saint_index_matches(candidate, limit=1):
            return {"mode": mode, "query": candidate}

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
    }


def _saint_missing_response(raw_query: str, language: str = "en") -> Dict[str, Any]:
    if language == "ar":
        answer = f"لم أجد مدخلًا مخصصًا للقديس '{raw_query}' في قاعدة بيانات القديسين المتاحة. جرّب تهجئة أخرى."
    else:
        answer = f"I could not find a dedicated saint entry for '{raw_query}' in the loaded saint database. Try a different spelling."
    return {
        "answer": answer,
        "sources": [],
        "entities": [],
        "options": [],
    }


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    global last_list, collection, arabic_collection, oai_client

    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="Missing OPENAI_API_KEY env var on server")

        if collection is None or arabic_collection is None or oai_client is None:
            startup()
            if collection is None or arabic_collection is None or oai_client is None:
                raise HTTPException(status_code=500, detail="Server not initialized")

        original_question = (req.question or "").strip()
        original_question = _canonicalize_saint_text(original_question)
        if not original_question:
            raise HTTPException(status_code=400, detail="Question cannot be empty")

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
        if detected_language == "ar":
            question = original_question
            history_resolved_entity = None
        else:
            question, history_resolved_entity = _rewrite_question_with_history(original_question, req.history)
            question = _canonicalize_saint_text(question)

        english_retrieval_query = "" if detected_language == "ar" else question
        retrieval_question = original_question if detected_language == "ar" else question
        entity = manual_saint_match["record_name"] if manual_saint_match else None
        clean_entities = []

        print("\n--- NEW REQUEST ---")
        print("ORIGINAL_QUESTION:", original_question)
        print("LANGUAGE:", detected_language)
        print("MODE:", mode)
        print("ENGLISH_DOC_COUNT:", _collection_count_safe(collection))
        print("ARABIC_DOC_COUNT:", _collection_count_safe(arabic_collection))
        print("ENGLISH_RETRIEVAL_QUERY:", english_retrieval_query)
        print("MATCHED_SAINT_ALIAS:", matched_saint_alias)
        print("History-resolved entity:", history_resolved_entity)
        print("History:", req.history)

        if detected_language == "ar":
            metadata_filter = _arabic_metadata_filter_for_mode(mode)
            top_k = max(1, min(req.top_k, 12))
            retrieval_top_k = min(16, max(top_k, 10))
            retrieval_queries = [retrieval_question]

            docs, metas = _retrieve_documents(
                retrieval_queries,
                top_k=retrieval_top_k,
                target_collection=arabic_collection,
                metadata_filter=metadata_filter,
            )
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
            filtered_docs, filtered_metas, rejected_count = _filter_relevant_documents(
                docs,
                metas,
                retrieval_question,
                entity=None,
            )
            docs, metas = filtered_docs, filtered_metas

            print("COLLECTION_USED:", ARABIC_COLLECTION_NAME)
            print("METADATA_FILTER_USED:", metadata_filter)
            print("RETRIEVED_CHUNK_COUNT:", len(docs))
            print("TOP_SOURCE_TITLES:", [_source_context_label(meta) for meta in metas[:3]])
            print("TOP_CHUNK_PREVIEWS:", [_normalize_arabic_context_text(doc)[:180] for doc in docs[:3]])
            print("RELEVANCE_REJECTED_COUNT:", rejected_count)

            if not docs or not metas:
                print("Response grounding status: no-source")
                return {
                    "answer": _no_source_answer("ar"),
                    "sources": [],
                    "entities": [],
                    "options": [],
                }

            sources = [_source_from_metadata(m) for m in metas]
            seen = set()
            unique_sources = []
            for source in sources:
                key = _source_key(source)
                if key in seen:
                    continue
                seen.add(key)
                unique_sources.append(source)

            context = "\n\n".join(
                f"[Source: {_source_context_label(meta)}]\n{_normalize_arabic_context_text(doc)}"
                for doc, meta in zip(docs, metas)
            )

            system_prompt = """
أنت مساعد للتعليم الأرثوذكسي.

القواعد:
- أجب باللغة العربية فقط.
- أجب فقط من سياق المصادر العربية المرفق.
- هذه المصادر العربية هي المصدر الوحيد المسموح به في هذا الطلب.
- لا تستخدم مصادر إنجليزية ولا تترجم إجابات من مصادر إنجليزية.
- إذا لم تجد في سياق المصادر العربية معلومات كافية، قل بالضبط:
  "لم أجد معلومات كافية عن هذا في المصادر العربية المتاحة."
- لا تخترع معلومات غير موجودة في المصادر.
- لا تضف قسمًا للمصادر في نهاية الإجابة.
"""

            user_prompt = f"""
السؤال:
{original_question}

السياق من المصادر العربية:
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
            followup_options: List[str] = []
            if mode == "catechism":
                followup_options = _catechism_followup_options(answer, original_question, language="ar")

            print("Answer generated successfully.")
            print("Response grounding status:", _response_grounding_status(answer, docs))

            return {
                "answer": answer,
                "sources": unique_sources[:6],
                "entities": [],
                "options": followup_options,
            }

        saint_intent = _extract_saint_chat_intent(question)
        if saint_intent:
            raw_saint_query = saint_intent["query"]
            saint_matches = _find_saint_index_matches(raw_saint_query, limit=12)
            _log_saint_query(raw_saint_query, _normalize_saint_search_query(raw_saint_query), saint_matches)

            if not saint_matches:
                return _saint_missing_response(raw_saint_query, language=detected_language)

            if saint_intent["mode"] == "list" or len(saint_matches) > 1:
                last_list = {str(i + 1): name for i, name in enumerate(saint_matches[:12])}
                return _saint_options_response(raw_saint_query, saint_matches, saint_intent["mode"], language=detected_language)

            entity = saint_matches[0]
            question = f"{entity} Orthodox saint biography life feast teachings martyr monk bishop"
            retrieval_question = question
        elif history_resolved_entity:
            entity = history_resolved_entity

        # Numbered follow-up resolution
        q_lower = question.lower()
        match = re.search(r"(?:the\s*)?(\d+)(?:st|nd|rd|th)?\s*(?:one|saint|mary|john)?", q_lower)
        if match and match.group(1) in last_list:
            entity = last_list[match.group(1)]
            question = f"{entity} Orthodox saint biography life feast teachings martyr monk bishop"
            retrieval_question = question

        print("REWRITTEN_QUESTION:", question)
        print("RESOLVED_ENTITY:", entity)
        print("Current last_list:", last_list)

        ambiguous_query = _extract_ambiguous_saint_query(question)
        if ambiguous_query and entity is None:
            core_name = _core_name_from_query(ambiguous_query)
            if core_name in AMBIGUOUS_SAINT_FALLBACKS:
                clean_entities = _filter_sourced_saint_options(AMBIGUOUS_SAINT_FALLBACKS[core_name])
                if len(clean_entities) > 1:
                    last_list = {str(i + 1): name for i, name in enumerate(clean_entities)}
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

            suggestion_options = (
                _find_arabic_saint_index_matches(ambiguous_query, limit=10)
                if detected_language == "ar"
                else _find_saint_suggestions(ambiguous_query, limit=10)
            )
            if len(suggestion_options) > 1:
                clean_entities = suggestion_options
                last_list = {str(i + 1): name for i, name in enumerate(clean_entities)}
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
        top_k = max(1, min(req.top_k, 12))
        retrieval_top_k = min(16, max(top_k, 12 if broad_list else 10 if definition_question else top_k))

        # Retrieval
        retrieval_queries = _build_retrieval_queries(retrieval_question, entity=entity)
        docs, metas = _retrieve_documents(retrieval_queries, top_k=retrieval_top_k, entity=entity)
        print("COLLECTION_USED:", COLLECTION_NAME)
        print("METADATA_FILTER_USED:", None)
        print("Retrieval queries:", retrieval_queries)
        filtered_docs, filtered_metas, rejected_count = _filter_relevant_documents(
            docs,
            metas,
            retrieval_question,
            entity=entity,
        )

        if not docs or not metas:
            _log_retrieval_debug(
                original_question,
                question,
                detected_language,
                english_retrieval_query,
                matched_saint_alias,
                entity,
                docs,
                metas,
                0,
                0,
            )
            print("Response grounding status: no-source")
            return {
                "answer": _no_source_answer(detected_language),
                "sources": [],
                "entities": []
            }

        if not filtered_docs:
            retry_seed = english_retrieval_query if detected_language == "ar" else original_question
            retry_queries = _build_retrieval_queries(retry_seed, entity=entity)
            retry_docs, retry_metas = _retrieve_documents(retry_queries, top_k=16, entity=entity)
            retry_filtered_docs, retry_filtered_metas, retry_rejected_count = _filter_relevant_documents(
                retry_docs,
                retry_metas,
                retry_seed if not entity else retrieval_question,
                entity=entity,
            )
            if retry_filtered_docs:
                docs, metas = retry_docs, retry_metas
                filtered_docs, filtered_metas = retry_filtered_docs, retry_filtered_metas
                rejected_count = retry_rejected_count
                print("Retry retrieval queries:", retry_queries)
            else:
                docs, metas = retry_docs or docs, retry_metas or metas
                rejected_count = retry_rejected_count if retry_docs else rejected_count

        _log_retrieval_debug(
            original_question,
            question,
            detected_language,
            english_retrieval_query,
            matched_saint_alias,
            entity,
            docs,
            metas,
            len(filtered_docs),
            rejected_count,
        )

        if not filtered_docs or not filtered_metas:
            print("Response grounding status: no-source")
            return {
                "answer": _no_source_answer(detected_language),
                "sources": [],
                "entities": []
            }

        docs, metas = filtered_docs, filtered_metas

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

        history_text = _recent_history_text(req.history) if history_resolved_entity else ""
        manual_arabic_saint_aliases = _manual_arabic_saint_alias_prompt()

        language_rules = """
- Answer in English.
- If the sources contain no relevant information, say exactly:
  "I could not find enough about that in the loaded sources."
""" if detected_language == "en" else """
- Answer in Arabic.
- Use clear Modern Standard Arabic suitable for Coptic Orthodox users in Egypt.
- Use only the provided English source context.
- Do not translate or transliterate saint names unless the exact saint is listed in the manual Arabic saint aliases below.
- If a saint does not have a manual Arabic alias below, keep the canonical English saint name.
- If the sources contain no relevant information, say exactly:
  "لم أجد معلومات كافية عن هذا في المصادر المتاحة."
- If the relevant sources partially answer the question, give a cautious partial answer and use wording like:
  "بحسب المصادر المتاحة..."
"""

        system_prompt = f"""
You are an Orthodox theology assistant.

Rules:
{language_rules}
- Answer ONLY using the provided sources.
- Use conversation history to resolve pronouns and short follow-up references, but only answer from the provided source context.
- Use only context that is relevant to the user's question. If provided context is unrelated to the user question, do not answer from it.
- If the sources contain no relevant information, use the no-source wording specified above for the selected answer language.
- If the relevant sources partially answer the question, provide a cautious partial answer instead of refusing.
- Do not say "I don't know" when the context supports a partial answer.
- If the user asks for a list, extract all relevant entities found in the context. If the context may not be exhaustive, say "From the loaded sources, I found..." or "This may not be exhaustive."
- If the sources mention a related fact but not enough for a complete answer, say what the sources mention and what they do not establish.
- Do not introduce saints, people, or places that are not relevant to the user's question.
- Do not explain why an unrelated saint or entity is not part of the answer unless the user asked about that saint or entity.
- Do not include inline citations in the answer body.
- Do not add a Sources section or raw source list at the bottom.
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
{original_question if detected_language == "ar" else question}

ORIGINAL USER QUESTION:
{original_question}

ENGLISH RETRIEVAL QUERY:
{english_retrieval_query}

MATCHED MANUAL SAINT ALIAS:
{matched_saint_alias or "None"}

MANUAL ARABIC SAINT ALIASES:
{manual_arabic_saint_aliases or "None"}

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

                last_list = {str(i + 1): item for i, item in enumerate(clean_entities)}

        print("Answer generated successfully.")
        print("Extracted entities:", clean_entities)
        print("Response grounding status:", _response_grounding_status(answer, docs))

        return {
            "answer": answer,
            "sources": unique_sources[:6],
            "entities": clean_entities,
            "options": followup_options
        }

    except HTTPException:
        raise
    except Exception as e:
        print("ERROR IN /chat:", repr(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/saint-suggestions", response_model=SaintSuggestionResponse)
def saint_suggestions(q: str, limit: int = 8, language: str = "en"):
    global collection, arabic_collection, oai_client

    query = (q or "").strip()
    if len(query) < 2:
        return {"suggestions": []}

    if collection is None or arabic_collection is None or oai_client is None:
        startup()
        if collection is None or arabic_collection is None or oai_client is None:
            raise HTTPException(status_code=500, detail="Server not initialized")

    try:
        if _detect_language(language, query) == "ar":
            suggestions = _find_arabic_saint_index_matches(query, limit=limit)
            _log_saint_query(query, _normalize_arabic_alias_key(query), suggestions)
        else:
            suggestions = _find_saint_suggestions(query, limit=limit)
            _log_saint_query(query, _normalize_saint_search_query(query), suggestions)
        return {"suggestions": suggestions}
    except Exception as e:
        print("ERROR IN /saint-suggestions:", repr(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/saints", response_model=SaintsListResponse)
def saints_list(q: str = "", search: str = "", limit: int = 400, offset: int = 0, language: str = "en"):
    global collection, arabic_collection, oai_client

    if collection is None or arabic_collection is None or oai_client is None:
        startup()
        if collection is None or arabic_collection is None or oai_client is None:
            raise HTTPException(status_code=500, detail="Server not initialized")

    try:
        raw_query = q or search
        if _detect_language(language, raw_query) == "ar":
            saints = _build_arabic_saint_name_index()
            query = _normalize_arabic_alias_key(raw_query)
            if query:
                saints = _find_arabic_saint_index_matches(raw_query, limit=400)
                _log_saint_query(raw_query, query, saints)
            print(f"SAINT_QUERY_LANGUAGE: ar")
        else:
            saints = _build_saint_name_index()
            query = _normalize_saint_search_query(raw_query)
            if query:
                saints = _find_saint_index_matches(raw_query, limit=400)
                _log_saint_query(raw_query, query, saints)
            print(f"SAINT_QUERY_LANGUAGE: en")
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
