"""Answer scoring for the eval harness: coverage, faithfulness, and the legacy 1-5 judge.

Coverage (EVAL-010): each question carries `key_facts` (extracted once from the reference
answer, stored in questions.jsonl). The judge marks every fact present / partial / absent
in the system answer and must quote the answer text that supports "present"; a quote that
is not actually in the answer downgrades the fact to partial. Score = (present + 0.5 partial) / total.

Faithfulness (EVAL-011): the system answer is split into atomic claims, each with the
[n] citations attached to it. Every claim is checked against the passages it cites:
    supported      the cited passage(s) state it
    bad_citation   the citation number does not exist, or the cited passage does not
                   support it but another passage does (wrong number)
    unsupported    no passage supports it
Uncited claims are checked against all passages and counted separately as `uncited`.

Both judges return JSON; both are extractive (they must quote), which is what makes them
harder to fool than a holistic 1-5 score (see EVAL-009).
"""

from __future__ import annotations

import json
import re
import time
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

CITATION_RE = re.compile(r"\[(\d+(?:\s*[,;]\s*\d+)*)\]")


_ARABIC_FOLD = str.maketrans({"ی": "ي", "ى": "ي", "ک": "ك", "ھ": "ه", "ة": "ه", "أ": "ا", "إ": "ا", "آ": "ا"})


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")  # maps Arabic presentation forms to base letters
    text = text.replace("ـ", "").translate(_ARABIC_FOLD)
    text = re.sub(r"[ً-ٰٟ]", "", text)
    text = re.sub(r"[\s‏‎]+", " ", text)
    text = re.sub(r"[\"'“”‘’«»]", "", text)
    return text.strip().lower()


def _retry_seconds(message: str, attempt: int) -> float:
    match = re.search(r"try again in ([0-9.]+)s", message)
    if match:
        return float(match.group(1)) + 0.5
    match = re.search(r"try again in ([0-9]+)ms", message)
    if match:
        return float(match.group(1)) / 1000.0 + 0.5
    return min(30.0, 2.0 * (attempt + 1))


def _squash(text: str) -> str:
    """Letters/digits only. Makes matching immune to pypdf's intra-word spaces ("sufferin g"),
    punctuation, citation markers like [3], and line breaks."""
    text = CITATION_RE.sub(" ", text or "")
    text = _norm(text)
    return re.sub(r"[^0-9a-z؀-ۿ]+", "", text)


MIN_FRAGMENT_CHARS = 8
MAX_TRIM_WORDS = 3


def _fragment_in_text(fragment: str, squashed_text: str) -> bool:
    q = _squash(fragment)
    if len(q) < MIN_FRAGMENT_CHARS:
        return True  # too short to be evidence on its own ("it is"); do not fail the quote on it
    if q in squashed_text:
        return True
    words = _norm(CITATION_RE.sub(" ", fragment)).split()
    if len(words) < 6:
        return False
    # Judges often splice a lead-in such as "St. Augustine says," onto the real span, or drop
    # the tail. Accept if the span survives after trimming up to MAX_TRIM_WORDS words at
    # either end, as long as at least 6 words remain.
    for head in range(0, MAX_TRIM_WORDS + 1):
        for tail in range(0, MAX_TRIM_WORDS + 1):
            if head == 0 and tail == 0:
                continue
            core = words[head : len(words) - tail if tail else len(words)]
            if len(core) < 6:
                continue
            if _squash(" ".join(core)) in squashed_text:
                return True
    return False


def quote_in_text(quote: str, text: str) -> bool:
    """Loose containment: normalised, whitespace/punctuation/citation-insensitive.
    A quote may join non-contiguous spans with "..." (each substantial span must occur),
    and a span may be trimmed by a few words at either end and still count."""
    squashed_text = _squash(text)
    fragments = [f for f in re.split(r"\.{3}|…|\[\.\.\.\]", quote or "") if _squash(f)]
    if not fragments:
        return False
    if all(len(_squash(f)) < MIN_FRAGMENT_CHARS for f in fragments):
        return False
    return all(_fragment_in_text(fragment, squashed_text) for fragment in fragments)


def _chat_json(client: Any, model: str, system: str, user: str, max_tokens: int = 1500) -> Tuple[Optional[Dict[str, Any]], str]:
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    kwargs: Dict[str, Any] = {"model": model, "messages": messages, "response_format": {"type": "json_object"}}
    variants = [dict(kwargs, temperature=0, max_tokens=max_tokens), dict(kwargs, max_completion_tokens=max_tokens * 2)]
    error = ""
    variant_index = 0
    for attempt in range(12):
        try:
            response = client.chat.completions.create(**variants[variant_index])
            return json.loads(response.choices[0].message.content or "{}"), ""
        except Exception as exc:
            text = str(exc)
            error = f"{exc!r}"[:300]
            if "temperature" in text or "max_tokens" in text:
                if variant_index == 0:
                    variant_index = 1
                    continue
                break
            if "429" in text or "rate limit" in text.lower() or "RateLimit" in type(exc).__name__:
                time.sleep(_retry_seconds(text, attempt))
                continue
            if "5" == text[:1] or "APIConnection" in type(exc).__name__ or "Timeout" in type(exc).__name__:
                time.sleep(2.0 * (attempt + 1))
                continue
            break
    return None, error


# ----------------------------------------------------------------------------
# legacy holistic judge (kept for continuity, no longer the headline number)
# ----------------------------------------------------------------------------

LEGACY_JUDGE_SYSTEM = """You are grading answers produced by a question-answering system over Coptic Orthodox catechism and saints' biographies.
You are given the user's question, a short REFERENCE answer written from the source pages, and the SYSTEM answer.
Score the SYSTEM answer from 1 to 5 for factual agreement with the reference and completeness:
5 = covers the key facts of the reference accurately, no contradictions; extra correct detail is fine.
4 = mostly correct and covers most key facts; minor omissions.
3 = partially correct: some key facts present, others missing or vague.
2 = largely misses the reference facts, or mixes in clear errors.
1 = wrong, irrelevant, or a refusal / non-answer.
Do not reward length. Do not penalise a different language if the meaning is right. Ignore citation markers like [1].
Respond with JSON only: {"score": <1-5>, "rationale": "<one sentence>"}"""


def legacy_judge(client: Any, model: str, item: Dict[str, Any], answer: str) -> Tuple[Optional[int], str]:
    user = f"QUESTION:\n{item['question']}\n\nREFERENCE ANSWER:\n{item.get('reference_answer', '')}\n\nSYSTEM ANSWER:\n{answer}\n"
    data, error = _chat_json(client, model, LEGACY_JUDGE_SYSTEM, user, max_tokens=200)
    if data is None:
        return None, f"judge error: {error}"
    try:
        return max(1, min(5, int(data.get("score")))), str(data.get("rationale", ""))[:300]
    except Exception:
        return None, "judge error: bad json"


# ----------------------------------------------------------------------------
# coverage
# ----------------------------------------------------------------------------

COVERAGE_SYSTEM = """You check whether a SYSTEM answer contains specific KEY FACTS. For every fact decide:
- "present": the answer states the fact (same meaning; wording and language may differ). You MUST copy the exact span of the answer that states it into "quote" (verbatim, 5-40 words, no paraphrase).
- "partial": the answer touches the fact but incompletely or vaguely (e.g. names the idea without the specific detail, or gives only one of two elements). Quote the closest span.
- "absent": the answer does not state it, or contradicts it. Leave "quote" empty.
Be strict: a fact is not present because a related idea is present. Do not infer facts the answer does not state. Ignore citation markers like [2].
Respond with JSON only: {"facts": [{"i": <index>, "status": "present|partial|absent", "quote": "<verbatim span or empty>"}]} with one entry per fact, in order."""


def coverage_judge(client: Any, model: str, item: Dict[str, Any], answer: str) -> Dict[str, Any]:
    facts = item.get("key_facts") or []
    if not facts:
        return {"score": None, "present": 0, "partial": 0, "absent": 0, "total": 0, "details": [], "error": "no key_facts"}
    numbered = "\n".join(f"{i}. {fact}" for i, fact in enumerate(facts, start=1))
    user = f"QUESTION:\n{item['question']}\n\nKEY FACTS:\n{numbered}\n\nSYSTEM ANSWER:\n{answer}\n"
    data, error = _chat_json(client, model, COVERAGE_SYSTEM, user, max_tokens=1200)
    if data is None:
        return {"score": None, "present": 0, "partial": 0, "absent": 0, "total": len(facts), "details": [], "error": error}
    entries = [e for e in (data.get("facts", []) or []) if isinstance(e, dict)]
    by_index: Dict[int, Dict[str, Any]] = {}
    if len(entries) == len(facts):
        # One entry per fact in order: trust position, not the model's own numbering
        # (models sometimes number from 0, which shifted every quote by one fact).
        by_index = {i: entry for i, entry in enumerate(entries, start=1)}
    else:
        indices = []
        for entry in entries:
            try:
                indices.append(int(entry.get("i")))
            except Exception:
                indices.append(None)
        offset = 1 if indices and all(i is not None for i in indices) and min(indices) == 0 else 0
        for entry, i in zip(entries, indices):
            if i is not None:
                by_index[i + offset] = entry
    details = []
    present = partial = absent = 0
    for i, fact in enumerate(facts, start=1):
        entry = by_index.get(i, {})
        status = str(entry.get("status", "absent")).lower()
        quote = str(entry.get("quote", "") or "")
        note = ""
        if status == "present":
            if not quote_in_text(quote, answer):
                status = "partial"
                note = "downgraded: quote not found in answer"
        if status not in {"present", "partial", "absent"}:
            status = "absent"
        if status == "present":
            present += 1
        elif status == "partial":
            partial += 1
        else:
            absent += 1
        details.append({"i": i, "fact": fact, "status": status, "quote": quote[:200], "note": note})
    total = len(facts)
    return {
        "score": (present + 0.5 * partial) / total,
        "present": present,
        "partial": partial,
        "absent": absent,
        "total": total,
        "details": details,
        "error": "",
    }


# ----------------------------------------------------------------------------
# faithfulness
# ----------------------------------------------------------------------------

FAITHFULNESS_SYSTEM = """You audit a SYSTEM answer against the numbered SOURCE PASSAGES it was generated from.
Step 1: split the answer into atomic factual claims (one checkable statement each; skip pure framing such as "In summary"). Keep the claim text close to the answer's wording. For each claim list the citation numbers attached to it in the answer (the [n] markers in that sentence or clause); use [] if none.
Step 2: for each claim decide:
- "supported_by_cited": at least one of its cited passages states the claim (same meaning). Give the passage number in "evidence_n" and copy a short verbatim span from that passage into "evidence".
- "supported_by_other": no cited passage states it (or it has no citation), but some other passage does. Give that passage number and span.
- "unsupported": no passage states it. Contradictions count as unsupported.
Be strict: general knowledge, plausible inference and embellishment are unsupported. Ignore the claim's own citation markers when reading passages.
Respond with JSON only: {"claims": [{"claim": "...", "citations": [n, ...], "verdict": "supported_by_cited|supported_by_other|unsupported", "evidence_n": <n or null>, "evidence": "<span or empty>"}]}"""


def faithfulness_judge(client: Any, model: str, answer: str, passages: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not passages:
        return {"error": "no passages", "claims": [], "n_claims": 0}
    valid_numbers = {int(p["n"]) for p in passages}
    context = "\n\n".join(f"[{p['n']}] {p.get('label', '')}\n{p.get('text', '')}" for p in passages)
    user = f"SOURCE PASSAGES:\n\n{context}\n\nSYSTEM ANSWER:\n{answer}\n"
    data, error = _chat_json(client, model, FAITHFULNESS_SYSTEM, user, max_tokens=2500)
    if data is None:
        return {"error": error, "claims": [], "n_claims": 0}
    claims_out: List[Dict[str, Any]] = []
    passage_text = {int(p["n"]): p.get("text", "") for p in passages}
    for entry in data.get("claims", []) or []:
        claim = str(entry.get("claim", "")).strip()
        if not claim:
            continue
        citations = []
        for c in entry.get("citations", []) or []:
            try:
                citations.append(int(c))
            except Exception:
                continue
        verdict = str(entry.get("verdict", "unsupported")).lower()
        evidence = str(entry.get("evidence", "") or "")
        evidence_n = entry.get("evidence_n")
        try:
            evidence_n = int(evidence_n) if evidence_n is not None else None
        except Exception:
            evidence_n = None
        invalid = [c for c in citations if c not in valid_numbers]
        note = ""
        if verdict.startswith("supported"):
            # The evidence span must really occur in a passage. If the judge named the wrong
            # passage number but the span exists elsewhere, re-attribute it; if it exists
            # nowhere, the judge invented the evidence and the claim is unsupported.
            evidence_ok = evidence_n in passage_text and quote_in_text(evidence, passage_text[evidence_n])
            if not evidence_ok:
                holders = [n for n, text in passage_text.items() if quote_in_text(evidence, text)]
                if holders:
                    evidence_n = holders[0] if not any(h in citations for h in holders) else next(h for h in holders if h in citations)
                    note = "evidence re-attributed to passage %d" % evidence_n
                else:
                    verdict = "unsupported"
                    note = "downgraded: evidence span not found in any passage"
        if verdict.startswith("supported"):
            verdict = "supported_by_cited" if (citations and evidence_n in citations) else ("supported_by_other" if citations else verdict)
        if invalid:
            status = "bad_citation"
        elif not citations:
            status = "supported" if verdict.startswith("supported") else "unsupported"
        elif verdict == "supported_by_cited":
            status = "supported"
        elif verdict == "supported_by_other":
            status = "bad_citation"
        else:
            status = "unsupported"
        claims_out.append(
            {
                "claim": claim[:300],
                "citations": citations,
                "invalid_citations": invalid,
                "cited": bool(citations),
                "verdict": verdict,
                "status": status,
                "evidence_n": evidence_n,
                "evidence": evidence[:200],
                "note": note,
            }
        )
    n = len(claims_out)
    counts = {
        "supported": sum(1 for c in claims_out if c["status"] == "supported"),
        "unsupported": sum(1 for c in claims_out if c["status"] == "unsupported"),
        "bad_citation": sum(1 for c in claims_out if c["status"] == "bad_citation"),
        "uncited": sum(1 for c in claims_out if not c["cited"]),
    }
    rates = {k: (v / n if n else None) for k, v in counts.items()}
    return {"error": "", "claims": claims_out, "n_claims": n, "counts": counts, "rates": rates}
