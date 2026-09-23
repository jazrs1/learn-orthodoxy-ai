"""Registry of the corpus documents: one entry per source, keyed by a stable `doc_id`."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

PDF_DIR = Path("data/pdfs")

WEBSITE_SOURCE_URLS = [
    "https://www.mindofchristlight.com/library-blog/blog-post-title-one-4p8fk-wslyt-7kd9z",
    "https://www.mindofchristlight.com/library-blog/blog-post-title-one-4p8fk-wslyt-7kd9z-rzzxd",
    "https://www.mindofchristlight.com/library-blog/blog-post-title-one-4p8fk-wslyt-7kd9z-rzzxd-yspaf",
    "https://www.mindofchristlight.com/library-blog/blog-post-title-one-4p8fk-wslyt-7kd9z-rzzxd-xw8g5",
    "https://www.mindofchristlight.com/library-blog/blog-post-title-one-4p8fk-wslyt-7kd9z-rzzxd-xw8g5-jejkp",
]


@dataclass(frozen=True)
class PdfSource:
    doc_id: str
    file: str
    work: str
    volume: int
    language: str  # "en" | "ar"
    content_type: str  # "catechism" | "saints"
    author: str = "Fr. Tadros Y. Malaty"

    @property
    def path(self) -> Path:
        return PDF_DIR / self.file


CATECHISM_EN = "Catechism of the Coptic Orthodox Church"
SAINTS_EN = "Encyclopedia of the Saints and Fathers of the Church"

PDF_SOURCES: List[PdfSource] = [
    PdfSource("cat1", "catechism1.pdf", CATECHISM_EN, 1, "en", "catechism"),
    PdfSource("cat2", "catechism2.pdf", CATECHISM_EN, 2, "en", "catechism"),
    PdfSource("sts1", "saints1.pdf", SAINTS_EN, 1, "en", "saints"),
    PdfSource("sts2", "saints2.pdf", SAINTS_EN, 2, "en", "saints"),
    PdfSource("sts3", "saints3.pdf", SAINTS_EN, 3, "en", "saints"),
    PdfSource("sts4", "saints4.pdf", SAINTS_EN, 4, "en", "saints"),
    PdfSource("ar-cat", "full arabic catechism.pdf", "كاتيكيزم الكنيسة القبطية الأرثوذكسية", 0, "ar", "catechism"),
    PdfSource("ar-sts", "full saints arabic.pdf", "قاموس آباء الكنيسة وقديسيها", 0, "ar", "saints"),
]

BY_DOC_ID: Dict[str, PdfSource] = {source.doc_id: source for source in PDF_SOURCES}
BY_FILE: Dict[str, PdfSource] = {source.file: source for source in PDF_SOURCES}


def pdf_source(key: str) -> PdfSource:
    """Look a PDF up by doc_id ("cat2") or file name ("catechism2.pdf")."""
    if key in BY_DOC_ID:
        return BY_DOC_ID[key]
    if key in BY_FILE:
        return BY_FILE[key]
    raise KeyError(f"Unknown source {key!r}; known: {sorted(BY_DOC_ID)}")
