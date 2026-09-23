"""Saint-list filters from the request analysis (ING-007): "named X" is a name, not a first letter."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from task_analysis import _parse, name_filter_from_question  # noqa: E402


@pytest.mark.parametrize("question, expected", [
    ("List the saints named Gregory", {"contains": "Gregory"}),
    ("saints named George", {"contains": "George"}),
    ("list the saints called St. Mark", {"contains": "Mark"}),
    ("saints whose names start with G", {"starts_with": "G"}),
    ("list the saints whose names begin with Ab", {"starts_with": "Ab"}),
    ("اذكر القديسين الذين يحملون اسم غريغوريوس", {"contains": "غريغوريوس"}),
    ("القديسون باسم جرجس", {"contains": "جرجس"}),
    ("اذكر القديسين الذين تبدأ أسماؤهم بحرف ج", {"starts_with": "ج"}),
    ("Who was St. George?", None),
    ("Tell me about the saint named Barbara", None),
    ("من هو القديس جرجس؟", None),
])
def test_filter_read_from_the_question(question, expected):
    assert name_filter_from_question(question) == expected


def test_contains_wins_when_the_model_returns_both_keys():
    data = {"retrieval_query": "Which saints are named Gregory?", "saint_name_filter": {"starts_with": "G", "contains": "Gregory"}}
    assert _parse(data, "which ones are the Gregorys?").saint_name_filter == {"contains": "Gregory"}
    assert _parse(data, "those beginning with G please").saint_name_filter == {"starts_with": "G"}


def test_the_users_words_override_the_model():
    data = {"retrieval_query": "Which saints are named Gregory?", "saint_name_filter": {"starts_with": "G"}}
    assert _parse(data, "List the saints named Gregory").saint_name_filter == {"contains": "Gregory"}
