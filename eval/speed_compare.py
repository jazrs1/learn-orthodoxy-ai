"""Before/after for the speed changes (RET-019): quality must hold, stages should shrink.

    python eval/speed_compare.py --before A.json B.json --after C.json D.json [--backend-logs L1 L2]

Tune split only, English and Arabic separately. Quality: coverage (all answerable; refusals count 0),
answerable questions refused, out-of-corpus questions refused (all and near misses, which the entity
check exists for), off-target answers; each as the mean of the runs with the per-run values, so run-to-
run noise is visible. Every question whose refusal outcome changed is listed. Speed: median and p90 of
each stage and of the total. The backend logs (optional) give the entity check's actions per run.
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from pathlib import Path

NEAR = {"saint_not_in_books", "non_coptic_doctrine", "false_premise", "same_name_confusion"}


def tune(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [r for r in data["records"] if r.get("split") == "tune"]


def refused(r):
    return r["outcome"] == "refused"


def quality(rows):
    answerable = [r for r in rows if not r["should_refuse"]]
    ooc = [r for r in rows if r["should_refuse"]]
    near = [r for r in ooc if r.get("subtype") in NEAR]
    cov = [0.0 if refused(r) else (r.get("coverage_score") or 0.0) for r in answerable]
    answered = [r for r in answerable if not refused(r) and r["outcome"] == "answered"]
    return {
        "coverage_all": statistics.mean(cov) if cov else None,
        "answerable_refused": sum(refused(r) for r in answerable) / len(answerable) if answerable else None,
        "ooc_refused": sum(refused(r) for r in ooc) / len(ooc) if ooc else None,
        "near_miss_refused": sum(refused(r) for r in near) / len(near) if near else None,
        "off_target": sum(bool(r.get("off_target")) for r in answered) / len(answered) if answered else None,
        "n": (len(answerable), len(ooc)),
    }


def pct(values):
    values = sorted(v for v in values if v is not None)
    if not values:
        return None
    q = statistics.quantiles(values, n=10, method="inclusive") if len(values) > 1 else [values[0]] * 9
    return {"median": round(statistics.median(values)), "p90": round(q[8])}


def speed(runs):
    rows = [r for run in runs for r in run if r["outcome"] == "answered" and r.get("stages_ms")]
    out = {s: pct([r["stages_ms"].get(s) for r in rows]) for s in ("analysis", "retrieval", "generation")}
    out["total"] = pct([r["latency_s"] * 1000 for r in rows])
    out["answered_n"] = len(rows)
    return out


def entity_actions(path):
    counts = Counter()
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.startswith('{"event": "request"'):
            continue
        record = json.loads(line)
        if record.get("endpoint") != "chat":
            continue
        action = (record.get("entity_check") or {}).get("action", "none (no subjects)")
        counts[action] += 1
        counts["analysis_cached"] += bool(record.get("analysis_cached"))
        counts[f"prefetch_{record.get('embedding_prefetch')}"] += 1
    return dict(counts)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--before", nargs="+", required=True)
    parser.add_argument("--after", nargs="+", required=True)
    parser.add_argument("--backend-logs", nargs="*", default=[])
    args = parser.parse_args()
    before = [tune(p) for p in args.before]
    after = [tune(p) for p in args.after]
    report = {"quality": {}, "speed": {}, "changed_refusals": [], "entity_check_after": [entity_actions(p) for p in args.backend_logs]}
    for language in ("en", "ar"):
        for label, runs in (("before", before), ("after", after)):
            per_run = [quality([r for r in run if r["language"] == language]) for run in runs]
            report["quality"][f"{language}/{label}"] = {
                key: {"mean": round(statistics.mean(v[key] for v in per_run), 4), "runs": [round(v[key], 4) for v in per_run]}
                for key in ("coverage_all", "answerable_refused", "ooc_refused", "near_miss_refused", "off_target")
                if all(v[key] is not None for v in per_run)
            } | {"n (answerable, out-of-corpus)": per_run[0]["n"]}
            report["speed"][f"{language}/{label}"] = speed([[r for r in run if r["language"] == language] for run in runs])
    # Questions refused in every before run but answered in an after run, or the other way round.
    ids = {r["id"] for r in after[0]}
    for qid in sorted(ids):
        b = [next(r for r in run if r["id"] == qid) for run in before]
        a = [next(r for r in run if r["id"] == qid) for run in after]
        if {refused(r) for r in b} != {refused(r) for r in a}:
            report["changed_refusals"].append(
                {"id": qid, "should_refuse": a[0]["should_refuse"], "before": [r["outcome"] for r in b], "after": [r["outcome"] for r in a]}
            )
    print(json.dumps(report, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
