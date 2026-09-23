"""The paired change with its noise band (eval/paired.py, RET-025)."""

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "eval"))
from paired import describe, paired_difference  # noqa: E402


def runs(*score_lists):
    return [{f"Q{i}": {"cov": s} for i, s in enumerate(scores)} for scores in score_lists]


value = lambda r: r["cov"]  # noqa: E731


def test_the_change_is_the_mean_of_per_question_differences_of_run_means():
    before = runs([0.5, 0.8, 0.6], [0.7, 0.8, 0.6])  # question means 0.6, 0.8, 0.6
    after = runs([0.7, 0.9, 0.6], [0.7, 0.9, 0.6])
    result = paired_difference(before, after, value)
    assert result["n"] == 3 and result["runs"] == (2, 2)
    assert result["change"] == pytest.approx((0.1 + 0.1 + 0.0) / 3)


def test_with_repeats_the_band_is_the_measured_re_run_noise():
    before = runs([0.5, 0.8, 0.6], [0.7, 0.8, 0.6])
    after = runs([0.7, 0.9, 0.6], [0.7, 0.9, 0.6])
    result = paired_difference(before, after, value)
    # Per-question variances: before (0.02, 0, 0), after (0, 0, 0) → pooled 0.02 / 6.
    assert result["method"] == "re-run noise"
    assert result["band"] == pytest.approx(1.96 * math.sqrt((0.02 / 6) * (1 / 2 + 1 / 2) / 3))


def test_with_single_runs_the_band_falls_back_to_the_wider_interval():
    result = paired_difference(runs([0.5, 0.8, 0.6]), runs([0.7, 0.9, 0.6]), value)
    assert result["method"] == "across questions, conservative"
    # t(2) = 4.30; sd of (0.2, 0.1, 0.0) = 0.1
    assert result["band"] == pytest.approx(4.30 * 0.1 / math.sqrt(3), rel=1e-3)


def test_a_consistent_drop_is_called_worse_and_noise_is_called_noise():
    drop = paired_difference(runs([0.9] * 20, [0.9] * 20), runs([0.8] * 20, [0.82] * 20), value)
    assert "WORSE" in describe(drop)
    noisy = paired_difference(runs([0.8, 0.9] * 10, [0.9, 0.8] * 10), runs([0.9, 0.8] * 10, [0.8, 0.9] * 10), value)
    assert "within noise" in describe(noisy)


def test_questions_missing_a_score_on_either_side_are_left_out():
    before = [{"Q1": {"cov": 0.5}, "Q2": {"cov": None}}]
    after = [{"Q1": {"cov": 0.7}, "Q2": {"cov": 0.9}}]
    assert paired_difference(before, after, value)["n"] == 1
