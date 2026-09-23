"""Segmentation helpers (INGEST_PLAN.md §5.1–5.3) and the Arabic page fixes found in Step 2."""

import pytest

from ingestion.extract_en import Line, paragraph_groups
from ingestion.structure import (
    Block,
    Unit,
    _endnote_runs,
    _recover_unbookmarked,
    _take_heading,
    catechism_en_units,
    saint_display_name,
    saints_en_units,
)
from ingestion.textnorm import fix_displaced_punctuation, orient_page_brackets

from .conftest import needs_pdfs


def line(text, y0, block, size=12.0, bold=False):
    return Line(text, size, bold, y0, y0 + 0.017, 0.15, block)


def test_wrapped_list_item_in_its_own_block_stays_one_paragraph():
    lines = [
        line("a. Feast of the Apostles (5th Epep) on which the Lakkan or Liturgy of the", 0.712, 20),
        line("Waters is prayed (also prayed on the Theophany).", 0.7321, 21),
        line("b. St. Joseph the Carpenter (26th Epep).", 0.7597, 22),
    ]
    assert [len(g) for g in paragraph_groups(lines)] == [2, 1]


def test_new_paragraph_after_a_sentence_end_or_a_list_marker():
    lines = [line("First paragraph ends here.", 0.30, 1), line("Second paragraph.", 0.319, 2),
             line("a. an item without a period", 0.338, 3), line("b. another item", 0.357, 4)]
    assert [len(g) for g in paragraph_groups(lines)] == [1, 1, 1, 1]


@pytest.mark.parametrize("heading, expected", [
    ("ABANOUB EL-NEHISSY (The martyr)", ("St. Abanoub El-Nehissy", "The martyr")),
    ("MACROBIUS (Macrawy), ST.", ("St. Macrobius", "")),
])
def test_saint_display_name(heading, expected):
    assert saint_display_name(heading) == expected


def test_arabic_heading_is_the_candidate_the_body_starts_with():
    candidates = [("يولوجيوس (أولوجيوس) الراهب", "Eulogius", True), ("يولوجيوس (أولوجيوس) الأسقف المعترف", "", True)]
    body = "يولوجيوس (أولوجيوس) الأسقف المعترف كان أسقفًا على الإسكندرية"
    heading, latin, rest, how = _take_heading(body, candidates)
    assert (heading, latin, how) == ("يولوجيوس (أولوجيوس) الأسقف المعترف", "", "font")
    assert rest.startswith("كان")


def test_arabic_heading_falls_back_to_the_words_before_the_latin_name():
    heading, latin, rest, how = _take_heading("نارسيسوس الأسقف الشهيد St. Narcissus وُلد في الشرق", [])
    assert (heading, latin, how) == ("نارسيسوس الأسقف الشهيد", "St. Narcissus", "before-latin")
    assert rest.startswith("وُلد")


def test_unbookmarked_question_is_split_out():
    unit = Unit("ar-cat", "ar", "catechism", "question", "q263", "263. سؤال؟", "path", question_no=263)
    unit.blocks = [Block("جواب السؤال الأول. 264. ما هي علاقة العناية الإلهية بالنعمة؟ جواب الثاني.", 663, 664,
                         page_breaks=[(60, 664)])]
    units = [unit]
    assert _recover_unbookmarked(units, {263}) == [264]
    assert [u.unit_id for u in units] == ["q263", "q264"]
    assert units[0].body_text == "جواب السؤال الأول."
    assert units[1].title == "264. ما هي علاقة العناية الإلهية بالنعمة؟"
    assert units[1].body_text == "جواب الثاني."
    assert units[1].page_end == 664


def test_web_endnote_lists_are_separated():
    paragraphs = ["Body text.", "[610] In fact, Dioscorus was not violent but the Nestorians were, as the emperor saw.",
                  "More body.", "[139] Danielou, vol. 1.", "[140] Eusebius 6:21.", "[141] Fairwhether, p50."]
    assert _endnote_runs(paragraphs) == [False, False, False, True, True, True]


def test_displaced_final_period_moves_back():
    assert fix_displaced_punctuation("وسقط . ميتًا اضطهاد") == "وسقط ميتًا. اضطهاد"
    assert fix_displaced_punctuation("إكليل .الاستشهاد نحتفل") == "إكليل الاستشهاد. نحتفل"
    assert fix_displaced_punctuation("318 .ما هو موقف") == "318. ما هو موقف"
    for unchanged in ("الأبد. وفى", "1969 . باقات عطرة", "يقول ... ثم", "(أع 5 : 1 ، 2 .)"):
        assert fix_displaced_punctuation(unchanged) == unchanged


def test_quotation_brackets_continued_from_the_previous_page():
    # pypdf's mirrored stream for: "... end of a quote] says: [quote 891] as he says: [open..."
    mirrored = "نهاية الاقتباس [. يقول: ] اقتباس 891 [ كما يقول: ] بداية"
    assert orient_page_brackets(mirrored) == "نهاية الاقتباس ]. يقول: [ اقتباس 891 ] كما يقول: [ بداية"


@needs_pdfs
def test_english_catechism_vol2_finds_every_question():
    units, stats = catechism_en_units("cat2")
    questions = [u for u in units if u.unit_type == "question"]
    assert stats["questions_missing"] == []
    assert [u.question_no for u in questions] == list(range(878, 1453))
    assert all(u.section_path.startswith("Book ") for u in questions)
    assert not any(u.section_path[-1].isdigit() for u in units)  # no glued footnote markers


@needs_pdfs
def test_saints_vol4_keeps_reference_lines():
    units, stats = saints_en_units("sts4")
    assert stats["entries"] > 400
    assert stats["entries_with_references"] > 300
    refs = [r for u in units for r in u.references]
    assert all(r.startswith("[") for r in refs)
    entry = next(u for u in units if u.saint_heading.startswith("SANAA, THE SOLDIER"))
    assert "[Synaxarion: 4 Baramouda]" in entry.references
