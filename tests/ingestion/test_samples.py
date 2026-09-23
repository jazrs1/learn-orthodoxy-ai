"""The 20 sample pages from Step 0: golden before/after files plus explicit checks of each fix.

If extraction changes on purpose, regenerate with `python -m ingestion samples --write` and review
the diff of tests/ingestion/golden/ and SAMPLES.md.
"""

import re

import pytest

from ingestion import extract_ar, extract_en, samples
from ingestion.textnorm import ARABIC_PRESENTATION_FORM

from .conftest import needs_pdfs

pytestmark = needs_pdfs

SAMPLES = {(s.doc_id, s.page): s for s in samples.SAMPLES}


@pytest.fixture(scope="module")
def en_pages():
    pages = {}
    for doc_id in ("cat1", "cat2", "sts1", "sts2", "sts3", "sts4"):
        numbers = [p for d, p in SAMPLES if d == doc_id]
        for page in extract_en.extract_pages(doc_id, numbers):
            pages[(doc_id, page.page)] = page
    return pages


@pytest.fixture(scope="module")
def ar_pages():
    pages = {}
    for doc_id in ("ar-cat", "ar-sts"):
        numbers = [p for d, p in SAMPLES if d == doc_id]
        for page in extract_ar.extract_pages(doc_id, numbers):
            pages[(doc_id, page.page)] = page
    return pages


@pytest.mark.parametrize("sample", samples.SAMPLES, ids=lambda s: f"{s.doc_id}-p{s.page}")
def test_matches_golden(sample):
    before_path, after_path = samples.golden_paths(sample)
    assert samples.before_text(sample) + "\n" == before_path.read_text(encoding="utf-8"), "pypdf output changed"
    assert samples.render_after(sample, samples.after_record(sample)) == after_path.read_text(encoding="utf-8")


@pytest.mark.parametrize("sample", [s for s in samples.SAMPLES if s.fixed], ids=lambda s: f"{s.doc_id}-p{s.page}")
def test_pypdf_split_words_are_fixed(sample, en_pages):
    before = samples.before_text(sample)
    after = en_pages[(sample.doc_id, sample.page)].text
    for artefact, clean in sample.fixed:
        assert artefact in before, f"v1 no longer shows {artefact!r}; update the sample"
        assert artefact not in after
        assert clean in after


def test_catechism_running_headers_and_page_numbers(en_pages):
    page = en_pages[("cat1", 371)]
    assert page.removed["header"] == ["Book 3: The Church: The Kingdom of God"]
    assert page.printed_page == "361"
    assert not page.text.startswith("Book 3")
    assert en_pages[("cat2", 16)].removed["header"] == ["Catechism of the Coptic Orthodox Church – Volume 2"]
    assert en_pages[("cat2", 16)].printed_page == "6"


def test_catechism_footnotes_leave_the_body(en_pages):
    page = en_pages[("cat2", 31)]
    assert [n.number for n in page.footnotes] == [37, 38, 39, 40, 41, 42]
    assert page.footnotes[1].text.endswith("28.1: p. 212.")  # continuation line joined to note 38
    assert page.markers == [37, 38, 39, 40, 41, 42]
    assert "St. John Climacus: Ladder" not in page.text  # note text is gone from the body
    assert "896. What is prayer?" in page.text  # the question heading stays


def test_superscript_ordinals_are_not_markers(en_pages):
    # "4th Century" in the Abanoub entry: a superscript word, not a footnote number
    page = en_pages[("sts1", 33)]
    assert page.markers == []
    assert re.search(r"4\s?th Century", page.text)


def test_saint_entry_heading_survives(en_pages):
    page = en_pages[("sts1", 33)]
    assert page.text.startswith("ABANOUB EL-NEHISSY")
    heading = [line for line in page.lines if line.text == "ABANOUB EL-NEHISSY"][0]
    assert heading.bold and heading.size == 14


def test_letter_divider_and_front_matter(en_pages):
    assert en_pages[("sts2", 143)].removed["divider"] == ["G"]
    front = en_pages[("cat1", 10)]
    assert front.printed_page == "x" and front.text == ""


@pytest.mark.parametrize("key", [k for k in SAMPLES if k[0].startswith("ar-")], ids=lambda k: f"{k[0]}-p{k[1]}")
def test_arabic_is_normalised(key, ar_pages):
    page = ar_pages[key]
    assert not ARABIC_PRESENTATION_FORM.search(page.text)
    assert "\n" not in page.text
    for reversed_form in ("اإل", "البالد", "ألنها", "هللا"):  # PyMuPDF's lam-alef reversal must not appear
        assert reversed_form not in page.text
    assert page.printed_page and page.printed_page not in page.text.split(" ")[-3:]


def test_arabic_ligatures_and_logical_order(ar_pages):
    text = ar_pages[("ar-sts", 100)].text
    for word in ("الإمبراطوري", "لا تريد", "لأنها", "القديسين"):
        assert word in text


def test_arabic_catechism_footnotes_and_markers(ar_pages):
    page = ar_pages[("ar-cat", 212)]
    assert [n.number for n in page.footnotes] == [592, 593, 594, 595, 596, 597, 598]
    assert "City of God" not in page.text and "Hexameron" not in page.text
    assert sorted(page.markers) == [592, 593, 594, 595, 596, 597, 598]
    assert "(نظام الدولة)" in page.text
    assert "1215." in page.text  # a question number is never taken for a marker


def test_arabic_verse_numbers_are_in_order(ar_pages):
    text = ar_pages[("ar-cat", 400)].text
    assert "أف ٤ : ١١ - ١٢" in text  # Ephesians 4:11-12, emitted reversed by the PDF


def test_arabic_page_pymupdf_mangles_is_complete(ar_pages):
    text = ar_pages[("ar-sts", 1500)].text
    assert "الثيؤلوغوس" in text and "براعته" in text
