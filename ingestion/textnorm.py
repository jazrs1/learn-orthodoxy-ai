"""Text normalisation shared by the extractors (INGEST_PLAN.md §3–4)."""

from __future__ import annotations

import re
import unicodedata


def _char_class(*ranges: tuple) -> str:
    """Regex character class from code-point ranges, written as numbers so the source stays readable."""
    return "[" + "".join(chr(lo) + "-" + chr(hi) for lo, hi in ranges) + "]"


NUL = chr(0)
HORIZONTAL_SPACE = re.compile("[" + chr(0x20) + chr(0x09) + chr(0xA0) + "]+")

ARABIC_LETTER = re.compile(_char_class((0x0621, 0x064A)))
ARABIC_ANY = re.compile(_char_class((0x0600, 0x06FF)))
ARABIC_INDIC_RUN = re.compile(_char_class((0x0660, 0x0669), (0x06F0, 0x06F9)) + "{2,}")
ARABIC_PRESENTATION_FORM = re.compile(_char_class((0xFB50, 0xFDFF), (0xFE70, 0xFEFF)))

# NFKC maps these fonts' presentation forms to the Persian code points; the text is Arabic.
_ARABIC_FOLD = {
    0x06CC: 0x064A,  # Farsi yeh          -> Arabic yeh
    0x06BE: 0x0647,  # heh doachashmee    -> heh
    0x06C1: 0x0647,  # heh goal           -> heh
    0x06D5: 0x0647,  # ae                 -> heh
    0x06A9: 0x0643,  # keheh              -> kaf
    0x0640: None,    # tatweel (elongation only)
    0x200C: None, 0x200D: None, 0x200E: None, 0x200F: None, 0xFEFF: None,  # ZWNJ, ZWJ, LRM, RLM, BOM
}


def normalize_arabic(text: str, balance: bool = True) -> str:
    """NFKC (presentation forms -> base letters), fold Persian look-alikes, drop tatweel and
    invisible marks, collapse whitespace, re-orient brackets, and put multi-digit Arabic-Indic
    numbers back in order (both pypdf and PyMuPDF emit them reversed, e.g. Matthew 28:20 comes out
    as 82:02; ASCII digits are not affected). Diacritics are kept: the model reads this text."""
    text = unicodedata.normalize("NFKC", text or "").replace(NUL, " ")
    text = text.translate(_ARABIC_FOLD)
    text = re.sub(r"\s+", " ", text).strip()
    text = ARABIC_INDIC_RUN.sub(lambda m: m.group(0)[::-1], text)
    return balance_mirrored_brackets(text) if balance else text


_BRACKETS = {"(": ")", "[": "]"}
_CLOSERS = {close: open_ for open_, close in _BRACKETS.items()}


def balance_mirrored_brackets(text: str, open_at_start: str = "") -> str:
    """pypdf emits brackets in RTL text in visual orientation, inconsistently: ")نظام الدولة("
    or "(كاثوليكية(". Read left to right in logical order, a closer with nothing open must be a
    mirrored opener, and an opener while the same kind is already open must be a mirrored closer.
    `open_at_start` names brackets already open when the text starts (a quotation continued from
    the previous page), which flips the reading of every bracket of that kind after it."""
    depth = {"(": open_at_start.count("("), "[": open_at_start.count("[")}
    out = []
    for ch in text:
        if ch in _BRACKETS:
            if depth[ch]:
                depth[ch] -= 1
                ch = _BRACKETS[ch]
            else:
                depth[ch] += 1
        elif ch in _CLOSERS:
            opener = _CLOSERS[ch]
            if depth[opener]:
                depth[opener] -= 1
            else:
                depth[opener] += 1
                ch = opener
        out.append(ch)
    return "".join(out)


def presentation_form_ratio(text: str) -> float:
    forms = len(ARABIC_PRESENTATION_FORM.findall(text))
    letters = len(ARABIC_LETTER.findall(text))
    return forms / max(1, forms + letters)


def normalize_whitespace(text: str) -> str:
    return HORIZONTAL_SPACE.sub(" ", (text or "").replace(NUL, " ")).strip()


def digits_key(text: str) -> str:
    """Repeated-line key: digits folded so 'Volume 2 \n300' and '... 301' compare equal."""
    return re.sub(r"\d+", "#", re.sub(r"\s+", " ", text.strip().lower()))


ROMAN = re.compile(r"^(?=[ivxlcdm]+$)m{0,3}(cm|cd|d?c{0,3})(xc|xl|l?x{0,3})(ix|iv|v?i{0,3})$", re.IGNORECASE)


def is_page_number(text: str) -> bool:
    value = text.strip()
    return bool(value) and (value.isdigit() and len(value) <= 4 or bool(ROMAN.match(value)))


def orient_page_brackets(text: str) -> str:
    """Balance a page's brackets, choosing whether a "[" quotation was already open when the page
    began. The catechism quotes the Fathers in [ ]: an opener follows a colon ("يقول: [") and a
    closer follows the footnote marker or the final period ("... 891 ]"), so the reading with more
    of those wins."""
    def score(candidate: str) -> int:
        return (len(re.findall(r":\s*\[", candidate)) + len(re.findall(r"[\d.]\s*\]", candidate))
                - len(re.findall(r":\s*\]", candidate)) - len(re.findall(r"[\d.]\s*\[", candidate)))
    plain = balance_mirrored_brackets(text)
    continued = balance_mirrored_brackets(text, open_at_start="[")
    best = continued if score(continued) > score(plain) else plain
    # A quotation still open at the end of the page runs on to the next: its opener follows a colon.
    last = best.rfind("]")
    if last > best.rfind("[") and re.search(r":\s*$", best[:last]):
        best = best[:last] + "[" + best[last + 1:]
    return best


# pypdf puts a line-final period before the line's last word in some RTL pages: "وسقط . ميتًا اضطهاد"
# is "وسقط ميتًا. اضطهاد", "إكليل .الاستشهاد نحتفل" is "إكليل الاستشهاد. نحتفل". A space before a
# period is otherwise not written; a space before a colon is ("يقول : ..."), so colons are left alone.
# After a number the period is the number's own: "318 .ما هو" is the question "318. ما هو"
# ("1969 . باقات", with spaces on both sides, ends a book title and is left alone).
DISPLACED_PUNCTUATION = re.compile(r"(?<=[^\s\d]) \. ?(" + _char_class((0x0621, 0x064A)) + r"\S*)")
NUMBER_PERIOD = re.compile(r"(?<=\d) \.(?=" + _char_class((0x0621, 0x064A)) + ")")


def fix_displaced_punctuation(text: str) -> str:
    text = DISPLACED_PUNCTUATION.sub(lambda m: f" {m.group(1)}.", text)
    return NUMBER_PERIOD.sub(". ", text)
