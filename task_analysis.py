"""Separate what the user wants to know from how they want it presented (DECISIONS.md RET-006).

One cheap chat call turns the user's message (plus recent history, when there is any) into:

    retrieval_query    a standalone search query: formatting instructions removed, pronouns in
                       follow-ups resolved, bare keywords expanded into a short question
    output_format      prose | table | list | comparison | summary | study_guide | other
    broad              whether the answer needs many separate entries or passages
    sub_queries        for broad requests, 2-4 narrower search queries (used by RET-007)
    saint_name_filter  {"starts_with": ...} or {"contains": ...} for "saints whose names ..." (RET-007)
    named_subjects     specific saints/doctrines/councils/terms the user asks about (GEN-006)
    in_scope           false only for requests clearly outside Christian faith and life (GEN-006)

The retrieval query is what gets embedded; the model still sees the user's original words,
so "make a table" reaches the answer prompt but no longer drags the embedding away from the
topic. Any failure (timeout, bad JSON, empty query) falls back to the raw question with
format "prose", and the error is recorded so it shows up in the request log.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

OUTPUT_FORMATS = ("prose", "table", "list", "comparison", "summary", "study_guide", "other")
MAX_QUERY_CHARS = 400
MAX_SUB_QUERIES = 4
MAX_SUBJECTS = 6
HISTORY_TURNS = 4
HISTORY_TURN_CHARS = 600

ANALYSIS_SYSTEM_PROMPT = """You prepare a user's message for a search over two Coptic Orthodox books: the Catechism of the Coptic Orthodox Church and the Encyclopedia of the Saints and Fathers of the Church. You never answer the question. Return JSON only, with exactly these keys:

"retrieval_query": one standalone search query stating WHAT the user wants to know, in the same language as the user's message.
  - Remove every instruction about presentation or task: table, chart, list, bullet points, summarize, compare, study guide, quiz, "make", "create", "give me", "in N words", and similar. Phrase what remains as a question or a topic, not a command (not "List ...", "Make ...").
  - If the message is a follow-up, replace pronouns and vague references ("he", "it", "that saint", "the second one") with the names or topics they refer to in the conversation.
  - If the message is a bare keyword or fragment ("fasting", "St Bishoy"), turn it into a short natural question ("What does the Church teach about fasting?", "Who was St. Bishoy?").
  - Keep names, titles and spellings as the user wrote them. Do not add facts, dates or answers.
"output_format": the presentation the user asked for, one of "prose", "table", "list", "comparison", "summary", "study_guide", "other". Use "prose" when none was requested. A quiz or set of review questions is "study_guide".
"broad": true if a good answer needs many separate entries or passages (listing saints by some criterion, all the fasts, differences between two churches, a study guide on a whole topic); false for a question about one person, term or teaching.
"sub_queries": if broad is true, 2 to 4 short search queries that together cover the request, each about one aspect the user actually named or implied; do not introduce new topics. When the request compares the Coptic Church with another church or tradition, make one sub-query just that church's name as a book would write it (e.g. "Roman Catholic Church"). Otherwise [].
"saint_name_filter": only when the user wants SEVERAL saints chosen by their name, with exactly one key: {"contains": "<name>"} for saints named or called a name ("all the saints named Gregory" -> {"contains": "Gregory"}; "القديسون الذين يحملون اسم جرجس" -> {"contains": "جرجس"}; never the name's first letter), or {"starts_with": "<letters>"} only when the user asks for names that start or begin with some letters ("saints whose names start with G" -> {"starts_with": "G"}). null for a question about one saint, and null otherwise.
"named_subjects": the specific saints, people, doctrines, councils, feasts, rites, objects or technical terms the message asks about, written as the user wrote them. Always fill this when the message names such a thing, including doctrines of other churches and things outside religion. Examples: "Who was St. Anthony of Padua?" -> ["St. Anthony of Padua"]; "the Catholic doctrine of papal infallibility" -> ["papal infallibility"]; "the Protestant principle of sola scriptura" -> ["sola scriptura"]; "a table of Catholic teachings on purgatory" -> ["purgatory"]; "why did the Coptic Church reject the filioque" -> ["filioque"]; "teaching on cryptocurrency" -> ["cryptocurrency"]; "the Council of Nicaea" -> ["Council of Nicaea"]. Leave out presentation words, broad categories ("saints", "differences", "teachings", "fasts"), and the churches or traditions themselves ("Catholic Church", "Protestants", "Coptic Orthodox Church"): "differences between Catholicism and the Coptic Church" -> []; "saints whose names start with G" -> []. Use [] if there are none.
"in_scope": false only if the message is clearly not about Christianity: not about God, Scripture, the Church (any Christian church), prayer, worship, sacraments, saints, Church Fathers, Church history, Christian life and ethics, or anything the Coptic catechism itself discusses (calendars and feasts, church buildings and icons, hymns and music, the history of Egypt and the Copts). Examples of false: sports results, geography, recipes, technology, novels, another religion's own teachings. Otherwise true; when unsure, true."""


@dataclass
class TaskAnalysis:
    retrieval_query: str
    output_format: str = "prose"
    broad: bool = False
    sub_queries: List[str] = field(default_factory=list)
    saint_name_filter: Optional[Dict[str, str]] = None
    named_subjects: List[str] = field(default_factory=list)
    in_scope: bool = True
    ok: bool = False
    used_history: bool = False
    error: Optional[str] = None
    model: Optional[str] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None

    def log_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["retrieval_query"] = self.retrieval_query[:MAX_QUERY_CHARS]
        return data


# "saints named Gregory", "saints called George", "القديسين الذين يحملون اسم جرجس", "القديسين باسم مينا"
NAMED_CUE = re.compile(
    r"\b(?:named|called)\s+(?:st\.?\s+|saint\s+|abba\s+|anba\s+)?([A-Za-z][\w'’-]+)"
    r"|(?:يحملون\s+اسم|يحمل\s+اسم|اسمهم|باسم|المسم[ىيو]ن?|الذين\s+يدعون|ي[ُ]?دعون)\s+([ء-ي]+)",
    re.IGNORECASE,
)
# "names that start with G", "whose names begin with Ab", "تبدأ أسماؤهم بحرف ج"
STARTS_WITH_CUE = re.compile(r"\b(?:start|starts|starting|begin|begins|beginning)\s+with\b|تبدأ|يبدأ|بحرف", re.IGNORECASE)
STARTS_WITH_VALUE = re.compile(
    r"\b(?:start|starts|starting|begin|begins|beginning)\s+with\s+(?:the\s+letter\s+|letters?\s+)?[\"'“‘]?([A-Za-z]{1,4})\b"
    r"|(?:تبدأ|يبدأ)\s+(?:أسماؤهم\s+|اسمه\s+|أسماؤهن\s+)?(?:بحرف\s+|بالحرف\s+|ب)[\"'“«]?\s*([ء-ي]{1,3})(?![ء-ي])",
    re.IGNORECASE,
)


def name_filter_from_question(question: str) -> Optional[Dict[str, str]]:
    """A saint-list filter read straight from the user's words, when they are unambiguous."""
    starts = STARTS_WITH_VALUE.search(question or "")
    if starts:
        return {"starts_with": (starts.group(1) or starts.group(2)).strip()}
    named = NAMED_CUE.search(question or "")
    if named and re.search(r"(?i)\bsaints\b|\blist\b|القديسين|القديسون|القديسات|اذكر|قائمة", question or ""):
        return {"contains": (named.group(1) or named.group(2)).strip()}
    return None


def _clean_text(value: Any, limit: int) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _history_block(history: List[Dict[str, str]]) -> str:
    lines = []
    for turn in history[-HISTORY_TURNS:]:
        content = _clean_text(turn.get("content"), HISTORY_TURN_CHARS)
        if content:
            lines.append(f"{turn.get('role', 'user')}: {content}")
    return "\n".join(lines)


def _parse(data: Dict[str, Any], question: str) -> TaskAnalysis:
    query = _clean_text(data.get("retrieval_query"), MAX_QUERY_CHARS)
    if not query:
        raise ValueError("empty retrieval_query")
    output_format = str(data.get("output_format") or "prose").strip().lower().replace(" ", "_")
    if output_format not in OUTPUT_FORMATS:
        output_format = "other"
    broad = data.get("broad") is True
    sub_queries = [
        _clean_text(item, MAX_QUERY_CHARS) for item in (data.get("sub_queries") or []) if _clean_text(item, MAX_QUERY_CHARS)
    ][:MAX_SUB_QUERIES] if broad and isinstance(data.get("sub_queries"), list) else []
    name_filter = None
    raw_filter = data.get("saint_name_filter")
    if isinstance(raw_filter, dict):
        # "contains" first: given both keys for "saints named Gregory", the model's "starts_with": "G"
        # listed every G saint and, with a 30-entry cap, missed the Gregorys (ING-007).
        order = ("starts_with", "contains") if STARTS_WITH_CUE.search(question) else ("contains", "starts_with")
        for key in order:
            value = _clean_text(raw_filter.get(key), 40)
            if value:
                name_filter = {key: value}
                break
    explicit = name_filter_from_question(question)
    if explicit:
        name_filter = explicit  # the user's own words beat the model's reading
    subjects = []
    if isinstance(data.get("named_subjects"), list):
        subjects = [_clean_text(item, 80) for item in data["named_subjects"] if _clean_text(item, 80)][:MAX_SUBJECTS]
    return TaskAnalysis(
        retrieval_query=query,
        output_format=output_format,
        broad=broad,
        sub_queries=sub_queries,
        saint_name_filter=name_filter,
        named_subjects=subjects,
        in_scope=data.get("in_scope") is not False,
        ok=True,
    )


def analyze_request(
    client: Any,
    question: str,
    history: List[Dict[str, str]],
    model: str,
    timeout_seconds: float = 8.0,
) -> TaskAnalysis:
    """Run the analysis call. Never raises: on any failure the raw question is returned."""
    used_history = bool(history)
    parts = []
    if used_history:
        # Only follow-ups need the conversation; a first message is analysed on its own.
        parts.append(f"CONVERSATION SO FAR\n{_history_block(history)}")
    parts.append(f"USER MESSAGE\n{question}")
    try:
        response = client.with_options(timeout=timeout_seconds, max_retries=0).chat.completions.create(
            model=model,
            temperature=0,
            max_tokens=350,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
                {"role": "user", "content": "\n\n".join(parts)},
            ],
        )
        analysis = _parse(json.loads(response.choices[0].message.content or "{}"), question)
        usage = getattr(response, "usage", None)
        analysis.prompt_tokens = getattr(usage, "prompt_tokens", None)
        analysis.completion_tokens = getattr(usage, "completion_tokens", None)
    except Exception as exc:  # timeout, API error, bad JSON, empty query
        analysis = TaskAnalysis(retrieval_query=question, error=f"{type(exc).__name__}: {exc}"[:200])
    analysis.used_history = used_history
    analysis.model = model
    return analysis


def default_model() -> str:
    return os.getenv("TASK_ANALYSIS_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
