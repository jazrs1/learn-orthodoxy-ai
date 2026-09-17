"""Assign every question in eval/questions.jsonl to a `tune` or `holdout` split.

    python eval/make_split.py            # 70/30, stratified by category (and subtype for
                                          # out-of-corpus), seed 20260915, only fills missing splits
    python eval/make_split.py --reassign  # recompute everything (use only if the set changes a lot)

Rules (DECISIONS.md EVAL-012):
- Stratified: within each category (and subtype, for out-of-corpus and task-style questions) about 30% go to holdout.
- Deterministic: a fixed seed and an alphabetical sort make the split reproducible.
- Sticky: questions that already have a split keep it unless --reassign is given, so adding
  questions later does not shuffle earlier ones between splits.
- Never tune anything (thresholds, prompts, routing rules) on holdout.
"""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

QUESTIONS = Path(__file__).resolve().parent / "questions.jsonl"
HOLDOUT_FRACTION = 0.3
SEED = 20260915
# Categories whose subtypes are balanced separately (phase 3: out-of-corpus kinds; phase 4: task formats).
SUBTYPE_STRATIFIED = {"out_of_corpus", "task"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reassign", action="store_true")
    parser.add_argument("--holdout", type=float, default=HOLDOUT_FRACTION)
    args = parser.parse_args()

    rows = [json.loads(line) for line in QUESTIONS.read_text(encoding="utf-8").splitlines() if line.strip()]
    rng = random.Random(SEED)
    groups = defaultdict(list)
    for row in rows:
        key = (row.get("category"), row.get("subtype") if row.get("category") in SUBTYPE_STRATIFIED else None)
        groups[key].append(row)

    changed = 0
    for key in sorted(groups, key=str):
        members = sorted(groups[key], key=lambda r: r["id"])
        fixed = [r for r in members if r.get("split") and not args.reassign]
        free = [r for r in members if not r.get("split") or args.reassign]
        target_holdout = round(len(members) * args.holdout)
        already_holdout = sum(1 for r in fixed if r["split"] == "holdout")
        need = max(0, target_holdout - already_holdout)
        rng.shuffle(free)
        for index, row in enumerate(free):
            row["split"] = "holdout" if index < need else "tune"
            changed += 1

    QUESTIONS.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    counts = defaultdict(lambda: defaultdict(int))
    for row in rows:
        counts[row["category"]][row["split"]] += 1
    print(f"assigned {changed} questions")
    for category, c in sorted(counts.items()):
        print(f"  {category:<14} tune={c['tune']:3d}  holdout={c['holdout']:3d}")
    total = defaultdict(int)
    for row in rows:
        total[row["split"]] += 1
    print(f"  {'total':<14} tune={total['tune']:3d}  holdout={total['holdout']:3d}")


if __name__ == "__main__":
    main()
