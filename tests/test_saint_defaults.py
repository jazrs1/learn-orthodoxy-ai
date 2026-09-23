"""Bare-name defaults and the hand-written alias audit (RET-011).

Same harness as test_saint_menus.py: the committed v2 saints index and reviewed chunks, OpenAI
stubbed, the first source of an answer shows which entry the request selected.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval"))

import alias_audit  # noqa: E402
import api  # noqa: E402
from tests.test_saint_menus import ask, assert_answer_about, choose, entry_chunk, v2  # noqa: E402,F401

ROWS = json.loads((ROOT / "data/saint_defaults.json").read_text(encoding="utf-8"))["defaults"]
ACTIVE = [row for row in ROWS if row.get("active", True)]


def arabic_question(row):
    return f"من هي القديسة {row['name_ar']}؟" if row.get("feminine") else f"من هو القديس {row['name_ar']}؟"


def test_every_line_has_a_reason_and_active_lines_a_target():
    for row in ROWS:
        assert row.get("reason"), row["name_en"]
        if row.get("active", True):
            assert row.get("target") and row.get("en") and row.get("ar"), row["name_en"]


# ---------------------------------------------------------------- the defaults


@pytest.mark.parametrize("row", ACTIVE, ids=[row["name_en"] for row in ACTIVE])
def test_a_bare_english_name_goes_to_its_major_saint(v2, row):
    reply = ask(f"Who was {row['name_en']}?")
    assert_answer_about(reply, row["target"])
    others = api._namesake_menu(row["name_en"], "en")
    if others:
        assert reply["namesakes"] == {"label": f"Looking for a different {row['name_en']}?", "name": row["name_en"]}
    else:  # one entry of the name (Anthony, Demiana in English): no link
        assert "namesakes" not in reply


@pytest.mark.parametrize("row", ACTIVE, ids=[row["name_en"] for row in ACTIVE])
def test_a_bare_arabic_name_goes_to_its_major_saint(v2, row):
    reply = ask(arabic_question(row), language="ar")
    assert_answer_about(reply, row["target"], "ar")
    if api._namesake_menu(row["name_ar"], "ar"):
        assert reply["namesakes"]["name"] == row["name_ar"]
        assert reply["namesakes"]["label"].startswith("هل تبحث عن")
    else:
        assert "namesakes" not in reply


def test_the_link_opens_the_other_saints_and_a_choice_answers_that_saint(v2):
    reply = ask("Who is St. Mary?")
    link = reply["namesakes"]
    menu = ask(link["label"], mode="saints", namesakes_of=link["name"])
    assert "St. Mary, the Virgin Theotokos." not in menu["options"]
    assert "mary-the-virgin-theotokos" not in menu["option_ids"]
    assert not menu["sources"] and len(menu["options"]) == 9
    saint_id = choose(menu, "St. Mary Magdalene")
    assert_answer_about(ask("search saint: St. Mary Magdalene", mode="saints", saint_id=saint_id), "mary-magdalene")


def test_the_arabic_link_opens_the_other_saints(v2):
    reply = ask("من هو مارمرقس؟", language="ar")
    assert_answer_about(reply, "marcus-the-apostle", "ar")
    menu = ask(reply["namesakes"]["label"], mode="saints", language="ar", namesakes_of=reply["namesakes"]["name"])
    assert "marcus-the-apostle" not in menu["option_ids"] and "مرقس الثاني" in menu["options"]
    saint_id = choose(menu, "مرقس الثاني")
    assert_answer_about(ask("من هو مرقس الثاني؟", mode="saints", language="ar", saint_id=saint_id), saint_id, "ar")


def test_an_epithet_names_the_saint_but_brings_no_namesakes(v2):
    # "العذراء" alone is the Theotokos; the other virgin martyrs are not "other Marys".
    reply = ask("من هي العذراء؟", language="ar")
    assert_answer_about(reply, "mary-the-virgin-theotokos", "ar")
    menu = ask(reply["namesakes"]["label"], mode="saints", language="ar", namesakes_of=reply["namesakes"]["name"])
    assert len(menu["options"]) == 9 and all("مريم" in option for option in menu["options"])


def test_the_link_lists_every_other_saint_of_the_name(v2):
    menu = ask("هل تبحث عن قديس آخر باسم مرقس؟", mode="saints", language="ar", namesakes_of="مرقس")
    assert len(menu["options"]) == 16 and "marcus-the-apostle" not in menu["option_ids"]


def test_names_off_the_list_keep_the_menu(v2):
    # St. Paul waits for the priest ("active": false): neither dictionary has the Apostle.
    assert "Abba Paul, the First Hermit" in ask("Who was St. Paul?")["options"]
    assert len(ask("من هو القديس بولس؟", language="ar")["options"]) >= 2
    assert ask("search saint: St. Gregory", mode="saints")["option_ids"]


def test_the_dictionarys_own_name_beats_a_default(v2):
    # "مينا الشهيد" and "مينا القديس" are other Minas' entries; "St. Mina the Wonder-Maker" is named.
    assert_answer_about(ask("من هو مينا الشهيد؟", language="ar"), "mina", "ar")
    assert_answer_about(ask("من هو مينا القديس؟", language="ar"), "mina-the-release-deacon", "ar")
    assert_answer_about(ask("Who was St. Mina, the Monk?"), "mina-the-monk")


def test_calendar_and_saints_list_names_use_the_defaults(v2):
    reply = ask("search saint: St. Mary", mode="saints", saint_name="St. Mary")
    assert_answer_about(reply, "mary-the-virgin-theotokos")
    assert reply["namesakes"]["name"] == "St. Mary"
    assert_answer_about(ask("من هو مرقس؟", mode="saints", language="ar", saint_name="مرقس"), "marcus-the-apostle", "ar")


# ---------------------------------------------------------------- the alias audit


def test_every_hand_written_alias_reaches_its_own_saint(v2):
    """eval/alias_audit.py's v2 checks on the committed index: no alias reaches another saint, names
    another entry, or misses its saint (the v1 half needs the local v1 store)."""
    english = list(api._build_saint_record_index())
    arabic = list(api._build_v2_arabic_saint_records())
    problems = []
    for source, language, alias, target in alias_audit.hand_written(english, arabic):
        if language == "en":
            kind, decided, _, _, issues = alias_audit.english_findings(alias, target, english, "v2")
        else:
            kind, decided, _, _, issues = alias_audit.arabic_findings(alias, target, arabic)
        if issues:
            problems.append((issues, source, alias, kind, [r.get("name") for r in decided[:2]]))
    assert problems == []


def test_the_aliases_the_audit_fixed(v2):
    assert_answer_about(ask("Who was St. Mark the Evangelist?"), "marcus-the-apostle")
    assert_answer_about(ask("Who was St. Cyril of Alexandria?"), "cyril-i-the-24th-pope-of-alexandria")
    # The Confessor has his own entry (listed twice by the dictionary); the Nehissy entry no longer
    # answers to his name.
    kind, decided = api._arabic_saint_decision("أبانوب المعترف")
    assert kind == "entry" and decided[0]["saint_id"] in {"abanoub-the-confessor", "ar-e2072"}
    # "بولس الرسول" (no entry in the dictionary) is not found inside "ارسطوبولس الرسول".
    assert api._arabic_saint_decision("بولس الرسول")[0] == "none"
    # "Pope Cyril" names six Popes; the table no longer sends it to Cyril I.
    assert "Pope Cyril" not in {a for g in api.SAINT_ALIAS_RECORDS for a in g["english_aliases"]}


def test_v1_theotokos_names_belong_to_the_theotokos(monkeypatch):
    names = ("St. Mary", "St. Mary, the Virgin Theotokos", "St. Mary, the Virgin Confessor")
    records = [{"id": api._saint_record_id(n), "name": n, "aliases": api._saint_aliases_for_name(n)} for n in names]
    api._assign_alias_owners(records, {})
    carriers = [r["name"] for r in records if "mother of god" in api._saint_alias_keys(r)]
    assert carriers == ["St. Mary, the Virgin Theotokos"]
    monkeypatch.setattr(api, "CORPUS_V2", False)
    monkeypatch.setattr(api, "saint_record_index", records)
    kind, decided = api._english_saint_decision("Holy Virgin Mary")
    assert (kind, decided[0]["name"]) == ("entry", "St. Mary, the Virgin Theotokos")
    kind, decided = api._english_saint_decision("St. Mary")  # the defaults list: v1 has the Theotokos too
    assert (kind, decided[0]["name"]) == ("default", "St. Mary, the Virgin Theotokos")


def test_an_index_name_ending_in_a_full_stop_is_found_by_its_exact_name(v2):
    # The calendar links "St. Mary, the Virgin Theotokos." (CAL-008): the exact lookup must find it.
    record = api._find_saint_record_exact("St. Mary, the Virgin Theotokos.")
    assert record is not None and record["id"] == "mary-the-virgin-theotokos"
    reply = ask("search saint: St. Mary, the Virgin Theotokos.", mode="saints", saint_name="St. Mary, the Virgin Theotokos.")
    assert_answer_about(reply, "mary-the-virgin-theotokos")
