"""v1 vs v2 comparison for Phase 5 Step 5 (INGEST_PLAN.md §10.2).

    python eval/phase5_compare.py --v1 A.json B.json --v2 C.json D.json [--faith F.json]

Headline: coverage (all answerable, refusals count 0), by language and split, as the mean of the
runs with the run-to-run spread. Then recall at equal context budget (budgets from the v1 runs),
context tokens, refusal rates, saints and Arabic detail, and per-question regressions.
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path

import budget_recall

NEAR = {"saint_not_in_books", "non_coptic_doctrine", "false_premise", "same_name_confusion"}


def load(paths):
    return [json.loads(Path(p).read_text(encoding="utf-8")) for p in paths]


def mean(values):
    values = [v for v in values if v is not None]
    return statistics.mean(values) if values else float("nan")


def pct(v):
    return "  n/a" if v != v else f"{100 * v:5.1f}"


def per_run(runs, select, metric):
    return [metric([r for r in run["records"] if select(r)]) for run in runs]


def cell(runs, select, metric):
    values = per_run(runs, select, metric)
    spread = (max(values) - min(values)) if len(values) > 1 else 0.0
    return f"{pct(mean(values))} ±{100 * spread / 2:4.1f}"


def coverage(rows):
    rows = [r for r in rows if not r["should_refuse"]]
    return mean([r.get("coverage_score") if r.get("coverage_score") is not None else 0.0 for r in rows]) if rows else float("nan")


def rate(rows, outcome):
    return (sum(1 for r in rows if r["outcome"] == outcome) / len(rows)) if rows else float("nan")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--v1", nargs="+", required=True)
    parser.add_argument("--v2", nargs="+", required=True)
    parser.add_argument("--faith")
    args = parser.parse_args()
    corpora = {"v1": load(args.v1), "v2": load(args.v2)}

    print("COVERAGE (all answerable; mean of runs ± half the run-to-run spread)")
    print(f"{'':22} {'v1':>12} {'v2':>12}   n")
    for lang in ("en", "ar"):
        for split in ("tune", "holdout", None):
            select = (lambda r, l=lang, s=split: r["language"] == l and (s is None or r.get("split") == s) and not r["should_refuse"])
            n = sum(1 for r in corpora["v1"][0]["records"] if select(r))
            label = f"{lang.upper()} {split or 'all'}"
            print(f"{label:22} {cell(corpora['v1'], select, coverage):>12} {cell(corpora['v2'], select, coverage):>12}   {n}")
    select_all = lambda r: not r["should_refuse"]  # noqa: E731
    print(f"{'ALL':22} {cell(corpora['v1'], select_all, coverage):>12} {cell(corpora['v2'], select_all, coverage):>12}")

    print("\nCOVERAGE by category (all splits)")
    cats = sorted({(r["language"], r.get("category"), r.get("mode")) for r in corpora["v1"][0]["records"] if not r["should_refuse"]})
    groups = defaultdict(list)
    for lang, cat, mode in cats:
        key = f"{lang}/{cat}" + (f"/{'catechism' if mode == 'catechism' else 'saints'}" if cat == "arabic" else "")
        groups[key].append((lang, cat, mode))
    for key, members in sorted(groups.items()):
        select = (lambda r, m=members: (r["language"], r.get("category"), r.get("mode")) in m and not r["should_refuse"])
        n = sum(1 for r in corpora["v1"][0]["records"] if select(r))
        print(f"  {key:26} {cell(corpora['v1'], select, coverage):>12} {cell(corpora['v2'], select, coverage):>12}   {n}")

    print("\nRECALL AT EQUAL CONTEXT BUDGET (budget = v1's mean context tokens per category, from the v1 runs)")
    budgets = defaultdict(list)
    for run in corpora["v1"]:
        for r in budget_recall.answerable(run["records"]):
            budgets[r.get("category")].append(sum(r["passage_tokens"]))
    budget = {c: statistics.mean(v) for c, v in budgets.items()}
    for name, runs in corpora.items():
        for lang in ("en", "ar", None):
            vals, full, ctx, prompts = [], [], [], []
            for run in runs:
                recs = [r for r in budget_recall.answerable(run["records"]) if lang is None or r["language"] == lang]
                vals.append(mean([budget_recall.recall(budget_recall.expected(r), [tuple(s) for s in budget_recall.within_budget(r, budget.get(r.get("category"), 0))]) for r in recs]))
                full.append(mean([budget_recall.recall(budget_recall.expected(r), [tuple(s) for s in r["passage_spans"]]) for r in recs]))
                ctx += [sum(r["passage_tokens"]) for r in recs]
                prompts += [r.get("prompt_tokens") for r in run["records"] if (lang is None or r["language"] == lang) and r.get("prompt_tokens")]
            print(f"  {name} {lang or 'all':3}  recall@budget {pct(mean(vals))}  recall(all passages) {pct(mean(full))}  "
                  f"context tokens median {statistics.median(ctx):6.0f} mean {mean(ctx):6.0f}  prompt tokens mean {mean(prompts):6.0f}")

    print("\nREFUSALS")
    for name, runs in corpora.items():
        rows = lambda run, f: [r for r in run["records"] if f(r)]  # noqa: E731
        ans = mean([rate(rows(run, lambda r: not r["should_refuse"]), "refused") for run in runs])
        clar = mean([rate(rows(run, lambda r: not r["should_refuse"]), "clarification") for run in runs])
        ooc = mean([rate(rows(run, lambda r: r["should_refuse"]), "refused") for run in runs])
        easy = mean([rate(rows(run, lambda r: r["should_refuse"] and not r.get("subtype")), "refused") for run in runs])
        near = mean([rate(rows(run, lambda r: r["should_refuse"] and r.get("subtype") in NEAR), "refused") for run in runs])
        task = mean([rate(rows(run, lambda r: r["should_refuse"] and r.get("subtype") == "task_style"), "refused") for run in runs])
        ar_ooc = mean([rate(rows(run, lambda r: r["should_refuse"] and r["language"] == "ar"), "refused") for run in runs])
        print(f"  {name}: answerable refused {pct(ans)}  clarification {pct(clar)} | out-of-corpus refused {pct(ooc)} "
              f"(easy {pct(easy)}, near-miss {pct(near)}, task {pct(task)}, Arabic {pct(ar_ooc)})")

    print("\nPER-QUESTION CHANGES (mean coverage over runs; |delta| >= 0.25)")
    def by_id(runs):
        scores = defaultdict(list)
        outcomes = defaultdict(list)
        for run in runs:
            for r in run["records"]:
                if not r["should_refuse"]:
                    scores[r["id"]].append(r.get("coverage_score") if r.get("coverage_score") is not None else 0.0)
                outcomes[r["id"]].append(r["outcome"])
        return {k: mean(v) for k, v in scores.items()}, outcomes
    s1, o1 = by_id(corpora["v1"])
    s2, o2 = by_id(corpora["v2"])
    meta = {r["id"]: r for r in corpora["v1"][0]["records"]}
    changes = sorted(((s2.get(i, 0) - s1[i], i) for i in s1), key=lambda x: x[0])
    worse = [(d, i) for d, i in changes if d <= -0.25]
    better = [(d, i) for d, i in changes if d >= 0.25]
    for title, rows in (("worse on v2", worse), ("better on v2", list(reversed(better)))):
        print(f"  -- {title}: {len(rows)}")
        for d, i in rows:
            print(f"     {i:7} {meta[i]['language']} {meta[i].get('category'):12} v1 {s1[i]:.2f} -> v2 {s2.get(i, 0):.2f}  "
                  f"outcomes v1 {o1[i]} v2 {o2.get(i)}  {meta[i]['question'][:60]}")
    flips = [i for i in o1 if meta[i]["should_refuse"] and any(o == "answered" for o in o2.get(i, [])) and not any(o == "answered" for o in o1[i])]
    print(f"  out-of-corpus answered on v2 but never on v1: {flips}")
    flips_back = [i for i in o1 if meta[i]["should_refuse"] and any(o == "answered" for o in o1[i]) and not any(o == "answered" for o in o2.get(i, []))]
    print(f"  out-of-corpus answered on v1 but never on v2: {flips_back}")

    if args.faith:
        faith = json.loads(Path(args.faith).read_text(encoding="utf-8"))
        print(f"\nFAITHFULNESS ({len(faith['ids'])} answers per corpus, same ids, judge {faith['judge_model']})")
        for name, data in faith["corpora"].items():
            s = data["summary"]
            print(f"  {name}: supported {pct(s['supported'])}  unsupported {pct(s['unsupported'])}  "
                  f"bad citation {pct(s['bad_citation'])}  uncited {pct(s['uncited'])}  claims {s['n_claims']}")

    for name, runs in corpora.items():
        print(f"\nspend {name}: " + ", ".join(f"${run.get('spend_usd', 0):.3f}" for run in runs))


if __name__ == "__main__":
    main()
