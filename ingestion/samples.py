"""The 20 sample pages from Step 0 (ING-001), rendered before (v1: pypdf) and after (this module).

`python -m ingestion samples --write` regenerates `tests/ingestion/golden/` and
`tests/ingestion/SAMPLES.md`; the tests compare fresh extraction against those files, so any
change to the extraction shows up as a reviewable diff.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

from pypdf import PdfReader

from . import extract_ar, extract_en
from .sources import pdf_source
from .textnorm import presentation_form_ratio

GOLDEN_DIR = Path("tests/ingestion/golden")
REPORT = Path("tests/ingestion/SAMPLES.md")


@dataclass(frozen=True)
class Sample:
    doc_id: str
    page: int
    why: str
    fixed: Tuple[Tuple[str, str], ...] = ()  # (v1 artefact, expected clean text)


SAMPLES: List[Sample] = [
    Sample("cat1", 10, "front matter: page is only a roman numeral"),
    Sample("cat1", 371, "pypdf splits 'o f them', 'son ship'; running header; footnote 923", (("o f them", "of them"), ("son ship", "sonship"))),
    Sample("cat1", 615, "pypdf split 'regrettin g'; footnote 1567", (("regrettin g", "regretting"),)),
    Sample("cat2", 16, "pypdf splits 'h is eyes', 'Whe n'; four footnotes", (("h is eyes", "his eyes"),)),
    Sample("cat2", 31, "pypdf split 'brin gs'; chapter + question heading; footnotes with continuation lines", (("brin gs", "brings"),)),
    Sample("cat2", 252, "Easter computation (PRD-02); pypdf 'c entury', 't he'", (("c entury", "century"),)),
    Sample("sts1", 33, "saint entry heading (Abanoub el-Nehissy); pypdf 'Semeno od'", (("Semeno od", "Semenood"),)),
    Sample("sts1", 144, "pypdf 'aud ience', 'b eautiful'", (("b eautiful", "beautiful"),)),
    Sample("sts1", 329, "pypdf 'sufferin g', 'fir e'", (("sufferin g", "suffering"),)),
    Sample("sts2", 143, "letter divider 'G', entry heading, sub-heading; pypdf 'th at', 'w ith'", (("w ith", "with"),)),
    Sample("sts2", 497, "pypdf 'sufferin g', 'multit ude'", (("sufferin g", "suffering"),)),
    Sample("sts3", 13, "pypdf 'e lder', 'gre atly'", (("e lder", "elder"),)),
    Sample("sts3", 240, "St. Moses and his sister Sarah (OOC-30); pypdf 'fath er', 'co nfessed'", (("co nfessed", "confessed"),)),
    Sample("sts4", 404, "alphabetical index page (excluded from chunks in Step 2; feeds the saints index)"),
    Sample("ar-cat", 50, "Arabic catechism: Latin footnotes 175-176, markers in the body, question 944"),
    Sample("ar-cat", 212, "Arabic catechism: seven Latin footnotes; mirrored brackets"),
    Sample("ar-cat", 400, "Arabic catechism: reversed Arabic-Indic verse numbers (Eph 4:11-12)"),
    Sample("ar-sts", 100, "Arabic saints: lam-alef ligatures (الإمبراطوري, لا, لأنها)"),
    Sample("ar-sts", 800, "Arabic saints: plain page"),
    Sample("ar-sts", 1500, "Arabic saints: the page where PyMuPDF drops letters (الثيؤلوغوس)"),
]


def before_text(sample: Sample) -> str:
    """What v1 stored for this page: pypdf's raw text."""
    source = pdf_source(sample.doc_id)
    return (PdfReader(str(source.path)).pages[sample.page - 1].extract_text() or "").strip()


def after_record(sample: Sample) -> Dict[str, object]:
    source = pdf_source(sample.doc_id)
    if source.language == "ar":
        page = extract_ar.extract_pages(sample.doc_id, [sample.page])[0]
        return {
            "extractor": extract_ar.EXTRACTOR, "printed_page": page.printed_page, "body": page.text,
            "footnotes": [(n.number, n.text) for n in page.footnotes], "markers": page.markers, "removed": page.removed,
        }
    page = extract_en.extract_pages(sample.doc_id, [sample.page])[0]
    return {
        "extractor": extract_en.EXTRACTOR, "printed_page": page.printed_page, "body": page.text,
        "footnotes": [(n.number, n.text) for n in page.footnotes], "markers": page.markers, "removed": page.removed,
    }


def render_after(sample: Sample, record: Dict[str, object]) -> str:
    lines = [
        f"# {sample.doc_id} p{sample.page} (printed page {record['printed_page']}) - {record['extractor']}",
        "", "## body", "", str(record["body"]) or "(empty)", "", "## footnotes", "",
    ]
    lines += [f"[{number}] {text}" for number, text in record["footnotes"]] or ["(none)"]  # type: ignore[union-attr]
    lines += ["", f"## footnote markers removed from the body: {record['markers']}", "", "## removed", ""]
    for kind, values in record["removed"].items():  # type: ignore[union-attr]
        for value in values:
            lines.append(f"{kind}: {value}")
    return "\n".join(lines).rstrip() + "\n"


def golden_paths(sample: Sample) -> Tuple[Path, Path]:
    stem = f"{sample.doc_id}_p{sample.page}"
    return GOLDEN_DIR / f"{stem}.before.txt", GOLDEN_DIR / f"{stem}.after.txt"


def _excerpt(text: str, length: int = 420) -> str:
    return re.sub(r"\s+", " ", text)[:length].replace("|", "/")


def write_all() -> None:
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    report = [
        "# Extraction samples: before (v1, pypdf) and after (Phase 5 Step 1)",
        "",
        "Generated by `python -m ingestion samples --write`; the golden files next to this report hold the full",
        "text. Arabic *before* is pypdf's raw output (presentation forms, as stored in v1).",
        "",
    ]
    for sample in SAMPLES:
        before = before_text(sample)
        record = after_record(sample)
        after = render_after(sample, record)
        before_path, after_path = golden_paths(sample)
        before_path.write_text(before + "\n", encoding="utf-8", newline="\n")
        after_path.write_text(after, encoding="utf-8", newline="\n")
        body = str(record["body"])
        report += [f"## {sample.doc_id} p{sample.page} - {sample.why}", ""]
        checks = []
        for artefact, clean in sample.fixed:
            checks.append(f"`{artefact}` in v1: {'yes' if artefact in before else 'no'}; `{clean}` now: {'yes' if clean in body else 'NO'}")
        if record["removed"].get("header"):  # type: ignore[union-attr]
            checks.append(f"running header removed: {record['removed']['header']}")  # type: ignore[index]
        if record["footnotes"]:
            checks.append(f"footnotes moved out of the body: {[n for n, _ in record['footnotes']]}")  # type: ignore[union-attr]
        if record["markers"]:
            checks.append(f"footnote markers removed: {record['markers']}")
        checks.append(f"printed page: {record['printed_page']}")
        if pdf_source(sample.doc_id).language == "ar":
            checks.append(f"presentation forms: {presentation_form_ratio(before):.0%} before, {presentation_form_ratio(body):.0%} after")
        report += [f"- {check}" for check in checks] + [""]
        report += ["| before (v1) | after |", "|---|---|", f"| {_excerpt(before)} | {_excerpt(body)} |", ""]
    REPORT.write_text("\n".join(report), encoding="utf-8", newline="\n")
    print(f"wrote {len(SAMPLES)} samples to {GOLDEN_DIR} and {REPORT}")
