"""Web section splitting (offline HTML) and the exact v1 rebuild on a few pages."""

from ingestion import legacy
from ingestion.web import parse_page

from .conftest import needs_pdfs, needs_v1_store

HTML = """
<html><head><title>T</title></head><body>
<nav>menu</nav>
<article>
  <h1>The Coptic Orthodox Church &amp; the Christian Dogmas</h1>
  <p>Intro paragraph.</p>
  <h2>The Holy Trinity</h2>
  <p>One God in three Persons.</p>
  <ul><li>Father</li><li>Son</li></ul>
  <h3>The Incarnation</h3>
  <p>The Word became flesh.</p>
  <p>The Word became flesh.</p>
</article>
<footer>copyright</footer>
</body></html>
"""


def test_web_page_is_split_at_h2_h3():
    page = parse_page("https://example.org/post#top", HTML)
    assert page.url == "https://example.org/post"
    assert page.title == "The Coptic Orthodox Church & the Christian Dogmas"
    assert [s.heading for s in page.sections] == ["", "The Holy Trinity", "The Incarnation"]
    assert page.sections[1].paragraphs == ["One God in three Persons.", "Father", "Son"]
    assert page.sections[2].paragraphs == ["The Word became flesh."]  # duplicates dropped
    assert "menu" not in str([s.text for s in page.sections]) and len(page.content_sha1) == 40


def test_legacy_window_chunker():
    assert legacy.chunk_text("a" * 7000, 3500, 400) == ["a" * 3500, "a" * 3500, "a" * 800]


@needs_pdfs
@needs_v1_store
def test_legacy_rebuild_matches_live_v1_on_sample_pages():
    import sqlite3

    wanted = {"saints1.pdf::p329::c0", "catechism2.pdf::p31::c0", "ar::full saints arabic.pdf::p100::c0"}
    con = sqlite3.connect("file:chroma_db/chroma.sqlite3?mode=ro", uri=True)
    live = dict(con.execute(
        "SELECT e.embedding_id, m.string_value FROM embeddings e JOIN embedding_metadata m ON m.id = e.id "
        f"WHERE m.key = 'chroma:document' AND e.embedding_id IN ({','.join('?' * len(wanted))})", sorted(wanted)))
    # Only these three pages are rebuilt here; `python -m ingestion verify-legacy` compares all 7,581.
    from pypdf import PdfReader

    rebuilt = {}
    for chunk_id in wanted:
        arabic = chunk_id.startswith("ar::")
        file, page, _ = chunk_id.removeprefix("ar::").split("::")
        raw = PdfReader(f"data/pdfs/{file}").pages[int(page[1:]) - 1].extract_text()
        size, overlap = (legacy.AR_CHUNK_CHARS, legacy.AR_OVERLAP_CHARS) if arabic else (legacy.EN_CHUNK_CHARS, legacy.EN_OVERLAP_CHARS)
        rebuilt[chunk_id] = legacy.chunk_text(raw.replace(legacy.NUL, " ").strip(), size, overlap)[0]
    assert rebuilt == live and len(live) == 3
