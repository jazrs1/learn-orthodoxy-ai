"""Derive the vector-distance refusal threshold from a results file, using the TUNE split only.

    python eval/threshold_analysis.py eval/results/<file>.json [--language en] [--split tune]
    python eval/threshold_analysis.py eval/results/<file>.json --simulate   # run made with the threshold off

For every question the best (smallest) vector distance across its retrieval queries is
taken from the stored `retrieval` hits. Answerable questions should fall *below* the
threshold, out-of-corpus questions *above* it. The script prints both distributions, a
sweep of candidate thresholds with the two error counts (answerable wrongly refused,
out-of-corpus wrongly passed), and the recommended value. Holdout questions are shown
only as a sanity check and must never drive the choice (DECISIONS.md EVAL-012, RET-004).
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path


def best_distances(records, language, split):
    answerable, ooc, ids = [], [], {}
    for r in records:
        if language and r.get("language") != language:
            continue
        if split and r.get("split") != split:
            continue
        dists = [h["distance"] for q in (r.get("retrieval") or []) if q.get("source") == "vector" for h in q.get("hits", []) if "distance" in h]
        if not dists:
            continue
        best = min(dists)
        ids[r["id"]] = best
        (ooc if r["should_refuse"] else answerable).append(best)
    return answerable, ooc, ids


def sweep(answerable, ooc, lo=0.8, hi=1.4, step=0.01):
    rows = []
    t = lo
    while t <= hi + 1e-9:
        blocked = sum(1 for d in answerable if d > t)
        passed = sum(1 for d in ooc if d <= t)
        rows.append((round(t, 2), blocked, passed))
        t += step
    return rows


def simulate(records, split, thresholds):
    """Phase 4 (RET-009): the run was made with the threshold switched off, so every question has a
    real answer. A threshold refusal happens before generation, so the outcome at threshold t is
    exactly "refused" when the English best distance exceeds t, else the recorded outcome."""
    rows = [r for r in records if (not split or r.get("split") == split)]
    for r in rows:
        if r.get("language") != "en":
            r["_best"] = None
            continue
        dists = [h["distance"] for q in (r.get("retrieval") or []) if q.get("source") == "vector" and not q.get("where_document") for h in q.get("hits", []) if "distance" in h]
        r["_best"] = min(dists) if dists else None  # saint lists have no vector search: never thresholded

    def entity_blocked(r):
        return (r.get("entity_check") or {}).get("action", "").startswith("decline") and r["outcome"] == "refused"

    answerable = [r for r in rows if not r["should_refuse"]]
    print(f"\nsimulation on split={split or 'all'}: answerable n={len(answerable)}, out-of-corpus n={len(rows) - len(answerable)}")
    print("  entity check blocked (answerable):", [r["id"] for r in answerable if entity_blocked(r)] or "none")
    print("  other refusals (answerable, no threshold):", [f"{r['id']}:{r.get('refusal_reason')}" for r in answerable if r["outcome"] == "refused" and not entity_blocked(r)] or "none")
    print("\n  threshold | answerable refused | ooc refused (easy / near-miss / task) | answerable blocked by threshold | ooc newly refused by threshold")
    for t in thresholds:
        def outcome(r):
            return "refused" if (t and r["_best"] is not None and r["_best"] > t) else r["outcome"]
        a_ref = sum(1 for r in answerable if outcome(r) == "refused")
        groups = {"easy": [], "near": [], "task": []}
        for r in rows:
            if not r["should_refuse"]:
                continue
            key = "easy" if not r.get("subtype") else ("task" if r.get("subtype") == "task_style" else "near")
            groups[key].append(outcome(r) == "refused")
        blocked = [f"{r['id']}({r['_best']:.3f})" for r in answerable if r["_best"] is not None and t and r["_best"] > t]
        newly = [r["id"] for r in rows if r["should_refuse"] and r["outcome"] != "refused" and outcome(r) == "refused"]
        fmt = lambda g: f"{sum(g)}/{len(g)}"
        label = f"{t:.2f}" if t else "off"
        print(f"  {label:>9} | {a_ref:>2}/{len(answerable)} | {fmt(groups['easy'])} / {fmt(groups['near'])} / {fmt(groups['task'])} | {blocked or '-'} | {newly or '-'}")
    ooc_pass = sorted((r["_best"], r["id"]) for r in rows if r["should_refuse"] and r["_best"] is not None and r["outcome"] != "refused")
    print("\n  out-of-corpus questions the model/entity check did NOT refuse (best distance):", [(i, round(d, 3)) for d, i in ooc_pass] or "none")
    ans = sorted(((r["_best"], r["id"]) for r in answerable if r["_best"] is not None), reverse=True)[:8]
    print("  largest answerable best distances:", [(i, round(d, 3)) for d, i in ans])
    ooc = sorted((r["_best"], r["id"]) for r in rows if r["should_refuse"] and r["_best"] is not None)[:12]
    print("  smallest out-of-corpus best distances:", [(i, round(d, 3)) for d, i in ooc])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("results")
    parser.add_argument("--language", default="en")
    parser.add_argument("--split", default="tune")
    parser.add_argument("--simulate", action="store_true", help="the run had the threshold off: replay candidate thresholds on its outcomes")
    args = parser.parse_args()
    data = json.loads(Path(args.results).read_text(encoding="utf-8"))
    records = data["records"]
    if not any(r.get("split") for r in records):
        print("WARNING: this results file has no split field; using all questions (not a proper tune-only derivation).")
        args.split = None

    if args.simulate:
        simulate(records, args.split, [0, 0.9, 0.95, 1.0, 1.05, 1.1, 1.15, 1.2, 1.25, 1.3, 1.35, 1.4])
        return
    ans, ooc, ids = best_distances(records, args.language, args.split)
    print(f"split={args.split or 'all'} language={args.language}: answerable n={len(ans)} out-of-corpus n={len(ooc)}")
    if ans:
        print(f"  answerable best distance: min={min(ans):.3f} median={statistics.median(ans):.3f} max={max(ans):.3f}")
    if ooc:
        print(f"  out-of-corpus best distance: min={min(ooc):.3f} median={statistics.median(ooc):.3f} max={max(ooc):.3f}")
    worst_ans = sorted(((d, i) for i, d in ids.items() if d in ans), reverse=True)[:5]
    easiest_ooc = sorted(((d, i) for i, d in ids.items() if d in ooc))[:5]
    print("  hardest answerable (largest distance):", [(i, round(d, 3)) for d, i in worst_ans])
    print("  closest out-of-corpus (smallest distance):", [(i, round(d, 3)) for d, i in easiest_ooc])

    rows = sweep(ans, ooc)
    print("\n  threshold  answerable_blocked  ooc_passed  total_errors")
    best_t, best_err = None, None
    for t, blocked, passed in rows:
        err = blocked + passed
        if best_err is None or err < best_err or (err == best_err and abs(t - 1.0) < abs(best_t - 1.0)):
            best_t, best_err = t, err
        if t * 100 % 5 == 0:
            print(f"  {t:9.2f}  {blocked:18d}  {passed:10d}  {err:12d}")
    if ans and ooc and max(ans) < min(ooc):
        mid = (max(ans) + min(ooc)) / 2
        print(f"\nseparable: every answerable <= {max(ans):.3f} and every out-of-corpus >= {min(ooc):.3f}; midpoint {mid:.3f}; margin {(min(ooc) - max(ans)):.3f}")
        print(f"recommended VECTOR_DISTANCE_THRESHOLD = {round(mid, 2)}")
    else:
        print(f"\nnot separable; minimum-error threshold = {best_t} with {best_err} errors")

    # holdout sanity check (never used to choose)
    if args.split == "tune":
        h_ans, h_ooc, _ = best_distances(records, args.language, "holdout")
        chosen = round((max(ans) + min(ooc)) / 2, 2) if (ans and ooc and max(ans) < min(ooc)) else best_t
        if h_ans or h_ooc:
            print(f"\nholdout check at {chosen}: answerable blocked {sum(1 for d in h_ans if d > chosen)}/{len(h_ans)}, out-of-corpus passed {sum(1 for d in h_ooc if d <= chosen)}/{len(h_ooc)}")


if __name__ == "__main__":
    main()
