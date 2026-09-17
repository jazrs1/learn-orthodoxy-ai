"""Print a side-by-side table of eval runs.

    python eval/compare_results.py                       # all results files, oldest first
    python eval/compare_results.py 20260915-170734 20260915-171208 --names baseline step1

Rows are the summary metrics; columns are runs. Pass `--md` for a Markdown table.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

RESULTS_DIR = Path(__file__).resolve().parent / "results"

ROWS = [
    ("judge model", lambda s, d: str(d.get("judge_model") or "-")),
    ("coverage (all answerable)", lambda s, d: pct(g(s, "coverage_all"))),
    ("coverage (answered only)", lambda s, d: pct(g(s, "coverage_answered"))),
    ("faithful: supported", lambda s, d: pct(g(s, "faith_supported"))),
    ("faithful: unsupported", lambda s, d: pct(g(s, "faith_unsupported"))),
    ("faithful: bad citation", lambda s, d: pct(g(s, "faith_bad_citation"))),
    ("off-target answers", lambda s, d: pct(g(s, "off_target_rate"))),
    ("answerable refused", lambda s, d: pct(g(s, "refusal_rate"))),
    ("answerable clarification", lambda s, d: pct(g(s, "clarification_rate"))),
    ("  short refused", lambda s, d: pct(g(s, "refusal_rate_short"))),
    ("  task-style refused", lambda s, d: pct(g(s, "refusal_rate_task"))),
    ("out-of-corpus refused", lambda s, d: pct(g(s, "ooc_correct_refusal_rate"))),
    ("  easy", lambda s, d: pct(g(s, "ooc_refused_easy"))),
    ("  near-miss", lambda s, d: pct(g(s, "ooc_refused_near_miss"))),
    ("  task-style", lambda s, d: pct(g(s, "ooc_refused_task"))),
    ("format followed (task)", lambda s, d: pct(g(s, "format_ok_rate"))),
    ("recall@k", lambda s, d: pct(g(s, "recall_at_k"))),
    ("recall@k (±1 page)", lambda s, d: pct(g(s, "recall_at_k_tol1"))),
    ("recall kept", lambda s, d: pct(g(s, "recall_kept"))),
    ("recall shown", lambda s, d: pct(g(s, "recall_shown"))),
    ("legacy judge answered-only", lambda s, d: num(g(s, "judge_mean_answered"))),
    ("legacy judge all-answerable", lambda s, d: num(g(s, "judge_mean_all"))),
    ("saints refused", lambda s, d: pct(cat(s, "saints", "refusal_rate"))),
    ("saints coverage (all)", lambda s, d: pct(cat(s, "saints", "coverage_all"))),
    ("saints recall@k", lambda s, d: pct(cat(s, "saints", "recall_at_k"))),
    ("follow-up coverage (all)", lambda s, d: pct(cat(s, "follow_up", "coverage_all"))),
    ("arabic coverage (all)", lambda s, d: pct(cat(s, "arabic", "coverage_all"))),
    ("answer chars (mean)", lambda s, d: num(g(s, "answer_chars_mean"), 0)),
    ("prompt tokens (mean)", lambda s, d: num(g(s, "prompt_tokens_mean"), 0)),
    ("completion tokens (mean)", lambda s, d: num(g(s, "completion_tokens_mean"), 0)),
    ("analysis tokens (mean)", lambda s, d: num(g(s, "analysis_tokens_mean"), 0)),
    ("retrieval ms (mean)", lambda s, d: num(g(s, "retrieval_ms_mean"), 0)),
    ("latency s (mean)", lambda s, d: num(g(s, "latency_s_mean"), 1)),
]


def _overall(summary):
    # phase-2 files: summary["answerable"]/["out_of_corpus"]; phase-3 files: summary["overall"]
    if "overall" in summary:
        return summary["overall"]
    flat = dict(summary.get("answerable", {}))
    ooc = summary.get("out_of_corpus", {})
    flat["ooc_correct_refusal_rate"] = ooc.get("correct_refusal_rate")
    flat["answer_chars_mean"] = summary.get("answer_chars_mean")
    flat["prompt_tokens_mean"] = summary.get("prompt_tokens_mean")
    flat["latency_s_mean"] = summary.get("latency_s_mean")
    return flat


def g(summary, key):
    return _overall(summary).get(key)


def cat(summary, category, key):
    return (summary.get("by_category", {}).get(category) or {}).get(key)


def split_metrics(summary, split):
    return (summary.get("by_split") or {}).get(split)


def pct(value) -> str:
    return "-" if value is None or value != value else f"{value * 100:.1f}%"


def num(value, digits: int = 2) -> str:
    return "-" if value is None or value != value else f"{value:.{digits}f}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("runs", nargs="*", help="timestamps (file stems) to compare; default: all")
    parser.add_argument("--names", nargs="*", help="column labels, same order as runs")
    parser.add_argument("--md", action="store_true", help="Markdown output")
    parser.add_argument("--split", help="report only this split (tune/holdout) where the run has splits")
    args = parser.parse_args()

    stems = args.runs or [p.stem for p in sorted(RESULTS_DIR.glob("*.json"))]
    names = args.names or stems
    data = [json.loads((RESULTS_DIR / f"{stem}.json").read_text(encoding="utf-8")) for stem in stems]

    width = max(len(n) for n in names + ["metric"]) + 2
    if args.md:
        print("| metric | " + " | ".join(names) + " |")
        print("|---|" + "|".join("---" for _ in names) + "|")
    else:
        print("metric".ljust(26) + "".join(n.rjust(width) for n in names))
    for label, fn in ROWS:
        cells = [fn((split_metrics(d["summary"], args.split) and {"overall": split_metrics(d["summary"], args.split), "by_category": split_metrics(d["summary"], args.split).get("by_category", {})}) or d["summary"], d) for d in data]
        if args.md:
            print(f"| {label} | " + " | ".join(cells) + " |")
        else:
            print(label.ljust(26) + "".join(c.rjust(width) for c in cells))
    if not args.md:
        print("\nruns: " + ", ".join(f"{n}={s}" for n, s in zip(names, stems)))


if __name__ == "__main__":
    main()
