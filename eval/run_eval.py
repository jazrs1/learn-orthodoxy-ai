"""Evaluation harness for the LearnOrthodoxy RAG backend.

Usage (from the repo root, backend running locally with INTERNAL_API_KEY set):

    python eval/run_eval.py                       # full run against http://127.0.0.1:8001
    python eval/run_eval.py --ids CAT-01 SNT-02   # subset
    python eval/run_eval.py --no-judge            # retrieval + refusal metrics only (no OpenAI cost)
    python eval/run_eval.py --split tune --coverage-only
                                                  # per-step check: tune split, coverage + refusal metrics,
                                                  # no faithfulness or legacy judge (phase 4)
    python eval/run_eval.py --backend https://... # another deployment
    python eval/run_eval.py --rejudge eval/results/<file>.json
                                                  # re-score the answers in an existing results file
                                                  # with the current judges (no backend calls);
                                                  # --split, --language and --coverage-only apply

Checking a change that can alter answers (RET-025): one tune run can't see a drop of a couple of
points (±3.4 pts English, ±7.2 Arabic; RET-022), so each side gets
    2 x  --split tune --coverage-only                 (restart the backend between runs)
    2 x  --split tune --language ar --coverage-only   (with the two above: 4 Arabic runs, ~$0.15 each)
and the sides are compared with eval/speed_compare.py (or phase5_compare.py), which prints the
change question by question with its noise band, e.g. "+1.2 ± 2.4 pts; within noise". Stored
baseline runs are reused while their configuration still matches production. About $1.50 per side.

Environment:
    INTERNAL_API_KEY / ORTHODOX_API_KEY  shared secret sent as X-Internal-Key (required for live runs)
    OPENAI_API_KEY                        needed for the judges
    EVAL_JUDGE_MODEL                      judge model (default: DEFAULT_JUDGE_MODEL below)

What it measures (see DECISIONS.md, EVAL-* entries):
- retrieval recall against `expected_sources`: recall@k (merged list that entered generation),
  recall_any (union of all query hits), recall_kept, recall_shown (sources returned to the user)
- refusal rate on answerable questions, correct-refusal rate on out-of-corpus questions
- COVERAGE (headline): fraction of the question's key facts present in the answer, judged
  extractively (the judge must quote the answer); refusals count as 0
- FAITHFULNESS (headline): fraction of the answer's claims supported by the passage they cite,
  plus unsupported and bad-citation rates
- the legacy holistic 1-5 judge score, kept for continuity only
- off-target answers: answered questions whose coverage is <= 0.25 (wrong entity / wrong topic)
- FORMAT (phase 4): for task-style questions with `expected_format`, whether the answer has that shape
- refusal breakdowns (phase 4): answerable refused for short (keyword) and task-style questions;
  out-of-corpus refused for easy (no subtype), near-miss (phase-3 subtypes) and task-style requests

Results are written to eval/results/<timestamp>.json and summarised on stdout. If questions carry a
`split` field (tune/holdout), every metric is also reported per split.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import statistics
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:  # optional: pick up OPENAI_API_KEY / INTERNAL_API_KEY from the repo .env
    from dotenv import load_dotenv

    load_dotenv(REPO_ROOT / ".env")
except Exception:  # pragma: no cover
    pass

import scoring  # noqa: E402
import spend  # noqa: E402

EVAL_DIR = Path(__file__).resolve().parent
V2_CHUNKS = REPO_ROOT / "build" / "corpus" / "v2" / "chunks.jsonl"
DEFAULT_LEDGER = EVAL_DIR / "results" / "spend-phase5.json"
# A first guess at one answerable question's cost (generation + coverage judge) before the run
# has measured its own; used only to decide whether the next question still fits under the ceiling.
INITIAL_QUESTION_COST = 0.03
DEFAULT_QUESTIONS = EVAL_DIR / "questions.jsonl"
DEFAULT_RESULTS_DIR = EVAL_DIR / "results"
DEFAULT_JUDGE_MODEL = "gpt-4.1"
OFF_TARGET_COVERAGE = 0.25

REFUSAL_MARKERS = (
    "could not find enough",
    "could not find a dedicated saint entry",
    "i could not find",
    "do not contain",
    "does not say",
    "no relevant",
    "لم أجد معلومات كافية",
    "لم اجد معلومات كافية",
    "لم أجد مدخلا",
    "لم أجد مدخلًا",
)
CLARIFICATION_MARKERS = (
    "i found multiple saints",
    "choose one option",
    "saint matches for",
    "اختر واحدًا",
    "وجدت أكثر من قديس",
)

CHUNK_ID_RE = re.compile(r"^(?:ar::)?(?P<pdf>.+?)::p(?P<page>\d+)::c(?P<chunk>\d+)$")

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


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------

NEAR_MISS_SUBTYPES = {"saint_not_in_books", "non_coptic_doctrine", "false_premise", "same_name_confusion"}


def load_questions(path: Path, ids: Optional[List[str]] = None, limit: Optional[int] = None, split: Optional[str] = None) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    with open(path, encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{path}:{line_no}: invalid JSON: {exc}")
            items.append(item)
    if ids:
        wanted = set(ids)
        items = [item for item in items if item["id"] in wanted]
    if split:
        items = [item for item in items if item.get("split") == split]
    if limit:
        items = items[:limit]
    return items


def expected_pages(item: Dict[str, Any]) -> Set[Tuple[str, int]]:
    pages: Set[Tuple[str, int]] = set()
    for source in item.get("expected_sources", []) or []:
        pdf = source.get("pdf")
        for page in source.get("pages", []) or []:
            pages.add((pdf, int(page)))
    return pages


def parse_chunk_id(chunk_id: str) -> Optional[Tuple[str, int]]:
    match = CHUNK_ID_RE.match(chunk_id or "")
    if not match:
        return None
    return match.group("pdf"), int(match.group("page"))


Span = Tuple[str, int, int]  # (pdf, first PDF page, last PDF page)
_V2_SPANS: Dict[str, Span] = {}


def _v2_spans() -> Dict[str, Span]:
    """v2 ids carry no page (INGEST_PLAN.md §10.1): the page range of every v2 chunk, read once
    from the local build output. Debug hits also carry it (see `remember_hit_spans`)."""
    if not _V2_SPANS and V2_CHUNKS.exists():
        with V2_CHUNKS.open(encoding="utf-8") as handle:
            for line in handle:
                meta = json.loads(line)["metadata"]
                _V2_SPANS[meta["chunk_id"]] = (meta.get("pdf") or meta.get("url"), int(meta["page_start"]), int(meta["page_end"]))
    return _V2_SPANS


def remember_hit_spans(debug: Dict[str, Any]) -> None:
    for query in debug.get("retrieval") or []:
        for hit in query.get("hits", []):
            if hit.get("page_start") is not None and hit.get("id"):
                _v2_spans().setdefault(hit["id"], (hit.get("pdf"), int(hit["page_start"]), int(hit["page_end"])))


def spans_from_ids(chunk_ids: List[str]) -> List[Span]:
    spans: List[Span] = []
    for chunk_id in chunk_ids or []:
        parsed = parse_chunk_id(chunk_id)
        if parsed:
            spans.append((parsed[0], parsed[1], parsed[1]))
        elif chunk_id in _v2_spans():
            spans.append(_v2_spans()[chunk_id])
    return spans


def pages_from_ids(chunk_ids: List[str]) -> List[Span]:  # kept for callers; now page ranges
    return spans_from_ids(chunk_ids)


def pages_from_sources(sources: List[Dict[str, Any]]) -> List[Span]:
    spans: List[Span] = []
    for source in sources or []:
        if source.get("pdf") and source.get("page") is not None:
            start = int(source["page"])
            spans.append((source["pdf"], start, int(source.get("page_end") or start)))
    return spans


def recall(expected: Set[Tuple[str, int]], found: List[Span], tolerance: int = 0) -> float:
    """Share of expected pages covered by a retrieved chunk: v1 chunks are single pages, v2 chunks
    cover page ranges (range-aware recall, INGEST_PLAN.md §10.1; identical to the old definition
    for v1)."""
    if not expected:
        return float("nan")
    hits = 0
    for pdf, page in expected:
        if any(fpdf == pdf and start - tolerance <= page <= end + tolerance for fpdf, start, end in found):
            hits += 1
    return hits / len(expected)


_ENCODING = None


def count_tokens(text: str) -> int:
    global _ENCODING
    if _ENCODING is None:
        import tiktoken

        _ENCODING = tiktoken.get_encoding("cl100k_base")
    return len(_ENCODING.encode(text or ""))


def classify_outcome(answer: str, sources: List[Dict[str, Any]], options: List[str], debug: Dict[str, Any] | None) -> str:
    """answered | refused | clarification. Prefer the backend's own verdict when present."""
    if debug and debug.get("outcome") in {"refused", "not_found"}:
        return "refused"
    if debug and debug.get("outcome") == "options":
        return "clarification"
    if debug and debug.get("outcome") == "answered":
        # Phase 4: the backend decides refusals from the answer's opening (GEN-004); a
        # partial answer that says "the sources do not say X" is an answer, not a refusal.
        return "answered"
    lowered = (answer or "").lower()
    if any(marker in lowered for marker in CLARIFICATION_MARKERS) or (options and not sources and not lowered.strip()):
        return "clarification"
    if any(marker in lowered for marker in REFUSAL_MARKERS):
        return "refused"
    if debug and debug.get("refusal"):
        return "refused"
    return "answered"


def mean(values: List[Any]) -> float:
    clean = [v for v in values if v is not None and v == v]  # drop None/NaN
    return statistics.mean(clean) if clean else float("nan")


def fmt(value: Any, pct: bool = True) -> str:
    if value is None or value != value:
        return "  n/a"
    return f"{value * 100:5.1f}%" if pct else f"{value:5.2f}"


def load_passages_from_chroma(chunk_ids: List[str]) -> List[Dict[str, Any]]:
    """Fallback for old results files that have no `passages`: read chunk text from the
    local Chroma sqlite store (read-only) in merged order, numbered 1..n."""
    db = REPO_ROOT / "chroma_db" / "chroma.sqlite3"
    if not chunk_ids or not db.exists():
        return []
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    marks = ",".join("?" for _ in chunk_ids)
    rows = con.execute(
        "select e.embedding_id, m.string_value from embeddings e join embedding_metadata m on m.id = e.id "
        f"where m.key = 'chroma:document' and e.embedding_id in ({marks})",
        chunk_ids,
    ).fetchall()
    con.close()
    text_by_id = {row[0]: row[1] for row in rows}
    passages = []
    for index, chunk_id in enumerate(chunk_ids, start=1):
        parsed = parse_chunk_id(chunk_id)
        label = f"{SOURCE_TITLES.get(parsed[0], parsed[0])}, p. {parsed[1]}" if parsed else chunk_id
        text = text_by_id.get(chunk_id, "")
        if chunk_id.startswith("ar::"):
            text = scoring._norm_display_arabic(text) if hasattr(scoring, "_norm_display_arabic") else text
        passages.append({"n": index, "id": chunk_id, "label": label, "text": text})
    return passages


# ----------------------------------------------------------------------------
# backend
# ----------------------------------------------------------------------------

def call_backend(base_url: str, api_key: str, item: Dict[str, Any], top_k: int, timeout: float,
                 retrieve_only: bool = False) -> Tuple[Dict[str, Any], float, int]:
    payload = {
        "question": item["question"],
        "history": item.get("history", []) or [],
        "top_k": top_k,
        "mode": item.get("mode", "chat"),
        "language": item.get("language", "en"),
        "debug": True,
    }
    if retrieve_only:
        payload["retrieve_only"] = True
    headers = {"Content-Type": "application/json", "X-Internal-Key": api_key, "X-Client-IP": "127.0.0.1"}
    last_error: Optional[Exception] = None
    for attempt in range(2):
        started = time.monotonic()
        try:
            response = requests.post(f"{base_url}/chat", json=payload, headers=headers, timeout=timeout)
            elapsed = time.monotonic() - started
            if response.status_code in (429, 500, 503) and attempt == 0:
                # 503 can be a transient OpenAI blip or insufficient_quota (the backend maps both to
                # "busy"); retry once, and let the caller stop the run if it persists.
                retry_after = int(response.headers.get("Retry-After", "10"))
                time.sleep(min(retry_after, 60))
                continue
            try:
                data = response.json()
            except ValueError:
                data = {"detail": response.text[:500]}
            return data, elapsed, response.status_code
        except requests.RequestException as exc:
            last_error = exc
            time.sleep(2)
    return {"detail": f"request failed: {last_error!r}"}, 0.0, 0


# ----------------------------------------------------------------------------
# scoring of one record
# ----------------------------------------------------------------------------

def score_record(
    record: Dict[str, Any], item: Dict[str, Any], client: Any, model: str, passages: List[Dict[str, Any]], coverage_only: bool = False
) -> None:
    """Attach legacy judge, coverage and faithfulness to an answerable record in place.

    coverage_only skips the legacy judge and the (expensive) faithfulness judge; used for the
    per-step tune runs in phase 4."""
    answer = record.get("answer") or ""
    outcome = record.get("outcome")
    if outcome == "answered":
        if coverage_only:
            record["judge_score"], record["judge_rationale"] = None, "skipped: coverage-only run"
        else:
            score, rationale = scoring.legacy_judge(client, model, item, answer)
            record["judge_score"], record["judge_rationale"] = score, rationale
        record["coverage"] = scoring.coverage_judge(client, model, item, answer)
        record["faithfulness"] = (
            {"error": "skipped: coverage-only run", "claims": [], "n_claims": 0}
            if coverage_only
            else scoring.faithfulness_judge(client, model, answer, passages)
        )
    else:
        record["judge_score"], record["judge_rationale"] = (None if coverage_only else 1), f"auto: {outcome}"
        total = len(item.get("key_facts") or [])
        record["coverage"] = {"score": 0.0 if total else None, "present": 0, "partial": 0, "absent": total, "total": total, "details": [], "error": ""}
        record["faithfulness"] = {"error": f"not scored: {outcome}", "claims": [], "n_claims": 0}
    cov = record["coverage"].get("score")
    record["coverage_score"] = cov
    record["off_target"] = bool(outcome == "answered" and cov is not None and cov <= OFF_TARGET_COVERAGE)
    faith = record["faithfulness"]
    rates = faith.get("rates") or {}
    record["faith_supported"] = rates.get("supported")
    record["faith_unsupported"] = rates.get("unsupported")
    record["faith_bad_citation"] = rates.get("bad_citation")
    record["faith_uncited"] = rates.get("uncited")
    record["faith_n_claims"] = faith.get("n_claims", 0)


# ----------------------------------------------------------------------------
# summary
# ----------------------------------------------------------------------------

def _metrics(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    answerable = [r for r in records if not r["should_refuse"]]
    ooc = [r for r in records if r["should_refuse"]]
    answered = [r for r in answerable if r["outcome"] == "answered"]

    def rate(rows: List[Dict[str, Any]], key: str, value: str) -> float:
        return sum(1 for r in rows if r.get(key) == value) / len(rows) if rows else float("nan")

    claims = [c for r in answered for c in (r.get("faithfulness") or {}).get("claims", [])]
    n_claims = len(claims)

    def claim_rate(status: str) -> float:
        return sum(1 for c in claims if c["status"] == status) / n_claims if n_claims else float("nan")

    short = [r for r in answerable if r.get("category") == "keyword"]
    task = [r for r in answerable if r.get("category") == "task"]
    ooc_easy = [r for r in ooc if not r.get("subtype")]
    ooc_near = [r for r in ooc if r.get("subtype") in NEAR_MISS_SUBTYPES]
    ooc_task = [r for r in ooc if r.get("subtype") == "task_style"]
    formatted = [r for r in answerable if r.get("format_ok") is not None]

    return {
        "n": len(records),
        "n_answerable": len(answerable),
        "n_out_of_corpus": len(ooc),
        "answered_rate": rate(answerable, "outcome", "answered"),
        "refusal_rate": rate(answerable, "outcome", "refused"),
        "clarification_rate": rate(answerable, "outcome", "clarification"),
        "ooc_correct_refusal_rate": rate(ooc, "outcome", "refused"),
        "ooc_false_answer_rate": rate(ooc, "outcome", "answered"),
        "refusal_rate_short": rate(short, "outcome", "refused"),
        "refusal_rate_task": rate(task, "outcome", "refused"),
        "n_short": len(short),
        "n_task": len(task),
        "ooc_refused_easy": rate(ooc_easy, "outcome", "refused"),
        "ooc_refused_near_miss": rate(ooc_near, "outcome", "refused"),
        "ooc_refused_task": rate(ooc_task, "outcome", "refused"),
        "n_ooc_easy": len(ooc_easy),
        "n_ooc_near_miss": len(ooc_near),
        "n_ooc_task": len(ooc_task),
        "format_ok_rate": (sum(1 for r in formatted if r["format_ok"]) / len(formatted)) if formatted else float("nan"),
        "n_format_checked": len(formatted),
        "recall_at_k": mean([r["recall_at_k"] for r in answerable if "recall_at_k" in r]),
        "recall_at_k_tol1": mean([r["recall_at_k_tol1"] for r in answerable if "recall_at_k_tol1" in r]),
        "recall_any": mean([r["recall_any"] for r in answerable if "recall_any" in r]),
        "recall_kept": mean([r["recall_kept"] for r in answerable if "recall_kept" in r]),
        "recall_shown": mean([r["recall_shown"] for r in answerable if "recall_shown" in r]),
        "hit_rate_at_k": mean([1.0 if r["recall_at_k"] > 0 else 0.0 for r in answerable if "recall_at_k" in r]),
        "coverage_answered": mean([r.get("coverage_score") for r in answered]),
        "coverage_all": mean([r.get("coverage_score") for r in answerable]),
        "off_target_rate": (sum(1 for r in answerable if r.get("off_target")) / len(answerable)) if answerable else float("nan"),
        "faith_supported": claim_rate("supported"),
        "faith_unsupported": claim_rate("unsupported"),
        "faith_bad_citation": claim_rate("bad_citation"),
        "faith_uncited": (sum(1 for c in claims if not c["cited"]) / n_claims) if n_claims else float("nan"),
        "faith_n_claims": n_claims,
        "faith_supported_per_answer": mean([r.get("faith_supported") for r in answered]),
        "judge_mean_answered": mean([r.get("judge_score") for r in answered]),
        "judge_mean_all": mean([r.get("judge_score") for r in answerable]),
        "judge_prev_mean_all": mean([r.get("judge_score_prev") for r in answerable]),
        "answer_chars_mean": mean([len(r.get("answer") or "") for r in answered]),
        "latency_s_mean": mean([r.get("latency_s") for r in records if r.get("latency_s")]),
        "prompt_tokens_mean": mean([r.get("prompt_tokens") for r in records if r.get("prompt_tokens")]),
        "completion_tokens_mean": mean([r.get("completion_tokens") for r in records if r.get("completion_tokens")]),
        "analysis_tokens_mean": mean([r.get("analysis_tokens") for r in records if r.get("analysis_tokens")]),
        "retrieval_ms_mean": mean([(r.get("stages_ms") or {}).get("retrieval") for r in records if (r.get("stages_ms") or {}).get("retrieval")]),
    }


def summarize(records: List[Dict[str, Any]], k: int) -> Dict[str, Any]:
    summary = {"k": k, "overall": _metrics(records), "by_category": {}, "by_split": {}}
    by_cat: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    by_split: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in records:
        by_cat[r.get("category") or "uncategorised"].append(r)
        if r.get("split"):
            by_split[r["split"]].append(r)
    for category, rows in sorted(by_cat.items()):
        summary["by_category"][category] = _metrics(rows)
    for split, rows in sorted(by_split.items()):
        summary["by_split"][split] = _metrics(rows)
        summary["by_split"][split]["by_category"] = {c: _metrics(rs) for c, rs in sorted(defaultdict(list, {c: [x for x in rows if (x.get("category") or "uncategorised") == c] for c in {x.get("category") for x in rows}}).items())}
    summary["errors"] = sum(1 for r in records if r["outcome"] == "error")
    return summary


def print_metrics(label: str, m: Dict[str, Any], k: int) -> None:
    print(f"--- {label} (n={m['n']}, answerable={m['n_answerable']}, out-of-corpus={m['n_out_of_corpus']}) ---")
    print(f"  coverage      answered-only {fmt(m['coverage_answered'])}  all-answerable {fmt(m['coverage_all'])}   off-target {fmt(m['off_target_rate'])}")
    print(f"  faithfulness  supported {fmt(m['faith_supported'])}  unsupported {fmt(m['faith_unsupported'])}  bad-citation {fmt(m['faith_bad_citation'])}  uncited {fmt(m['faith_uncited'])}  (claims {m['faith_n_claims']})")
    print(f"  outcomes      refused {fmt(m['refusal_rate'])}  clarification {fmt(m['clarification_rate'])}  | out-of-corpus refused {fmt(m['ooc_correct_refusal_rate'])}  false answer {fmt(m['ooc_false_answer_rate'])}")
    print(
        f"  refused by    short {fmt(m['refusal_rate_short'])} (n={m['n_short']})  task {fmt(m['refusal_rate_task'])} (n={m['n_task']})"
        f"  | ooc easy {fmt(m['ooc_refused_easy'])} (n={m['n_ooc_easy']})  near-miss {fmt(m['ooc_refused_near_miss'])} (n={m['n_ooc_near_miss']})"
        f"  task {fmt(m['ooc_refused_task'])} (n={m['n_ooc_task']})"
    )
    latency = f"   latency {m['latency_s_mean']:.1f}s" if m["latency_s_mean"] == m["latency_s_mean"] else ""
    print(f"  format        followed {fmt(m['format_ok_rate'])} (n={m['n_format_checked']}){latency}")
    print(f"  retrieval     recall@{k} {fmt(m['recall_at_k'])}  (+/-1 {fmt(m['recall_at_k_tol1'])})  kept {fmt(m['recall_kept'])}  shown {fmt(m['recall_shown'])}")
    prev = f"  prev-judge all {fmt(m['judge_prev_mean_all'], pct=False)}" if m.get("judge_prev_mean_all") == m.get("judge_prev_mean_all") else ""
    print(f"  legacy judge  answered-only {fmt(m['judge_mean_answered'], pct=False)}  all-answerable {fmt(m['judge_mean_all'], pct=False)}{prev}")
    print(f"  answer chars  {m['answer_chars_mean']:.0f}" if m["answer_chars_mean"] == m["answer_chars_mean"] else "")


def print_summary(summary: Dict[str, Any]) -> None:
    k = summary["k"]
    print("\n==================== SUMMARY ====================")
    print_metrics("overall", summary["overall"], k)
    for split, m in summary["by_split"].items():
        print_metrics(f"split={split}", m, k)
    print("\nby category:      n   refused  cover(all)  faith-sup  faith-unsup  bad-cit  recall@k  judge(all)")
    for category, m in summary["by_category"].items():
        print(
            f"  {category:<14} {m['n']:3d}  {fmt(m['refusal_rate'])}   {fmt(m['coverage_all'])}    {fmt(m['faith_supported'])}    "
            f"{fmt(m['faith_unsupported'])}    {fmt(m['faith_bad_citation'])}  {fmt(m['recall_at_k'])}   {fmt(m['judge_mean_all'], pct=False)}"
        )
    if summary.get("errors"):
        print(f"\nerrors: {summary['errors']}")


def write_results(results_dir: Path, payload: Dict[str, Any]) -> Path:
    results_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    payload["timestamp"] = stamp
    out_path = results_dir / f"{stamp}.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def make_judge_client() -> Any:
    try:
        from openai import OpenAI

        return OpenAI()
    except Exception as exc:
        print(f"WARNING: judge disabled ({exc!r})", file=sys.stderr)
        return None


# ----------------------------------------------------------------------------
# modes
# ----------------------------------------------------------------------------

def run_rejudge(args: argparse.Namespace) -> int:
    source = Path(args.rejudge)
    prior = json.loads(source.read_text(encoding="utf-8"))
    questions = {item["id"]: item for item in load_questions(Path(args.questions))}
    client = make_judge_client()
    if client is None:
        return 2
    records = prior["records"]
    if args.ids:
        records = [r for r in records if r["id"] in set(args.ids)]
    # The same filters as a live run, so a re-judge can cover just the tune split or one language.
    if args.split:
        records = [r for r in records if (questions.get(r["id"]) or {}).get("split") == args.split]
    if args.language:
        records = [r for r in records if r.get("language") == args.language]
    print(f"Re-scoring {len(records)} records from {source.name} with {args.judge_model}\n")
    for index, record in enumerate(records, start=1):
        record["judge_score_prev"] = record.get("judge_score")
        record["judge_rationale_prev"] = record.get("judge_rationale")
        item = questions.get(record["id"])
        if item is None:
            continue
        record["split"] = item.get("split")
        if record["should_refuse"]:
            record["judge_score"] = None
            continue
        passages = record.get("passages") or load_passages_from_chroma(record.get("merged_ids") or [])
        record["subtype"] = item.get("subtype")
        record["format_ok"] = scoring.format_check(item.get("expected_format"), record.get("answer") or "") if record["outcome"] == "answered" else None
        score_record(record, item, client, args.judge_model, passages, coverage_only=args.coverage_only)
        print(
            f"[{index:2d}/{len(records)}] {record['id']:<7} {record['outcome']:<10} prev={record['judge_score_prev']!s:<4} judge={record.get('judge_score')!s:<4} "
            f"cov={fmt(record.get('coverage_score'))} faith-sup={fmt(record.get('faith_supported'))} unsup={fmt(record.get('faith_unsupported'))}  {record['question'][:50]}"
        )
    summary = summarize(records, prior.get("k", args.k))
    payload = {
        **prior,
        "label": args.label or f"rejudge of {source.name} with {args.judge_model}",
        "judge_model": args.judge_model,
        "judge_model_prev": prior.get("judge_model"),
        "rejudged_from": source.name,
        "summary": summary,
        "records": records,
    }
    out_path = write_results(Path(args.results_dir), payload)
    print_summary(summary)
    print(f"\nresults written to {out_path}")
    return 0


def run_live(args: argparse.Namespace) -> int:
    api_key = os.getenv("INTERNAL_API_KEY") or os.getenv("ORTHODOX_API_KEY") or ""
    if not api_key:
        print("ERROR: set INTERNAL_API_KEY (or ORTHODOX_API_KEY) so the backend accepts the requests.", file=sys.stderr)
        return 2

    base_url = args.backend.rstrip("/")
    items = load_questions(Path(args.questions), args.ids, args.limit, args.split)
    if args.language:
        # One language only: e.g. the Arabic tune questions run several times (RET-025).
        items = [item for item in items if item.get("language") == args.language]
    if not items:
        print("No questions selected.", file=sys.stderr)
        return 2

    ledger = spend.SpendLedger(Path(args.spend_ledger) if args.spend_ledger else None, args.max_spend)
    raw_client = None if (args.no_judge or args.retrieve_only) else make_judge_client()
    client = spend.MeteredClient(raw_client, ledger) if raw_client is not None else None

    try:
        health = requests.get(f"{base_url}/health", timeout=10).json()
    except Exception as exc:
        print(f"ERROR: backend not reachable at {base_url}: {exc!r}", file=sys.stderr)
        return 2
    print(f"Backend {base_url}: {health}")
    judge_mode = "off" if client is None else (f"{args.judge_model} (coverage only)" if args.coverage_only else args.judge_model)
    print(f"Questions: {len(items)}   split: {args.split or 'all'}   judge: {judge_mode}   k={args.k}   "
          f"corpus: {args.corpus_label or health.get('corpus_version')}   retrieve-only: {args.retrieve_only}")
    if args.max_spend is not None:
        print(f"Spend ledger {args.spend_ledger}: ${ledger.prior:.4f} spent so far, ceiling ${args.max_spend:.2f}\n")

    records: List[Dict[str, Any]] = []
    stopped: Optional[str] = None
    costs: List[float] = []
    for index, item in enumerate(items, start=1):
        projected = (max(costs) if costs else INITIAL_QUESTION_COST) * (0.1 if args.retrieve_only else 1.0)
        try:
            ledger.check(projected)
        except spend.BudgetExceeded as exc:
            stopped = str(exc)
            print(f"STOP: {stopped}", file=sys.stderr)
            break
        before = ledger.run_usd
        data, elapsed, status = call_backend(base_url, api_key, item, args.k, args.timeout, retrieve_only=args.retrieve_only)
        if status in (401, 403, 500, 503) or status == 0:
            # Persisting after one retry: possibly insufficient_quota or an auth failure behind a
            # generic backend error. The key is shared with production, so stop and look at the log.
            stopped = f"backend returned HTTP {status} for {item['id']} after a retry: {str(data.get('detail'))[:200]}"
            print(f"STOP: {stopped}", file=sys.stderr)
            break
        answer = str(data.get("answer", "") or "")
        sources = data.get("sources") or []
        options = data.get("options") or []
        debug = data.get("debug") or {}
        error = data.get("detail") if status != 200 else None
        remember_hit_spans(debug)
        spend.record_backend_spend(ledger, debug, len(item["question"]))

        outcome = "error" if error else ("retrieve_only" if args.retrieve_only and debug.get("outcome") == "retrieve_only"
                                         else classify_outcome(answer, sources, options, debug))
        exp = expected_pages(item)
        merged_ids = debug.get("merged_ids") or []
        retrieved_ids = debug.get("retrieved_ids") or []
        kept_ids = debug.get("kept_ids") or []
        passages = debug.get("passages") or []

        record: Dict[str, Any] = {
            "id": item["id"],
            "category": item.get("category"),
            "subtype": item.get("subtype"),
            "expected_format": item.get("expected_format"),
            "split": item.get("split"),
            "language": item.get("language", "en"),
            "mode": item.get("mode", "chat"),
            "should_refuse": bool(item.get("should_refuse")),
            "verified": item.get("verified", True),
            "question": item["question"],
            "http_status": status,
            "latency_s": round(elapsed, 2),
            "outcome": outcome,
            "answer": answer,
            "answer_chars": len(answer),
            "sources": sources,
            "options": options,
            "error": error,
            "request_id": debug.get("request_id"),
            "retrieval_queries": debug.get("retrieval_queries"),
            "retrieval": debug.get("retrieval"),
            "merged_ids": merged_ids,
            "kept_ids": kept_ids,
            "passages": passages,
            "retrieved_count": len(retrieved_ids),
            "best_distance": debug.get("best_distance"),
            "prompt_tokens": debug.get("prompt_tokens"),
            "completion_tokens": debug.get("completion_tokens"),
            "stages_ms": debug.get("stages_ms"),
            "refusal_reason": debug.get("refusal_reason"),
            "task_analysis": debug.get("task_analysis"),
            "analysis_tokens": debug.get("analysis_tokens"),
            "entity_check": debug.get("entity_check"),
            "model": debug.get("model"),
            # For recall at equal context budget (INGEST_PLAN.md §10.2): each passage's size and pages,
            # in the order the model saw them.
            "passage_tokens": [count_tokens(p.get("text", "")) for p in passages],
            "passage_spans": [list(s) for s in spans_from_ids([p.get("id") for p in passages])] if passages else [],
            "context_tokens": sum(count_tokens(p.get("text", "")) for p in passages),
        }
        record["format_ok"] = scoring.format_check(item.get("expected_format"), answer) if outcome == "answered" and not item.get("should_refuse") else None

        if exp:
            record["recall_at_k"] = recall(exp, pages_from_ids(merged_ids[: args.k]))
            record["recall_at_k_tol1"] = recall(exp, pages_from_ids(merged_ids[: args.k]), tolerance=1)
            record["recall_any"] = recall(exp, pages_from_ids(retrieved_ids))
            record["recall_kept"] = recall(exp, pages_from_ids(kept_ids))
            record["recall_shown"] = recall(exp, pages_from_sources(sources))
            record["expected_pages"] = sorted(f"{pdf}:p{page}" for pdf, page in exp)

        if client is not None and not item.get("should_refuse"):
            try:
                score_record(record, item, client, args.judge_model, passages, coverage_only=args.coverage_only)
            except spend.FatalOpenAIError:
                records.append(record)
                stopped = "fatal OpenAI error in the judge (quota or auth)"
                break

        record["spend_usd"] = round(ledger.run_usd - before, 5)
        costs.append(ledger.run_usd - before)
        records.append(record)
        r_at_k = record.get("recall_at_k")
        print(
            f"[{index:2d}/{len(items)}] {item['id']:<7} {outcome:<13} "
            f"r@k={fmt(r_at_k) if r_at_k is not None else '  -   '} "
            f"cov={fmt(record.get('coverage_score')) if record.get('coverage_score') is not None else '  -   '} "
            f"sup={fmt(record.get('faith_supported')) if record.get('faith_supported') is not None else '  -   '} "
            f"unsup={fmt(record.get('faith_unsupported')) if record.get('faith_unsupported') is not None else '  -   '} "
            f"j={record.get('judge_score') if record.get('judge_score') is not None else '-'} "
            f"{elapsed:4.1f}s {item['question'][:48]}"
        )

    summary = summarize(records, args.k)
    payload = {
        "label": args.label,
        "corpus_label": args.corpus_label or health.get("corpus_version"),
        "backend": base_url,
        "backend_health": health,
        "questions_file": str(Path(args.questions)),
        "k": args.k,
        "judge_model": None if client is None else args.judge_model,
        "split_filter": args.split,
        "language_filter": args.language,
        "coverage_only": bool(args.coverage_only),
        "retrieve_only": bool(args.retrieve_only),
        "spend_usd": round(ledger.run_usd, 5),
        "spend_by_model": {k: round(v, 5) for k, v in sorted(ledger.run_by_model.items())},
        "stopped": stopped,
        "summary": summary,
        "records": records,
    }
    out_path = write_results(Path(args.results_dir), payload)
    ledger.save(f"{out_path.name} {args.label}".strip())
    print_summary(summary)
    print(f"\nspend this run ${ledger.run_usd:.4f}; ledger total ${ledger.total:.4f}")
    print(f"results written to {out_path}")
    if stopped:
        print(f"RUN STOPPED EARLY: {stopped}", file=sys.stderr)
        return 3
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--backend", default=os.getenv("EVAL_BACKEND_URL", "http://127.0.0.1:8001"))
    parser.add_argument("--questions", default=str(DEFAULT_QUESTIONS))
    parser.add_argument("--results-dir", default=str(DEFAULT_RESULTS_DIR))
    parser.add_argument("--ids", nargs="*", help="only run these question ids")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--k", type=int, default=8, help="k for recall@k (also sent as top_k)")
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--judge-model", default=os.getenv("EVAL_JUDGE_MODEL", DEFAULT_JUDGE_MODEL))
    parser.add_argument("--no-judge", action="store_true")
    parser.add_argument("--split", choices=["tune", "holdout"], help="only run questions from this split")
    parser.add_argument("--language", choices=["en", "ar"], help="only run questions in this language")
    parser.add_argument("--coverage-only", action="store_true", help="skip the faithfulness and legacy judges (coverage + refusal metrics only)")
    parser.add_argument("--rejudge", metavar="RESULTS_JSON", help="re-score an existing results file with the current judges")
    parser.add_argument("--label", default="", help="free-text label stored in the results file")
    parser.add_argument("--corpus-label", default="", help="which corpus the backend serves (v1/v2); defaults to /health")
    parser.add_argument("--retrieve-only", action="store_true", help="stop the backend after retrieval (no answer, no judge)")
    parser.add_argument("--max-spend", type=float, help="stop before a question would take the ledger total over this (USD)")
    parser.add_argument("--spend-ledger", default=str(DEFAULT_LEDGER), help="JSON file that accumulates spend across runs")
    args = parser.parse_args()
    if args.rejudge:
        return run_rejudge(args)
    return run_live(args)


if __name__ == "__main__":
    sys.exit(main())
