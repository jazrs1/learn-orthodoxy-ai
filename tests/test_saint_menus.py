"""Namesake menus (RET-010): question -> menu -> choice by saint ID -> answer led by that entry.

The v2 saint records are built from the committed saints index and reviewed chunks
(data/corpus/v2), as the API builds them from Chroma. No server, no OpenAI: task analysis is off,
vector search returns one unrelated passage, and the model answer cites passage [1], so the first
source shows which entry the request selected.
"""

import gzip
import json
import os
import sys
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import api  # noqa: E402
import corpus_runtime  # noqa: E402
from request_log import RequestTrace  # noqa: E402

NOISE_EN = "v2:sts1:saint:abanoub-el-nehissy:c1"


class FakeCollection:
    """The part of a Chroma collection the saint code reads: get by ids or by one metadata field."""

    def __init__(self, rows):
        self.rows = rows
        self.by_id = {row["id"]: row for row in rows}

    def get(self, ids=None, where=None, include=None, limit=None, offset=None):
        if ids is not None:
            rows = [self.by_id[i] for i in ids if i in self.by_id]
        elif where:
            (field, value), = where.items()
            rows = [row for row in self.rows if row["metadata"].get(field) == value]
        else:
            rows = self.rows[offset or 0:(offset or 0) + (limit or len(self.rows))]
        return {"ids": [r["id"] for r in rows], "documents": [r["document"] for r in rows],
                "metadatas": [r["metadata"] for r in rows]}

    def count(self):
        return len(self.rows)


@lru_cache(maxsize=1)
def saint_chunks():
    """The reviewed v2 saints chunks, by language."""
    rows = {"en": [], "ar": []}
    with gzip.open(ROOT / "data/corpus/v2/chunks.jsonl.gz", "rt", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            if row["metadata"].get("content_type") == "saints":
                rows[row["metadata"]["language"]].append(row)
    return rows


class FakeCompletions:
    def create(self, **kwargs):
        message = SimpleNamespace(content="This saint is described in the passage [1].")
        usage = SimpleNamespace(prompt_tokens=1, completion_tokens=1, total_tokens=2)
        return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason="stop")], usage=usage)


@pytest.fixture
def v2(monkeypatch):
    chunks = saint_chunks()
    english, arabic = FakeCollection(chunks["en"]), FakeCollection(chunks["ar"])
    noise = {"en": english.by_id[NOISE_EN], "ar": chunks["ar"][0]}

    def retrieve(queries, top_k, entity=None, target_collection=None, **kwargs):
        row = noise["ar"] if target_collection is arabic else noise["en"]
        return [row["document"]], [row["metadata"]], [0.9]

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(api, "CORPUS_V2", True)
    monkeypatch.setattr(api, "TASK_ANALYSIS_ENABLED", False)
    monkeypatch.setattr(api, "collection", english)
    monkeypatch.setattr(api, "arabic_collection", arabic)
    monkeypatch.setattr(api, "oai_client", SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions())))
    monkeypatch.setattr(api, "_retrieve_documents", retrieve)
    monkeypatch.setattr(api, "_retrieve_arabic_lexical_documents", lambda *a, **k: ([], []))
    for cache in ("saint_record_index", "saint_name_index", "arabic_v2_saint_records", "arabic_saint_name_index"):
        monkeypatch.setattr(api, cache, [])
    return SimpleNamespace(english=english, arabic=arabic)


def ask(question, mode="chat", language="en", **selection):
    request = api.ChatRequest(question=question, mode=mode, language=language, **selection)
    with RequestTrace("chat") as trace:
        payload = api._chat_impl(request, trace)
    # Validated the way FastAPI sends it.
    return api.ChatResponse(**payload).model_dump()


def entry_chunk(saint_id, language):
    """The first chunk id of a saint's own entry in that language."""
    saint = next(s for s in corpus_runtime.load_saints_index() if s["id"] == saint_id)
    entry = next(e for e in saint["entries"] if e["lang"] == language)
    return corpus_runtime.first_chunk_id(entry)


def choose(menu, label):
    """The ID the frontend sends for the chip with this label."""
    assert menu["options"] and len(menu["option_ids"]) == len(menu["options"]), menu
    return menu["option_ids"][menu["options"].index(label)]


def assert_answer_about(reply, saint_id, language="en"):
    assert not reply["options"], reply["options"]
    assert reply["sources"], reply["answer"]
    assert reply["sources"][0]["chunk_id"] == entry_chunk(saint_id, language)


def pick(question, label, mode="chat", language="en"):
    """Ask, get a menu, then send the chosen entry's ID back the way a chip does."""
    menu = ask(question, mode=mode, language=language)
    saint_id = choose(menu, label)
    chip_question = f"من هو {label}؟" if language == "ar" else f"search saint: {label}"
    return saint_id, ask(chip_question, mode="saints", language=language, saint_id=saint_id)


# ---------------------------------------------------------------- English


def test_the_apostolic_goes_straight_to_him(v2):
    reply = ask("Who was St. Athanasius the Apostolic?")
    assert_answer_about(reply, "athanasius-the-apostolic-the-20th-pope-of-alexandria")
    assert "option_ids" not in reply


def test_bare_athanasius_goes_to_the_apostolic_and_the_link_lists_the_others(v2):
    # RET-011: bare "St. Athanasius" is the Apostolic (data/saint_defaults.json); the other six are
    # one click away, and each choice reaches its entry by ID.
    reply = ask("Who was St. Athanasius?")
    assert_answer_about(reply, "athanasius-the-apostolic-the-20th-pope-of-alexandria")
    link = reply["namesakes"]
    menu = ask(link["label"], mode="saints", namesakes_of=link["name"])
    assert len(menu["options"]) == 6 and not menu["sources"]
    for label in ("St. Athanasius (The martyr, vol. 1, p. 269)", "St. Athanasius II, the 28th Pope of Alexandria"):
        saint_id = choose(menu, label)
        assert_answer_about(ask(f"search saint: {label}", mode="saints", saint_id=saint_id), saint_id)


def test_the_reported_loop_is_gone(v2):
    """The owner's report: choosing the Apostolic brought the same menu back."""
    menu = ask("Who was St. Athanasius the Apostolic?")
    assert not menu["options"]
    # Even the chip text alone (as saved menus without IDs send it) reaches him.
    reply = ask("search saint: St. Athanasius the Apostolic, the 20th Pope of Alexandria", mode="saints")
    assert_answer_about(reply, "athanasius-the-apostolic-the-20th-pope-of-alexandria")


def test_a_choice_is_selected_by_id_whatever_the_text_says(v2):
    reply = ask("search saint: St. Athanasius", mode="saints", saint_id="athanasius")
    assert_answer_about(reply, "athanasius")


def test_the_agathons(v2):
    menu = ask("search saint: St. Agathon", mode="saints")
    assert len(menu["options"]) == 5 and len(set(menu["option_ids"])) == 5
    # Two entries share the descriptor "The Martyr" on the same page; their IDs keep them apart.
    for label in ("St. Agathon (The Martyr, vol. 1, p. 105)", "St. Agathon (The Martyr, vol. 1, p. 105, entry 2)",
                  "St. Agathon, the 39th Pope"):
        saint_id, reply = pick("search saint: St. Agathon", label, mode="saints")
        assert_answer_about(reply, saint_id)
    assert_answer_about(ask("Who was St. Agathon the Stylite?"), "agathon-the-stylite")
    assert ask("Who was St. Agathon the Martyr?")["option_ids"] == ["agathon", "agathon-2"]


def test_the_gregorys(v2):
    menu = ask("search saint: St. Gregory", mode="saints")
    assert len(menu["options"]) == 6
    saint_id, reply = pick("search saint: St. Gregory", "St. Gregory the Nazianzus", mode="saints")
    assert saint_id == "gregory-the-nazianzus"
    assert_answer_about(reply, saint_id)
    assert_answer_about(ask("Who was St. Gregory of Nyssa?"), "gregory-of-nyssa")


def test_the_anthonys(v2):
    # The English encyclopedia has one Anthony: no menu.
    assert_answer_about(ask("search saint: St. Anthony", mode="saints"), "anthony-father-of-the-monks")
    assert_answer_about(ask("Who was St. Anthony the Great?"), "anthony-father-of-the-monks")


def test_the_great_martyr_and_of_alexandria(v2):
    assert_answer_about(ask("Tell me about St. George the Great Martyr"), "george-the-capaducian")
    assert_answer_about(ask("Who was St. Athanasius of Alexandria?"), "athanasius-the-apostolic-the-20th-pope-of-alexandria")
    assert_answer_about(ask("Who was St. Athanasius the Martyr?"), "athanasius")


def test_saints_list_and_calendar_names_select_one_entry(v2):
    # "St. Athanasius" on the calendar is the Apostolic's feast (curated), not a menu.
    reply = ask("search saint: St. Athanasius", mode="saints", saint_name="St. Athanasius")
    assert_answer_about(reply, "athanasius-the-apostolic-the-20th-pope-of-alexandria")


def test_an_unknown_id_falls_back_to_the_question(v2):
    assert_answer_about(ask("search saint: St. Gregory of Nyssa", mode="saints", saint_id="no-such-saint"), "gregory-of-nyssa")


# ---------------------------------------------------------------- Arabic


def test_arabic_apostolic_goes_straight_to_him(v2):
    assert_answer_about(ask("من هو القديس أثناسيوس الرسولي؟", language="ar"),
                        "athanasius-the-apostolic-the-20th-pope-of-alexandria", "ar")


def test_arabic_bare_athanasius_goes_to_the_apostolic_and_the_link_lists_the_others(v2):
    reply = ask("من هو القديس أثناسيوس؟", language="ar")
    assert_answer_about(reply, "athanasius-the-apostolic-the-20th-pope-of-alexandria", "ar")
    link = reply["namesakes"]
    menu = ask(link["label"], mode="saints", language="ar", namesakes_of=link["name"])
    assert len(menu["options"]) == 6
    saint_id = choose(menu, "أثناسيوس الشهيد")
    assert saint_id == "athanasius"
    assert_answer_about(ask("من هو أثناسيوس الشهيد؟", mode="saints", language="ar", saint_id=saint_id), saint_id, "ar")


def test_arabic_agathons(v2):
    saint_id, reply = pick("من هو القديس أغاثون؟", "أغاثون العمودي القديس", language="ar")
    assert saint_id == "agathon-the-stylite"
    assert_answer_about(reply, saint_id, "ar")
    assert_answer_about(ask("من هو أغاثون العمودي؟", language="ar"), "agathon-the-stylite", "ar")


def test_arabic_gregorys(v2):
    menu = ask("من هو القديس غريغوريوس؟", language="ar")
    assert len(menu["options"]) == 6
    saint_id, reply = pick("من هو القديس غريغوريوس؟", "إغريغوريوس ( غريغوريوس ) النزينزي القديس", language="ar")
    assert_answer_about(reply, saint_id, "ar")
    assert_answer_about(ask("من هو القديس غريغوريوس النزينزي؟", language="ar"), saint_id, "ar")


def test_arabic_anthonys(v2):
    # Bare "أنطونيوس" is the Father of the Monks (RET-011); the martyr is behind the link.
    reply = ask("من هو القديس أنطونيوس؟", language="ar")
    assert_answer_about(reply, "anthony-father-of-the-monks", "ar")
    menu = ask(reply["namesakes"]["label"], mode="saints", language="ar", namesakes_of=reply["namesakes"]["name"])
    assert menu["options"] == ["أنطونيوس الشهيد"]
    saint_id = choose(menu, "أنطونيوس الشهيد")
    assert_answer_about(ask("من هو أنطونيوس الشهيد؟", mode="saints", language="ar", saint_id=saint_id), saint_id, "ar")
    assert_answer_about(ask("من هو الأنبا أنطونيوس الكبير؟", language="ar"), "anthony-father-of-the-monks", "ar")


def test_arabic_questions_about_other_things_get_no_menu(v2):
    reply = ask("من هو المسيح؟", language="ar")
    assert not reply["options"]


# ---------------------------------------------------------------- v1: the same code path


def test_v1_alias_table_no_longer_makes_the_apostolic_ambiguous(monkeypatch):
    """v1 looped the same way: the hand-written alias table gave both v1 Athanasius records each
    other's names, so each choice matched both and brought the menu back."""
    records = [
        {"id": api._saint_record_id(name), "name": name, "aliases": api._saint_aliases_for_name(name)}
        for name in ("St. Athanasius", "St. Athanasius the Apostolic,", "St. Athanasius, Bishop of Qus")
    ]
    both = [r for r in records if "athanasius apostolic" in api._saint_alias_keys(r)]
    assert len(both) == 2  # the cause, before ownership is assigned
    api._assign_alias_owners(records, {})
    monkeypatch.setattr(api, "CORPUS_V2", False)
    monkeypatch.setattr(api, "saint_record_index", records)
    kind, decided = api._english_saint_decision("St. Athanasius the Apostolic")
    assert (kind, [r["name"] for r in decided]) == ("entry", ["St. Athanasius the Apostolic,"])
    kind, decided = api._english_saint_decision("St. Athanasius of Alexandria")
    assert (kind, [r["name"] for r in decided]) == ("entry", ["St. Athanasius the Apostolic,"])
    # Bare, it is the Apostolic by the defaults list (RET-011), with the other two behind the link.
    kind, decided = api._english_saint_decision("St. Athanasius")
    assert kind == "default" and [r["name"] for r in decided][0] == "St. Athanasius the Apostolic,"
    assert {r["name"] for r in decided[1:]} == {"St. Athanasius", "St. Athanasius, Bishop of Qus"}
