"""Faithfulness on a fixed subset of answers, for a v1/v2 comparison (INGEST_PLAN.md §10.2).

    python eval/faithfulness_subset.py eval/results/<v1 run>.json eval/results/<v2 run>.json --max-spend 6

Judges the answers already stored in two coverage-only results files (nothing is regenerated), on
the same 15 question ids for both corpora: 4 English saints, 3 Arabic, 4 catechism, 2 task,
1 keyword and 1 multi-part question, drawn with a fixed seed from those answered in both runs.
Uses the same faithfulness judge as run_eval.py (claims vs the passage each one cites).
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(EVAL_DIR))

import run_eval  # noqa: E402
import scoring  # noqa: E402
import spend  # noqa: E402

STRATA = [("saints", "en", 4), ("arabic", "ar", 3), ("catechism", "en", 4), ("task", "en", 2), ("keyword", "en", 1), ("multi_part", "en", 1)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("runs", nargs=2)
    parser.add_argument("--judge-model", default="gpt-4.1")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--max-spend", type=float)
    parser.add_argument("--spend-ledger", default=str(run_eval.DEFAULT_LEDGER))
    args = parser.parse_args()
    runs = [json.loads(Path(p).read_text(encoding="utf-8")) for p in args.runs]
    by_id = [{r["id"]: r for r in run["records"]} for run in runs]
    both = sorted(i for i in by_id[0] if i in by_id[1]
                  and by_id[0][i]["outcome"] == "answered" and by_id[1][i]["outcome"] == "answered" and not by_id[0][i]["should_refuse"])
    rng = random.Random(args.seed)
    chosen = []
    for category, language, n in STRATA:
        pool = [i for i in both if by_id[0][i].get("category") == category and by_id[0][i].get("language") == language]
        chosen += sorted(rng.sample(pool, min(n, len(pool))))
    print("question ids:", chosen)
    ledger = spend.SpendLedger(Path(args.spend_ledger), args.max_spend)
    client = spend.MeteredClient(run_eval.make_judge_client(), ledger)
    out = {"ids": chosen, "judge_model": args.judge_model, "runs": args.runs, "corpora": {}}
    stopped = None
    try:
        for run, records in zip(runs, by_id):
            label = run.get("corpus_label") or "?"
            claims, per_answer = [], {}
            for qid in chosen:
                ledger.check(0.08)
                record = records[qid]
                result = scoring.faithfulness_judge(client, args.judge_model, record.get("answer") or "", record.get("passages") or [])
                per_answer[qid] = {"rates": result.get("rates"), "n_claims": result.get("n_claims"), "error": result.get("error"),
                                   "claims": result.get("claims")}
                claims += result.get("claims") or []
                rates = result.get("rates") or {}
                print(f"  {label} {qid:7} claims={result.get('n_claims', 0):3} supported={run_eval.fmt(rates.get('supported'))} "
                      f"unsupported={run_eval.fmt(rates.get('unsupported'))} bad-citation={run_eval.fmt(rates.get('bad_citation'))}", flush=True)
            n = len(claims)
            summary = {status: (sum(1 for c in claims if c["status"] == status) / n if n else None)
                       for status in ("supported", "unsupported", "bad_citation")}
            summary["uncited"] = (sum(1 for c in claims if not c.get("cited")) / n) if n else None
            summary["n_claims"] = n
            out["corpora"][label] = {"summary": summary, "answers": per_answer}
            print(f"{label}: " + ", ".join(f"{k} {run_eval.fmt(v) if k != 'n_claims' else v}" for k, v in summary.items()))
    except (spend.FatalOpenAIError, spend.BudgetExceeded) as exc:
        stopped = str(exc)
        print(f"STOP: {stopped}", file=sys.stderr)
    out_path = run_eval.write_results(EVAL_DIR / "results", {"label": "faithfulness subset v1 vs v2", **out, "stopped": stopped,
                                                                "spend_usd": round(ledger.run_usd, 5)})
    ledger.save(f"{out_path.name} faithfulness subset")
    print(f"spend ${ledger.run_usd:.4f}; ledger total ${ledger.total:.4f}; written to {out_path}")
    return 3 if stopped else 0


if __name__ == "__main__":
    raise SystemExit(main())
