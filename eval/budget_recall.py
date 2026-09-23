"""Recall at equal context budget (INGEST_PLAN.md §10.2).

    python eval/budget_recall.py eval/results/<v1 file>.json eval/results/<v2 file>.json [more v2 files]

A bigger chunk scores more easily on range-aware recall, so each corpus is also scored with the
passages it would fit into the *v1* context budget: for every question category, the budget is the
mean context tokens v1 used on that category (from the first file), and a corpus's passages count
in the order the model saw them until their running total reaches the budget. Works on live results
files and on retrieval_sweep.py files (both carry `passage_tokens` and `passage_spans`).
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path


def expected(record):
    out = set()
    for key in record.get("expected_pages") or []:
        pdf, page = key.rsplit(":p", 1)
        out.add((pdf, int(page)))
    return out


def recall(exp, spans):
    if not exp:
        return None
    return sum(1 for pdf, page in exp if any(s[0] == pdf and s[1] <= page <= s[2] for s in spans)) / len(exp)


def within_budget(record, budget):
    spans, used = [], 0
    for tokens, span in zip(record.get("passage_tokens") or [], record.get("passage_spans") or []):
        if used >= budget:
            break
        spans.append(span)
        used += tokens
    return spans


def answerable(records):
    return [r for r in records if not r.get("should_refuse") and expected(r) and r.get("passage_tokens")]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("baseline", help="the v1 results or sweep file that sets the budgets")
    parser.add_argument("others", nargs="+")
    args = parser.parse_args()
    files = [args.baseline, *args.others]
    data = {f: json.loads(Path(f).read_text(encoding="utf-8")) for f in files}
    base = answerable(data[args.baseline]["records"])
    budgets = defaultdict(list)
    for r in base:
        budgets[r.get("category")].append(sum(r["passage_tokens"]))
    budget = {c: statistics.mean(v) for c, v in budgets.items()}
    print("v1 budget (mean context tokens) by category:", {c: round(v) for c, v in sorted(budget.items())})
    header = f"{'file':44} {'corpus':6} {'k':>3} {'n':>3} {'recall(all)':>11} {'recall@budget':>13} {'ctx median':>10} {'ctx mean':>9}"
    print(header)
    rows = {}
    for f in files:
        recs = answerable(data[f]["records"])
        full = [recall(expected(r), [tuple(s) for s in r["passage_spans"]]) for r in recs]
        capped = [recall(expected(r), [tuple(s) for s in within_budget(r, budget.get(r.get("category"), 0))]) for r in recs]
        ctx = [sum(r["passage_tokens"]) for r in recs]
        rows[f] = recs
        print(f"{Path(f).name[:44]:44} {str(data[f].get('corpus_label')):6} {str(data[f].get('k')):>3} {len(recs):>3} "
              f"{statistics.mean(full):11.3f} {statistics.mean(capped):13.3f} {statistics.median(ctx):10.0f} {statistics.mean(ctx):9.0f}")
    print("\nby category and language (recall@budget):")
    for f in files:
        by = defaultdict(list)
        for r in rows[f]:
            by[(r.get("language"), r.get("category"))].append(recall(expected(r), [tuple(s) for s in within_budget(r, budget.get(r.get("category"), 0))]))
        print(f"  {Path(f).name[:40]:40}", {f"{lang}/{cat}": f"{statistics.mean(v):.2f} (n={len(v)})" for (lang, cat), v in sorted(by.items())})


if __name__ == "__main__":
    main()
