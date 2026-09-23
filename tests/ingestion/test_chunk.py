"""Sentence splitting, packing, overlap and headers (INGEST_PLAN.md §5.4, §6)."""

import pytest

from ingestion.chunk import LIMITS, OVERLAP_SHARE, chunk_text, chunk_unit, pack, pieces_of, split_sentences
from ingestion.corpus import chunk_header, unit_chunks
from ingestion.structure import Block, Unit


def sentences(text, language="en"):
    return [text[a:b].strip() for a, b in split_sentences(text, language)]


def test_sentence_split_keeps_abbreviations_together():
    text = "St. Mark came to Alexandria in A.D. 61. Fr. Tadros cites p. 12 of vol. 2. J. Smith agrees! Does he?"
    assert sentences(text) == [
        "St. Mark came to Alexandria in A.D. 61.",
        "Fr. Tadros cites p. 12 of vol. 2.",
        "J. Smith agrees!",
        "Does he?",
    ]


def test_arabic_sentences_split_on_arabic_question_mark():
    text = "ما هو الإيمان؟ الإيمان هو الثقة بما يُرجى. والإيقان بأمور لا تُرى."
    assert len(sentences(text, "ar")) == 3


def unit_of(paragraphs, language="en", pages=None):
    unit = Unit("cat2", language, "catechism", "question", "q896", "896. What is prayer?", "Book 4 › The Life of Prayer",
                question_no=896)
    for index, text in enumerate(paragraphs):
        page = pages[index] if pages else 20
        unit.blocks.append(Block(text, page, page))
    return unit


def long_paragraph(n, word="prayer"):
    return " ".join(f"The {word} of the Church number {i} lifts the heart to God." for i in range(n))


def test_chunks_respect_the_maximum_and_overlap_within_the_unit():
    unit = unit_of([long_paragraph(40), long_paragraph(40, "fast"), long_paragraph(40, "psalm")])
    chunks = chunk_unit(unit)
    minimum, _, maximum = LIMITS["en"]
    assert len(chunks) > 2
    assert all(c.size <= maximum for c in chunks)
    for previous, current in zip(chunks, chunks[1:]):
        repeated = current.pieces[: current.overlap]
        assert [p.text for p in repeated] == [p.text for p in previous.pieces[len(previous.pieces) - len(repeated):]]
        assert sum(p.size for p in repeated) <= maximum * OVERLAP_SHARE
        assert current.overlap < len(current.pieces)  # never a whole repeated chunk


def test_a_short_unit_stays_one_chunk():
    unit = unit_of(["Prayer is conversation with God.", "It needs a pure heart."])
    chunks = chunk_unit(unit)
    assert len(chunks) == 1
    assert chunk_text(chunks[0]) == "Prayer is conversation with God.\n\nIt needs a pure heart."


def test_no_thin_last_chunk():
    unit = unit_of([long_paragraph(33), "One more short line ends it."])
    chunks = chunk_unit(unit)
    minimum = LIMITS["en"][0]
    assert all(c.size >= minimum * 0.5 for c in chunks)


def test_pages_follow_sentences_across_a_page_break():
    unit = unit_of([])
    unit.add("The first page ends in the middle of a", 20)
    unit.add("sentence that the next page finishes. Then a new one starts on page 21.", 21)
    assert len(unit.blocks) == 1
    pieces = pieces_of(unit)
    assert (pieces[0].page_start, pieces[0].page_end) == (20, 21)
    assert (pieces[1].page_start, pieces[1].page_end) == (21, 21)


def test_block_split_keeps_pages():
    block = Block("aaaa bbbb cccc", 5, 6, page_breaks=[(10, 6)])
    head, tail = block.split(5)
    assert (head.text, head.page_start, head.page_end) == ("aaaa", 5, 5)
    assert (tail.text, tail.page_start, tail.page_end, tail.page_breaks) == ("bbbb cccc", 5, 6, [(5, 6)])


def test_headers_carry_the_unit_into_every_chunk():
    unit = unit_of([long_paragraph(60)])
    chunks = unit_chunks(unit, {20: "10"}, None)
    assert len(chunks) > 1
    header = "Catechism, Book 4 › The Life of Prayer — 896. What is prayer?"
    assert all(c.document.startswith(header + "\n\n") for c in chunks)
    assert [c.id for c in chunks] == [f"v2:cat2:q896:c{i}" for i in range(1, len(chunks) + 1)]


def test_metadata_is_flat_and_complete():
    chunks = unit_chunks(unit_of(["Prayer is conversation with God."]), {20: "10"}, None)
    meta = chunks[0].metadata
    assert all(isinstance(v, (str, int, float, bool)) for v in meta.values())
    for field in ("chunk_id", "corpus_version", "doc_id", "source_type", "pdf", "url", "work", "volume", "author", "language",
                  "content_type", "unit_type", "unit_id", "unit_title", "section_path", "subsection", "question_no", "saint_id",
                  "saint_name", "ref_book", "ref_chapter_start", "ref_verse_start", "ref_chapter_end", "ref_verse_end",
                  "page_start", "page_end", "printed_page_start", "printed_page_end", "chunk_index", "chunk_count",
                  "token_count", "extractor", "normalizer", "text_sha1", "synaxarion_date", "western_date"):
        assert field in meta, field
    assert (meta["pdf"], meta["printed_page_start"], meta["question_no"]) == ("catechism2.pdf", "10", 896)


@pytest.mark.parametrize("unit, expected", [
    (Unit("sts1", "en", "saints", "saint_entry", "saint:abanoub", "ABANOUB EL-NEHISSY (The martyr)",
          saint_heading="ABANOUB EL-NEHISSY (The martyr)"), "Saint: ABANOUB EL-NEHISSY (The martyr)"),
    (Unit("ar-sts", "ar", "saints", "saint_entry", "e0001", "واخس الشهيد", saint_heading="واخس الشهيد"), "سيرة: واخس الشهيد"),
    (Unit("ar-cat", "ar", "catechism", "question", "q1", "1. ما هو الإيمان؟", "الكتاب الأول"),
     "الكاتيكيزم، الكتاب الأول — 1. ما هو الإيمان؟"),
    (Unit("web-1", "en", "web", "web_section", "s1", "Why Chalcedon?", "The Coptic Church"), "The Coptic Church — Why Chalcedon?"),
])
def test_chunk_headers(unit, expected):
    assert chunk_header(unit) == expected
