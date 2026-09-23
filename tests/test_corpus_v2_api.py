"""v2 citations and saint names in the API (ING-005), with v1 output unchanged. No server, no OpenAI."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import api  # noqa: E402
import corpus_runtime  # noqa: E402
from request_log import chunk_id_from_metadata  # noqa: E402

V1_META = {"source_type": "pdf", "pdf": "saints1.pdf", "page": 33, "chunk_index": 0, "title": "saints1"}


def v2_meta(chunk_id, entry, **extra):
    base = {"corpus_version": "v2", "chunk_id": chunk_id, "source_type": "pdf", "pdf": "saints1.pdf", "language": "en",
            "work": "Encyclopedia of the Saints and Fathers of the Church", "volume": 1, "content_type": "saints",
            "unit_type": "saint_entry", "unit_title": entry.upper(), "saint_name": entry, "question_no": 0,
            "page_start": 43, "page_end": 45, "printed_page_start": "33", "printed_page_end": "35"}
    return {**base, **extra}


def test_v2_labels_name_the_question_or_saint_with_printed_pages():
    saint = v2_meta("v2:sts1:saint:abanoub-el-nehissy:c2", "St. Abanoub El-Nehissy")
    assert corpus_runtime.source_label(saint) == \
        "Encyclopedia of the Saints and Fathers of the Church, Vol. 1 — St. Abanoub El-Nehissy, pp. 33–35"
    question = v2_meta("v2:cat2:q896:c1", "x", content_type="catechism", unit_type="question", unit_title="896. What is prayer?",
                       question_no=896, work="Catechism of the Coptic Orthodox Church", volume=2, pdf="catechism2.pdf",
                       printed_page_start="21", printed_page_end="21")
    assert corpus_runtime.source_label(question) == "Catechism of the Coptic Orthodox Church, Vol. 2 — Q896 “What is prayer?”, p. 21"
    arabic = {**question, "language": "ar", "work": "كاتيكيزم الكنيسة القبطية الأرثوذكسية", "volume": 0,
              "unit_title": "896. ما هي الصلاة؟", "printed_page_start": "19", "printed_page_end": "19"}
    assert corpus_runtime.source_label(arabic) == "كاتيكيزم الكنيسة القبطية الأرثوذكسية — س 896 «ما هي الصلاة؟»، ص 19"


def test_v1_sources_and_labels_are_unchanged():
    assert api._source_from_metadata(V1_META) == {"source_type": "pdf", "pdf": "saints1.pdf", "page": 33}
    assert api._friendly_source_label(V1_META) == "Encyclopedia of the Saints and Fathers of the Church, Volume 1, p. 33"
    assert chunk_id_from_metadata(V1_META) == "saints1.pdf::p33::c0"
    dumped = api.ChatResponse(answer="a", sources=[{**api._source_from_metadata(V1_META), "n": 1, "label": "L"}]).model_dump()
    assert dumped["sources"][0] == {"source_type": "pdf", "pdf": "saints1.pdf", "page": 33, "url": None, "title": None, "n": 1, "label": "L"}


def test_v2_source_keeps_pdf_page_and_adds_printed_pages_and_entry():
    meta = v2_meta("v2:sts1:saint:abanoub-el-nehissy:c2", "St. Abanoub El-Nehissy")
    source = api._source_from_metadata(meta)
    assert (source["page"], source["page_end"], source["pages"], source["entry"]) == (43, 45, "33–35", "St. Abanoub El-Nehissy")
    assert chunk_id_from_metadata(meta) == "v2:sts1:saint:abanoub-el-nehissy:c2"
    dumped = api.ChatResponse(answer="a", sources=[{**source, "n": 1, "label": "L"}]).model_dump()
    assert dumped["sources"][0]["chunk_id"] == "v2:sts1:saint:abanoub-el-nehissy:c2"


def test_two_saints_cited_from_the_same_page_are_two_sources_in_v2_only():
    first = v2_meta("v2:sts1:saint:abadion:c1", "St. Abadion", page_start=26, page_end=26)
    second = v2_meta("v2:sts1:saint:abamon:c1", "St. Abamon", page_start=26, page_end=26)
    _, numbered = api._build_numbered_context(["one", "two"], [first, second])
    sources, cited = api._cited_sources("A [1]. B [2].", numbered)
    assert [s["entry"] for s in sources] == ["St. Abadion", "St. Abamon"] and cited == 2
    _, numbered_v1 = api._build_numbered_context(["one", "two"], [V1_META, {**V1_META, "chunk_index": 1}])
    assert len(api._cited_sources("A [1]. B [2].", numbered_v1)[0]) == 1  # v1 behaviour, kept for v1


def test_saint_names_are_tidied_and_namesakes_told_apart():
    assert corpus_runtime.tidy_saint_name("Abba Bishoy, St") == "Abba Bishoy"
    assert corpus_runtime.tidy_saint_name("St. Abercius, Fr.") == "Fr. Abercius"
    records = [
        {"id": "athanasius", "name": "St. Athanasius", "descriptor": "The martyr",
         "metadata": {"volume": 1, "page_start": 280, "printed_page_start": "269"}},
        {"id": "athanasius-the-apostolic", "name": "St. Athanasius the Apostolic", "descriptor": "", "metadata": {}},
        {"id": "agathon", "name": "St. Agathon", "descriptor": "The Martyr", "metadata": {"volume": 1, "page_start": 105}},
        {"id": "agathon-2", "name": "St. Agathon", "descriptor": "The Martyr", "metadata": {"volume": 1, "page_start": 105}},
    ]
    api._disambiguate_names(records, {"athanasius": "athanasius-the-apostolic"})
    assert [r["name"] for r in records] == [
        "St. Athanasius (The martyr, vol. 1, p. 269)",
        "St. Athanasius the Apostolic",
        "St. Agathon (The Martyr, vol. 1, p. 105)",
        "St. Agathon (The Martyr, vol. 1, p. 105, entry 2)",
    ]
