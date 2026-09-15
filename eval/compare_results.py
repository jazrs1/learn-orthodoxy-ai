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
    ("answerable refused", lambda s, d: pct(s["answerable"]["refusal_rate"])),
    ("answerable clarification", lambda s, d: pct(s["answerable"]["clarification_rate"])),
    ("out-of-corpus refused", lambda s, d: pct(s["out_of_corpus"]["correct_refusal_rate"])),
    ("recall@k", lambda s, d: pct(s["answerable"]["recall_at_k"])),
    ("recall@k (±1 page)", lambda s, d: pct(s["answerable"]["recall_at_k_tol1"])),
    ("recall kept", lambda s, d: pct(s["answerable"]["recall_kept"])),
    ("recall shown", lambda s, d: pct(s["answerable"]["recall_shown"])),
    ("judge answered-only", lambda s, d: num(s["answerable"]["judge_mean_answered"])),
    ("judge all-answerable", lambda s, d: num(s["answerable"]["judge_mean_all"])),
    ("saints refused", lambda s, d: pct(s["by_category"].get("saints", {}).get("refusal_rate"))),
    ("saints recall@k", lambda s, d: pct(s["by_category"].get("saints", {}).get("recall_at_k"))),
    ("saints judge (all)", lambda s, d: num(s["by_category"].get("saints", {}).get("judge_mean_all"))),
    ("follow-up judge (all)", lambda s, d: num(s["by_category"].get("follow_up", {}).get("judge_mean_all"))),
    ("arabic judge (all)", lambda s, d: num(s["by_category"].get("arabic", {}).get("judge_mean_all"))),
    ("prompt tokens (mean)", lambda s, d: num(s.get("prompt_tokens_mean"), 0)),
    ("latency s (mean)", lambda s, d: num(s.get("latency_s_mean"), 1)),
]


def pct(value) -> str:
    return "-" if value is None or value != value else f"{value * 100:.1f}%"


def num(value, digits: int = 2) -> str:
    return "-" if value is None or value != value else f"{value:.{digits}f}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("runs", nargs="*", help="timestamps (file stems) to compare; default: all")
    parser.add_argument("--names", nargs="*", help="column labels, same order as runs")
    parser.add_argument("--md", action="store_true", help="Markdown output")
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
        cells = [fn(d["summary"], d) for d in data]
        if args.md:
            print(f"| {label} | " + " | ".join(cells) + " |")
        else:
            print(label.ljust(26) + "".join(c.rjust(width) for c in cells))
    if not args.md:
        print("\nruns: " + ", ".join(f"{n}={s}" for n, s in zip(names, stems)))


if __name__ == "__main__":
    main()
