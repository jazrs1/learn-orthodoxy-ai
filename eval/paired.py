"""A change between two sets of eval runs, as "Δ ± noise band" (RET-022, RET-025).

Each question is compared with itself: its score is averaged over each side's runs, and the change is
the mean of the per-question differences.

The band answers "could re-running alone have moved it this much?", on these same questions:
- With at least two runs on each side, the re-run noise is measured directly: each question's spread
  across its repeated runs, pooled over questions and both sides (RET-022's method). The band is
  1.96 × sqrt(pooled variance × (1/runs before + 1/runs after) / questions).
- With a single run on a side there are no repeats to measure, so the band falls back to a t-interval
  over the per-question differences. That also counts real question-to-question differences in the
  change, so it is wider (conservative), and is labelled as such.
A change whose band includes 0 can't be told apart from noise.
"""

from __future__ import annotations

import math
import statistics
from typing import Any, Callable, Dict, Iterable, List, Optional

# Two-sided 95% t critical values by degrees of freedom; 1.96 beyond 30.
_T95 = {1: 12.71, 2: 4.30, 3: 3.18, 4: 2.78, 5: 2.57, 6: 2.45, 7: 2.36, 8: 2.31, 9: 2.26, 10: 2.23,
        11: 2.20, 12: 2.18, 13: 2.16, 14: 2.14, 15: 2.13, 16: 2.12, 17: 2.11, 18: 2.10, 19: 2.09, 20: 2.09,
        21: 2.08, 22: 2.07, 23: 2.07, 24: 2.06, 25: 2.06, 26: 2.06, 27: 2.05, 28: 2.05, 29: 2.05, 30: 2.04}


def t95(df: int) -> float:
    return _T95.get(df, 1.96) if df >= 1 else float("nan")


Record = Dict[str, Any]


def paired_difference(
    before_runs: List[Dict[str, Record]],
    after_runs: List[Dict[str, Record]],
    value: Callable[[Record], Optional[float]],
    ids: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    """`before_runs` and `after_runs` map question id → record, one dict per run."""
    ids = list(ids) if ids is not None else sorted(set.intersection(*(set(r) for r in before_runs + after_runs)))
    diffs: List[float] = []
    variances: List[float] = []
    for qid in ids:
        b = [x for x in (value(run[qid]) for run in before_runs if qid in run) if x is not None]
        a = [x for x in (value(run[qid]) for run in after_runs if qid in run) if x is not None]
        if not (a and b):
            continue
        diffs.append(statistics.mean(a) - statistics.mean(b))
        variances += [statistics.variance(side) for side in (b, a) if len(side) >= 2]
    n = len(diffs)
    runs = (len(before_runs), len(after_runs))
    mean = statistics.mean(diffs) if diffs else float("nan")
    if min(runs) >= 2 and variances:
        pooled = statistics.mean(variances)
        band = 1.96 * math.sqrt(pooled * (1 / runs[0] + 1 / runs[1]) / n)
        method = "re-run noise"
    else:
        band = t95(n - 1) * statistics.stdev(diffs) / math.sqrt(n) if n >= 2 else float("nan")
        method = "across questions, conservative"
    return {"change": mean, "band": band, "n": n, "runs": runs, "method": method}


def describe(result: Dict[str, Any], unit: float = 100.0, label: str = "pts") -> str:
    """"+1.2 ± 2.4 pts (95%, re-run noise; 53 questions, 2 vs 2 runs); within noise"."""
    change, band = result["change"] * unit, result["band"] * unit
    verdict = "within noise" if abs(change) <= band else ("better" if change > 0 else "WORSE")
    before, after = result["runs"]
    return (
        f"{change:+.1f} ± {band:.1f} {label} (95%, {result['method']}; {result['n']} questions, "
        f"{after} vs {before} runs); {verdict}"
    )
