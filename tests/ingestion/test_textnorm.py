"""Arabic and whitespace normalisation (INGEST_PLAN.md §4). Characters are built with chr() so the
test source stays plain ASCII-safe for every editor."""

from ingestion.textnorm import (
    balance_mirrored_brackets,
    digits_key,
    is_page_number,
    normalize_arabic,
    normalize_whitespace,
    presentation_form_ratio,
)


def s(*codes: int) -> str:
    return "".join(map(chr, codes))


def test_presentation_forms_become_base_letters():
    # "المحبوسين" as isolated/initial/medial/final presentation forms, as pypdf emits it
    glyphs = s(0xFE8D, 0xFEDF, 0xFEE4, 0xFEA4, 0xFE92, 0xFEEE, 0xFEB3, 0xFBFF, 0xFEE6)
    assert presentation_form_ratio(glyphs) == 1.0
    out = normalize_arabic(glyphs)
    assert out == "المحبوسين"
    assert presentation_form_ratio(out) == 0.0


def test_lam_alef_ligature_is_logical_order():
    # U+FEFB (lam-alef ligature) must become lam + alef, not alef + lam
    assert normalize_arabic(s(0xFEFB)) == "لا"


def test_persian_lookalikes_are_folded():
    farsi_yeh, heh_doachashmee, keheh = s(0x06CC), s(0x06BE), s(0x06A9)
    assert normalize_arabic("في" + farsi_yeh + " " + heh_doachashmee + "ذا " + keheh + "تاب") == "فيي هذا كتاب"


def test_tatweel_and_invisible_marks_removed_diacritics_kept():
    text = "كـــتاب" + s(0x200F) + " الحُكْمَ"
    assert normalize_arabic(text) == "كتاب الحُكْمَ"


def test_nul_and_whitespace():
    assert normalize_arabic("أ" + s(0) + "ب\n\n ج") == "أ ب ج"
    assert normalize_whitespace("a" + s(0xA0) + " b" + s(9) + "c") == "a b c"


def test_arabic_indic_numbers_are_reordered_ascii_untouched():
    reversed_ref = "مت " + s(0x668, 0x662) + ": " + s(0x660, 0x662)  # "مت ٨٢: ٠٢" as extracted
    assert normalize_arabic(reversed_ref) == "مت " + s(0x662, 0x668) + ": " + s(0x662, 0x660)  # Matthew 28:20
    assert normalize_arabic("1215. سؤال") == "1215. سؤال"
    assert normalize_arabic("٥") == "٥"


def test_mirrored_brackets_are_balanced():
    assert balance_mirrored_brackets("(كاثوليكية(؟") == "(كاثوليكية)؟"
    assert balance_mirrored_brackets(")أف ٤ : ١١ - ١٢ (.") == "(أف ٤ : ١١ - ١٢ )."
    assert balance_mirrored_brackets("(نظام الدولة) أهم") == "(نظام الدولة) أهم"
    assert balance_mirrored_brackets("(أ) (ب)") == "(أ) (ب)"


def test_page_numbers_and_header_keys():
    assert is_page_number("361") and is_page_number("xiv") and is_page_number("x")
    assert not is_page_number("Book 3") and not is_page_number("12345")
    assert digits_key("Catechism – Volume 2 ") == digits_key("catechism – volume 7")
