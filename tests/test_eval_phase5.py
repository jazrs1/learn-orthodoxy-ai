"""Phase 5 eval helpers (ING-006): range-aware recall, the equal-budget cut, the spend ceiling."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval"))

import budget_recall  # noqa: E402
import run_eval  # noqa: E402
import spend  # noqa: E402


def test_recall_is_range_aware_and_unchanged_for_single_pages():
    expected = {("saints1.pdf", 33), ("saints1.pdf", 34)}
    assert run_eval.recall(expected, [("saints1.pdf", 33, 35)]) == 1.0
    assert run_eval.recall(expected, [("saints1.pdf", 33, 33)]) == 0.5  # a v1 chunk is one page
    assert run_eval.recall(expected, [("saints1.pdf", 35, 35)], tolerance=1) == 0.5
    assert run_eval.spans_from_ids(["saints1.pdf::p33::c0", "ar::full saints arabic.pdf::p116::c1"]) == [
        ("saints1.pdf", 33, 33), ("full saints arabic.pdf", 116, 116)]


def test_budget_cut_counts_passages_until_the_budget_is_reached():
    record = {"passage_tokens": [400, 400, 400], "passage_spans": [["a.pdf", 1, 1], ["a.pdf", 2, 2], ["a.pdf", 3, 3]]}
    assert budget_recall.within_budget(record, 700) == [["a.pdf", 1, 1], ["a.pdf", 2, 2]]
    assert budget_recall.within_budget(record, 0) == []


def test_ledger_refuses_a_question_that_would_cross_the_ceiling(tmp_path):
    ledger = spend.SpendLedger(tmp_path / "ledger.json", max_spend=1.0)
    ledger.add("gpt-4.1", 400_000, 0, "judge")  # $0.80
    ledger.check(0.1)
    with pytest.raises(spend.BudgetExceeded):
        ledger.check(0.3)
    ledger.save("t")
    assert spend.SpendLedger(tmp_path / "ledger.json", 1.0).prior == pytest.approx(0.8)


def test_quota_and_auth_errors_stop_the_judge():
    class Quota(Exception):
        status_code = 429

        def __str__(self):
            return "Error code: 429 - insufficient_quota"

    class Client:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    raise Quota()

    metered = spend.MeteredClient(Client, spend.SpendLedger(None, None))
    with pytest.raises(spend.FatalOpenAIError):
        metered.chat.completions.create(model="gpt-4.1", messages=[])
