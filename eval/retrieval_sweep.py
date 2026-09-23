"""Retrieval-only sweep over top-k for one corpus (Phase 5 Step 5, INGEST_PLAN.md §10.2).

    python eval/retrieval_sweep.py --corpus v2 --ks 8 10 12 14 16 --split tune
    python eval/retrieval_sweep.py --corpus v1 --ks 8 --split tune

Runs the /chat flow in-process with `retrieve_only` (no answer is generated). Each question's
analysis call is made once and cached (`--cache`), so every k and both corpora see exactly the same
analysis, and a sweep costs only the query embeddings after the first pass. Writes one results file
per k in the format `threshold_analysis.py` and `budget_recall.py` read: `records` with
`retrieval` hits, best distance, passages' token counts and page spans.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(EVAL_DIR))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--corpus", choices=["v1", "v2"], required=True)
    parser.add_argument("--ks", type=int, nargs="+", default=[8])
    parser.add_argument("--split", choices=["tune", "holdout"], default="tune")
    parser.add_argument("--questions", default=str(EVAL_DIR / "questions.jsonl"))
    parser.add_argument("--cache", default=str(EVAL_DIR / "results" / "analysis-cache-tune.json"))
    parser.add_argument("--max-spend", type=float)
    parser.add_argument("--spend-ledger", default=str(EVAL_DIR / "results" / "spend-phase5.json"))
    parser.add_argument("--results-dir", default=str(EVAL_DIR / "results"))
    args = parser.parse_args()

    os.chdir(REPO_ROOT)
    os.environ["CORPUS_VERSION"] = args.corpus
    os.environ.setdefault("TOP_K_V2", "0")  # the sweep sets k itself
    os.environ.setdefault("MAX_TOP_K", "16")
    from dotenv import load_dotenv

    load_dotenv(REPO_ROOT / ".env")
    from fastapi import HTTPException

    import api
    import run_eval
    import spend
    from request_log import RequestTrace
    from task_analysis import TaskAnalysis

    ledger = spend.SpendLedger(Path(args.spend_ledger), args.max_spend)
    cache_path = Path(args.cache)
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    original = api._analyze_request

    def cached_analysis(question, history):
        key = json.dumps([question, history], ensure_ascii=False)
        if key in cache:
            return TaskAnalysis(**cache[key])
        ledger.check(0.001)
        analysis = original(question, history)
        if analysis.error and any(k in analysis.error.lower() for k in ("insufficient_quota", "401", "403", "authentication", "permission")):
            raise spend.FatalOpenAIError(f"analysis call failed: {analysis.error}")
        ledger.add(analysis.model or "gpt-4o-mini", analysis.prompt_tokens or 0, analysis.completion_tokens or 0, "analysis")
        cache[key] = asdict(analysis)
        return analysis

    api._analyze_request = cached_analysis
    api.startup()
    items = run_eval.load_questions(Path(args.questions), split=args.split)
    stopped = None
    written = []
    try:
        for k in args.ks:
            records = []
            for item in items:
                with RequestTrace("chat") as trace:
                    try:
                        payload = api._chat_impl(api.ChatRequest(
                            question=item["question"], history=item.get("history", []) or [], mode=item.get("mode", "chat"),
                            language=item.get("language", "en"), top_k=k, retrieve_only=True), trace)
                    except HTTPException as exc:
                        raise spend.FatalOpenAIError(f"{item['id']}: HTTP {exc.status_code} {exc.detail}")
                    debug = trace.debug_payload()
                queries = debug.get("retrieval_queries") or []
                ledger.add("text-embedding-3-small", sum(len(str(q)) for q in queries) // 3, 0, "embedding")
                passages = debug.get("passages") or []
                ids = [p.get("id") for p in passages]
                spans = run_eval.spans_from_ids(ids)
                expected = run_eval.expected_pages(item)
                records.append({
                    "id": item["id"], "category": item.get("category"), "subtype": item.get("subtype"), "split": item.get("split"),
                    "language": item.get("language", "en"), "mode": item.get("mode", "chat"), "should_refuse": bool(item.get("should_refuse")),
                    "question": item["question"], "outcome": debug.get("outcome") or ("options" if payload.get("options") else "other"),
                    "retrieval": debug.get("retrieval"), "best_distance": debug.get("best_distance"),
                    "retrieval_plan": debug.get("retrieval_plan"), "merged_ids": ids,
                    "passage_tokens": [run_eval.count_tokens(p.get("text", "")) for p in passages],
                    "passage_spans": [list(s) for s in spans],
                    "context_tokens": sum(run_eval.count_tokens(p.get("text", "")) for p in passages),
                    "expected_pages": sorted(f"{pdf}:p{page}" for pdf, page in expected),
                    "recall_all": run_eval.recall(expected, spans) if expected else None,
                })
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            out = Path(args.results_dir) / f"sweep-{args.corpus}-k{k}-{args.split}-{stamp}.json"
            out.write_text(json.dumps({"label": f"retrieval sweep {args.corpus} k={k}", "corpus_label": args.corpus, "k": k,
                                       "split_filter": args.split, "retrieve_only": True, "records": records},
                                      ensure_ascii=False, indent=1), encoding="utf-8")
            written.append(out)
            answerable = [r for r in records if not r["should_refuse"] and r["recall_all"] is not None]
            tokens = sorted(r["context_tokens"] for r in records if not r["should_refuse"])
            print(f"{args.corpus} k={k}: recall {sum(r['recall_all'] for r in answerable) / len(answerable):.3f} "
                  f"(n={len(answerable)}), median context tokens {tokens[len(tokens) // 2]} -> {out.name}", flush=True)
    except (spend.FatalOpenAIError, spend.BudgetExceeded) as exc:
        stopped = str(exc)
        print(f"STOP: {stopped}", file=sys.stderr)
    finally:
        cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
        ledger.save(f"retrieval sweep {args.corpus} ks={args.ks}")
        print(f"spend this sweep ${ledger.run_usd:.4f}; ledger total ${ledger.total:.4f}")
    return 3 if stopped else 0


if __name__ == "__main__":
    raise SystemExit(main())
