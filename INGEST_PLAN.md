# Phase 5 — Re-ingestion plan (AUDIT A1, C1–C8)

**Status:** proposal, awaiting approval. Nothing is built yet.
**Branch:** `phase-5-ingest` (off `main` at `bfb17d9`).
**Author/date:** 2026-09-22.

Step 0 made no OpenAI calls. The measurements below come from local extraction with pypdf, PyMuPDF and pdfplumber, run in a scratch venv outside the project, and from read-only reads of the current Chroma store.

---

## 0. Decisions I need from you

Each has a recommendation; the reasons are in the sections referenced.

| # | Decision | Recommendation | § |
|---|---|---|---|
| D1 | English extractor | **PyMuPDF** (AGPL, offline ingestion only). pdfplumber (MIT) is an equal-quality fallback, about 15× slower. | 2 |
| D2 | Arabic extractor | **pypdf + NFKC + letter folding** for the text; PyMuPDF only to locate page numbers and Latin footnotes | 2, 4 |
| D3 | Arabic chunk size | Same *word* budget as English (≈230–460 words, ≈900–1,700 cl100k tokens), not the same token budget | 5.4 |
| D4 | Footnotes | Pull them out of the body and attach them to their question as a "Notes" block | 3 |
| D5 | Page numbers in citation labels | Show the **printed** page (catechism printed = PDF index − 10); keep the PDF index in metadata and in the eval | 6, 11 |
| D6 | Where v2 lives | Separate Chroma directory **and** versioned collection names, chosen by one variable `CORPUS_VERSION` | 9 |
| D7 | How v2 reaches Railway | A one-off build over `railway ssh` into a separate directory on the volume, verified against a committed manifest | 9.3 |
| D8 | Old ingestion scripts | Delete them in Step 1, after the new module can also rebuild v1 exactly (a `v1-legacy` profile), so rollback never depends on them | 8 |
| D9 | Eval size | Optionally add ~10 Arabic and ~5 saints questions to **tune** before Step 5; there are only 10 answerable Arabic questions today | 10.4 |

---

## 1. What v1 is today (measured)

| | English (`orthodox_pdfs`) | Arabic (`orthodox_arabic_pdfs`) |
|---|---|---|
| Chunks | 3,774 (3,567 PDF pages + 207 web) | 3,807 |
| Median chunk | 662 cl100k tokens (one page) | 1,280 tokens |
| Text size | 9.7 M chars ≈ 2.5 M tokens | 6.2 M chars after NFKC ≈ 4.6 M tokens (0.75 tokens/char vs 0.26 for English) |
| Chunk ID | `saints1.pdf::p329::c0` | `ar::full saints arabic.pdf::p100::c0` |
| Metadata | `source_type, pdf, title (= file stem), page, chunk_index, language, source_group` | same |

A chunk is a page (AUDIT C7). Retrieval, citations, the runtime saint index, the eval and the calendar all depend on that shape (§11).

---

## 2. Extraction: evidence and choice

**Sample.** 20 pages chosen to cover the known problems:
- English (14 pages): the seven pages where the current store has pypdf splits ("sufferin g", "o f them", "son ship", "sacrifice s", "h is eyes", "brin gs", "e lder"); a front-matter page ("x"); the Easter page with footnotes; a saint entry heading; the "G" letter page; St. Moses and his sister Sarah; the alphabetical index page.
- Arabic (6 pages): three from each Arabic PDF.

The Arabic comparison was then repeated on 79 random pages.

### 2.1 English: split words, headers, footnotes

| extractor | split words / page (14 pages) | known artefacts fixed | ms / page | layout info |
|---|---|---|---|---|
| pypdf (v1) | **1–6** on 11 of 14 pages (`sufferin g`, `fir e`, `th at`, `w ith`, `fath er`, `co nfessed` …) | 0 of 7 | 100–195 | none |
| **PyMuPDF** | 0 (one page each has `U S` = "U.S.A." and `s words` = "`’s words`", both genuine) | 7 of 7 | **10–32** | font, size, bold, position per line |
| pdfplumber | same as PyMuPDF | 7 of 7 | 190–300 | per-character font/size |

**What the layout information makes possible, measured on the samples:**
- **Running headers:** catechism headers such as "Book 3: The Church: The Kingdom of God" / "Catechism of the Coptic Orthodox Church – Volume 2" sit in the top 5 % of the page at 10–11 pt. The printed page number is a 12 pt line at y ≈ 0.92 (catechism) or 0.79 (saints).
- **Footnotes:** 10 pt lines starting with a number at y ≥ 0.82 ("923 St. Augustine of Hippo, Lectures or Tractates…"). The markers in the body are superscripts (smaller font, raised).
- **Saint structure:** entry headings are 14 pt bold ("ABANOUB EL-NEHISSY" + "(The martyr)"); sub-headings are 12 pt bold ending in ":" ("In Semenood:", "His Life of Seclusion:"); letter dividers are 24 pt ("G").

None of this is visible to pypdf. That is why v1's saint index reconstructs headings from upper-case ratios (AUDIT C5).

**Choice (D1): PyMuPDF for English.** pdfplumber gives the same text and also exposes font sizes, so it is a drop-in fallback if you would rather avoid AGPL. The cost is about 10 minutes instead of about 40 seconds for the English corpus.

### 2.2 Arabic: presentation forms, word order, completeness

| extractor | presentation forms | lines per word | logical order | lam-alef "لا" | completeness vs the other |
|---|---|---|---|---|---|
| pypdf (v1) | 76–82 % (NFKC fixes them) | ~2 (one word per line) | yes, after NFKC | **correct** ("لا تريد", "لأنها", "الإمبراطوري") | complete |
| PyMuPDF | 0 % | 0.1–0.6 | yes | **reversed** ("ال تريد", "ألنها", "اإلمبراطوري"), the Allah ligature as "هللا", and "." / "،" / brackets at the wrong end of words | **drops letters in some spans**: on saints p.1500 "براعته" → "براعت", "الثيؤلوغوس" → "ثهوتييؤ" |
| pdfplumber | 76–82 % | ~0.1 | **no** (visual order, reversed) | — | — |

I wrote a repair for PyMuPDF that swaps back each ligature, detected by its zero-width alef glyph, and moves the misplaced punctuation. It works (0 reversed ligatures left). But on 79 random pages the repaired PyMuPDF text still disagrees with pypdf on more than 5 % of words on **17 of 39 catechism pages and 10 of 40 saints pages** (7 below 80 %), because of the dropped letters.

pypdf's only defects are:
- NFKC leaves Persian ی/ھ letter variants, which are folded to ي/ه;
- each word sits on its own line, which is joined;
- occasional displaced sentence punctuation and digits ("8 م" for "268م").

**Choice (D2):** Arabic text comes from **pypdf + NFKC + folding** (§4). PyMuPDF is used only to *locate* things to remove, all of which it extracts reliably because they are Latin or digits: the page number and the Latin footnote lines ("593 Homilies on 2Cor, homily 15:3") of the Arabic catechism.

### 2.3 Licenses

| library | license | what it means here |
|---|---|---|
| PyMuPDF | **AGPL-3.0** (or a commercial license from Artifex) | Fine for **offline ingestion**. It is imported only by the ingestion module, never by `api.py`, so the web service does not link it. We do not distribute PyMuPDF or offer it over a network. It does get installed in the Railway image, because the one-off build runs there (§9.3). If the ingestion code were ever shipped inside a product under a proprietary license, or PyMuPDF moved into the request path, get that reviewed. The repo has no LICENSE file today. |
| pdfplumber / pdfminer.six | MIT | No obligations beyond the notice. |
| pypdf | BSD-3-Clause | Already a dependency. |

I'll pin `pymupdf` exactly in `requirements.txt` and add a comment that it is ingestion-only.

---

## 3. Cleaning

All rules are per page, before structure is applied, and each one has a test on the sample pages (Step 1).

- **Running headers / page numbers (English):** drop lines in the top 7 % or bottom 12 % of the page when either (a) the line is only a number, or (b) its text, with digits normalised, repeats on ≥ 20 % of the pages of that PDF. Keep the printed page number per page in a page map (§6).
- **Footnotes (catechism, D4):** a footnote is a line at ≥ 0.80 page height, smaller than body text, starting with a number that matches a superscript marker on the same or an earlier page. Markers are removed from the body text. Footnotes are gathered per question and appended after the answer as `Notes:` followed by `[923] St. Augustine, Tractates on John 13.17–18…`. They stay attached to the question that cites them, rather than to whatever sits at the bottom of the page. The alternative is to drop them, which is simpler but loses "which Father said this", and answers use that.
- **Arabic:**
  - page numbers, and the catechism's Latin footnote lines, are located with PyMuPDF and removed from the pypdf text;
  - the entry marker ✞ is kept (it is structure, §5.2);
  - superscript footnote digits glued to words ("إليك175") are split off with a letter→digit boundary rule.
- **Front matter and non-content pages:** table of contents, acknowledgments, the Encyclopedia's alphabetical index (saints4 pp. 403–473) and pages with < 40 characters of body text are not chunked (AUDIT C4). The index pages feed the saints index (§7) instead; they are what polluted the G-saints retrieval in RET-007. The catechism TOC pages are what "make a table…" retrieved in EVAL-014.
- **Hyphenation:** a line ending in `-` followed by a lower-case start is joined. It was rare in the audit (≤ 6 per 40 pages), but it is free.
- **Whitespace:** lines are joined into paragraphs using the layout (a new block or a bigger vertical gap starts a paragraph). This is what the chunker splits sentences on.

---

## 4. Arabic normalisation (applied before embedding and stored as the document text)

1. **NFKC** turns presentation forms into base letters (AUDIT C2: 74 % of the letters in v1 are presentation forms).
2. **Letter folding:** ی→ي, ھ→ه, ک→ك, ۀ→ه. The query side already folds the same way (`_normalize_arabic_alias_key`, entity check).
3. **Line joining:** pypdf's word-per-line output is joined with spaces. Paragraphs are recovered from sentence punctuation and the ✞ / question-number markers, because pypdf gives no layout.
4. **Tatweel (ـ) removed.** Diacritics are **kept** in the stored text, which the model reads, and handled at query time by the existing matchers.
5. **Logical order** is what pypdf already produces. A test asserts that common words ("القديس", "الكنيسة", "لأن") are present and reversed forms ("سيدقلا", "ألن") are absent on every sample page.

This means the query (embedded as normal Arabic) and the documents live in the same space for the first time (AUDIT C2, RET-003). The Arabic distance threshold, off today (open question 9), becomes something to re-measure in Step 5.

---

## 5. Structure and chunking

### 5.1 Catechism (English vols 1–2, Arabic one volume): one unit per numbered question

- **Index:** the PDF bookmarks:
  - English vol. 1: 885 level-2 entries = Q1–877;
  - English vol. 2: 575 = Q878–1452;
  - Arabic: 1,532 numbered = Q1–1452, 2 gaps.

  The level-1 bookmarks (58 / 55 / 134) are the Book and chapter titles, which become `section_path`.
- **Boundaries:** a question starts at its bookmark's page and position (the heading text is located on the page) and ends where the next question starts, even pages later. Expected: **1,452 questions per language**, minus the 1–2 bookmark gaps per book, which are reconciled by the `N.` heading pattern in the text.
- **Chunk header** (embedded and stored): `Catechism, Book 4 › The Life of Prayer — Q896. What is prayer?` Continuation chunks repeat the header, so the question survives a split (AUDIT C7a).

### 5.2 Saints (English Encyclopedia vols 1–4, Arabic dictionary): one unit per entry, split by sub-heading

- **English:**
  - an entry starts at a 14 pt bold heading group (consecutive heading lines merged: "QUZMAN EL-TAĤAWY AND HIS COMPANIONS" + "(The martyrs)") and runs to the next;
  - 12 pt bold lines ending in ":" are sub-sections;
  - 24 pt letter dividers are dropped.
  - First count: about 2,000 heading groups before merging wrapped headings. The expected number is ~1,600–1,700: the Vol. 4 alphabetical index lists 1,598 English–Arabic name pairs, and v1's runtime index has 1,363.
- **Arabic:** an entry starts at each ✞ (2,149 in v1's text) and its heading is the text up to the first sentence or descriptor break. This is the rule `build_arabic_saints_index.py` already uses; it produced 1,919 names.
- **Chunk header:** `Saint: Abanoub el-Nehissy (The martyr) — In Semenood`. A chunk about his death on the next page therefore still carries his name (the AUDIT C7a example).
- **Joint entries** ("AARON AND JULIUS, SS.", "DEMIANA AND THE FORTY VIRGINS") stay one unit. Each named saint becomes an alias (§7).

### 5.3 Web pages (five Mind of Christ Light articles): one unit per section

- A unit is split at `h2`/`h3` inside the article root; the page title plus the section heading forms the header.
- Pages are fetched at build time, as in v1, and each page's content hash goes into the manifest, so a Railway build can tell whether the site changed since the local build.

### 5.4 Chunk size, splitting and overlap

- **Size:** measured in cl100k tokens (the tokenizer of `text-embedding-3-small`).
  - English: target 300–600 tokens (aim ~450).
  - Arabic (D3): the same *word* budget, ≈230–460 words ≈ 900–1,700 tokens, because cl100k spends ~2.9× more tokens per Arabic character. With the same token budget, Arabic chunks would hold ~110–220 words, and there would be about 3× as many of them (~11k vs ~4k), which means more fragments per entry and a bigger index.
  - Short units stay whole: a 150-token Q&A is one chunk and is never merged with its neighbours.
- **Splitting:** on sentence boundaries (`. ! ? ؟ ۔` plus closing quotes; no split inside `St.`, `Fr.`, `A.D.`, `vol.`, `p.`, or before a verse reference). A sentence longer than the maximum is split at `;`/`,`, and as a last resort at a word boundary; never mid-word.
- **Overlap:** the last ~15 % (one or two sentences) of a chunk begins the next chunk of the **same unit**. Units are page-independent, so the overlap crosses page boundaries naturally. There is no overlap across units, because the next unit is a different question or saint.
- **Near-empty:** chunks under 40 tokens of body text (after the header) are merged into their neighbour in the same unit, or dropped if the unit is empty.

**Expected size (estimate, confirmed in Step 2):**
- English: 2.5 M tokens / ~450 + overlap ≈ 6,000–6,500 chunks, vs 3,774 in v1.
- Arabic: 4.6 M tokens / ~1,300 + overlap ≈ 4,000 chunks, vs 3,807 in v1.

---

## 6. Metadata schema and IDs

Chroma 0.6 metadata is flat (str/int/float/bool; no lists or null), so absent values use `""` or `0`, and every chunk carries every field.

| field | example | notes |
|---|---|---|
| `chunk_id` | `v2:cat2:q896:c1` | stored in metadata too, so `chunk_id_from_metadata` stops reconstructing it (LOG-002 revisit) |
| `corpus_version` | `v2` | |
| `doc_id` | `cat2`, `sts1`, `ar-cat`, `ar-sts`, `web-3f2a…` | stable key per source document |
| `source_type` | `pdf` / `website` | unchanged meaning |
| `pdf` / `url` | `catechism2.pdf` | kept, so v1-shaped code and the eval's `expected_sources` keep working |
| `work` | `Catechism of the Coptic Orthodox Church` | human title; replaces `SOURCE_TITLES` lookups by filename |
| `volume` | `2` (0 = n/a) | |
| `author` | `Fr. Tadros Y. Malaty` | |
| `language` | `en` / `ar` | |
| `content_type` | `catechism` / `saints` / `web` / later `commentary` | |
| `unit_type` | `question` / `saint_entry` / `web_section` / later `scripture_passage` | |
| `unit_id` | `q896`, `saint:abanoub-el-nehissy`, `s3` | stable within `doc_id` |
| `unit_title` | `896. What is prayer?` / `ABANOUB EL-NEHISSY (The martyr)` | |
| `section_path` | `Book 4 › Chapter 2: The Life of Prayer` | ` › `-joined; `""` for saints |
| `subsection` | `In Semenood` | saints sub-heading |
| `question_no` | `896` (0 = n/a) | |
| `saint_id` / `saint_name` | `abanoub-el-nehissy` / `St. Abanoub el-Nehissy` | joins the saints index (§7) |
| `ref_book`, `ref_chapter_start`, `ref_verse_start`, `ref_chapter_end`, `ref_verse_end` | `""`, `0` … | **reserved for Fr. Tadros's Bible commentaries**: `unit_type=scripture_passage`, `unit_id=JHN.3.16-21`; numeric fields allow Chroma `$gte`/`$lte` range filters |
| `page_start`, `page_end` | `99`, `100` | **PDF page index** (what the eval and any future `#page=` links use) |
| `printed_page_start`, `printed_page_end` | `89`, `90` | what a reader finds in the book (D5) |
| `chunk_index`, `chunk_count` | `1`, `3` | within the unit |
| `token_count` | `438` | |
| `extractor`, `normalizer` | `pymupdf-1.28.2`, `nfkc+fold-v1` | |
| `text_sha1` | … | the manifest and the Railway verification compare these |

**Adding the commentaries later** needs no redesign: a new `doc_id` per book, `content_type=commentary`, `unit_type=scripture_passage` with the `ref_*` fields, `section_path` for the commentary's own chapters, and one new segmenter keyed on verse headings. The retrieval, citation and eval code keys on `unit_title`, `section_path` and page ranges, never on the content type.

---

## 7. Ingest-time saints index (replaces runtime heading parsing and `saint_index_overrides.py`)

The build writes `data/corpus/v2/saints_index.json`, committed and loaded once at API startup, with no Chroma scan.

```json
{ "id": "abanoub-el-nehissy",
  "name_en": "St. Abanoub el-Nehissy", "name_ar": "القديس أبانوب النهيسي",
  "heading_en": "ABANOUB EL-NEHISSY (The martyr)", "descriptor": "martyr",
  "aliases_en": ["Abanoub", "Apa-Noub of Nahisah", "St. Abanoub El-nehissy"],
  "aliases_ar": ["أبانوب النهيسي", "أبا نوب"],
  "entries": [ {"lang": "en", "doc_id": "sts1", "unit_id": "saint:abanoub-el-nehissy", "page_start": 33, "page_end": 35},
               {"lang": "ar", "doc_id": "ar-sts", "unit_id": "saint:ar-0042", "page_start": 71, "page_end": 72} ] }
```

- **English ↔ Arabic linking:** the Vol. 4 alphabetical index lists each entry as `ENGLISH HEADING...الاسم العربي` (1,598 lines). That pairs English entries with Arabic names; the Arabic names are then matched to ✞ headings in the Arabic book. Step 2 reports the link rate and the unlinked residue.
- **Aliases from:**
  - bracketed variants in headings ("MACROBIUS (Macrawy)");
  - joint-entry names;
  - the hand tables already in the code (`MANUAL_SAINT_ALIASES` in `api.py` and `saint-display.ts`, `arabic_saints_index.py` seeds);
  - **every v1 display name**, mapped to its v2 entry by page overlap, so old links keep resolving (§11).
- `saint_index_overrides.py` (replacements/exclusions) becomes a reviewed curation file, `data/corpus/saints_curation.json`, applied at build time with a reason per line.
- **Consumers in Step 4:**
  - saint-intent lookup and menu (RET-001);
  - saint lists (RET-007), which will use each entry's first chunk instead of "first 600 characters";
  - `/saints` for both languages;
  - `/saint-detail`;
  - the named-subject check, which gains alias matching (GEN-006 revisit).

---

## 8. Code layout

One package replaces `ingest.py`, `ingest_arabic_sources.py`, `ingest_web.py`, `ingest_all_sources.py`, `build_arabic_saints_index.py` and `ingest_embeddings.py`:

```
ingestion/
  sources.py      registry: doc_id, file/url, work, volume, language, content_type, extractor, segmenter
  extract.py      english_pdf (PyMuPDF lines with font/size/position), arabic_pdf (pypdf + PyMuPDF zones), web (requests + bs4)
  clean.py        headers/page numbers/footnotes/front matter, hyphen join, Arabic normalisation
  structure.py    catechism (bookmarks), saints (fonts / ✞), web (h2/h3) → units with a char→page map
  chunk.py        sentence splitter, cl100k sizing, overlap, page ranges, headers
  saints_index.py build + EN↔AR linking + curation
  embed.py        batching; retries only on transient 429/5xx; STOPS on insufficient_quota, 401, 403
  build.py        CLI
tests/ingestion/  sample-page fixtures + before/after text
```

**CLI:**
- `python -m ingestion build --corpus v2 [--dry-run] [--lang en|ar] [--resume] [--chroma-dir PATH]`
  - `--dry-run` extracts, chunks and writes stats plus the manifest with **no OpenAI calls**; that is Step 2.
  - The real build writes `data/corpus/v2/manifest.json`: counts, per-document text hashes, the chunk-ID list hash, library versions. Upserts are idempotent (deterministic IDs), so `--resume` finishes an interrupted build.
- `--corpus v1-legacy` reproduces v1 exactly (pypdf, per-page 3,500/400 windows, v1 IDs and metadata; D8). That is the only reason the old scripts would otherwise be needed for a v1 rebuild.

**Quota safety:** today's embedder retries any error containing "429" up to 10 times, and `insufficient_quota` is also a 429. The new embedder treats `insufficient_quota`, 401 and 403 as fatal and exits immediately with the batch number, as you asked, because the key is shared with production.

**Tests** use `pytest` in a new `requirements-dev.txt`: extraction on the 20 sample pages with before/after text, cleaning rules, Arabic normalisation invariants, the sentence splitter, page-range bookkeeping and a manifest round trip.

---

## 9. Versioning and deployment

### 9.1 Selection

- One variable, **`CORPUS_VERSION`** (`v1` default | `v2`), selects:
  - the persist directory: `<chroma root>/` for v1, as now, and `<chroma root>/../chroma_v2/` (or `CHROMA_DIR_V2`) for v2;
  - the collection names: `orthodox_pdfs` / `orthodox_arabic_pdfs` vs **`orthodox_pdfs_v2` / `orthodox_arabic_pdfs_v2`**;
  - the saints index source: runtime heading parsing vs `saints_index.json`;
  - the metadata-dependent code paths (§11).
- The existing `CHROMA_COLLECTION`, `CHROMA_ARABIC_COLLECTION` and `CHROMA_DIR` still override for experiments.
- **Why a separate directory as well as new names (D6):** v1's files are never opened for writing by a v2 build, so "v1 untouched" is checkable byte for byte (checksums before and after Step 3). Rollback cannot be affected by anything v2 did, and retiring v1 later is deleting one directory. The version suffix on the names protects against a mis-set directory.

### 9.2 Local (Step 3)

- Build into `chroma_db_v2/` (gitignored), next to `chroma_db/`.
- Record SHA-256 of `chroma_db/chroma.sqlite3` and the v1 segment directories before and after; they must match.

### 9.3 Railway (Step 6, executed only when you say so)

- **Boot ingestion is not used.** `start_backend.py` currently re-ingests v1 with the old scripts when a collection is under-populated. It will:
  - never auto-ingest for v2;
  - with `CORPUS_VERSION=v2`, exit immediately with a clear message if the v2 collections are missing, or if their counts or ID hash differ from `manifest.json`.

  Railway keeps the old deployment serving until a new one passes its health check, so a bad switch fails fast instead of waiting the 30 minutes (`healthcheckTimeout: 1800`).
- **Build (D7):** while v1 keeps serving:
  1. `railway ssh` into the backend service.
  2. Run `setsid nohup python -m ingestion build --corpus v2 --chroma-dir $V2_DIR > $V2_DIR.build.log 2>&1 &`.

  It writes a directory the running API never opens, costs ≈ $0.17 in embeddings, and takes about 25–35 minutes (pypdf on 2,867 Arabic pages ≈ 17 min, plus embeddings). `--resume` recovers from a dropped session or a restart. **Do not deploy during the build** (a redeploy replaces the container). I could not confirm that a detached process survives the ssh session ending; Step 6 includes a check.
- **Alternative:** build locally and copy the directory up. It avoids a second embedding bill ($0.17), but copying Chroma's HNSW binaries across machines and piping a ~300 MB tarball through `railway ssh` are both unverified. The re-embedded build is compared against the local manifest instead: same chunk IDs and text hashes means the same corpus.
- **Switch:** set `CORPUS_VERSION=v2` and `AUTO_INGEST_ON_START=0`, which redeploys. `start_backend` verifies, `/health` reports `corpus_version` and counts, and a smoke set runs through the proxy.
- **Rollback:** set `CORPUS_VERSION=v1` and redeploy. v1's directory was never touched.
- **Volume:**
  - v1 ≈ 209 MB; v2 is estimated at 250–350 MB (≈ 10k vectors × 1,536 floats + HNSW + text + FTS).
  - **Check the volume's size limit in the Railway dashboard before the build**; I have no access.
  - Keep v1 for at least two weeks after the switch, then delete its directory. The v1 code paths can be removed in a later cleanup, while `v1-legacy` still reproduces v1 if ever needed.
- `chromadb` is pinned to `==0.6.3` (it is `>=0.5,<1.0` today), so local and Railway write the same on-disk format.

---

## 10. Eval changes and a fair v1/v2 comparison

### 10.1 Page-range-aware recall

- The backend's debug hits gain `pdf`, `page_start` and `page_end` per chunk; for v1, both page fields equal the page parsed from the ID.
- A retrieved chunk covers expected page *p* when the PDF matches and `page_start ≤ p ≤ page_end`. v1 numbers are unchanged by this definition; that gets verified by recomputing recall on the stored v1 results files.
- `recall_shown` uses the new `page_start`/`page_end` on returned sources.

### 10.2 Keeping it fair

- **The same code, date, models and questions.** Only `CORPUS_VERSION` changes. The config is the production one: gpt-4.1-mini generation, gpt-4o-mini analysis, prompt v3, entity check on, gpt-4.1 judge.
- **A bigger chunk scores more easily** on range-aware recall, and v2 chunks can span 2–3 pages. So these are also reported:
  1. **recall at equal context budget:** hits counted only until the cumulative context tokens reach v1's mean for that question type, as well as recall@8;
  2. **context tokens per answer**, and answer **coverage**, which does not depend on chunk shape and stays the headline;
  3. the ±1-page variant, kept only for continuity with earlier tables.
- **Top-k for v2** is chosen **before** any generation run, from a retrieval-only pass on **tune** (see below). It is set so v2's median context tokens match v1's; otherwise v2 would win or lose on budget, not on chunk quality.
- **Distance threshold:** v2 distances will differ (RET-009 revisit), so the English threshold and the possible Arabic one are re-derived on tune from a retrieval-only distance sweep, with the same `--simulate` method as RET-009. The chosen value is reported, not tuned on holdout.
- **Noise:** generation at temperature 0.2 moves single-question coverage by ±0.3–0.7 (RET-007). Each corpus is run **twice** on tune+holdout (coverage-only), and means are reported with the run-to-run spread. Differences under ~5 points on tune (~10 on holdout, EVAL-012) are called noise.
- **Separately reported:**
  - English vs Arabic;
  - tune vs holdout;
  - the categories catechism / saints / keyword / task / follow-up / multi-part;
  - refusals: answerable refused, out-of-corpus refused (easy / near-miss / task).
- **Faithfulness:** 15 answers per corpus, the same 15 question IDs, stratified to include ≥ 4 saints and ≥ 3 Arabic.

### 10.3 Harness additions

- **`debug.retrieve_only`**, honoured only for callers holding the internal key: the backend returns after retrieval, with no generation call. That makes top-k and threshold sweeps cost only the analysis call plus embeddings.
- `run_eval.py --corpus-label` so result files say which corpus they measured.

### 10.4 Weak spots

- There are only **10 answerable Arabic** questions (7 tune / 3 holdout) and 13 saints questions, so a regression there will be hard to tell from noise. That is D9: I'd add ~10 Arabic and ~5 saints questions to **tune only** before Step 5, verified against the PDFs like the others.
- Expected pages stay valid: they are PDF page indices, and every entry has an evidence quote.

---

## 11. Downstream effects (everything that reads chunk IDs or metadata)

| Where | Today | With v2 |
|---|---|---|
| `api._source_from_metadata`, `_friendly_source_label`, `SOURCE_TITLES` | pdf + page; title from filename | adds `work`, `volume`, `unit_title`, `section_path`, `question_no`, `saint_name`, page range. **Label** e.g. `Catechism of the Coptic Orthodox Church, Vol. 2 — Q896 “What is prayer?”, pp. 89–90` / `Encyclopedia of the Saints…, Vol. 1 — St. Abanoub el-Nehissy, pp. 33–35` (printed pages, D5) |
| `_build_numbered_context` | `[n] label\ntext` | the same, with the richer label; chunk headers are already in the text |
| `_cited_sources` — **the merging bug** | dedupes by `(pdf, page)`, so two saints cited from the same page collapse into one entry and the second `[n]` renders as a muted, unlinked number (UI-006 limit 1) | **one source per cited passage**, keyed by chunk ID. Every `[n]` links. Resolves UI-006 limit 1 and open question 22 (saint entry name in sources) |
| `Source` model (pydantic) | `pdf, page, n, label` | new optional fields; v1 responses unchanged |
| frontend `lib/sources.ts`, `AnswerWithSources` | maps filename → title, shows `p.` | prefers the backend `label` / `unit_title` / page range when present; old saved messages (Postgres) keep rendering from `pdf`/`page` |
| `request_log.chunk_id_from_metadata` | rebuilds v1 IDs | reads `chunk_id` from metadata when present |
| runtime saint index (`_build_saint_record_index`, `_build_arabic_saint_name_index`, `saint_index_overrides.py`, `arabic_saints_index.py`, `data/saints_ar_generated.json`) | built from ALL-CAPS lines at runtime; ~1,363 EN / 1,937 AR | `saints_index.json` under v2; v1 path kept until retirement |
| saint lists (RET-007) | "HEADING + first 600 chars" of the record | the entry's first chunk (with its page range) |
| Arabic lexical scan (`_retrieve_arabic_lexical_documents`) | NFKC per document per request | text is already normalised, so the per-request normalisation becomes a no-op (the O(N) scan itself is out of scope, AUDIT C13) |
| entity check (GEN-006) | space-insensitive matching to survive "sufferin g" | unchanged (still correct); gains saint aliases |
| distance threshold (RET-009), Arabic threshold (RET-003) | 1.25 / off | re-derived for v2 (§10.2) |
| `start_backend.py` auto-ingest | boot-time v1 ingestion | disabled for v2; verify-or-exit |
| eval: `CHUNK_ID_RE`, `pages_from_ids`, `load_passages_from_chroma`, `threshold_analysis.py` | parse v1 IDs | read page ranges from debug hits; passages by v2 ID from the v2 directory |
| **calendar saint links** (`orthodox-site/scripts/calendar/snapshot-saints-index.py`, `saints-index.snapshot.json`, `saint-link-overrides.json`, `saints.katameros.json`) | snapshot of the **v1** runtime index; 87 EN / 165 AR links and 21 overrides name v1 display names (e.g. "St. George, the Capaducian") | (1) v2 keeps every v1 display name as an alias, so existing `/chat?saint=` links and saved chat chips resolve on day one; (2) the snapshot script reads `saints_index.json` instead of importing `api`; (3) regenerate the snapshot, rerun `npm run calendar:saints`, and fix any override the extractor rejects (it fails loudly on unknown names); (4) review the link diff. Done in Step 6's checklist, after the switch, as a frontend commit |
| saved conversations (Postgres) | `sources` JSON and entity chips with v1 names | still render (backward-compatible fields); chips resolve through the v1-name aliases |
| `/debug/chroma*` | samples and counts | report `corpus_version` |
| `ui-audit/tools/fixtures.json` | v1-shaped sources | add one v2-shaped source so screenshots exercise the new label |
| README / `.env.example` | boot ingestion instructions | one-off build, `CORPUS_VERSION`, switch and rollback |

---

## 12. Cost estimate

List prices as I know them; **check current OpenAI pricing** before approving:
- `text-embedding-3-small` $0.02 / 1M tokens;
- gpt-4o-mini $0.15 / $0.60, gpt-4.1-mini $0.40 / $1.60, gpt-4.1 $2 / $8 per 1M input / output tokens.

Token counts come from `20260916-220035` (mean prompt 7,685, completion 335, analysis 988).

| Item | Tokens | Cost |
|---|---|---|
| **Embed v2 locally (Step 3)** | EN ≈ 2.5 M + AR ≈ 4.6 M + ~15 % overlap + headers ≈ **8.5 M** | **≈ $0.17** |
| Embed v2 again on Railway (Step 6, D7) | same | ≈ $0.17 |
| Retrieval-only sweep, one corpus, 119 questions | analysis ~1k + one embedding per question | ≈ $0.03 per sweep; ~4 sweeps ≈ $0.12 |
| **One coverage-only eval run, tune+holdout, one corpus** (80 answerable, 39 negatives) | answerable ≈ $0.0036 generation + $0.0002 analysis + ~$0.007 coverage judge; negatives ≈ $0.002 | **≈ $1.0 per run** |
| Step 5 coverage: v1 ×2 + v2 ×2 | | ≈ $4.0 |
| Step 5 faithfulness: 15 answers × 2 corpora (gpt-4.1, ~10k context in + ~1.5k out) | | ≈ $1.0 |
| **Phase 5 total, if everything is approved** | | **≈ $5.5–6.5** |

- **Rate limits:** gpt-4.1's 30k tokens-per-minute limit (open question 15) makes the faithfulness pass take ~10 minutes. The runs must not overlap. Each eval run starts with a one-question probe, so a quota or auth error stops everything before the batch.
- **Production cost per request after the switch:** v2 contexts are matched to v1's token budget (§10.2), so the per-request cost should not move. It is measured in Step 5, not assumed.

---

## 13. Risks and unknowns

- **Saint heading edge cases:** wrapped upper-case headings, joint entries, heretics and non-saints with entries. Step 2 reports found vs expected against the alphabetical index and lists every unmatched name, so the gap is visible rather than guessed.
- **Arabic text quality:** pypdf occasionally misplaces sentence punctuation and multi-digit numbers ("8 م"). This doesn't hurt embeddings much, but dates in Arabic answers could be affected; the Step 1 tests quantify it.
- **Distances change** with smaller, cleaner chunks: true hits usually get closer, but the threshold must be re-derived (§10.2), not assumed.
- **Railway unknowns:** volume size limit, whether `setsid nohup` survives the ssh session, and container CPU during the build (the API keeps serving; extraction is single-threaded).
- **Printed vs PDF pages (D5):** changing the label to printed pages is visible to users; if you prefer continuity, keep PDF pages.

---

## 14. How the steps map to deliverables

| Step | Deliverable | OpenAI |
|---|---|---|
| 1 | `ingestion/` extraction + cleaning + Arabic normalisation; `--corpus v1-legacy`; tests on the 20 sample pages with before/after text; old scripts removed; quota-safe embedder | none |
| 2 | chunkers, metadata, `saints_index.json`, `--dry-run` stats (chunk counts, token histogram, questions/entries found vs expected, chunks without section/saint), 10 sample chunks per type | none |
| 3 | v2 built into `chroma_db_v2/`; v1 checksums unchanged; manifest | **embedding, ≈ $0.17, after your approval** |
| 4 | `CORPUS_VERSION`; labels/citations/one source per passage; ingest-time saints index; v1 unchanged when set to v1 (an identical-output check on a few questions with retrieve-only) | none (retrieve-only checks use analysis + embedding, ≈ $0.01; I'll ask first) |
| 5 | retrieval-only top-k/threshold sweep on tune; coverage v1 vs v2 ×2 on tune+holdout (EN/AR separately); faithfulness on 15; regressions flagged | **≈ $5, after your approval** |
| 6 | the deployment runbook (build, switch, verify, rollback, calendar regeneration, env vars); nothing pushed | none |
