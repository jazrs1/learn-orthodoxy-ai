"""Generate eval/human_check.md: a hand-grading sheet to compare the LLM judge with a human.

    python eval/make_human_check.py                      # latest results file, 10 questions
    python eval/make_human_check.py --results eval/results/<file>.json --n 10 --seed 7

Picks answered, answerable questions spread across categories (round-robin over
categories in a seeded random order), and writes question, reference answer, model
answer and judge score with a blank for the human score. Fill in "Your score" and
notes, then compare with the judge column.
"""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
RESULTS_DIR = EVAL_DIR / "results"


def latest_results() -> Path:
    files = sorted(RESULTS_DIR.glob("*.json"))
    if not files:
        raise SystemExit("no results files found; run eval/run_eval.py first")
    return files[-1]


def load_questions() -> dict:
    items = {}
    with open(EVAL_DIR / "questions.jsonl", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                item = json.loads(line)
                items[item["id"]] = item
    return items


def pick(records: list, n: int, seed: int) -> list:
    rng = random.Random(seed)
    by_cat = defaultdict(list)
    for record in records:
        if record.get("should_refuse") or record.get("outcome") != "answered":
            continue
        by_cat[record.get("category", "?")].append(record)
    for rows in by_cat.values():
        rng.shuffle(rows)
    order = sorted(by_cat)
    rng.shuffle(order)
    chosen: list = []
    while len(chosen) < n and any(by_cat.values()):
        for category in order:
            if by_cat[category] and len(chosen) < n:
                chosen.append(by_cat[category].pop())
    return chosen


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--results", help="results JSON (default: latest in eval/results)")
    parser.add_argument("--n", type=int, default=10)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--out", default=str(EVAL_DIR / "human_check.md"))
    args = parser.parse_args()

    path = Path(args.results) if args.results else latest_results()
    data = json.loads(path.read_text(encoding="utf-8"))
    questions = load_questions()
    chosen = pick(data["records"], args.n, args.seed)

    lines = [
        "# Human check of the LLM judge",
        "",
        f"Source results: `{path.name}` (judge model: `{data.get('judge_model')}`). "
        f"{len(chosen)} answered questions chosen across categories with seed {args.seed}.",
        "",
        "Grade each SYSTEM answer 1-5 with the same rubric the judge uses:",
        "5 = covers the key facts of the reference accurately; 4 = mostly correct, minor omissions; "
        "3 = partially correct; 2 = largely misses the reference or has clear errors; 1 = wrong, irrelevant or a refusal. "
        "Do not reward length. Fill in **Your score** and optional notes, then compare with the judge column.",
        "",
        "| # | id | category | judge | your score |",
        "|---|----|----------|-------|------------|",
    ]
    for index, record in enumerate(chosen, start=1):
        lines.append(f"| {index} | {record['id']} | {record.get('category')} | {record.get('judge_score')} |  |")
    lines.append("")

    for index, record in enumerate(chosen, start=1):
        item = questions.get(record["id"], {})
        lines.extend(
            [
                "---",
                "",
                f"## {index}. {record['id']} ({record.get('category')}, {record.get('language')})",
                "",
                f"**Question:** {record['question']}",
                "",
                "**Reference answer (from the verified pages):**",
                "",
                f"> {item.get('reference_answer', '').replace(chr(10), ' ')}",
                "",
                f"**Expected pages:** {', '.join(record.get('expected_pages') or [])}",
                "",
                "**System answer:**",
                "",
                *[f"> {line}" if line.strip() else ">" for line in (record.get("answer") or "").splitlines()],
                "",
                f"**Judge score:** {record.get('judge_score')} — {record.get('judge_rationale', '')}",
                "",
                "**Your score (1-5):** ____",
                "",
                "**Notes:**",
                "",
            ]
        )
    Path(args.out).write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {args.out} with {len(chosen)} questions from {path.name}")


if __name__ == "__main__":
    main()
