import argparse
import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Tuple

from pypdf import PdfReader

DEFAULT_PDF_PATH = Path("data/pdfs/full saints arabic.pdf")
DEFAULT_OUTPUT_PATH = Path("data/saints_ar_generated.json")

BODY_CUE_PATTERN = re.compile(
    r"\s+(?:نشأته|نشأتها|حياته|حياتها|سيرته|سيرتها|طفولته|كان|كانت|عاش|عاشت|ولد|ولدت|وُلد|قال|سأل|يروي|روى|لما|إذ|القتل|لقاء)\b"
)
ENTRY_MARKER = "\u271e"


def contains_arabic(value: str) -> bool:
    return bool(re.search(r"[\u0600-\u06ff]", value or ""))


def normalize_arabic_display(value: str) -> str:
    text = normalize_arabic_text(value)
    return re.sub(r"\s+", " ", text).strip()


def normalize_arabic_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "")
    text = text.replace("ی", "ي").replace("ک", "ك").replace("ھ", "ه")
    text = text.replace("\u0640", "")
    return text


def normalize_arabic_key(value: str) -> str:
    text = normalize_arabic_display(value)
    text = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    text = text.replace("ى", "ي").replace("ة", "ه")
    text = re.sub(r"[\u064b-\u065f\u0670]", "", text)
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def is_plausible_heading(value: str) -> bool:
    text = normalize_arabic_display(value)
    if not text or not contains_arabic(text):
        return False
    if len(text) < 2 or len(text) > 90:
        return False
    if re.search(r"[.!؟:؛]", text):
        return False
    if re.match(r"^(?:كان|كانت|عاش|عاشت|ولد|ولدت|وُلد|تنيح)\b", text):
        return False
    lowered_key = normalize_arabic_key(text)
    if lowered_key in {"قديسون اخرون", "قديسون باسم", "فهرس"}:
        return False
    if len(text.split()) > 8:
        return False
    return True


def heading_from_segment(segment: str) -> str:
    segment = segment.strip()
    heading = re.split(r"\s{2,}", segment, maxsplit=1)[0]
    heading = re.split(r"\s+(?:St\.|SS\.)\b", heading, maxsplit=1)[0]
    heading = normalize_arabic_display(heading)
    heading = BODY_CUE_PATTERN.split(heading, maxsplit=1)[0]
    heading = re.sub(r"\s*\d+\s*$", "", heading).strip()
    return heading


def entry_id(name: str) -> str:
    digest = hashlib.sha1(normalize_arabic_key(name).encode("utf-8")).hexdigest()[:12]
    return f"ar-saint-{digest}"


def extract_entries(pdf_path: Path) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    reader = PdfReader(str(pdf_path))
    entries: List[Dict[str, Any]] = []
    seen = set()
    pages_with_arabic = 0
    arabic_character_count = 0
    previews: List[str] = []
    warnings: List[str] = []

    for page_index, page in enumerate(reader.pages):
        try:
            raw_text = (page.extract_text() or "").replace("\x00", " ")
        except Exception as exc:
            warnings.append(f"page {page_index + 1}: extract_text failed: {exc!r}")
            continue

        text = normalize_arabic_text(raw_text)
        arabic_count = len(re.findall(r"[\u0600-\u06ff]", text))
        if arabic_count <= 0:
            continue

        pages_with_arabic += 1
        arabic_character_count += arabic_count
        if len(previews) < 3:
            previews.append(normalize_arabic_display(text)[:220])

        if ENTRY_MARKER not in text:
            continue

        for segment in text.split(ENTRY_MARKER)[1:]:
            heading = heading_from_segment(segment)
            if not is_plausible_heading(heading):
                continue
            key = normalize_arabic_key(heading)
            if not key or key in seen:
                continue
            seen.add(key)
            preview = normalize_arabic_display(segment)[:240]
            entries.append(
                {
                    "id": entry_id(heading),
                    "name_ar": heading,
                    "aliases_ar": [],
                    "source_title": "full saints arabic",
                    "page_start": page_index + 1,
                    "page_end": page_index + 1,
                    "preview": preview,
                }
            )

    entries.sort(key=lambda item: normalize_arabic_key(str(item.get("name_ar", ""))))
    stats = {
        "pdf_path": str(pdf_path),
        "file_exists": pdf_path.exists(),
        "file_size_bytes": pdf_path.stat().st_size if pdf_path.exists() else 0,
        "page_count": len(reader.pages),
        "pages_with_arabic_text": pages_with_arabic,
        "arabic_character_count": arabic_character_count,
        "generated_count": len(entries),
        "previews": previews,
        "warnings": warnings,
    }
    if pages_with_arabic < 10 or arabic_character_count < 1000:
        stats["warnings"].append(
            "Arabic PDF text extraction failed or returned too little text. Need OCR or different PDF extraction."
        )
    if len(entries) < 50:
        stats["warnings"].append(
            "Arabic saint heading extraction produced very few entries. Check PDF extraction before relying on this index."
        )
    return entries, stats


def build_index(pdf_path: Path = DEFAULT_PDF_PATH, output_path: Path = DEFAULT_OUTPUT_PATH) -> Dict[str, Any]:
    if not pdf_path.exists():
        raise FileNotFoundError(f"full saints arabic PDF is not present in the deployed source files: {pdf_path}")

    entries, stats = extract_entries(pdf_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output = {
        "source_title": "full saints arabic",
        "generated_by": Path(__file__).name,
        "stats": stats,
        "saints": entries,
    }
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Arabic saints index from full saints arabic PDF.")
    parser.add_argument("--pdf", default=str(DEFAULT_PDF_PATH), help="Path to full saints arabic PDF.")
    parser.add_argument("--out", default=str(DEFAULT_OUTPUT_PATH), help="Output JSON path.")
    args = parser.parse_args()

    stats = build_index(Path(args.pdf), Path(args.out))
    print("Arabic saints index build complete.")
    print(f"PDF path: {stats['pdf_path']}")
    print(f"File exists: {stats['file_exists']}")
    print(f"File size bytes: {stats['file_size_bytes']}")
    print(f"Page count: {stats['page_count']}")
    print(f"Pages with Arabic text: {stats['pages_with_arabic_text']}")
    print(f"Arabic character count: {stats['arabic_character_count']}")
    print(f"Generated Arabic saint entries: {stats['generated_count']}")
    print(f"Warnings: {stats['warnings']}")


if __name__ == "__main__":
    main()
