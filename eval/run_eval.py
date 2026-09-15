"""Evaluation harness for the LearnOrthodoxy RAG backend.

Usage (from the repo root, backend running locally with INTERNAL_API_KEY set):

    python eval/run_eval.py                       # full run against http://127.0.0.1:8001
    python eval/run_eval.py --ids CAT-01 SNT-02   # subset
    python eval/run_eval.py --no-judge            # retrieval + refusal metrics only (no OpenAI cost)
    python eval/run_eval.py --backend https://... # another deployment
    python eval/run_eval.py --rejudge eval/results/<file>.json
                                                  # re-score the answers in an existing results file
                                                  # with the current judge (no backend calls)

Environment:
    INTERNAL_API_KEY / ORTHODOX_API_KEY  shared secret sent as X-Internal-Key (required for live runs)
    OPENAI_API_KEY                        needed for the LLM judge
    EVAL_JUDGE_MODEL                      judge model (default: DEFAULT_JUDGE_MODEL below)

What it measures (see DECISIONS.md, EVAL-* entries):
- retrieval recall against `expected_sources` at three points in the pipeline:
    * recall@k      over the ordered chunk list that entered the relevance filter (merged_ids[:k])
    * recall_any    over every chunk any retrieval query returned (union)
    * recall_kept   over chunks that survived the relevance filter (what the model actually saw)
    * recall_shown  over the `sources` returned to the user (max 6)
- refusal rate on answerable questions, and correct-refusal rate on out-of-corpus questions
- an LLM-judged 1-5 answer score against the reference answer (answered questions only)

Results are written to eval/results/<timestamp>.json and summarised on stdout.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
try:  # optional: pick up OPENAI_API_KEY / INTERNAL_API_KEY from the repo .env
    from dotenv import load_dotenv

    load_dotenv(REPO_ROOT / ".env")
except Exception:  # pragma: no cover
    pass

EVAL_DIR = Path(__file__).resolve().parent
DEFAULT_QUESTIONS = EVAL_DIR / "questions.jsonl"
DEFAULT_RESULTS_DIR = EVAL_DIR / "results"

# The judge must be a stronger model than (and a different one from) the generator,
# so the generator is not grading its own style. See DECISIONS.md EVAL-007.
DEFAULT_JUDGE_MODEL = "gpt-4.1"

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


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------

def load_questions(path: Path, ids: Optional[List[str]] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
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


def pages_from_ids(chunk_ids: List[str]) -> Set[Tuple[str, int]]:
    pages: Set[Tuple[str, int]] = set()
    for chunk_id in chunk_ids or []:
        parsed = parse_chunk_id(chunk_id)
        if parsed:
            pages.add(parsed)
    return pages


def pages_from_sources(sources: List[Dict[str, Any]]) -> Set[Tuple[str, int]]:
    pages: Set[Tuple[str, int]] = set()
    for source in sources or []:
        if source.get("pdf") and source.get("page") is not None:
            pages.add((source["pdf"], int(source["page"])))
    return pages


def recall(expected: Set[Tuple[str, int]], found: Set[Tuple[str, int]], tolerance: int = 0) -> float:
    if not expected:
        return float("nan")
    hits = 0
    for pdf, page in expected:
        if any(fpdf == pdf and abs(fpage - page) <= tolerance for fpdf, fpage in found):
            hits += 1
    return hits / len(expected)


def classify_outcome(answer: str, sources: List[Dict[str, Any]], options: List[str], debug: Dict[str, Any] | None) -> str:
    """answered | refused | clarification. Prefer the backend's own verdict when present."""
    if debug and debug.get("outcome") in {"refused", "not_found"}:
        return "refused"
    if debug and debug.get("outcome") == "options":
        return "clarification"
    lowered = (answer or "").lower()
    if any(marker in lowered for marker in CLARIFICATION_MARKERS) or (options and not sources and not lowered.strip()):
        return "clarification"
    if any(marker in lowered for marker in REFUSAL_MARKERS):
        return "refused"
    if debug and debug.get("refusal"):
        return "refused"
    return "answered"


def mean(values: List[float]) -> float:
    clean = [v for v in values if v is not None and v == v]  # drop None/NaN
    return statistics.mean(clean) if clean else float("nan")


def fmt(value: Any, pct: bool = True) -> str:
    if value is None or value != value:
        return "  n/a"
    return f"{value * 100:5.1f}%" if pct else f"{value:5.2f}"


# ----------------------------------------------------------------------------
# backend + judge calls
# ----------------------------------------------------------------------------

def call_backend(base_url: str, api_key: str, item: Dict[str, Any], top_k: int, timeout: float) -> Tuple[Dict[str, Any], float, int]:
    payload = {
        "question": item["question"],
        "history": item.get("history", []) or [],
        "top_k": top_k,
        "mode": item.get("mode", "chat"),
        "language": item.get("language", "en"),
        "debug": True,
    }
    headers = {"Content-Type": "application/json", "X-Internal-Key": api_key, "X-Client-IP": "127.0.0.1"}
    last_error: Optional[Exception] = None
    for attempt in range(2):
        started = time.monotonic()
        try:
            response = requests.post(f"{base_url}/chat", json=payload, headers=headers, timeout=timeout)
            elapsed = time.monotonic() - started
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", "5"))
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


JUDGE_SYSTEM = """You are grading answers produced by a question-answering system over Coptic Orthodox catechism and saints' biographies.
You are given the user's question, a short REFERENCE answer written from the source pages, and the SYSTEM answer.
Score the SYSTEM answer from 1 to 5 for factual agreement with the reference and completeness:
5 = covers the key facts of the reference accurately, no contradictions; extra correct detail is fine.
4 = mostly correct and covers most key facts; minor omissions.
3 = partially correct: some key facts present, others missing or vague.
2 = largely misses the reference facts, or mixes in clear errors.
1 = wrong, irrelevant, or a refusal / non-answer.
Do not reward length. Do not penalise a different language if the meaning is right. Ignore citation markers like [1].
Respond with JSON only: {"score": <1-5>, "rationale": "<one sentence>"}"""


def judge_answer(client: Any, model: str, item: Dict[str, Any], answer: str) -> Tuple[Optional[int], str]:
    user = (
        f"QUESTION:\n{item['question']}\n\n"
        f"REFERENCE ANSWER:\n{item.get('reference_answer', '')}\n\n"
        f"SYSTEM ANSWER:\n{answer}\n"
    )
    messages = [{"role": "system", "content": JUDGE_SYSTEM}, {"role": "user", "content": user}]
    kwargs: Dict[str, Any] = {"model": model, "messages": messages, "response_format": {"type": "json_object"}}
    attempts = [dict(kwargs, temperature=0, max_tokens=200), dict(kwargs, max_completion_tokens=400)]
    last_error = ""
    for attempt_kwargs in attempts:
        try:
            response = client.chat.completions.create(**attempt_kwargs)
            data = json.loads(response.choices[0].message.content or "{}")
            score = max(1, min(5, int(data.get("score"))))
            return score, str(data.get("rationale", ""))[:300]
        except Exception as exc:  # e.g. reasoning models reject `temperature`; retry without it
            last_error = f"judge error: {exc!r}"[:300]
            if "temperature" not in str(exc) and "max_tokens" not in str(exc):
                break
    return None, last_error


# ----------------------------------------------------------------------------
# summary
# ----------------------------------------------------------------------------

def summarize(records: List[Dict[str, Any]], k: int) -> Dict[str, Any]:
    answerable = [r for r in records if not r["should_refuse"]]
    ooc = [r for r in records if r["should_refuse"]]

    def rate(rows: List[Dict[str, Any]], key: str, value: str) -> float:
        return sum(1 for r in rows if r.get(key) == value) / len(rows) if rows else float("nan")

    summary: Dict[str, Any] = {
        "n_questions": len(records),
        "n_answerable": len(answerable),
        "n_out_of_corpus": len(ooc),
        "errors": sum(1 for r in records if r["outcome"] == "error"),
        "answerable": {
            "answered_rate": rate(answerable, "outcome", "answered"),
            "refusal_rate": rate(answerable, "outcome", "refused"),
            "clarification_rate": rate(answerable, "outcome", "clarification"),
            "recall_at_k": mean([r["recall_at_k"] for r in answerable if "recall_at_k" in r]),
            "recall_at_k_tol1": mean([r["recall_at_k_tol1"] for r in answerable if "recall_at_k_tol1" in r]),
            "recall_any": mean([r["recall_any"] for r in answerable if "recall_any" in r]),
            "recall_kept": mean([r["recall_kept"] for r in answerable if "recall_kept" in r]),
            "recall_shown": mean([r["recall_shown"] for r in answerable if "recall_shown" in r]),
            "hit_rate_at_k": mean([1.0 if r["recall_at_k"] > 0 else 0.0 for r in answerable if "recall_at_k" in r]),
            "judge_mean_answered": mean([r["judge_score"] for r in answerable if r.get("judge_score") and r["outcome"] == "answered"]),
            "judge_mean_all": mean([r["judge_score"] for r in answerable if r.get("judge_score")]),
            "judge_prev_mean_answered": mean([r["judge_score_prev"] for r in answerable if r.get("judge_score_prev") and r["outcome"] == "answered"]),
            "judge_prev_mean_all": mean([r["judge_score_prev"] for r in answerable if r.get("judge_score_prev")]),
        },
        "out_of_corpus": {
            "correct_refusal_rate": rate(ooc, "outcome", "refused"),
            "false_answer_rate": rate(ooc, "outcome", "answered"),
            "clarification_rate": rate(ooc, "outcome", "clarification"),
        },
        "latency_s_mean": mean([r["latency_s"] for r in records if r.get("latency_s")]),
        "prompt_tokens_mean": mean([r["prompt_tokens"] for r in records if r.get("prompt_tokens")]),
        "by_category": {},
    }
    by_cat: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in records:
        by_cat[r["category"] or "uncategorised"].append(r)
    for category, rows in sorted(by_cat.items()):
        summary["by_category"][category] = {
            "n": len(rows),
            "answered_rate": rate(rows, "outcome", "answered"),
            "refusal_rate": rate(rows, "outcome", "refused"),
            "clarification_rate": rate(rows, "outcome", "clarification"),
            "recall_at_k": mean([r["recall_at_k"] for r in rows if "recall_at_k" in r]),
            "recall_kept": mean([r["recall_kept"] for r in rows if "recall_kept" in r]),
            "judge_mean_all": mean([r["judge_score"] for r in rows if r.get("judge_score")]),
            "judge_mean_answered": mean([r["judge_score"] for r in rows if r.get("judge_score") and r["outcome"] == "answered"]),
        }
    return summary


def print_summary(summary: Dict[str, Any], k: int) -> None:
    a = summary["answerable"]
    o = summary["out_of_corpus"]
    print("\n==================== SUMMARY ====================")
    print(f"questions: {summary['n_questions']}  answerable: {summary['n_answerable']}  out-of-corpus: {summary['n_out_of_corpus']}  errors: {summary['errors']}")
    print(f"answerable  answered {fmt(a['answered_rate'])}  refused {fmt(a['refusal_rate'])}  clarification {fmt(a['clarification_rate'])}")
    print(f"retrieval   recall@{k} {fmt(a['recall_at_k'])}  (+/-1 page {fmt(a['recall_at_k_tol1'])})  any-query {fmt(a['recall_any'])}  kept {fmt(a['recall_kept'])}  shown {fmt(a['recall_shown'])}  hit-rate {fmt(a['hit_rate_at_k'])}")
    print(f"judge (1-5) answered-only {fmt(a['judge_mean_answered'], pct=False)}  all-answerable {fmt(a['judge_mean_all'], pct=False)}")
    if a.get("judge_prev_mean_all") == a.get("judge_prev_mean_all"):  # not NaN
        print(f"prev judge  answered-only {fmt(a['judge_prev_mean_answered'], pct=False)}  all-answerable {fmt(a['judge_prev_mean_all'], pct=False)}")
    print(f"out-of-corp correct refusal {fmt(o['correct_refusal_rate'])}  false answer {fmt(o['false_answer_rate'])}  clarification {fmt(o['clarification_rate'])}")
    lat = summary["latency_s_mean"]
    tok = summary["prompt_tokens_mean"]
    print(f"latency mean {lat:.1f}s   prompt tokens mean {tok:.0f}" if lat == lat and tok == tok else "")
    print("\nby category:      n  answered  refused  clarif  recall@k   kept   judge(all) judge(ans)")
    for category, row in summary["by_category"].items():
        print(
            f"  {category:<14} {row['n']:3d}  {fmt(row['answered_rate'])}  {fmt(row['refusal_rate'])}  {fmt(row['clarification_rate'])}  "
            f"{fmt(row['recall_at_k'])}  {fmt(row['recall_kept'])}  {fmt(row['judge_mean_all'], pct=False)}   {fmt(row['judge_mean_answered'], pct=False)}"
        )


def write_results(results_dir: Path, payload: Dict[str, Any]) -> Path:
    results_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    payload["timestamp"] = stamp
    out_path = results_dir / f"{stamp}.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


# ----------------------------------------------------------------------------
# modes
# ----------------------------------------------------------------------------

def make_judge_client() -> Any:
    try:
        from openai import OpenAI

        return OpenAI()
    except Exception as exc:
        print(f"WARNING: judge disabled ({exc!r})", file=sys.stderr)
        return None


def run_rejudge(args: argparse.Namespace) -> int:
    source = Path(args.rejudge)
    prior = json.loads(source.read_text(encoding="utf-8"))
    questions = {item["id"]: item for item in load_questions(Path(args.questions))}
    judge_client = make_judge_client()
    if judge_client is None:
        return 2
    records = prior["records"]
    prev_model = prior.get("judge_model")
    print(f"Re-judging {len(records)} records from {source.name}: {prev_model} -> {args.judge_model}\n")
    for index, record in enumerate(records, start=1):
        record["judge_score_prev"] = record.get("judge_score")
        record["judge_rationale_prev"] = record.get("judge_rationale")
        item = questions.get(record["id"])
        if record["should_refuse"] or item is None:
            record["judge_score"] = None
            record["judge_rationale"] = None
        elif record["outcome"] == "answered":
            record["judge_score"], record["judge_rationale"] = judge_answer(judge_client, args.judge_model, item, record["answer"])
        else:
            record["judge_score"], record["judge_rationale"] = 1, f"auto: {record['outcome']}"
        print(f"[{index:2d}/{len(records)}] {record['id']:<7} prev={record['judge_score_prev']!s:<4} new={record['judge_score']!s:<4} {record['question'][:60]}")
    summary = summarize(records, prior.get("k", args.k))
    payload = {
        **prior,
        "label": args.label or f"rejudge of {source.name} with {args.judge_model}",
        "judge_model": args.judge_model,
        "judge_model_prev": prev_model,
        "rejudged_from": source.name,
        "summary": summary,
        "records": records,
    }
    out_path = write_results(Path(args.results_dir), payload)
    print_summary(summary, prior.get("k", args.k))
    # per-question agreement between the two judges
    pairs = [(r["judge_score_prev"], r["judge_score"]) for r in records if r.get("judge_score_prev") and r.get("judge_score") and r["outcome"] == "answered"]
    if pairs:
        same = sum(1 for a, b in pairs if a == b)
        within1 = sum(1 for a, b in pairs if abs(a - b) <= 1)
        print(f"\njudge agreement on {len(pairs)} answered questions: exact {same/len(pairs)*100:.0f}%, within 1 point {within1/len(pairs)*100:.0f}%, mean diff (new-prev) {mean([b - a for a, b in pairs]):+.2f}")
    print(f"\nresults written to {out_path}")
    return 0


def run_live(args: argparse.Namespace) -> int:
    api_key = os.getenv("INTERNAL_API_KEY") or os.getenv("ORTHODOX_API_KEY") or ""
    if not api_key:
        print("ERROR: set INTERNAL_API_KEY (or ORTHODOX_API_KEY) so the backend accepts the requests.", file=sys.stderr)
        return 2

    base_url = args.backend.rstrip("/")
    items = load_questions(Path(args.questions), args.ids, args.limit)
    if not items:
        print("No questions selected.", file=sys.stderr)
        return 2

    judge_client = None if args.no_judge else make_judge_client()

    try:
        health = requests.get(f"{base_url}/health", timeout=10).json()
    except Exception as exc:
        print(f"ERROR: backend not reachable at {base_url}: {exc!r}", file=sys.stderr)
        return 2
    print(f"Backend {base_url}: {health}")
    print(f"Questions: {len(items)}   judge: {'off' if judge_client is None else args.judge_model}   k={args.k}\n")

    records: List[Dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        data, elapsed, status = call_backend(base_url, api_key, item, args.k, args.timeout)
        answer = str(data.get("answer", "") or "")
        sources = data.get("sources") or []
        options = data.get("options") or []
        debug = data.get("debug") or {}
        error = data.get("detail") if status != 200 else None

        outcome = "error" if error else classify_outcome(answer, sources, options, debug)
        exp = expected_pages(item)
        merged_ids = debug.get("merged_ids") or []
        retrieved_ids = debug.get("retrieved_ids") or []
        kept_ids = debug.get("kept_ids") or []

        record: Dict[str, Any] = {
            "id": item["id"],
            "category": item.get("category"),
            "language": item.get("language", "en"),
            "mode": item.get("mode", "chat"),
            "should_refuse": bool(item.get("should_refuse")),
            "verified": item.get("verified", True),
            "question": item["question"],
            "http_status": status,
            "latency_s": round(elapsed, 2),
            "outcome": outcome,
            "answer": answer,
            "sources": sources,
            "options": options,
            "error": error,
            "request_id": debug.get("request_id"),
            "retrieval_queries": debug.get("retrieval_queries"),
            "retrieval": debug.get("retrieval"),
            "merged_ids": merged_ids,
            "kept_ids": kept_ids,
            "retrieved_count": len(retrieved_ids),
            "filter_rejected": debug.get("filter_rejected"),
            "best_distance": debug.get("best_distance"),
            "prompt_tokens": debug.get("prompt_tokens"),
            "completion_tokens": debug.get("completion_tokens"),
            "stages_ms": debug.get("stages_ms"),
        }

        if exp:
            record["recall_at_k"] = recall(exp, pages_from_ids(merged_ids[: args.k]))
            record["recall_at_k_tol1"] = recall(exp, pages_from_ids(merged_ids[: args.k]), tolerance=1)
            record["recall_any"] = recall(exp, pages_from_ids(retrieved_ids))
            record["recall_kept"] = recall(exp, pages_from_ids(kept_ids))
            record["recall_shown"] = recall(exp, pages_from_sources(sources))
            record["expected_pages"] = sorted(f"{pdf}:p{page}" for pdf, page in exp)

        if judge_client is not None and not item.get("should_refuse") and outcome == "answered":
            score, rationale = judge_answer(judge_client, args.judge_model, item, answer)
            record["judge_score"] = score
            record["judge_rationale"] = rationale
        elif not item.get("should_refuse") and outcome in {"refused", "clarification", "error"}:
            record["judge_score"] = 1 if judge_client is not None else None
            record["judge_rationale"] = f"auto: {outcome}"

        records.append(record)
        r_at_k = record.get("recall_at_k")
        print(
            f"[{index:2d}/{len(items)}] {item['id']:<7} {outcome:<13} "
            f"r@k={fmt(r_at_k) if r_at_k is not None else '  -   '} "
            f"kept={fmt(record.get('recall_kept')) if record.get('recall_kept') is not None else '  -   '} "
            f"judge={record.get('judge_score') if record.get('judge_score') is not None else '-'} "
            f"{elapsed:5.1f}s  {item['question'][:60]}"
        )

    summary = summarize(records, args.k)
    payload = {
        "label": args.label,
        "backend": base_url,
        "backend_health": health,
        "questions_file": str(Path(args.questions)),
        "k": args.k,
        "judge_model": None if judge_client is None else args.judge_model,
        "summary": summary,
        "records": records,
    }
    out_path = write_results(Path(args.results_dir), payload)
    print_summary(summary, args.k)
    print(f"\nresults written to {out_path}")
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
    parser.add_argument("--rejudge", metavar="RESULTS_JSON", help="re-score an existing results file with the current judge")
    parser.add_argument("--label", default="", help="free-text label stored in the results file")
    args = parser.parse_args()
    if args.rejudge:
        return run_rejudge(args)
    return run_live(args)


if __name__ == "__main__":
    sys.exit(main())
