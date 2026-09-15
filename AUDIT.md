# LearnOrthodoxy — Codebase and RAG Pipeline Audit

Date: 2026-09-15. Scope: read-only review of the whole repo, plus read-only inspection of the local `chroma_db/` store (opened via sqlite in `mode=ro`) and the source PDFs (pypdf, no writes). No secrets were read or copied; only env var *names* were checked.

Line references are `file:line` and were verified against the current `main` (commit `337b9d9`).

---

## 1. Architecture summary

**Two deployables in one repo.**

| Piece | Tech | Where it runs | Entry |
|---|---|---|---|
| Frontend + chat persistence | Next.js 16.2 / React 19, `pg` | Vercel (root dir `orthodox-site`) | `orthodox-site/app/**` |
| RAG backend | FastAPI, ChromaDB 0.6.3 (persistent, local HNSW), OpenAI SDK | Railway (`python start_backend.py`) | `api.py` (3,220 lines) |

**Ingestion path (offline / on first boot).** `start_backend.py:92-145` checks Chroma counts and, if the English collection has < `MIN_CHROMA_DOCUMENTS` (1000) or the Arabic one is empty, runs ingestion before starting uvicorn. `ingest.py` reads each English PDF page with `pypdf` (`ingest.py:31-48`), slices the page text into 3,500-char windows with 400-char overlap (`ingest.py:27-28, 51-65`), attaches `{pdf, title, page, chunk_index, language, source_group}` metadata (`ingest.py:73-84`), and `ingest_embeddings.py:58-101` embeds batches with `text-embedding-3-small` and upserts into Chroma collection `orthodox_pdfs`. `ingest_web.py` does the same for five blog URLs. `ingest_arabic_sources.py` does the same for the two Arabic PDFs into a second collection `orthodox_arabic_pdfs` (3,000/350 chars). A separate script `build_arabic_saints_index.py` parses the Arabic saints PDF into `data/saints_ar_generated.json` (1,919 names).

**Query path.** Browser → `POST /api/chat` (`orthodox-site/app/api/chat/route.ts`) → loads last 6 messages from Postgres (`route.ts:69-71`) → `POST {ORTHODOX_API_URL}/chat` with `{question, history, top_k: 8, mode, language}` and a 20 s abort (`route.ts:86-100`) → FastAPI `chat()` (`api.py:2666-3155`) → language detection → (Arabic branch: vector + lexical scan of the Arabic collection) or (English branch: regex "saint intent" / history rewriting / numbered-follow-up resolution / ambiguity check → 1–8 Chroma queries → keyword "relevance" filter → optional retry) → context string → one non-streaming `gpt-4o-mini` completion at temperature 0.2 → regex extraction of numbered entities → JSON `{answer, sources, entities, options, can_learn_more}` → Next.js saves user + assistant turns to Postgres and returns.

**System prompts** live inline in `api.py`: Arabic at `api.py:2807-2819`, English at `api.py:3033-3071` (user-prompt template `api.py:3073-3097`). A third, older prompt lives in `answer_question.py:37-45` (unused by the app).

**State.**
- Vectors + chunk text: Chroma sqlite + HNSW in `chroma_db/` (gitignored; ~209 MB locally; on Railway expected on a volume at `/app/chroma_db`).
- Conversations/messages: Postgres tables from `orthodox-site/migrations/001_create_chat_tables.sql`, keyed by an anonymous httpOnly cookie (`lib/chat-auth.ts`).
- In-process globals in the API: `collection`, `arabic_collection`, `oai_client`, lazily built saint indexes, and **`last_list`, a process-wide dict shared by all users** (`api.py:1749`).
- Source PDFs: committed to git (`data/pdfs`, 82 MB) because Railway ingests from them at boot.

**Config.** Backend env: `OPENAI_API_KEY`, `CHROMA_DIR`, `AUTO_INGEST_ON_START`, `MIN_CHROMA_DOCUMENTS`, `ALLOWED_ORIGINS`, `CORS_ALLOW_ORIGIN_REGEX`, optional `EMBED_*`, `OPENAI_EMBED_MODEL`. Frontend env: `POSTGRES_URL`/`DATABASE_URL`, `ORTHODOX_API_URL`, `NEXT_PUBLIC_API_URL`, contact-form vars. `vercel-build` runs Postgres migrations at build time (`orthodox-site/package.json:8`).

**What the corpus actually looks like (measured from the local Chroma store).**

| Collection | Chunks | Median chars | Notes |
|---|---|---|---|
| `orthodox_pdfs` | 3,774 (3,567 PDF + 207 web) | 2,655 | 50 chunks are < 100 chars (page-number-only pages like `"x"`, `"iii"`); 1,235 begin with a running header |
| `orthodox_arabic_pdfs` | 3,807 | 2,152 | ~74 % of Arabic letters stored as Unicode *presentation forms*; more newline characters than words |

Only 30 of ~3,570 English PDF pages produced more than one chunk. In practice **a chunk is a page**; the 400-char overlap almost never applies, and no chunk ever spans a page boundary.

**Things I could not determine (no access, or would require API calls):**
- What is actually deployed on Railway/Vercel today (env values, volume, plan limits, whether Vercel Fluid Compute is on and what the function `maxDuration` is; no `maxDuration` is set in any route file).
- The real production domain: code says `learnorthodoxy.net` (`app/layout.tsx:6`, `app/sitemap.ts:3`, `app/robots.ts:3`); you said learnorthodoxy.com.
- Actual embedding-quality impact of the Arabic presentation-form issue (strongly implied by the data; confirming it needs an embedding experiment).
- Real production latency/cost per request (no logging or metrics exist).

---

## 2. CHANGE — things that exist but should work differently

Organised by pipeline stage. Each item says what the code does, where, and why it hurts answers.

### 2.1 PDF parsing

**C1. `pypdf.extract_text()` is the extractor, and its output has intra-word spacing artefacts.** `ingest.py:38`, `ingest_arabic_sources.py:82`. Samples pulled from the stored chunks: `"o f them"`, `"son ship"`, `"sufferin g"`, `"e lder"`, `"h is eyes"`, `"brin gs"`, `"sacrifice s"`. These Word-generated PDFs are a known weak spot for pypdf.
*Why it hurts:* broken tokens weaken embeddings (the model sees `sufferin` + `g`), and they silently break every exact-substring check the app relies on (the relevance filter, saint-heading detection, lexical search). A biography that says `"sufferin g"` won't match the keyword `suffering`. PyMuPDF (`fitz`) or `pdfplumber` produce clean text for these files.

**C2. Arabic text is stored as presentation-form glyphs, one word per line.** Measured over 400 Arabic chunks: 351,910 presentation-form code points (U+FB50–FDFF / FE70–FEFF) vs 123,357 base Arabic letters; 170,886 newlines vs 118,237 words. The ingestion path never normalises (`ingest_arabic_sources.py:82` just strips `\x00`). The API *does* NFKC-normalise at query time (`api.py:592-597`, `api.py:2803`) — so the LLM sees readable Arabic and the lexical scan works — **but the embeddings were computed on the raw glyph soup while the user's query is embedded as normal Arabic.**
*Why it hurts:* query and document embeddings live in different token spaces, so vector recall in Arabic is likely poor and the app is leaning on the O(N) lexical scan (see C13). The PDFs themselves contain a real Arabic text layer (2,044 of 2,049 pages have Arabic), so this is fixable at ingestion: extract with PyMuPDF (which emits logical-order base letters), NFKC-normalise, join lines, then embed.

**C3. Running headers, page numbers and footnotes are embedded in every chunk.** Catechism pages start with `"Catechism of the Coptic Orthodox Church – Volume 2 \n300 \n"` or `"Book 3: The Church: The Kingdom of God \n361 \n"` (1,235 chunks); saints pages start with the bare page number (`"329 \n \n"`); catechism pages end with footnote citations (`"36 St. Cyril of Jerusalem, Catechetical Lectures 4.2 (NPNF II…"`).
*Why it hurts:* the header pushes every catechism chunk toward the same embedding region ("Coptic Orthodox Church"), and the words `coptic`/`orthodox`/`church` then satisfy the keyword filter for *any* question mentioning the Church, letting unrelated chunks through. The footnote text belongs with the sentence that cites it, not glued to the bottom of an arbitrary page.

**C4. 50 near-empty chunks (front-matter pages).** e.g. `catechism1.pdf::p10::c0` = `"x"`, `p3` = `"iii"`. Harmless for retrieval (they rarely rank), but they are noise in the index and in `/debug` counts; drop pages with < ~40 chars of body text.

**C5. Rich document structure is ignored.** Both catechism PDFs carry PDF bookmarks for every numbered question (943 and 630 outline entries: `"896. What is prayer?"`, `"1165. What do we know about…"`) and the body text has the same numbered Q&A headings. The saints volumes are alphabetical dictionaries with ALL-CAPS entry headings (`"ABANOUB EL-NEHISSY \n(The martyr)"`, `"MACEDONIUS, THE HERETIC"`), bold sub-headings (`"His Life of Seclusion:"`), and per-entry bibliographic tags (`"[Butler: January 24]"`). None of this reaches the index. Instead, `api.py:2041-2112` re-derives saint entries at runtime by scanning every English chunk for lines whose uppercase ratio ≥ 0.72 (`api.py:1952-1972`), then patches the result with hand-maintained lists (`saint_index_overrides.py`).
*Why it hurts:* the ideal retrieval unit for the catechism is "one Q&A", and for the saints "one entry (or one entry section)". Page-chunks cut entries mid-sentence, merge the tail of one saint with the head of the next, and carry no `section`/`question`/`saint` metadata to filter or cite by.

**C6. Multi-column / scanned pages.** Not an issue here: all sampled pages have a text layer; no empty-text pages in the samples; `hyphenated line breaks` were ≤ 6 per 40 pages. Fine.

### 2.2 Chunking

**C7. Fixed character windows inside a page, with per-page reset.** `ingest.py:51-65` (duplicated verbatim in `ingest_arabic_sources.py:38-52` and `ingest_web.py:35-49`). Because page text (median ~2,500–2,970 chars) is smaller than the 3,500 window, chunking degenerates to "1 chunk = 1 page"; the overlap only exists on the 30 pages that exceeded 3,500 chars.
*Why it hurts:* (a) a saint's life that spans pages 33–35 is three unrelated chunks with no overlap; the question "how did Abanoub die?" may match page 34 by name but the death is on page 35, where the name is never mentioned. (b) Chunks are large (≈650 tokens) and topically mixed, so a chunk's embedding is the average of several unrelated paragraphs, and the specific paragraph you want is diluted. (c) When the window *does* split, it splits mid-word.

**C8. Metadata is thin.** Only `pdf`, `page`, `chunk_index`, `title` (= file stem such as `saints1`). No section title, no question number, no saint name, no entry start/end page. The `title` field for the English PDFs is `"catechism1"`, which is useless in a citation.

### 2.3 Embeddings

**C9. Model choice and consistency — fine.** `text-embedding-3-small` at both ingest (`ingest_embeddings.py:11`) and query (`api.py:1863-1866`), 1,536 dims confirmed in the store. Batching with token-aware batches and 429 backoff (`ingest_embeddings.py:21-36, 72-88`) is solid. Two caveats: (1) the C2 Arabic normalisation mismatch above; (2) `OPENAI_EMBED_MODEL` is env-overridable at ingest but hard-coded at query time, so changing the env var silently breaks retrieval.

**C10. Collection is opened with an embedding function at API startup but created without one at ingest** (`ingest.py:91` vs `api.py:1869-1873`). Chroma 0.6 tolerates this; Chroma ≥ 1.0 validates it and will refuse. Pin or align before upgrading.

### 2.4 Retrieval

**C11. Similarity scores are thrown away; multi-query results are merged in query order, not by score.** `api.py:453-517`: each of up to 8 queries returns `top_k` hits; results are de-duplicated and appended in the order the queries were issued; the list is then truncated to `top_k` (`api.py:515-516`). `distances` is never read anywhere in the file.
*Why it hurts:* with an entity, `_build_retrieval_queries` (`api.py:992-1035`) issues ~10 queries, so the final context is "the top 10–16 hits of query #1 and whatever fit from #2", never "the best 12 across all queries". There is also no similarity threshold, so a nonsense question still gets 8 chunks of something and the model is told to answer from them.

**C12. The keyword "relevance" filter causes false refusals and is the biggest single source of "the answer was in the PDF but it refused".** `api.py:1146-1179` requires ≥ 2 of the question's non-stopword words (≥ 3 letters) to appear as raw substrings in `chunk + title + pdf`. The stopword list (`api.py:1038-1073`) omits `why`, `when`, `where`, `does`, `did`, `can`, `should`, `explain`, `meaning`, `teach`, `church`, `coptic`, `orthodox`, `saint`, `about`…
- "Why fasting?" → keywords `[why, fasting]` → both must appear. A chunk explaining fasting without the literal word "why" is rejected → `"I could not find enough about that in the loaded sources."`
- No stemming: `fasting` ≠ `fasts`, `monasteries` ≠ `monastery` (the code special-cases only "upper egypt" + `monaster`, `api.py:1168-1169`, and "abu fana", `api.py:1171-1172`), and C1's `"sufferin g"` never matches `suffering`.
- Conversely, "What does the Coptic Orthodox Church teach about salvation?" passes *every* catechism chunk because `coptic` + `orthodox` sit in the running header (C3).
- If everything is rejected, a retry runs with `top_k=16` (`api.py:2968-2987`); if that is also rejected, the user gets the refusal even though `docs` were retrieved (`api.py:3002-3010`).
Vector similarity already ranks relevance; a substring gate on top of it mostly removes correct answers. Replace it with score thresholds + a reranker (see ADD).

**C13. Arabic lexical search is a full-collection scan on every request.** `api.py:693-775` pages through the entire Arabic collection with `collection.get(limit=500, offset=…)` (3,807 docs ≈ 8 MB of text), NFKC-normalises every document in Python, and substring-counts terms. This runs on **every** Arabic chat request.
*Why it hurts:* latency of seconds per request on Railway's CPU, competing with the 20 s Vercel abort; and the scoring (`hits*10 + phrase_hits*120`, `api.py:741-745`) has no length normalisation, so long chunks win. Chroma already maintains an FTS5 table (`embedding_fulltext_search` is present in the sqlite) reachable through `where_document={"$contains": …}`; or store a normalised copy of the text and use BM25 (`rank_bm25`) built once at startup.

**C14. The English retrieval query is the raw user text, including whatever the frontend appended.** `api.py:2707-2708, 2930`. For follow-up chips, the frontend appends up to 1,200 chars of the *previous answer* to the question (`orthodox-site/app/chat/page.tsx:245-250`), and that whole blob becomes the embedding query and the keyword source for C12.
*Why it hurts:* the query vector is dominated by the previous answer, so retrieval returns the same chunks again and the follow-up is answered with stale context; and the extra words make the keyword gate stricter.

**C15. Question rewriting is regex + hard-coded expansions, and the LLM rewriter is dead code.** `_rewrite_question_with_history` (`api.py:957-973`) fires only when the previous assistant message contained any `**bold**` span (`api.py:914-920`, which is *any* bolded phrase such as `**Baptism**`) and the new question contains a pronoun or `this`/`that` (`api.py:946-954`), then simply appends the entity name to the question. `_build_retrieval_queries` hard-codes expansions for two topics ("apostolic fathers", "upper egypt monasteries", `api.py:996-1017`). The LLM-based rewriter `_build_english_retrieval_query` (`api.py:853-890`) is never called. In `catechism` mode history rewriting is disabled entirely (`api.py:2700-2702`).
*Why it hurts:* multi-part questions ("Who was St. Mary of Egypt and what feast day is she remembered on?") are embedded as one vector and retrieved as one topic; genuine follow-ups ("and what did he write?") miss unless the previous answer happened to bold the right name.

**C16. Any digit in the question can hijack it into a saint biography.** `api.py:2874-2879`: `re.search(r"(?:the\s*)?(\d+)(?:st|nd|rd|th)?\s*(?:one|saint|mary|john)?", q_lower)` matches *any* number; if that number is a key in the global `last_list` (populated whenever any prior answer contained a numbered list, `api.py:3137`), the question is discarded and replaced by `"<saint> Orthodox saint biography life feast teachings martyr monk bishop"`. "What are the 7 sacraments?" after any answer with ≥ 7 numbered items becomes a biography of item 7. Because `last_list` is process-global (`api.py:1749`), item 7 may be from *another user's* conversation.

**C17. "Saint intent" regexes swallow ordinary questions.** `api.py:2599-2626`: `^(?:who\s+is|who\s+was|tell\s+me\s+about|about)\s+(.+)$` with `_find_saint_index_matches(candidate)` as the only guard. "Tell me about baptism" → no saint match → falls through, fine; but "Who was Arius?" or "Tell me about the Council of Nicaea" get scored against saint names with prefix/substring rules (`api.py:366-373`) and can return "I found multiple saints matching…" or "I could not find a dedicated saint entry for 'the Council of Nicaea'" (`api.py:2860-2865`) instead of running retrieval. Short names are always treated as ambiguous (`api.py:1729`), with a hard-coded fallback table (`api.py:46-70`).

**C18. `top_k` and result count.** Frontend always sends `top_k: 8` (`route.ts:94`); backend widens to 10–16 (`api.py:2926-2927`) and then sends **all** surviving chunks to the model (no truncation after filtering, `api.py:3012-3028`). That is ~10–16 page-sized chunks ≈ 8–12 k tokens of context per answer. Reasonable for gpt-4o-mini's window, but it is the wrong shape: many large mixed chunks rather than the best 6–10 focused ones.

### 2.5 Context assembly

**C19. Chunks are concatenated in arbitrary order with a minimal label** (`api.py:3024-3028`: `[Source: saints1.pdf p.329]`). No ordering by score or by document position, no grouping of adjacent pages, no token budget, and no truncation of individual chunks. Website chunks carry only `title (url)`.
*Why it hurts:* the model cannot tell which chunk is most relevant, cannot see that two chunks are consecutive pages of the same entry, and has no page-level reference it could cite in a human-readable way ("Encyclopedia of Saints vol. 1, p. 329" would be better than `saints1.pdf p.329`).

**C20. Conversation history is essentially not used for generation.** History text is injected only when `history_resolved_entity` is set (`api.py:3030`), otherwise the model sees `CONVERSATION SO FAR:` followed by nothing. History is never passed as prior `messages`. The frontend works around this by pasting the previous answer into the question (C14).

### 2.6 Prompting

**C21. The English system prompt actively produces shallow answers.** `api.py:3049-3071`:
- `"Do not include inline citations"` and `"Do not add a Sources section"` — explicitly forbids the citations you want.
- `"When listing items, ALWAYS use numbered format exactly like: 1. Name"` — pushes every answer toward terse lists (which the entity regex then mines, `api.py:3113`).
- No instruction on depth, on quoting the source, on synthesising across several chunks, on explaining terms, or on how long an answer should be. gpt-4o-mini defaults to brief.
- Three separate refusal instructions (`api.py:3035-3036, 3057, 3060-3061`) plus `"If provided context is unrelated to the user question, do not answer from it"` bias the model toward refusing when only part of the context is on-topic.
- The user prompt (`api.py:3073-3097`) pads every request with `ENGLISH RETRIEVAL QUERY`, `MATCHED MANUAL SAINT ALIAS`, and a full `MANUAL ARABIC SAINT ALIASES` table (Arabic strings, `api.py:843-850`) that is irrelevant to English answers. The `language_rules` branch for Arabic (`api.py:3037-3047`) is dead: Arabic requests return from the Arabic branch at `api.py:2725-2852` and never reach it.

**C22. The Arabic system prompt is stricter and has no partial-answer rule.** `api.py:2807-2819` demands the exact refusal sentence when information is "not sufficient" and gives no "answer partially" instruction (the English prompt has one at `api.py:3058`). Combined with C2, Arabic mode refuses more.

**C23. Grounding status and "learn more" gating are string matching on the answer text.** `api.py:1286-1306` and `orthodox-site/app/chat/page.tsx:276-293` search the answer for phrases like `"could not find"`, `"partial"`, `"the sources mention"`. Any answer that legitimately contains the word "partial" is classified as a partial answer. These should be structured outputs from the model (or from retrieval scores), not phrase sniffing.

### 2.7 Generation

**C24. Model and parameters.** `gpt-4o-mini`, `temperature=0.2`, no `max_tokens`, no `seed`, no streaming, no timeout on the OpenAI call (`api.py:2829-2836`, `api.py:3099-3106`). The model is hard-coded in three places (`api.py:858, 2830, 3100`) plus `answer_question.py:56`. For a theology tutor that must synthesise several passages, gpt-4o-mini is the floor, not the ceiling; make the generation model an env var and evaluate a stronger model for generation while keeping a cheap one for query rewriting.

**C25. No streaming anywhere.** Backend returns one JSON blob; Next.js waits for it (`route.ts:86-104`); UI shows typing dots. Perceived latency = full retrieval + full generation, under a 20 s abort. Longer, better answers make this worse. Stream from FastAPI (SSE) through a Next.js streaming route.

### 2.8 Error handling and edge cases

**C26. Empty question length bound / very long questions.** Only emptiness is checked (`api.py:2682`). A 50 k-character question is embedded as-is (8,191-token embedding limit → OpenAI 400 → surfaced as HTTP 500 with the raw error string) and pasted into the prompt.

**C27. Internal error text is returned to the browser.** `api.py:3153-3155` returns `str(e)` in the 500 body; `route.ts:105-116` forwards `detail` to the user. OpenAI/Chroma error messages leak implementation details.

**C28. Startup uses the deprecated `@app.on_event("startup")`** (`api.py:1851`) and every endpoint re-calls `startup()` if globals are unset (`api.py:2675-2678`, `api.py:1923-1924`, …). Use a FastAPI lifespan and fail fast.

**C29. Vercel timeout.** The proxy aborts at 20 s (`route.ts:99`, `saint-detail/route.ts:59`). The Arabic path (C13) plus a long gpt-4o-mini answer can reach that. No `maxDuration` is exported from any route, so the Vercel plan default applies — verify it in the dashboard.

**C30. Rate limits / retries.** Ingestion retries 429s (`ingest_embeddings.py:76-88`); the request path does not. A 429 from OpenAI during chat becomes a 500 to the user.

**C31. Frontend follow-up chips force `mode: "catechism"` and hide the user message** (`orthodox-site/app/chat/page.tsx:874-889`) regardless of the tab the user is in, and catechism mode disables history handling on the backend (C15). Follow-ups in Saints/Chat mode therefore run through the wrong branch.

**C32. Duplicate saint-alias tables on both sides** must be kept in sync by hand: `api.py:74-151` and `orthodox-site/lib/saint-display.ts:9-71`.

**C33. Deployment/ops details.**
- `start_backend.py` auto-ingests on boot when the volume is empty. Without a Railway volume every deploy re-embeds ~7,600 chunks (an OpenAI bill and a multi-minute boot); the README says "recommended", the code should refuse to start ingestion in production unless explicitly opted in.
- `persist_chroma_client` (`chroma_store.py:77-81`) calls `client.persist()`, which does not exist in Chroma ≥ 0.4; the exception is swallowed. Delete it.
- README paths point at `/Users/johnazer/orthodox-ai/...` (`README.md:5-6, 111, 124`), and it references `orthodox-site/.env.example`, which does not exist.
- `next.config.ts` is empty; `@/*` path alias in `tsconfig.json` is unused (all imports are relative).

---

## 3. REMOVE — dead code, unused dependencies, redundant files, scaffolding

**Backend (`api.py`).**
- `_build_english_retrieval_query` (`api.py:853-890`) — defined, never called (only reference is its own `def`). With it, `_fallback_english_retrieval_query` (`api.py:836-840`) and `_arabic_retrieval_hints` (`api.py:810-833`) are only reachable from dead code.
- `_extract_core_name_mentions` (`api.py:1551-1565`) — never called.
- `english_retrieval_query` variable (`api.py:2707`) is always `""` or the question; the `ENGLISH RETRIEVAL QUERY` / `MATCHED MANUAL SAINT ALIAS` / `MANUAL ARABIC SAINT ALIASES` prompt fields (`api.py:3086-3093`) and the Arabic `language_rules` branch (`api.py:3037-3047`) are leftovers from before the Arabic collection existed and never affect an Arabic answer.
- `manual_saint_match` / `_resolve_manual_saint_alias` (`api.py:2687-2696`) only runs for `detected_language == "ar"`, and the Arabic branch never uses `entity`; the result is only printed.
- `_find_weak_saint_mentions` (`api.py:2391-2437`) is used only by `/debug/saints` and does a full-collection scan; drop with the debug endpoint or gate it.
- ~60 `print()` debug lines in the request path (`api.py:2712-2723, 2769-2775, 2881-2883, 2934-2938, 3139-3141`, `_log_retrieval_debug`), several of which dump the full conversation history to stdout (`api.py:2723`). Replace with structured logging (see ADD).

**Backend (files).**
- `chroma_client.py` — a re-export shim of `chroma_store.py`; nothing imports the module (`grep "from chroma_client"` is empty; the string matches elsewhere are a local variable name).
- `main.py` — two-line re-export of `api.app`; `Procfile`/`railway.json` use `start_backend.py`, and uvicorn is invoked with `api:app`.
- `chat.html` — legacy single-file frontend that posts directly to `/chat`; superseded by the Next.js app.
- `answer_question.py`, `test_search.py`, `verify_chroma.py` — ad-hoc dev scripts with hard-coded questions and a third copy of the system prompt; keep at most one under a `scripts/` folder or turn them into the evaluation harness (ADD A9).
- Three identical `chunk_text` functions (`ingest.py:51`, `ingest_arabic_sources.py:38`, `ingest_web.py:35`) and three near-identical `get_collection` / `extract_pages` / `build_chunks` sets — consolidate into one ingestion module with a source-type parameter.
- `runtime.txt` says `python-3.11.9`; the local venv is 3.11.9 but `__pycache__` also contains `cpython-313` files, so someone has run it under 3.13 too. Keep one.
- `posthog` in `requirements.txt` is not imported by the project. It is a transitive Chroma dependency and the `<6` pin was a known workaround for a Chroma/posthog break; keep the pin but comment why, or move to a lockfile.

**Frontend.**
- `orthodox-site/public/pdfs/*.pdf` (34 MB, six files) — no reference anywhere in `app/`, `components/`, `lib/`. They are a second committed copy of the corpus.
- `orthodox-site/icons/checkmark.svg`, `icons/copy.svg` — duplicates of `public/icons/*`; only the `public/` copies are referenced (`app/chat/page.tsx:993`).
- `orthodox-site/images/creditsformat.png` — unreferenced (only `frtadros.webp` is imported).
- `orthodox-site/public/{file,globe,next,vercel,window}.svg` — create-next-app scaffolding.
- `orthodox-site/app/sources/page.tsx` — a redirect to `/credits`; fine to keep if the URL was ever shared, otherwise remove.
- `app/layout.tsx:9` references `/og-image.png`, which does not exist in `public/`.
- `console.log` calls on every render/request in `app/chat/page.tsx` (`364-370, 470-481, 493, 647-673, 684-687, 845-846`) and `app/api/chat/route.ts:61`.
- `lib/i18n.ts` keys never used: `placeholder`, `success`, `youMightAlsoAsk`, `moreCatechismTopics`, `noSaintsFound` (duplicate of `noResultsFound`).

**Repo.**
- `data/pdfs/` (82 MB) is committed so Railway can auto-ingest. If ingestion moves to a one-off job that writes the volume (recommended), the PDFs can leave git (LFS or object storage). At minimum stop committing the `public/pdfs` duplicate. Tracked size today: 119 MB.

---

## 4. ADD — missing capabilities worth building

**A1. Structure-aware ingestion (highest leverage).** One ingestion module that: extracts with PyMuPDF; strips running headers/page numbers/front matter; joins hyphenated and word-per-line output; NFKC-normalises Arabic; segments the catechism by numbered question (use the PDF bookmarks as the section index) and the saints volumes by entry heading + sub-heading; produces ~300–600-token chunks with sentence-boundary splits and cross-page overlap; and stores `{book, volume, section_title, question_no | saint_name, page_start, page_end, chunk_index, language}`. Also emit a `saints_index.json` (name, aliases, page range) at ingest time so `api.py:2041-2112` and `build_arabic_saints_index.py` become unnecessary.

**A2. Real ranking: hybrid retrieval + reranking.** Keep the score from Chroma; run vector + BM25 (or Chroma `$contains`) per query; fuse with reciprocal-rank fusion; then rerank the top ~30 with a cross-encoder (e.g. `bge-reranker`) or an LLM listwise rerank; apply a score threshold before deciding "no source". Delete the substring filter (C12).

**A3. LLM query understanding.** One cheap call that, given history + question, returns `{standalone_question, sub_questions[], entity?, language, intent: saint_lookup|catechism|general}`. Replaces the regex stack (C15–C17) and gives real multi-part-question handling (retrieve per sub-question, then merge). `_build_english_retrieval_query` is a half-built version of this.

**A4. Citations with page numbers.** Number the context blocks (`[1] Encyclopedia of Saints, vol. 1, p. 329 — entry "Abanoub el-Nehissy"`), ask the model to cite `[n]` inline, map back to `sources` with `book`, `page`, `section`. The frontend already stores `sources` per message (`migrations/001_create_chat_tables.sql:24`) and links nothing; render them as clickable footnotes (you can even deep-link into the PDF page if you keep `public/pdfs` for that purpose).

**A5. Conversation memory done properly.** Pass the last N turns as `messages` to the model; keep the standalone rewritten question for retrieval; drop the frontend "paste the previous answer into the question" hack (`page.tsx:245-250`) and the global `last_list`. Store `entities`/`options` per message (already done) and resolve numbered follow-ups against *that conversation's* last assistant message, server-side, using the conversation ID.

**A6. Streaming answers** end-to-end (FastAPI SSE → Next.js `ReadableStream` → UI).

**A7. Answer-quality prompt.** Persona + audience (Coptic Orthodox catechumen / learner), required depth ("explain, then give the source's own words where helpful"), synthesis across chunks, partial-answer wording, citation format, no forced list format, and a separate short refusal rule. Version the prompt in a file, not inline.

**A8. Observability.** Per-request structured log (request id, language, mode, rewritten queries, retrieved chunk ids + scores, reranked ids, tokens in/out, latency per stage, model, grounding decision) to stdout as JSON, plus optional Langfuse/OpenTelemetry. Today there is no way to answer "why did this refuse?" after the fact.

**A9. Evaluation set.** 40–60 questions across catechism, saints, Arabic, follow-ups and multi-part, each with expected pages/entries and a short reference answer, plus ~10 out-of-corpus questions that *should* refuse. Script that runs retrieval-only metrics (recall@k of expected pages) and an LLM-judged answer score, so every change in this plan can be measured. Seed it from the catechism prompts already listed in `app/chat/page.tsx:53-165`.

**A10. Backend hardening.** Shared-secret header between Vercel and Railway; per-IP/per-session rate limiting on `/chat`; question length cap (~1,000 chars); `max_tokens`; OpenAI call timeout + one retry on 429/5xx; remove or protect `/debug/*`.

**A11. Arabic pipeline parity.** After A1/C2, use the same hybrid retrieval and prompt structure for Arabic; add a partial-answer rule; consider a multilingual embedding model (`text-embedding-3-large` or a multilingual open model) and measure with the Arabic slice of A9.

**A12. Response caching.** Cache embedding of identical queries and full answers for identical `(question, language, mode)` within a short TTL; the catechism prompt cards send identical strings repeatedly.

---

## 5. Security and cost concerns

**S1. The backend is public and unauthenticated.** `NEXT_PUBLIC_API_URL` is shipped to the browser (README), and `/chat` accepts any origin-less request (CORS only restricts browsers). Anyone can call the Railway URL directly and spend your OpenAI credit; there is no rate limit, no API key, no per-request token cap, and `top_k` up to 12 is client-controlled (`api.py:1402`).

**S2. Unbounded input → unbounded tokens.** No question length limit (C26); no `max_tokens` on completions (C24); 10–16 page-sized chunks per prompt (C18). Per-request cost is dominated by ~8–12 k input tokens, and the Arabic path adds a second embedding call plus the lexical scan CPU. The one place with a rate limit (`app/api/contact/route.ts:76-92`) uses an in-memory map, which does not survive across Vercel function instances.

**S3. CORS.** `allow_credentials=True` together with `allow_origin_regex=https://.*\.vercel\.app` (`api.py:1736-1743`, `.env.example`) means any `*.vercel.app` site can make credentialed cross-origin requests. Cookies are not used on the backend today, so exposure is limited, but narrow the regex to your own project prefix.

**S4. Debug endpoints are public.** `/debug/chroma`, `/debug/chroma/{en,ar}`, `/debug/saints` (`api.py:1919-1949, 2584-2596`) return sample documents, file paths, and counts, and `/debug/saints` triggers full-collection scans. `/health` also reveals `openai_ready`.

**S5. Error leakage.** Raw exception strings reach the client (C27). Full user history is printed to Railway logs (`api.py:2723`).

**S6. Secrets hygiene — OK.** `.env` and `orthodox-site/.env.local` are gitignored and have never been committed (checked `git log --all` for `.env*`; only `.env.example` appears). `.env.example` contains only placeholders plus two real contact email addresses.

**S7. Postgres TLS.** `rejectUnauthorized: false` in `lib/db.ts:25` and `scripts/migrate-postgres.mjs:57` disables certificate verification. Use the provider's CA or `sslmode=verify-full`.

**S8. Anonymous session cookie is the only tenancy boundary.** Fine for the product, but conversations are unrecoverable if the cookie is cleared and there is no retention policy; note it for later.

**S9. Auto-ingest on boot** (C33) can silently re-spend embedding cost on every deploy if the volume is missing or `CHROMA_DIR` is mis-set.

---

## 6. Prioritised action plan

Effort: **S** = hours, **M** = 1–3 days, **L** = a week or more. Impact is on answer quality unless marked otherwise.

### Top 5 (do these first, in this order)

| # | Action | Impact | Effort | Why first |
|---|---|---|---|---|
| 1 | **Build the evaluation set + structured request logging** (A8, A9) | High (enabler) | S | Every other change becomes measurable; without it you are guessing. Can be done before touching the pipeline. |
| 2 | **Rewrite the generation prompt and feed history as messages** (C20, C21, C22, A5, A7) + set `max_tokens`, make the model an env var | High | S | Cheapest large win: allows citations, depth and synthesis; removes the list-only and triple-refusal bias. No re-ingest needed. |
| 3 | **Remove the hijack heuristics**: delete the keyword relevance filter (C12), the global `last_list` + digit regex (C16), the frontend answer-pasting (C14), and narrow the saint-intent regexes (C17); use scores + a threshold for "no source" (C11) | High | S–M | These are the direct causes of "refused when the answer was there" and "answered a different question". |
| 4 | **Re-ingest with structure-aware chunking and a better extractor** (C1–C5, C7, C8, A1) — PyMuPDF, header/footer stripping, per-Q&A and per-saint-entry chunks, sentence-boundary 300–600-token chunks with overlap, rich metadata, NFKC-normalised Arabic | Very high | L | The single largest quality lever, but it needs #1 to prove it and #2/#3 to show its full effect. |
| 5 | **Hybrid retrieval + reranking + LLM query rewriting** (C11, C13, C15, A2, A3) | High | M | Turns "top-8 of one vector query" into real ranking; fixes multi-part and follow-up questions; replaces the O(N) Arabic scan. |

### Everything else, ranked

| Rank | Item | Ref | Impact | Effort |
|---|---|---|---|---|
| 6 | Citations with page numbers rendered in the UI | A4 | High (trust) | M |
| 7 | Streaming end-to-end | A6, C25 | Medium (perceived quality) | M |
| 8 | Backend auth secret + rate limiting + input caps + remove `/debug` | S1, S2, S4, A10 | High (cost/security) | S |
| 9 | Arabic embedding fix (normalise before embedding) — falls out of #4; if #4 slips, do this alone | C2 | High (Arabic) | S |
| 10 | Evaluate a stronger generation model behind the env var from #2 | C24 | Medium–High | S (+ cost) |
| 11 | Fix Arabic prompt (partial-answer rule) and route follow-up chips through the current mode | C22, C31 | Medium | S |
| 12 | Replace string-sniffed grounding/learn-more with structured model output | C23 | Medium | S |
| 13 | Ingest-time saints index (English + Arabic) replacing runtime heading parsing and override tables | C5, A1 | Medium (saints tab) | M (part of #4) |
| 14 | Consolidate three ingestion scripts into one module; delete dead functions and files listed in §3 | §3 | Low (maintainability) | S |
| 15 | Lifespan startup, error sanitising, OpenAI timeout/retry, question length cap | C26–C30 | Medium (reliability) | S |
| 16 | Remove `public/pdfs` duplicate and scaffolding assets; fix README paths; fix `og-image`, site URL | §3, C33 | Low | S |
| 17 | Postgres TLS verification; narrow CORS regex; stop logging history | S3, S5, S7 | Low–Medium (security) | S |
| 18 | Response/embedding cache | A12 | Low (cost) | S |
| 19 | Move corpus out of git / one-off ingestion job instead of boot-time ingest | C33, S9 | Low (ops) | M |

### Things that are fine as they are

- Embedding model choice and ingestion batching/backoff (`ingest_embeddings.py`).
- Chroma as the vector store at this corpus size (~7.6 k chunks); no need for a hosted vector DB yet.
- Postgres schema and the Next.js proxy/persistence layer (`lib/conversations.ts`, `migrations/001_*`) — simple and correct, including transactional turn saves.
- Contact form validation, honeypot, Turnstile support (`app/api/contact/route.ts`).
- Deterministic chunk IDs and upsert semantics (safe re-runs).
