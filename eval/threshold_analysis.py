"""Derive the vector-distance refusal threshold from a results file, using the TUNE split only.

    python eval/threshold_analysis.py eval/results/<file>.json [--language en] [--split tune]

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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("results")
    parser.add_argument("--language", default="en")
    parser.add_argument("--split", default="tune")
    args = parser.parse_args()
    data = json.loads(Path(args.results).read_text(encoding="utf-8"))
    records = data["records"]
    if not any(r.get("split") for r in records):
        print("WARNING: this results file has no split field; using all questions (not a proper tune-only derivation).")
        args.split = None

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
