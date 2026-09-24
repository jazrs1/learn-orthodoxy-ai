# Decision Log — audit phases 1–4

This file records the engineering decisions made while working through the
[AUDIT.md](AUDIT.md) action plan on the `audit-phase-1` branch (Parts A–C) and the
`audit-phase-2` branch (Steps 0–3), the `audit-phase-3` branch (Steps 1–5) and the `audit-phase-4` branch (Steps 1–6). It is written for
someone who reads code comfortably but may be new to RAG systems, backend security,
or evaluation methodology. Every entry explains what problem was being solved, which
alternatives were realistic, what was chosen and why, and a short "concept to learn"
with a search term to go deeper.

Entries are grouped by category and numbered per category (`SEC-001`, `LOG-001`,
`EVAL-001`, ...). Commit hashes: Part A `9989d1f`, Part B `9a4e345`, Part C `ab1cd8d`; Phase 2 Step 0 `7c90db7`, Step 1 `f1e6f0c`, Step 2 `124c744`, Step 3 `9fcf9dd`; Phase 3 Step 1 `a849b17`, Step 2 `5c17620`, Step 3 `3f0cb4c`, Step 4 `24c5ee7`.

## Table of contents

- [Security](#security)
  - [SEC-001: Shared-secret header between Next.js and FastAPI](#sec-001-shared-secret-header-between-nextjs-and-fastapi)
  - [SEC-002: Fail closed when the internal key is missing](#sec-002-fail-closed-when-the-internal-key-is-missing)
  - [SEC-003: Stop shipping the backend URL to the browser](#sec-003-stop-shipping-the-backend-url-to-the-browser)
  - [SEC-004: Hide /debug/* behind ENABLE_DEBUG](#sec-004-hide-debug-behind-enable_debug)
  - [SEC-005: Per-user rate limiting via a forwarded client IP](#sec-005-per-user-rate-limiting-via-a-forwarded-client-ip)
  - [SEC-006: Input caps: question length, history size, top_k](#sec-006-input-caps-question-length-history-size-top_k)
  - [SEC-007: Generic error messages to clients](#sec-007-generic-error-messages-to-clients)
- [Reliability & Error Handling](#reliability--error-handling)
  - [REL-001: OpenAI timeout and single retry via the SDK](#rel-001-openai-timeout-and-single-retry-via-the-sdk)
  - [REL-002: max_tokens on every completion](#rel-002-max_tokens-on-every-completion)
  - [REL-003: Remove the process-global `last_list` and digit regex](#rel-003-remove-the-process-global-last_list-and-digit-regex)
- [Logging & Observability](#logging--observability)
  - [LOG-001: One JSON line per request, emitted from a request-scoped trace object](#log-001-one-json-line-per-request-emitted-from-a-request-scoped-trace-object)
  - [LOG-002: Chunk ids and distances are logged; chunk text and history are not](#log-002-chunk-ids-and-distances-are-logged-chunk-text-and-history-are-not)
  - [LOG-003: Refusal detection reuses the existing phrase heuristic, extended to Arabic](#log-003-refusal-detection-reuses-the-existing-phrase-heuristic-extended-to-arabic)
  - [LOG-004: Per-stage latency via "laps" rather than nested timers](#log-004-per-stage-latency-via-laps-rather-than-nested-timers)
- [Evaluation](#evaluation)
  - [EVAL-001: A hand-verified question set with page-level expected sources](#eval-001-a-hand-verified-question-set-with-page-level-expected-sources)
  - [EVAL-002: Retrieval recall measured at four points in the pipeline](#eval-002-retrieval-recall-measured-at-four-points-in-the-pipeline)
  - [EVAL-003: LLM-as-judge with a 1–5 rubric against the reference answer](#eval-003-llm-as-judge-with-a-15-rubric-against-the-reference-answer)
  - [EVAL-004: Retrieval debug data returned in the response instead of scraped from logs](#eval-004-retrieval-debug-data-returned-in-the-response-instead-of-scraped-from-logs)
  - [EVAL-005: Baseline run committed under eval/results/](#eval-005-baseline-run-committed-under-evalresults)
  - [EVAL-006: What the baseline run showed (and where it corrects AUDIT.md)](#eval-006-what-the-baseline-run-showed-and-where-it-corrects-auditmd)
  - [EVAL-007: Judge moved to a stronger, different model (gpt-4.1) with a human-check sheet](#eval-007-judge-moved-to-a-stronger-different-model-gpt-41-with-a-human-check-sheet)
  - [EVAL-008: Phase 2 results, step by step](#eval-008-phase-2-results-step-by-step)
  - [EVAL-009: Judge vs human on the 10-question check sheet](#eval-009-judge-vs-human-on-the-10-question-check-sheet)
  - [EVAL-010: Coverage replaces the holistic score as the headline quality metric](#eval-010-coverage-replaces-the-holistic-score-as-the-headline-quality-metric)
  - [EVAL-011: Faithfulness — every claim is checked against the passage it cites](#eval-011-faithfulness--every-claim-is-checked-against-the-passage-it-cites)
  - [EVAL-012: Near-miss out-of-corpus questions and a sticky tune/holdout split](#eval-012-near-miss-out-of-corpus-questions-and-a-sticky-tuneholdout-split)
  - [EVAL-013: Phase 3 before/after on tune and holdout](#eval-013-phase-3-beforeafter-on-tune-and-holdout)
  - [EVAL-014: Phase 4 diagnosis — where the production refusals and weak answers come from](#eval-014-phase-4-diagnosis--where-the-production-refusals-and-weak-answers-come-from)
  - [EVAL-015: Task-style questions, production examples, and a format metric](#eval-015-task-style-questions-production-examples-and-a-format-metric)
- [Retrieval](#retrieval)
  - [RET-001: A saint-index miss falls through to retrieval instead of refusing](#ret-001-a-saint-index-miss-falls-through-to-retrieval-instead-of-refusing)
  - [RET-002: The keyword relevance filter is deleted; results are merged by vector distance](#ret-002-the-keyword-relevance-filter-is-deleted-results-are-merged-by-vector-distance)
  - [RET-003: "No relevant source" is decided by a distance threshold chosen from the eval data](#ret-003-no-relevant-source-is-decided-by-a-distance-threshold-chosen-from-the-eval-data)
  - [RET-004: The distance threshold stays at 1.0; near-miss refusals need a different mechanism](#ret-004-the-distance-threshold-stays-at-10-near-miss-refusals-need-a-different-mechanism)
  - [RET-005: Raise the distance threshold to 1.1 after a production false refusal on a short query](#ret-005-raise-the-distance-threshold-to-11-after-a-production-false-refusal-on-a-short-query)
  - [RET-006: One analysis call separates the retrieval query from the requested task](#ret-006-one-analysis-call-separates-the-retrieval-query-from-the-requested-task)
  - [RET-007: Broad requests retrieve wider; saint lists are built from the saint index](#ret-007-broad-requests-retrieve-wider-saint-lists-are-built-from-the-saint-index)
  - [RET-008: Comparisons with another church also retrieve the passages that name it](#ret-008-comparisons-with-another-church-also-retrieve-the-passages-that-name-it)
  - [RET-009: Distance threshold 1.25, as an off-topic guard only](#ret-009-distance-threshold-125-as-an-off-topic-guard-only)
  - [RET-010: Namesake menus select by saint ID; a menu only for genuinely shared names](#ret-010-namesake-menus-select-by-saint-id-a-menu-only-for-genuinely-shared-names)
  - [RET-011: Default saints for bare names; hand-written alias audit](#ret-011-default-saints-for-bare-names-hand-written-alias-audit)
  - [RET-012: Where a request's time goes, and what could make it faster (report, not changed)](#ret-012-where-a-requests-time-goes-and-what-could-make-it-faster-report-not-changed)
  - [RET-013: The Arabic lexical scan runs over an in-memory copy of the normalised chunks](#ret-013-the-arabic-lexical-scan-runs-over-an-in-memory-copy-of-the-normalised-chunks)
  - [RET-014: Each query text is embedded once per request, and the search is given the vectors](#ret-014-each-query-text-is-embedded-once-per-request-and-the-search-is-given-the-vectors)
  - [RET-015: The question is embedded while the analysis call runs, and reused when the analysis leaves it unchanged](#ret-015-the-question-is-embedded-while-the-analysis-call-runs-and-reused-when-the-analysis-leaves-it-unchanged)
  - [RET-016: A first-turn question asked before reuses its analysis](#ret-016-a-first-turn-question-asked-before-reuses-its-analysis)
  - [RET-017: The home page's example questions keep their answer, replayed as a stream](#ret-017-the-home-pages-example-questions-keep-their-answer-replayed-as-a-stream)
  - [RET-018: Each hop of a question is timed: the site's routes and the backend write lines that join up](#ret-018-each-hop-of-a-question-is-timed-the-sites-routes-and-the-backend-write-lines-that-join-up)
  - [RET-019: Verification of the speed changes: quality holds; Arabic answers start ~0.7 s sooner, English ~0.1 s, repeated example questions at once](#ret-019-verification-of-the-speed-changes-quality-holds-arabic-answers-start-07-s-sooner-english-01-s-repeated-example-questions-at-once)
  - [RET-020: The path from click to first word, hop by hop, and what creating the conversation in the stream route would save (report)](#ret-020-the-path-from-click-to-first-word-hop-by-hop-and-what-creating-the-conversation-in-the-stream-route-would-save-report)
  - [RET-021: A new chat's conversation is created when its first answer is saved; the answer and sources arrive before the IDs; a failed save is retried, then said plainly](#ret-021-a-new-chats-conversation-is-created-when-its-first-answer-is-saved-the-answer-and-sources-arrive-before-the-ids-a-failed-save-is-retried-then-said-plainly)
  - [RET-022: Owner's decisions after RET-020, and how small a regression one tune run can catch (proposal)](#ret-022-owners-decisions-after-ret-020-and-how-small-a-regression-one-tune-run-can-catch-proposal)
  - [RET-024: Production, hop by hop: ~0.25–0.45 s outside the backend; the slow parts are in the backend; Railway runs across the continent from Vercel and Neon](#ret-024-production-hop-by-hop-025045-s-outside-the-backend-the-slow-parts-are-in-the-backend-railway-runs-across-the-continent-from-vercel-and-neon)
  - [RET-025: Checks of answer changes use two runs per side, Arabic four, and report the change with its noise band; the judge's share of the noise is small](#ret-025-checks-of-answer-changes-use-two-runs-per-side-arabic-four-and-report-the-change-with-its-noise-band-the-judges-share-of-the-noise-is-small)
  - [RET-023: AR-03 with the RET-010/011 saint commits on and off: no regression](#ret-023-ar-03-with-the-ret-010011-saint-commits-on-and-off-no-regression)
- [Prompting & Generation](#prompting--generation)
  - [GEN-001: System prompts live in versioned files under prompts/](#gen-001-system-prompts-live-in-versioned-files-under-prompts)
  - [GEN-002: A learner-oriented prompt with one refusal rule, numbered passages and inline [n] citations](#gen-002-a-learner-oriented-prompt-with-one-refusal-rule-numbered-passages-and-inline-n-citations)
  - [GEN-003: Conversation history is sent as real messages](#gen-003-conversation-history-is-sent-as-real-messages)
  - [GEN-004: Prompt v3 — flexible about format and task, strict about content](#gen-004-prompt-v3--flexible-about-format-and-task-strict-about-content)
  - [GEN-005: Generation model: gpt-4.1-mini recommended over gpt-4o-mini](#gen-005-generation-model-gpt-41-mini-recommended-over-gpt-4o-mini)
  - [GEN-006: Named-subject check before generation, plus a scope gate for Arabic](#gen-006-named-subject-check-before-generation-plus-a-scope-gate-for-arabic)
  - [GEN-007: Streaming answers — plan: SSE from FastAPI through the Next.js route, /chat unchanged](#gen-007-streaming-answers--plan-sse-from-fastapi-through-the-nextjs-route-chat-unchanged)
  - [GEN-008: /chat/stream — one shared preparation, the answer streamed, the log line written when the stream ends](#gen-008-chatstream--one-shared-preparation-the-answer-streamed-the-log-line-written-when-the-stream-ends)
- [Frontend](#frontend)
  - [FE-001: Follow-up chips are ordinary user turns in the conversation's own mode](#fe-001-follow-up-chips-are-ordinary-user-turns-in-the-conversations-own-mode)
  - [FE-002: Answers are rendered as Markdown (GFM tables), wide tables scroll inside the bubble](#fe-002-answers-are-rendered-as-markdown-gfm-tables-wide-tables-scroll-inside-the-bubble)
- [UI/UX](#uiux)
  - [UI-001: UI refresh on its own branch, frontend only, shipped with Phase 4](#ui-001-ui-refresh-on-its-own-branch-frontend-only-shipped-with-phase-4)
  - [UI-002: Audit screenshots use browser-level API mocks filled with real eval answers](#ui-002-audit-screenshots-use-browser-level-api-mocks-filled-with-real-eval-answers)
  - [UI-003: Accessibility and performance measured with axe and Lighthouse on a production build](#ui-003-accessibility-and-performance-measured-with-axe-and-lighthouse-on-a-production-build)
  - [UI-004: Fixes ranked by first-time-visitor impact; showing sources is priority one](#ui-004-fixes-ranked-by-first-time-visitor-impact-showing-sources-is-priority-one)
  - [UI-005: Three design directions proposed; the choice is pending](#ui-005-three-design-directions-proposed-the-choice-is-pending)
  - [UI-006: Citations link to a per-answer Sources list; books shown as text, not PDF links](#ui-006-citations-link-to-a-per-answer-sources-list-books-shown-as-text-not-pdf-links)
  - [UI-007: Design foundation — self-hosted fonts, color and type tokens, logical CSS, real icons](#ui-007-design-foundation--self-hosted-fonts-color-and-type-tokens-logical-css-real-icons)
  - [UI-008: Broken states fixed; language remembered in a cookie and rendered on the server](#ui-008-broken-states-fixed-language-remembered-in-a-cookie-and-rendered-on-the-server)
  - [UI-009: A landing page that explains the site; the empty history column is hidden for new visitors](#ui-009-a-landing-page-that-explains-the-site-the-empty-history-column-is-hidden-for-new-visitors)
  - [UI-010: Sharing and SEO — one site URL, per-page metadata, a real social card, no debug logging](#ui-010-sharing-and-seo--one-site-url-per-page-metadata-a-real-social-card-no-debug-logging)
  - [UI-011: Font loading trimmed after the first "after" measurement](#ui-011-font-loading-trimmed-after-the-first-after-measurement)
  - [UI-012: Traditional redesign on its own branch; logo redrawn as outlined SVG (proposal)](#ui-012-traditional-redesign-on-its-own-branch-logo-redrawn-as-outlined-svg-proposal)
  - [UI-013: Classical type and logo colors — EB Garamond for display, Source Serif 4 kept for reading](#ui-013-classical-type-and-logo-colors--eb-garamond-for-display-source-serif-4-kept-for-reading)
  - [UI-014: Book-style layout replaces the app patterns; logo assets wired in through one switch](#ui-014-book-style-layout-replaces-the-app-patterns-logo-assets-wired-in-through-one-switch)
  - [UI-015: Verification of the traditional design; the italic font is preloaded only where it is used](#ui-015-verification-of-the-traditional-design-the-italic-font-is-preloaded-only-where-it-is-used)
  - [UI-016: Italic reserved for quoted matter inside answers; the italic font file is dropped](#ui-016-italic-reserved-for-quoted-matter-inside-answers-the-italic-font-file-is-dropped)
  - [UI-017: Home page order: the hero first, the Today line below the example questions](#ui-017-home-page-order-the-hero-first-the-today-line-below-the-example-questions)
  - [UI-018: The Today banner becomes one quiet line](#ui-018-the-today-banner-becomes-one-quiet-line)
  - [UI-019: Navigation cut to Chat, Catechism, Saints and Calendar; Credits and Contact in a footer; one language toggle](#ui-019-navigation-cut-to-chat-catechism-saints-and-calendar-credits-and-contact-in-a-footer-one-language-toggle)
  - [UI-020: Past chats open as a drawer on the home page; repeated titles listed once; phone header padding](#ui-020-past-chats-open-as-a-drawer-on-the-home-page-repeated-titles-listed-once-phone-header-padding)
  - [UI-021: A two-line hero description; "sources shown" said once](#ui-021-a-two-line-hero-description-sources-shown-said-once)
  - [UI-022: Four example questions, without dotted leaders](#ui-022-four-example-questions-without-dotted-leaders)
  - [UI-023: Home page declutter: what still competes on the first screen (report, not changed)](#ui-023-home-page-declutter-what-still-competes-on-the-first-screen-report-not-changed)
  - [UI-024: The Today banner goes back to the top, as a full-width band](#ui-024-the-today-banner-goes-back-to-the-top-as-a-full-width-band)
  - [UI-025: A collapsible past-chats sidebar shared by the home and chat pages; a four-link header without divider; the language toggle set like the links](#ui-025-a-collapsible-past-chats-sidebar-shared-by-the-home-and-chat-pages-a-four-link-header-without-divider-the-language-toggle-set-like-the-links)
  - [UI-026: Streamed answers in the chat page: words fade in, tables wait for their last row, Stop, Jump to latest, one announcement](#ui-026-streamed-answers-in-the-chat-page-words-fade-in-tables-wait-for-their-last-row-stop-jump-to-latest-one-announcement)
  - [UI-027: Verification of streaming: time to first text against v2, a colour fade instead of an opacity one, axe at 0](#ui-027-verification-of-streaming-time-to-first-text-against-v2-a-colour-fade-instead-of-an-opacity-one-axe-at-0)
  - [UI-028: The question is scrolled near the top once; the view stays put while the answer streams; a small "↓" jumps to the latest text](#ui-028-the-question-is-scrolled-near-the-top-once-the-view-stays-put-while-the-answer-streams-a-small--jumps-to-the-latest-text)
  - [UI-029: The saints pane streams its answer like the chat; every place that asks for an answer checked](#ui-029-the-saints-pane-streams-its-answer-like-the-chat-every-place-that-asks-for-an-answer-checked)
- [Code Cleanup](#code-cleanup)
- [Deployment & Config](#deployment--config)
  - [DEP-001: Model name and tuning knobs moved to environment variables](#dep-001-model-name-and-tuning-knobs-moved-to-environment-variables)
- [Calendar](#calendar)
  - [CAL-001: Calendar data source — compute feasts and fasts ourselves; saints from Katameros only once permission is given](#cal-001-calendar-data-source--compute-feasts-and-fasts-ourselves-saints-from-katameros-only-once-permission-is-given)
  - [CAL-002: Feasts and fasts generated from written-out rules into a static file; coptic-calendar only converts dates](#cal-002-feasts-and-fasts-generated-from-written-out-rules-into-a-static-file-coptic-calendar-only-converts-dates)
  - [CAL-003: Katameros saint titles extracted once into one swappable file, linked conservatively to our saints index](#cal-003-katameros-saint-titles-extracted-once-into-one-swappable-file-linked-conservatively-to-our-saints-index)
  - [CAL-004: "Today" comes from the visitor's clock, picked before first paint; the day boundary and saint order are one setting each](#cal-004-today-comes-from-the-visitors-clock-picked-before-first-paint-the-day-boundary-and-saint-order-are-one-setting-each)
  - [CAL-005: Today strip at the top of the home page, linking the date to the calendar and the saint to our saints index](#cal-005-today-strip-at-the-top-of-the-home-page-linking-the-date-to-the-calendar-and-the-saint-to-our-saints-index)
  - [CAL-006: /calendar — one server-rendered month at a time, a keyboard grid, and a detail panel with saint links](#cal-006-calendar--one-server-rendered-month-at-a-time-a-keyboard-grid-and-a-detail-panel-with-saint-links)
  - [CAL-007: Verification of the calendar feature](#cal-007-verification-of-the-calendar-feature)
  - [CAL-008: Calendar saint links regenerated from v2 (runbook step 3.5)](#cal-008-calendar-saint-links-regenerated-from-v2-runbook-step-35)
- [Ingestion](#ingestion)
  - [ING-001: Re-ingestion design (Phase 5 Step 0) — PyMuPDF for English, pypdf + NFKC for Arabic, structure-aware units, v2 alongside v1](#ing-001-re-ingestion-design-phase-5-step-0--pymupdf-for-english-pypdf--nfkc-for-arabic-structure-aware-units-v2-alongside-v1)
  - [ING-002: One ingestion package; extraction and cleaning verified corpus-wide; v1 rebuild proven identical; old scripts deleted](#ing-002-one-ingestion-package-extraction-and-cleaning-verified-corpus-wide-v1-rebuild-proven-identical-old-scripts-deleted)
  - [ING-003: Per-source segmenters, chunker, ingest-time saints index and the v2 dry run](#ing-003-per-source-segmenters-chunker-ingest-time-saints-index-and-the-v2-dry-run)
  - [ING-004: v2 embedded locally into chroma_db/v2; v1 byte-identical before and after](#ing-004-v2-embedded-locally-into-chroma_dbv2-v1-byte-identical-before-and-after)
  - [ING-005: Retrieval on v2 behind CORPUS_VERSION; one source per cited passage; ingest-time saints index; v1 output proven identical](#ing-005-retrieval-on-v2-behind-corpus_version-one-source-per-cited-passage-ingest-time-saints-index-v1-output-proven-identical)
  - [ING-006: v1 vs v2 evaluation — v2 raises Arabic coverage by 13 points, English is unchanged; v2 top-k 16, threshold stays 1.25](#ing-006-v1-vs-v2-evaluation--v2-raises-arabic-coverage-by-13-points-english-is-unchanged-v2-top-k-16-threshold-stays-125)
  - [ING-007: "Saints named X" lists by name, Arabic saint lists on v2, top-k 16 kept, Arabic page ranges read in order](#ing-007-saints-named-x-lists-by-name-arabic-saint-lists-on-v2-top-k-16-kept-arabic-page-ranges-read-in-order)
  - [ING-008: Deployment runbook for v2 — background build (option B) recommended over railway ssh](#ing-008-deployment-runbook-for-v2--background-build-option-b-recommended-over-railway-ssh)
- [Open questions](#open-questions)

---

## Security

### SEC-001: Shared-secret header between Next.js and FastAPI
- **Date / Part:** 2026-09-15, Part A (commit 9989d1f)
- **Audit ref:** S1, A10
- **Context:** The FastAPI backend on Railway was reachable by anyone on the internet. Its URL was even shipped in the browser bundle. Anyone could `POST /chat` and spend the project's OpenAI credit, and nothing distinguished the real frontend from a script.
- **Options considered:**
  1. *Shared secret header* checked on every request. Pros: ~20 lines, no new infrastructure, works with any HTTP client. Cons: one static credential; must be rotated by hand if leaked.
  2. *Signed requests (HMAC of body + timestamp)*. Pros: replay-resistant, the secret never travels on the wire. Cons: more code on both sides, clock skew handling; overkill for a server-to-server hop that already runs over TLS.
  3. *Network-level isolation* (Railway private networking / IP allow-list of Vercel egress). Pros: no application code. Cons: Vercel egress IPs are not stable on hobby plans, and Railway private networking does not reach Vercel.
- **Decision:** Option 1. A FastAPI HTTP middleware (`api.py`, `require_internal_key`) rejects any request whose `X-Internal-Key` header does not match `INTERNAL_API_KEY` (constant-time compare with `hmac.compare_digest`). `/health` and CORS preflights are exempt. The Next.js server routes attach the header through a new `orthodox-site/lib/backend.ts` helper.
- **Why:** It closes the "anyone can call it" hole with the least machinery, and it composes with everything else (rate limiting can now trust forwarded headers, see SEC-005). Middleware rather than a per-route dependency so that any route added later is protected by default.
- **Files changed:** `api.py`, `orthodox-site/lib/backend.ts`, `orthodox-site/app/api/{chat,saint-detail,saints,saint-suggestions}/route.ts`, `.env.example`, `orthodox-site/.env.example`, `README.md`.
- **Concept to learn:** This is *service-to-service authentication*. A public frontend server (Next.js on Vercel) proxies to a private backend; the backend cannot see who the human is, so it at least verifies that the *caller* is the trusted server. Constant-time comparison matters because a naive `==` returns faster when the first byte differs, which an attacker can measure to guess the secret byte by byte. Search: "API key authentication middleware", "timing attack string comparison".
- **Revisit if:** more than one caller needs different permissions (then move to per-caller keys or JWTs); or if the key has to be rotated without downtime (support two valid keys during rotation).

### SEC-002: Fail closed when the internal key is missing
- **Date / Part:** 2026-09-15, Part A (commit 9989d1f)
- **Audit ref:** S1
- **Context:** What should the backend do if `INTERNAL_API_KEY` is simply not set on Railway?
- **Options considered:**
  1. *Allow everything with a warning* (fail open). Pros: nothing breaks when you forget the variable. Cons: forgetting the variable silently reopens the exact hole we are closing.
  2. *Refuse everything except /health with 503* (fail closed). Pros: a misconfiguration is loud and obvious within seconds of deploying. Cons: the site is down until the variable is set.
- **Decision:** Fail closed. The middleware returns `503 Server is not configured.`, and startup logs an ERROR.
- **Why:** Security controls that quietly disable themselves are worse than none, because everyone believes they are on. `/health` stays open so Railway's health check still passes and you can see the service is alive but misconfigured.
- **Files changed:** `api.py`.
- **Concept to learn:** *Fail-open vs fail-closed.* When a safety mechanism cannot do its job, it either lets traffic through (open) or blocks it (closed). Authentication should fail closed; things like a metrics exporter should fail open. Search: "fail open vs fail closed security".
- **Revisit if:** you add a local-dev mode where setting a key is annoying; even then prefer a dev-only default key over disabling the check.

### SEC-003: Stop shipping the backend URL to the browser
- **Date / Part:** 2026-09-15, Part A (commit 9989d1f)
- **Audit ref:** S1 (and the "stop exposing" instruction)
- **Context:** `NEXT_PUBLIC_API_URL` was read as a fallback in four server routes. Anything prefixed `NEXT_PUBLIC_` is inlined into the client JavaScript bundle, so the Railway URL was public even though no browser code used it. `chat.html`, the legacy page, called the backend directly from the browser.
- **Options considered:**
  1. Keep the fallback for convenience. Cons: the URL keeps leaking; a future developer might start using it from client code.
  2. Read only `ORTHODOX_API_URL` (server-only) and centralise the fetch in one helper.
- **Decision:** Option 2. `backendUrl()` in `lib/backend.ts` reads `ORTHODOX_API_URL` only; the file imports `server-only` so it cannot be bundled for the client. `NEXT_PUBLIC_API_URL` can be deleted from Vercel.
- **Why:** With the secret header in place the URL alone is not a credential, but there is no reason to publish it, and centralising the fetch means the header, timeout and IP forwarding cannot be forgotten in a new route.
- **Files changed:** `orthodox-site/lib/backend.ts`, the four API routes, `README.md`.
- **Concept to learn:** In Next.js, environment variables are server-only unless they start with `NEXT_PUBLIC_`; those are baked into the browser bundle at build time. The `server-only` package makes a module throw if it is imported from client code. Search: "Next.js environment variables NEXT_PUBLIC", "server-only package".
- **Revisit if:** a truly client-side feature needs the backend (it should not; add a Next.js route instead).

### SEC-004: Hide /debug/* behind ENABLE_DEBUG
- **Date / Part:** 2026-09-15, Part A (commit 9989d1f)
- **Audit ref:** S4
- **Context:** `/debug/chroma`, `/debug/chroma/{en,ar}` and `/debug/saints` returned sample documents, paths and counts, and `/debug/saints` scans the whole collection.
- **Options considered:** delete the endpoints; keep them but require the internal key (already true after SEC-001); additionally gate them by an env flag.
- **Decision:** Keep them, require the key *and* `ENABLE_DEBUG=1`; otherwise respond `404 Not found`.
- **Why:** They are genuinely useful when diagnosing a Railway volume problem. 404 instead of 403 so their existence is not advertised in production.
- **Files changed:** `api.py` (`_require_debug_enabled`).
- **Concept to learn:** *Feature flags for operational endpoints.* Debug surfaces are a common source of information leaks; gating them by environment keeps production's attack surface small while keeping the tooling one env var away. Search: "security through obscurity vs defense in depth", "feature flag".
- **Revisit if:** you build real observability (LOG-* entries); most of these endpoints then become redundant and can be deleted.

### SEC-005: Per-user rate limiting via a forwarded client IP
- **Date / Part:** 2026-09-15, Part A (commit 9989d1f)
- **Audit ref:** S1, S2, A10
- **Context:** Nothing limited how fast `/chat` could be called. Each call costs an embedding plus a ~10k-token completion.
- **Options considered:**
  1. *Per-IP limit using the TCP peer address.* Cons: every request reaches the backend from Vercel's servers, so all users share one or a few IPs; the limiter would throttle everyone together and never isolate an abuser.
  2. *Forward the end user's IP from Next.js in a header and limit on that.* Pros: per-user isolation. Cons: the header is spoofable, so it may only be trusted from authenticated callers.
  3. *A library (`slowapi`) or a shared store (Redis).* Pros: battle-tested; Redis survives restarts and multiple instances. Cons: a new dependency or a new service for a single-process backend.
- **Decision:** Option 2 with a small in-memory sliding-window limiter (`SlidingWindowRateLimiter` in `api.py`): 20 requests/min per client IP plus a global ceiling of 300/min (both env-configurable). Next.js sends `X-Client-IP` from Vercel's `x-forwarded-for`. The backend trusts that header only because SEC-001 already proved the caller is our own server. Responses are `429` with a `Retry-After` header.
- **Why:** Gives real per-user protection and a hard cost ceiling with zero new infrastructure. The global limiter is the "cost guard": even a distributed abuser cannot exceed 300 calls/min.
- **Files changed:** `api.py`, `orthodox-site/lib/backend.ts`.
- **Concept to learn:** *Rate limiting* bounds how many requests a key (IP, user, API key) may make per time window. Behind a proxy or CDN the socket IP is the proxy's, so you must use a forwarded header (`X-Forwarded-For`) and only from proxies you trust, otherwise clients can forge it. A *sliding window* counts events in the last N seconds rather than resetting on the minute, which avoids a burst at each boundary. Search: "sliding window rate limiter", "X-Forwarded-For trusted proxies".
- **Revisit if:** the backend runs more than one process or instance (counters are per process; move to Redis), or if legitimate classroom use from one NAT IP hits the per-IP cap (raise `CHAT_RATE_LIMIT_PER_MINUTE` or key on the anonymous session cookie instead).

### SEC-006: Input caps: question length, history size, top_k
- **Date / Part:** 2026-09-15, Part A (commit 9989d1f)
- **Audit ref:** S2, C26
- **Context:** A 50,000-character question would be embedded (failing at the embedding limit) and pasted into the prompt; history was an untyped list of arbitrary size; `top_k` was client-controlled.
- **Options considered:** validate in Pydantic (returns 422 with a schema error), or validate in code with a plain 400 message; cap only the question vs also history.
- **Decision:** In code: `400 Question is too long…` above `MAX_QUESTION_CHARS` (1000, env-configurable); history sanitised to the last 12 well-formed messages of at most 4000 chars each; `top_k` clamped to 1–12 server-side. The Next.js route checks the 1000-char cap too so the user sees the message without a round trip.
- **Why:** A friendly 400 is better for the UI than Pydantic's 422 structure. Bounding history was not in the task list but falls under S2 (unbounded tokens) and was two lines.
- **Files changed:** `api.py` (`_sanitize_history`, chat handler), `orthodox-site/app/api/chat/route.ts`.
- **Concept to learn:** *Input validation at the trust boundary.* Everything from the network is untrusted; size limits protect cost and availability, not only correctness. Search: "input validation OWASP", "denial of wallet".
- **Revisit if:** the product wants long pasted passages as questions (raise the cap and truncate the retrieval query separately).

### SEC-007: Generic error messages to clients
- **Date / Part:** 2026-09-15, Part A (commit 9989d1f)
- **Audit ref:** C27, S5
- **Context:** Every `except Exception` returned `str(e)` to the browser; OpenAI and Chroma error strings leaked implementation details.
- **Options considered:** keep raw messages in dev only; always generic; generic plus an error id the user can quote.
- **Decision:** Always generic. Three fixed messages (server error, busy, timeout), chosen by exception type; the real exception goes to the server log with a stack trace via `logger.exception`. OpenAI rate limits/5xx/connection errors map to `503` with `Retry-After`, timeouts to `504`.
- **Why:** The frontend already shows `detail` verbatim, so the message must be user-safe. Distinguishing 503/504 lets the UI (or a future retry) behave sensibly.
- **Files changed:** `api.py` (`_openai_error_to_http`, all `except` blocks).
- **Concept to learn:** *Error handling at the edge:* log everything server-side, tell the client only what it can act on. Search: "information disclosure error messages", "HTTP 503 Retry-After".
- **Revisit if:** you add request ids to logs (Part B); then include the id in the generic message so users can report it.

## Reliability & Error Handling

### REL-001: OpenAI timeout and single retry via the SDK
- **Date / Part:** 2026-09-15, Part A (commit 9989d1f)
- **Audit ref:** C24, C30
- **Context:** Completions had no timeout and no retry; a stalled OpenAI request held the worker until Vercel gave up at 20 s.
- **Options considered:** hand-written retry loop around each call (like `ingest_embeddings.py` does); use the OpenAI SDK's built-in `timeout` and `max_retries`; a generic library such as `tenacity`.
- **Decision:** SDK built-ins: `OpenAI(timeout=25, max_retries=1)`. The SDK retries once, with backoff, on 408/409/429/5xx, connection errors and timeouts.
- **Why:** It is the smallest correct change and covers every call through that client (including the embedding calls Chroma makes are *not* covered — Chroma constructs its own OpenAI client; see Open questions).
- **Files changed:** `api.py` (startup).
- **Concept to learn:** *Timeouts and bounded retries.* A retry is only safe for idempotent operations (a completion request is), and must be bounded or it multiplies load during an outage. The 25 s timeout plus one retry means a worst case of ~50 s, longer than the Vercel proxy's 20 s abort, so the proxy remains the effective ceiling. Search: "exponential backoff retry idempotent", "timeout budget".
- **Revisit if:** streaming is added (per-token timeouts differ), or the proxy timeout changes.

### REL-002: max_tokens on every completion
- **Date / Part:** 2026-09-15, Part A (commit 9989d1f)
- **Audit ref:** S2, C24
- **Context:** No completion had `max_tokens`; the model could in theory run to its maximum output length.
- **Decision:** `ANSWER_MAX_TOKENS` (default 1200, env-configurable) on both answer completions; the dead query-rewrite helper already had 90.
- **Why:** 1200 tokens is roughly 900 words, enough for a thorough theology answer with room for citations later, while bounding cost.
- **Files changed:** `api.py`.
- **Concept to learn:** `max_tokens` caps *output* tokens only; input cost is bounded by the context you assemble (chunk count and size). Search: "OpenAI max_tokens vs context window".
- **Revisit if:** answers get truncated mid-sentence (raise it, or ask the model for a length target in the prompt).

### REL-003: Remove the process-global `last_list` and digit regex
- **Date / Part:** 2026-09-15, Part A (commit 9989d1f)
- **Audit ref:** C16
- **Context:** A module-level dict remembered the last numbered list produced by *any* user; any question containing a digit 1–12 could be rewritten into a saint biography from another user's list.
- **Options considered:** rebuild per-conversation resolution now (frontend already stores `options`/`entities` per message); remove and leave a TODO.
- **Decision:** Removed the global, its five write sites and the regex; left a TODO describing the correct design (resolve against the previous assistant message of *this* conversation, and only for clear ordinal selections). Numbered follow-ups typed by hand ("the 2nd one") no longer work; clicking an option chip still works because the frontend sends an explicit `search saint: <name>`.
- **Why:** The task said not to build it yet, and shipping a cross-user bug is worse than a missing convenience.
- **Files changed:** `api.py`.
- **Concept to learn:** *Request-scoped vs process-scoped state.* Anything stored at module level in a web server is shared by every request and every user; per-conversation state must be keyed by a conversation id and stored where the conversation lives (here, Postgres). Search: "shared mutable state web server", "request scope".
- **Revisit if:** users ask for typed ordinal follow-ups; implement per the TODO.

## Logging & Observability

### LOG-001: One JSON line per request, emitted from a request-scoped trace object
- **Date / Part:** 2026-09-15, Part B (commit 9a4e345)
- **Audit ref:** A8, C13 (latency visibility), S5 (history in logs)
- **Context:** The request path had ~60 `print()` calls that dumped the full conversation history, chunk previews and internal state as free text. You could not answer "why did request X refuse?" after the fact, and the lines could not be indexed or filtered.
- **Options considered:**
  1. *Keep prints but add a prefix.* Cheap, but still unstructured and still leaks history/chunk text.
  2. *One structured record per request*, built up during the request and emitted once at the end. Pros: a single line holds everything (queries, ids, distances, tokens, timings, outcome); trivial to `jq`; no interleaving between concurrent requests. Cons: a crash before emission loses the partial record unless handled (handled: the context manager emits on exceptions too).
  3. *OpenTelemetry tracing / Langfuse.* Pros: dashboards, span trees. Cons: a new dependency and a hosted service; too much for the current scale, and it can be added on top of the same trace object later.
- **Decision:** Option 2. New module `request_log.py` with `RequestTrace`: a context manager that records fields, per-stage laps, retrieval hits and generation usage, and writes `json.dumps(record)` to the `orthodox.request` logger (stdout, bare JSON, no prefix). `chat()` became a thin wrapper that opens the trace and calls `_chat_impl()`; `/saints` and `/saint-suggestions` emit a smaller record. The request id is returned to the client in `X-Request-ID`.
- **Why:** Railway captures stdout, so JSON-per-line is immediately searchable there and portable to any log platform. Emitting once per request means the log is a complete, self-contained story of that request.
- **Files changed:** `request_log.py` (new), `api.py`.
- **Concept to learn:** *Structured logging* means logging key/value data instead of sentences, so machines can filter (`outcome=refused AND language=ar`) and aggregate (p95 of `stages_ms.generation`). A *request id* correlates the client's error, the proxy log and the backend log for the same call. Search: "structured logging JSON", "correlation id request tracing".
- **Revisit if:** you want span-level timing inside retrieval or multi-service traces; then wrap the same fields in OpenTelemetry spans.

### LOG-002: Chunk ids and distances are logged; chunk text and history are not
- **Date / Part:** 2026-09-15, Part B (commit 9a4e345)
- **Audit ref:** A8, S5
- **Context:** The task requires retrieved chunk ids with distances and which chunks survived filtering, but forbids logging chunk text or the full history.
- **Options considered:** change `_retrieve_documents` to return ids/distances (touches every caller and the merge/filter helpers, risking a behaviour change in a "logging only" part); or reconstruct ids from metadata and record hits inside the retrieval functions via a context variable.
- **Decision:** The second. `chunk_id_from_metadata()` rebuilds the deterministic ingestion id (`saints1.pdf::p329::c0`, `ar::…`, `website::<hash>::c<n>`) so "kept" ids can be derived from the surviving metadata without changing any function signature. Inside `_retrieve_documents` the Chroma response's `ids` and `distances` are attached per query; the lexical Arabic search attaches its integer scores. History contributes only a message count; the question is logged truncated to 300 chars (it is needed to interpret the retrieval queries, which contain it anyway).
- **Why:** Zero change to ranking behaviour in this part, and the ids are enough to look up any chunk in Chroma or the eval tooling.
- **Files changed:** `request_log.py`, `api.py` (`_retrieve_documents`, `_retrieve_arabic_lexical_documents`, filter call sites).
- **Concept to learn:** *Log minimisation.* Logs are a data store with weak access controls; keep identifiers, not payloads. Vector "distance" here is Chroma's default L2 distance between query and chunk embeddings (lower = more similar); logging it lets you later pick a similarity threshold from real traffic. Search: "PII in logs", "cosine vs L2 distance embeddings".
- **Revisit if:** ingestion id formats change (update `chunk_id_from_metadata` in lockstep, or store the id in metadata at ingest time, which is the cleaner long-term fix).

### LOG-003: Refusal detection reuses the existing phrase heuristic, extended to Arabic
- **Date / Part:** 2026-09-15, Part B (commit 9a4e345)
- **Audit ref:** C23
- **Context:** The log needs a "was this a refusal?" flag. The only signal today is `_response_grounding_status`, which sniffs English phrases in the answer; the Arabic refusal sentence was not detected, so an Arabic refusal was logged as `answered`.
- **Decision:** Added the Arabic no-source marker to the heuristic and log `refusal` + `grounding` + a `refusal_reason` for pipeline-level refusals (`nothing_retrieved`, `no_source_after_filter`, `saint_not_in_index`). Did not build a structured "grounded/refused" model output yet (AUDIT C23) because that changes prompting, which is a later part.
- **Files changed:** `api.py`.
- **Concept to learn:** Distinguish *pipeline refusals* (retrieval returned nothing) from *model refusals* (the LLM said it could not find it). They need different fixes, so log which one happened. Search: "RAG failure modes retrieval vs generation".
- **Revisit if:** the prompt is rewritten to return a structured grounding field; then replace the phrase sniffing entirely.

### LOG-004: Per-stage latency via "laps" rather than nested timers
- **Date / Part:** 2026-09-15, Part B (commit 9a4e345)
- **Context:** Per-stage timing (prepare, retrieval, filter, retry, generation, postprocess) was required. The handler is one long function with early returns, so wrapping each stage in a `with` block would have meant re-indenting hundreds of lines.
- **Decision:** `trace.lap("name")` records the time since the previous lap. A `stage()` context manager also exists for new code.
- **Why:** Minimal diff, and laps naturally sum to `total_ms`. Windows' clock resolution (~15 ms) makes sub-millisecond stages show as `0.0`; on Linux (Railway) they will be accurate.
- **Files changed:** `request_log.py`, `api.py`.
- **Concept to learn:** Measuring where time goes is the first step of any latency work; here retrieval (which includes the embedding HTTP call) and generation dominate. Search: "latency budget", "p95 latency".
- **Revisit if:** the handler is refactored into stage functions; then use `stage()` blocks.

## Evaluation

### EVAL-001: A hand-verified question set with page-level expected sources
- **Date / Part:** 2026-09-15, Part C (commit ab1cd8d)
- **Audit ref:** A9
- **Context:** Nothing measured answer quality; every pipeline change so far has been judged by feel. An evaluation set needs questions whose answers demonstrably exist on known pages, so that retrieval can be scored mechanically and answers can be scored against a reference.
- **Options considered:**
  1. *Generate questions with an LLM from random chunks.* Fast and scalable, but the questions inherit the extractor's artefacts, tend to be unnaturally specific, and the "expected page" is whatever chunk was sampled rather than where a real reader would look.
  2. *Hand-write questions from the product's own prompts and the books' structure, then verify each expected page by opening it.* Slower, but the questions look like what users type, and every expected page is confirmed.
  3. *Collect real user questions from Postgres.* Best realism, but there are no ground-truth pages and no consent process for reusing them; worth adding later as an unlabelled "smoke" set.
- **Decision:** Option 2. `eval/questions.jsonl` has 62 entries: 20 catechism (seeded from the prompt cards in `orthodox-site/app/chat/page.tsx` plus the numbered Q&A headings), 13 saints, 4 multi-part, 5 follow-ups (with the prior turn in `history`), 10 Arabic, and 10 out-of-corpus questions that must be refused. Expected pages were located by searching the local Chroma store (read-only) and the PDF bookmarks, then confirmed by extracting the page with pypdf; each entry stores an `evidence` quote from that page. The two on-topic-sounding refusal questions (cryptocurrency, a 2024 papal message) test "false answers" specifically.
- **Why:** Page numbers are the unit the pipeline can be scored on today (a chunk is a page). Storing the evidence quote lets you hand-check an entry in seconds and makes the set robust to re-chunking: after re-ingestion the expected *pages* stay valid even if chunk ids change.
- **Files changed:** `eval/questions.jsonl`.
- **Concept to learn:** A *golden set* (or ground-truth set) is a fixed list of inputs with known correct outputs; it turns "does it feel better?" into a number you can compare across commits. Keep it small enough to verify by hand and stable enough that scores are comparable over time; add new cases when you find a real failure. Search: "evaluation golden dataset", "RAG evaluation ground truth".
- **Revisit if:** the corpus changes (re-verify pages), or when you have real user questions to add as a second, unlabelled set.

### EVAL-002: Retrieval recall measured at four points in the pipeline
- **Date / Part:** 2026-09-15, Part C (commit ab1cd8d)
- **Audit ref:** A9, C11, C12
- **Context:** "Retrieval recall@k" is ambiguous in this pipeline because a chunk can be found by one of up to eight queries, then dropped by the merge/truncation, then dropped again by the keyword relevance filter, and finally not shown because only six sources are returned. The audit claims the filter throws away correct chunks; the eval should be able to prove or disprove that.
- **Decision:** `eval/run_eval.py` reports, for every answerable question, the fraction of expected pages found in: `merged_ids[:k]` (**recall@k**, the ordered list that entered the filter, k = 8 to match the frontend's `top_k`), the union of all query hits (**recall_any**), the chunks that survived the filter (**recall_kept**), and the `sources` returned to the user (**recall_shown**). A ±1-page variant is also reported because saint entries span page boundaries. Chunk ids are parsed (`saints1.pdf::p329::c0` → page 329) so the metric survives the coming re-chunking as long as ids keep encoding pages.
- **Why:** The gap between consecutive metrics localises the loss: `recall_any − recall@k` is what truncation/merge order costs, `recall@k − recall_kept` is what the keyword filter costs, `recall_kept − recall_shown` is the six-source cap.
- **Files changed:** `eval/run_eval.py`, `request_log.py` (`debug_payload`), `api.py` (`debug: true` request flag).
- **Concept to learn:** *Recall@k* = fraction of relevant items that appear in the top k results. In RAG, retrieval recall is an upper bound on answer quality: the model cannot cite what it never saw. Measuring recall at each stage is an *ablation*: you learn which stage to fix first. Search: "recall@k information retrieval", "RAG evaluation retrieval vs generation".
- **Revisit if:** chunk ids stop encoding page numbers (then store `page` in the debug payload directly), or once a reranker exists (add a recall-after-rerank point).

### EVAL-003: LLM-as-judge with a 1–5 rubric against the reference answer
- **Date / Part:** 2026-09-15, Part C (commit ab1cd8d)
- **Audit ref:** A9
- **Context:** Retrieval metrics do not say whether the final answer is right. Human grading of 50+ answers per run is not sustainable.
- **Options considered:** string overlap metrics (ROUGE/BLEU: penalise paraphrase, meaningless for Arabic vs English); exact-fact checklists per question (accurate, but expensive to author); an LLM judge comparing the system answer to the reference (cheap, correlates reasonably with human judgement, but has biases).
- **Decision:** An LLM judge (`gpt-4o-mini` by default, `EVAL_JUDGE_MODEL` to override) scores answered questions 1–5 for factual agreement and completeness against the reference, with an instruction not to reward length; refusals and clarifications on answerable questions score 1 automatically and are also reported separately so that "refused" is never hidden inside an average. Both `judge_mean_answered` and `judge_mean_all` are printed.
- **Why:** The reference answers are short and page-grounded, so the judge's job is closer to "does this contain these facts?" than to open-ended grading, which is where LLM judges are most reliable. Using the same model family as the generator is a known bias (it may like its own style); the default keeps cost low and can be swapped by env var.
- **Files changed:** `eval/run_eval.py`.
- **Concept to learn:** *LLM-as-a-judge* uses a model to grade outputs against a rubric. It is fast and cheap but can prefer longer answers, its own phrasing, or the first option shown, so keep rubrics concrete, fix `temperature=0`, and spot-check a sample by hand. Search: "LLM as a judge bias", "G-Eval".
- **Revisit if:** judge scores disagree with your spot checks (switch judge model or add per-question fact checklists), or when you start comparing two prompts (use pairwise judging instead of absolute scores).

### EVAL-004: Retrieval debug data returned in the response instead of scraped from logs
- **Date / Part:** 2026-09-15, Part C (commit ab1cd8d)
- **Audit ref:** A8/A9
- **Context:** The eval needs chunk ids/distances per question. Part B logs them, but tying a log line back to an HTTP response requires log access, which does not exist for a remote deployment.
- **Options considered:** parse the server log; add a separate `/debug/retrieve` endpoint (duplicates the pipeline); add an opt-in `debug: true` flag to `/chat` that attaches the trace's safe subset to the response.
- **Decision:** The opt-in flag. `ChatRequest.debug` (default false) makes `/chat` include `debug` with request id, retrieval hits, merged/kept ids, stages and token counts. No chunk text is included, and the flag is only reachable by callers holding the internal key (SEC-001).
- **Why:** One code path, works against any deployment, and the payload is exactly what the log line already contains.
- **Files changed:** `api.py`, `request_log.py`.
- **Concept to learn:** *Observability hooks for testing*: exposing internal decisions in a controlled, authenticated way lets tests assert on behaviour without coupling to log formats. Search: "debug endpoints authentication", "testability observability".
- **Revisit if:** the frontend ever proxies user-controlled flags to the backend (it currently does not send `debug`; keep it that way or strip it in `route.ts`).

### EVAL-005: Baseline run committed under eval/results/
- **Date / Part:** 2026-09-15, Part C (commit ab1cd8d)
- **Context:** Later parts change retrieval, prompting and ingestion; each needs a "before" number.
- **Decision:** `run_eval.py` writes `eval/results/<timestamp>.json` (config, summary, and every record including the answer text) and the baseline file is committed. Future runs are compared by summary; results files are small (~200 KB).
- **Why:** Committing the baseline makes the improvement claims in later commits reproducible and reviewable in a diff.
- **Files changed:** `eval/results/`.
- **Concept to learn:** *Regression testing for quality*: keep the artefacts, not just the numbers, so you can inspect exactly which questions regressed. Search: "evaluation-driven development".
- **Revisit if:** the results directory grows large (then keep only tagged baselines and gitignore the rest).

### EVAL-006: What the baseline run showed (and where it corrects AUDIT.md)
- **Date / Part:** 2026-09-15, Part C (commit ab1cd8d), results file `eval/results/20260915-165311.json`
- **Audit ref:** C12, C15, C17
- **Context:** First run of the harness against the unchanged retrieval/prompt pipeline (after the Part A/B hardening, which does not touch ranking).
- **Findings:**
  - Out-of-corpus: 10/10 correctly refused, including the two on-topic-sounding traps. The refusal machinery is not the problem for off-topic input.
  - Answerable: 13.5 % refused (7 of 52). **Six of the seven** are natural saint questions ("Who was St. Bishoy?", "Who was St. Demiana and how was she martyred?") that never reach retrieval: the saint-intent regex (`_extract_saint_chat_intent`) captures everything after "who was", looks it up in the runtime saint index, and on a miss returns "I could not find a dedicated saint entry". AUDIT.md C17 described this as an edge case; the eval shows it is the **dominant** refusal cause and it fires even on a bare canonical name. This is the first thing to fix in the retrieval part.
  - The keyword relevance filter (C12) caused one refusal (FU-01: the correct page was retrieved at rank 3 and then rejected) and starved one answer (FU-02). Real, but smaller than C17 on this set.
  - Follow-ups: history resolution (C15) only works when the previous assistant message contains a `**bold**` name; FU-02 (no bold) retrieved unrelated pages and scored 2/5.
  - Retrieval recall@8 is 62 % exact / 75 % within one page; recall_any equals recall@8, i.e. multi-query fan-out currently adds nothing that survives truncation. Judge scores are high (4.3 answered-only) even when the expected page was missed, because neighbouring pages of the same section often contain the same teaching; expected pages in the set are therefore *sufficient*, not *necessary*, and recall should be read together with the judge score.
  - Arabic: 10/10 answered, mean judge 4.4, but recall@8 only 50 %; consistent with C2 (embedding mismatch) being masked by the lexical scan.
- **Decision:** Record these as the baseline; no pipeline changes in this phase. Priority order for the next phase, based on evidence rather than the audit's ordering: (1) remove/soften the saint-intent short-circuit, (2) replace the keyword filter with score thresholds, (3) LLM history rewriting, (4) re-ingestion.
- **Files changed:** none (analysis only).
- **Concept to learn:** *Error analysis*: after measuring, read the failures one by one and group them by cause before optimising anything; the largest bucket is usually not the one you expected. Search: "error analysis machine learning Andrew Ng".
- **Revisit if:** the question set changes (re-baseline first).

### EVAL-007: Judge moved to a stronger, different model (gpt-4.1) with a human-check sheet
- **Date / Part:** 2026-09-15, Phase 2 Step 0 (commit 7c90db7)
- **Audit ref:** EVAL-003 revisit, open question 5
- **Context:** The baseline judge was `gpt-4o-mini`, the same model that writes the answers. A model grading its own output tends to like its own phrasing, and a weaker judge misses subtle errors.
- **Options considered:**
  1. *gpt-4.1*: newer non-reasoning model, supports `temperature=0` and JSON mode, cheap, different from the generator. 
  2. *gpt-5.x reasoning models*: strongest available, but they reject `temperature` and `max_tokens`, run slower, and cost more per call; fine for a final check, heavy for every step.
  3. *Two judges and take the average*: more robust, double cost.
- **Decision:** Default `DEFAULT_JUDGE_MODEL = "gpt-4.1"`, overridable with `EVAL_JUDGE_MODEL`. `judge_answer()` now retries without `temperature`/`max_tokens` so a gpt-5.x judge also works. Added `--rejudge <results.json>` to re-score existing answers without calling the backend, so two judges can be compared on identical answers, and `eval/make_human_check.py`, which writes `eval/human_check.md` with 10 answered questions spread across categories for hand grading.
- **Why:** Re-judging the same 45 baseline answers showed the two judges agree exactly 64 % of the time and within one point 98 %; gpt-4.1 was on average **0.38 points more generous** (answered-only 4.69 vs 4.31). So the old judge was not inflating scores; if anything it was stricter. The judge change therefore does not manufacture an improvement, but all phase-2 numbers use gpt-4.1 and are compared only to the gpt-4.1 re-run of the baseline. The human sheet is the only way to know which judge is *right*; that is left to you.
- **Files changed:** `eval/run_eval.py`, `eval/make_human_check.py`, `eval/human_check.md` (generated), `eval/results/20260915-170358.json` (re-judged baseline).
- **Concept to learn:** *Judge calibration.* Before trusting an automatic grader, measure its agreement with a human on a sample (Cohen's kappa or simple "within one point" agreement). A judge can be consistently generous or strict; that is harmless for *comparing* two runs with the same judge, but it matters for absolute claims like "4.7 out of 5". Search: "LLM judge calibration inter-rater agreement", "Cohen's kappa".
- **Revisit if:** your hand scores on `human_check.md` differ from the judge by more than one point on several questions (then try a gpt-5.x judge or add per-question fact checklists).

### EVAL-008: Phase 2 results, step by step
- **Date / Part:** 2026-09-15, Phase 2 Step 4
- **Audit ref:** summary of RET-001..003, GEN-001..003, EVAL-007
- **Context:** Every step in phase 2 was followed by a full eval run so each change has its own before/after numbers. `eval/compare_results.py` prints the table below from the results files.

| metric | phase1 (4o-mini judge) | baseline (4.1 judge) | step1 routing | step2 prompts | step3 ranking |
|---|---|---|---|---|---|
| answerable refused | 13.5% | 13.5% | 1.9% | 0.0% | 0.0% |
| out-of-corpus refused | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| recall@8 | 62.2% | 62.2% | 73.1% | 73.1% | 73.1% |
| recall@8 (±1 page) | 75.3% | 75.3% | 86.9% | 86.9% | 86.9% |
| recall kept | 60.3% | 60.3% | 71.2% | 71.2% | 74.0% |
| recall shown | 57.4% | 57.4% | 68.3% | 66.3% | 69.6% |
| judge answered-only | 4.31 | 4.64 | 4.61 | 4.67 | 4.77 |
| judge all-answerable | 3.87 | 4.15 | 4.54 | 4.67 | 4.77 |
| saints refused | 30.8% | 30.8% | 0.0% | 0.0% | 0.0% |
| saints recall@8 | 53.8% | 53.8% | 82.1% | 82.1% | 82.1% |
| saints judge (all) | 3.15 | 3.77 | 4.77 | 4.77 | 4.92 |
| follow-up judge (all) | 3.60 | 3.60 | 3.60 | 3.60 | 4.60 |
| arabic judge (all) | 4.40 | 4.50 | 4.50 | 4.80 | 4.80 |
| prompt tokens (mean) | 6260 | 6260 | 5843 | 5908 | 6900 |
| latency s (mean) | 2.4 | 2.4 | 2.5 | 3.3 | 3.1 |

Results files: baseline `20260915-170734`, step 1 `20260915-171208`, step 2 `20260915-171939`, step 3 `20260915-172546`; the phase-1 column is `20260915-165311` (same answers re-judged in `20260915-170358`).
- **Reading the table:** Step 1 removed almost all wrongful refusals and lifted retrieval recall, because saints questions finally reached retrieval. Step 2 changed *how* answers are written (citations, depth) and did not touch retrieval; its judge gain is modest because most answers were already scored high. Step 3 fixed the ordering problem that had produced a confidently wrong follow-up answer.
- **What got worse:** (1) Step 2 turned FU-01 from a refusal into a wrong-entity answer (fixed by Step 3). (2) Step 2 raised latency from 2.5 s to 3.3 s and answer length roughly doubled, which is the intended depth but costs output tokens. (3) Step 3 raised mean prompt tokens by 17 % because no chunk is filtered any more. (4) "recall shown" dipped in Step 2 (68.3 % → 66.3 %) because sources are now the cited passages only; it recovered in Step 3. (5) Retrieval recall is flat at 73.1 % after Step 1: the remaining misses (CAT-01, CAT-03, CAT-08, CAT-14, AR-03/04/06/08) are pages the embedding search does not rank in the top 8; they need the re-ingestion (cleaner, smaller chunks) and query rewriting, not more routing changes.
- **Files changed:** `eval/compare_results.py`.
- **Concept to learn:** *Ablation by steps.* Changing one thing per run and re-measuring is the only way to attribute an improvement (or a regression) to a specific change; the phase-1 column shows why the judge had to be fixed first, so that later columns are comparable. Search: "ablation study", "A/B evaluation offline".
- **Revisit if:** the human check sheet disagrees with the judge; then re-read this table with the corrected scores.

### EVAL-009: Judge vs human on the 10-question check sheet
- **Date / Part:** 2026-09-15, Phase 3 Step 1 (commit a849b17)
- **Audit ref:** EVAL-003, EVAL-007, open question 5
- **Context:** The project owner hand-graded the 10 answers in `eval/human_check.md` (answers from the phase-2 baseline run `20260915-170734`, old prompt, gpt-4.1 judge) and reported: judge mean 4.6 vs human 3.8, exact agreement 4/10, judge never below the human, with three failure patterns (misses omitted halves/sources, credits absent facts, rewards unverifiable extras), worst on long answers.
- **Verification against the files:** all three numbers are exactly right (judge 4.60, human 3.80, 4/10 exact, 0/10 judge-below-human; the six disagreements are +1 ×4 and +2 ×2). The three patterns hold on inspection:
  - *Absent facts credited:* SNT-10's judge rationale credits "the miracle" (the infant flour miracle); the word "flour" does not occur in the answer. AR-03's rationale credits "his meeting with Anba Anthony"; the answer only says Anthony regarded him as a model, no meeting.
  - *Omitted halves:* MP-03's judge said "covers the key facts"; the answer has the purpose half and none of the four "why" facts. CAT-11 covers Q730 but only echoes Q752.
  - *Unverifiable extras rewarded:* SNT-02 (baptism by Macarius), SNT-10 (deacon at 20, Amhara monastery, king Matolomy, six wings) are not in the reference and were not checked against the pages; the rubric said "extra correct detail is fine", which the judge read as "extra detail is fine".
- **Length:** on the 10 graded answers the judge's *excess* over the human correlates with answer length (Pearson 0.66, Spearman 0.57; the two +2 cases are the two longest answers, 1,256 and 1,529 chars). Across the full result sets, however, the judge's *score* does not rise with length (Spearman −0.02 on 45 baseline answers, −0.22 on 52 step-3 answers). So the judge is not simply rewarding length; long answers give omissions and unsupported extras more room to hide, and a rubric that only looks for "key facts of the reference" cannot see either. That is the case for two separate metrics (EVAL-010).
- **Specific questions from the notes:** (1) MP-03: `catechism2.pdf p.159` *was* retrieved, at rank 1, in both the graded run and the latest run, with p.169 at rank 4; the omission was generation, not retrieval, and the step-3 answer to MP-03 now covers both halves (Paradise, "medicine of the soul", St. Jerome's "foundation of virtues"). (2) FU-02 is *not* fixed in the latest results (judge 3, would be a human 1–2): the retrieval query is still the bare "What does St. Anthony say about practicing it?" with no history rewrite, so it retrieves Anthony passages about discernment (saints3 p.384) instead of catechism2 p.114, and the answer bridges the gap with an unsupported claim ("...which includes the Jesus Prayer"). It needs the history-aware query rewrite (a later step); the faithfulness metric should flag the bridging claim.
- **Files changed:** `eval/human_check.md` (scores and notes recorded).
- **Concept to learn:** *Judge failure modes.* A single holistic score lets a grader compensate: length and fluency mask omissions, and plausible extras get credited because nothing forces the grader to locate each fact in the text. Requiring the grader to *quote* evidence for every credited fact (extractive grading) is the standard fix. Search: "LLM judge verbosity bias", "extractive evaluation quote evidence".
- **Revisit if:** after EVAL-010 the new metrics still disagree with these ten human grades.

### EVAL-010: Coverage replaces the holistic score as the headline quality metric
- **Date / Part:** 2026-09-15, Phase 3 Step 2 (commit 5c17620)
- **Audit ref:** EVAL-009 (patterns 1 and 2), A9
- **Context:** The 1–5 judge credited facts that were not in the answer and missed omitted halves of multi-part questions. A number that cannot be traced back to specific facts cannot be argued with.
- **Options considered:**
  1. *Tighten the 1–5 rubric.* Cheap, but still one holistic number; the failure is structural, not a wording problem.
  2. *Fact-level coverage with mandatory quotes.* Each question carries a fixed list of key facts; the judge must find each one and quote the answer span that states it. The score is a fraction with a visible breakdown.
  3. *Human grading only.* Most reliable, does not scale to a run per commit.
- **Decision:** Option 2. `key_facts` were extracted once from every reference answer (gpt-4.1 draft, then hand-corrected: multi-part questions have facts tagged `Part 1:`/`Part 2:` so both halves must appear; near-duplicates were merged) and stored in `eval/questions.jsonl` (52 questions, 290 facts). `scoring.coverage_judge` asks for `present | partial | absent` per fact with a verbatim quote for `present`; a quote that does not occur in the answer downgrades the fact to `partial` (matching is normalised: case, punctuation, citation markers and Arabic letter variants are ignored). Score = (present + 0.5·partial) / total; refusals and clarifications score 0. `off_target` marks answered questions with coverage ≤ 0.25 (wrong entity or wrong topic). The 1–5 judge is still computed for continuity but no longer headlines.
- **Why (validation on the 10 hand-graded answers):** coverage ranks them almost exactly as the human did: Spearman 0.90 vs 0.65 for the old judge; mapped to a 1–5 scale it agrees exactly on 6/10 and within one point on 10/10 (old judge 4/10 and 8/10) and its mean error is −0.2 (old judge +0.8). It found what the human found: MP-03's missing "why" half (3 of 4 Part 1 facts absent), SNT-10's missing birth date and baptismal name, AR-03 at 25 %, FU-02 at 0 %. The two remaining disagreements are direction-consistent: SNT-02 (human 4, coverage 50 %) and MP-03 (human 3, coverage 57 %).
- **Bugs found while validating (fixed):** the judge numbered facts from 0 in some responses, shifting every quote by one fact; the harness now trusts the order of the entries instead of the judge's own index. Quotes joined with "…" are matched fragment by fragment.
- **Files changed:** `eval/scoring.py` (new), `eval/run_eval.py`, `eval/questions.jsonl` (`key_facts`), `eval/compare_results.py`.
- **Concept to learn:** *Reference-based fact coverage* (as in FActScore / "atomic facts") turns grading into a checklist: it cannot credit what it cannot quote, so verbosity buys nothing. Fixing the fact list *once* also means the metric is stable across runs. Search: "atomic fact evaluation FActScore", "extractive grading LLM evaluation".
- **Revisit if:** reference answers are extended (add facts, never remove), or if partial credit is systematically over-used (then require quotes for `partial` too).

### EVAL-011: Faithfulness — every claim is checked against the passage it cites
- **Date / Part:** 2026-09-15, Phase 3 Step 2 (commit 5c17620)
- **Audit ref:** EVAL-009 (pattern 3), GEN-002 revisit, open question 7
- **Context:** The old judge rewarded plausible extra details that nobody checked against the sources; citations were parsed but never verified.
- **Decision:** `scoring.faithfulness_judge` splits the answer into atomic claims with the `[n]` markers attached to each, and asks the judge for a verdict per claim with a verbatim evidence span from a named passage. Claim status: `supported` (the cited passage, or any passage for an uncited claim, states it), `bad_citation` (the citation number does not exist, or the cited passage does not support it but another passage does), `unsupported` (no passage states it). The harness verifies every evidence span: if it is not in the named passage it searches all passages and re-attributes the citation; if it occurs nowhere, the judge invented the evidence and the claim becomes `unsupported`. The backend's `debug` payload now includes the passage texts (never logged; only for authenticated debug callers), and older results files fall back to reading chunk text from the local Chroma store by id. Reported as claim-weighted rates: % supported, % unsupported, % bad citation, % uncited.
- **What it caught on the 10 hand-graded answers:** SNT-10's unsupported feast-day claim; MP-02's claims that God delays prayer "to teach patience and persistence" and "because the request is inappropriate", which the human also flagged as unverified; every remaining flagged claim in the first pass turned out to be a *matcher* failure on pypdf's intra-word spaces ("sufferin g"), spliced lead-ins ("St. Augustine says, …") and ellipses, which is why the matcher is now insensitive to spaces, punctuation and citation markers, tolerates up to three trimmed words at either end and matches ellipsis fragments separately.
- **What it does not catch, by design:** AR-03 scored 100 % supported although the human rated it 3, because its claims *are* stated in the passages the pipeline retrieved (generic pages mentioning St. Paul, not his entry); the answer is faithful to the wrong pages. That is a retrieval failure and shows up as coverage 25 %, not as unfaithfulness. Faithfulness measures "did the model make things up"; coverage measures "did it answer the question"; both are needed.
- **Cost:** one extra gpt-4.1 call per answer with the full context (~7–14k tokens), which hits the 30k tokens-per-minute limit on this account when two runs overlap; `_chat_json` retries on 429 with the server's suggested wait.
- **First full run with both metrics (`eval/results/20260915-184419.json`, current pipeline, pre-hardening 62-question set):** coverage 63.8 % (catechism 52.6 %, saints 69.7 %, multi-part 88.6 %, follow-up 71.0 %, Arabic 65.0 %); faithfulness 86.4 % supported / 11.9 % unsupported / 1.7 % bad citation over 603 claims, 39.6 % of claims uncited; 13.5 % of answerable questions off-target (coverage ≤ 0.25: CAT-01, CAT-04, CAT-13, CAT-15, FU-02 and two others). The legacy judge gave the same answers 4.75/5. The most instructive cases are CAT-15 and CAT-13: the expected page was retrieved (recall 100 %) but the answer was written from neighbouring pages, so coverage is 10–17 %; recall says "available", coverage says "not used". That gap is invisible to the old judge and is the next generation-side problem to work on.
- **Files changed:** `eval/scoring.py`, `eval/run_eval.py`, `api.py` (`_build_numbered_context` passes passages to the trace), `request_log.py` (`debug_passages`).
- **Concept to learn:** *Faithfulness / attribution evaluation.* In RAG the model can be wrong in two independent ways: retrieve the wrong text (coverage drops) or say things the retrieved text does not support (faithfulness drops). Judging support requires the grader to point at evidence; verifying that the evidence really exists in the source is what keeps the grader honest. Search: "RAG faithfulness metric", "attributable to identified sources (AIS)", "citation verification".
- **Revisit if:** the pipeline starts returning shorter chunks (then per-claim evidence spans get easier and the ±3-word tolerance can shrink), or when a reranker changes which passages are shown (re-run the 10-answer validation).

### EVAL-012: Near-miss out-of-corpus questions and a sticky tune/holdout split
- **Date / Part:** 2026-09-15, Phase 3 Step 3 (commit 3f0cb4c)
- **Audit ref:** RET-003 revisit, open question 8
- **Context:** The refusal threshold had been chosen on nine easy negatives (sourdough, iPhone…). Those tell you nothing about the failure that matters for this product: confident answers about saints who are not in these books, doctrines the books do not discuss, or premises that are false. And every metric so far was measured on the same questions used to make decisions, so improvements could be over-fitted to the set.
- **Decision:**
  - 23 new out-of-corpus questions (OOC-11…33), each verified absent by corpus search: 10 saints not in the books that share a first name or a near-miss token with saints who are (Anthony of Padua, Ignatius of Loyola, John of the Cross, Gregory Palamas, Francis of Assisi where only a bishop *of* Assisi exists, Herman of Alaska who appears only as a footnote publisher…); 6 non-Coptic doctrines (purgatory, papal infallibility where the book speaks once of the *Church's* infallibility, sola scriptura, Immaculate Conception, filioque, and the Arabic purgatory); 4 false premises (St. Anthony on Mount Athos, St. Paul the Hermit's wife, St. Bishoy's commentary on Revelation, St. Demiana's father "the pope"); 3 same-name confusions (Cyril's brother Methodius, Moses the Black's "sister Sarah" who belongs to a different St. Moses on saints3 p.240, St. Barbara "moving to Egypt" when only her relics did). Each entry records a `subtype` and the search evidence.
  - `eval/make_split.py` assigns `split: tune | holdout` (30 % holdout), stratified by category and, for out-of-corpus, by subtype; deterministic seed; *sticky* so questions keep their split when new ones are added. Result: 59 tune / 26 holdout (out-of-corpus 23/10, catechism 14/6, saints 9/4, Arabic 7/3, follow-up 3/2, multi-part 3/1). `run_eval.py` reports every metric per split; `compare_results.py --split holdout` prints one split.
  - Rule: thresholds, prompts and routing rules are tuned on `tune` only; `holdout` numbers are reported but never used to choose.
- **Why:** Near-miss negatives are what a distance threshold actually has to separate; the easy ones were all ≥ 1.45 away. A holdout split is the only defence against the eval quietly becoming a training set for the pipeline; 26 questions is small, so treat holdout deltas under ~10 points as noise.
- **First run on the hardened set (`20260915-190224.json`):** out-of-corpus refusal fell from 100 % (10 easy negatives) to 81.8 % (33 negatives; tune 82.6 %, holdout 80.0 %): the near misses do their job. Answerable metrics are unchanged in substance (coverage 68.7 % overall; tune 62.9 %, holdout 81.6 %; the holdout happens to hold easier questions, which is why both splits are always reported).
- **Files changed:** `eval/questions.jsonl`, `eval/make_split.py`, `eval/run_eval.py`, `eval/compare_results.py`, `eval/threshold_analysis.py`.
- **Concept to learn:** *Train/validation/test discipline applied to evals.* Every time you look at a number and change the system, that number stops being an unbiased estimate; keeping a slice you never look at while tuning gives you one that still is. *Hard negatives* (near misses) are the examples that define where a classifier's boundary really is. Search: "holdout set overfitting evaluation", "hard negative mining".
- **Revisit if:** the holdout ever drives a decision (then it is burnt: create a new one), or when the set grows past ~150 questions (then a 20 % holdout is enough).

### EVAL-013: Phase 3 before/after on tune and holdout
- **Date / Part:** 2026-09-15, Phase 3 Step 5
- **Context:** "Before" is the phase-2 end state (`20260915-172546`, 62 questions, no pipeline change since) re-scored with the new judges and the new split labels (`20260915-194608`); "after" is the phase-3 step-4 run on the hardened 86-question set (`20260915-192113`). The retrieval and generation code did not change during phase 3, so answerable-question differences are run-to-run generation noise; the phase-3 work changed *what is measured* and *what is asked*.

| metric | tune before | tune after | holdout before | holdout after |
|---|---|---|---|---|
| coverage (all answerable) | 61.7% | 60.8% | 74.0% | 79.0% |
| faithful: supported | 88.1% | 86.1% | 85.6% | 90.6% |
| faithful: unsupported | 9.2% | 10.7% | 13.3% | 6.8% |
| faithful: bad citation | 2.7% | 3.2% | 1.1% | 2.6% |
| off-target (coverage ≤ 25 %) | 8.3% | 8.1% | 6.2% | 6.2% |
| answerable refused | 0.0% | 0.0% | 0.0% | 0.0% |
| out-of-corpus refused | 100% (5 easy) | 82.6% (23 incl. near-miss) | 100% (5 easy) | 80.0% (10 incl. near-miss) |
| recall@8 | 70.8% | 71.6% | 78.1% | 78.1% |
| mean answer length (chars) | 1831 | 1829 | 1681 | 1699 |

- **Reading:** the honest headline is that the pipeline is unchanged and now measured properly: about 61 % of the key facts appear in answers on tune (79 % on the easier holdout), 86–91 % of claims are supported by the cited passages, 7–11 % are unsupported (mostly generic embellishment: "a significant figure in the Coptic tradition"), 2–3 % carry a wrong citation number, and roughly 8 % of answerable questions are answered off-target. The out-of-corpus column is the one real change: the near-miss questions cut correct refusals from 100 % to ~82 % and the failures are doctrine positions invented from general knowledge plus one merged biography (RET-004). The before-column's 100 % is over five easy negatives per split and is not comparable.
- **Five worst faithfulness failures (after run):** SNT-03 (47 % unsupported: "a significant figure in the Coptic Orthodox tradition", "celebrated for her transformation from a life of sin", the Jerusalem pilgrimage which is not on the retrieved pages); AR-03 (57 %: generic "greatest saints… founder of asceticism in Egypt" filler, retrieval missed his entry); CAT-05 (50 %: "faith… encompasses belief, trust, and spiritual insight", a paraphrased Cyril quote about "all things accomplished by faith" not in the passage); FU-03 (50 %: interpretive glosses on why he was called the Jeremian); AR-07 (42 %: an outline of the Lord's Prayer's petitions that the passage does not contain).
- **Concept to learn:** an eval upgrade usually makes numbers *look* worse; that is the point. Search: "measurement validity", "Goodhart's law".
- **Revisit if:** phase 4 changes the pipeline; then this table is the baseline.

### EVAL-014: Phase 4 diagnosis — where the production refusals and weak answers come from
- **Date / Part:** 2026-09-16, Phase 4 Step 1
- **Audit ref:** RET-005, open questions 12, 17, 18
- **Context:** After the phase 1–3 deploy, the priest who uses the app reported that it refuses too often when asked to *do* something with the sources (make a table, list saints, compare, summarize), and three production requests showed the pattern. Before changing anything, each was replayed against the unchanged pipeline (local backend, `VECTOR_DISTANCE_THRESHOLD=1.1`, prompt v2) with `debug: true`, together with close variants, and the request-log fields were read.

| request (mode) | outcome | where it comes from (log fields) |
|---|---|---|
| "create a table with all saints whos names start with g" (chat and saints) | refused | **model refusal** (`grounding=no-source`, no `refusal_reason` because model refusals were not labelled); `best_distance` 1.042 (so the old 1.0 threshold would also have refused it); **narrow retrieval**: the 8 chunks are saints4 pp. 403–404 and 429–430, the *alphabetical index* of the Encyclopedia, which lists names with no text. Production answered the same request once, and its table column "Noted in the alphabetical index [2]" is exactly what those pages allow. |
| "list saints whose names start with G" | refused | **saint-intent routing**: `saint_intent=list`, `saint_intent_explicit=true`, `saint_query="saints"`, `saint_match_count=0`, `saint_intent_fallthrough=true`; the retrieval query was replaced by the canned `"saints Orthodox saint biography life feast teachings martyr monk bishop"`, which retrieves generic pages; then a model refusal. |
| "list saints who were martyred in Egypt" | answered, 2 saints | same saint-intent rewrite as above; the answer is built from two incidental mentions. |
| "saints starting with G" | answered | no routing; `best_distance` 1.007; answer from the index pages plus three G entries; two rows say "details are not provided". |
| "why is coptic easter different than catholic" | answered | `best_distance` 0.955, passages [1] catechism2 p.252, [7] p.251 (the calendar pages). Generation adds general knowledge (see below). |
| "make a table with the differences between catholicism and coptic" (chat and catechism) | refused | **model refusal**, `best_distance` 0.900 (well under the threshold), but `context_chars` 2,240 and `prompt_tokens` 1,130: the formatting words pulled the embedding towards short table-of-contents and page-header chunks (catechism1 p.9, catechism2 p.494 …), so the model saw eight near-empty passages. The plain question "What are the differences between the Coptic Orthodox Church and the Catholic Church?" answered from real pages (context 28k chars). |
| "make a table of the fasts and their lengths" | refused | **distance threshold** (`refusal_reason=distance_above_threshold`, `best_distance` 1.405), although the retrieved pages *were* the fasting pages (catechism2 pp. 249, 159–171). |
| "make a table of Catholic teachings on purgatory" | refused (correct) | model refusal at 1.099, one hundredth under the threshold. |
| "summarize … baptism", "make a study guide on the Holy Trinity" | answered | no problem: these phrasings stay topical. |

- **The Easter answer, claim by claim** (production answer cited [1][7] = catechism2 p.252 and p.251 for this query): *Gregory XIII in 1582* — supported (p.251: "In 1582 A. D., Pope Gregory XIII of Rome omitted ten days"). *Julius Caesar, 45 BC* — unsupported and wrong for this corpus: the catechism says 46 B.C., on p.250, which is not among the retrieved passages. *A year of 365.2425 days* — unsupported: p.251 gives 365.25 (Julian) and 365.24217 (solar); 365.2425 is the Gregorian mean year from general knowledge. *Pope Demetrius established the computus at Nicaea* — contradicted: p.251 says Demetrius (second century) devised it and "the Council of Nicaea approved this computation" later. The local replay produced a different wording with the same pattern ("one day every 128 years" is not in the passages; the passages say about a day and a half every two centuries). What the passages *do* say — the Orthodox still compute the Resurrection with the Julian calendar, Gregory XIII dropped the Jewish Passover from the computation — is only partly in either answer.
- **Findings:** four independent causes, none of which is "the distance threshold is too strict" alone: (1) formatting words in the embedded query ("make a table …") either push the distance up (1.405 for the fasts) or pull retrieval to empty structural chunks; (2) the saint-list regex replaces the query when the index has no match; (3) saint lists have no data source except the name-only index pages, so a table can only say "noted in the index"; (4) the v2 prompt's single refusal rule is applied when the passages do not look like a table's worth of material, and nothing forbids general-knowledge filler. Model refusals were not labelled in the log (`refusal_reason` empty), which made (4) look like (1) until the fields were compared.
- **Decision:** address them in that order: separate the retrieval query from the task (Step 2), give broad and saint-list requests their own retrieval (Step 3), rewrite the prompt for format/content (Step 4), then re-derive the threshold with an entity check in place (Step 5).
- **Files changed:** none (analysis; probe script kept out of the repo).
- **Concept to learn:** *Query/instruction separation.* An embedding model encodes everything in the text, including "make a table"; instructions about the output are noise for retrieval and should be removed before embedding. Search: "query rewriting RAG", "instruction-following vs retrieval query".
- **Revisit if:** new production failures do not fit these four causes.

### EVAL-015: Task-style questions, production examples, and a format metric
- **Date / Part:** 2026-09-16, Phase 4 Step 1
- **Audit ref:** EVAL-012, RET-005, open question 17
- **Context:** The eval had no request that asks the system to *do* something with the sources, so none of the production failures above could show up in a number. The ten keyword questions from RET-005 were unverified.
- **Decision:**
  - **KW-01…KW-10 verified.** Every evidence quote and every key fact was located on the listed PDF page with pypdf (`verified: true`). One evidence string was rewritten (KW-06: a straight apostrophe cut the quote short) and KW-10 gained a p.197 quote. No new short questions were added.
  - **Production examples:** `PRD-01` (G-saints table, category `task`), `PRD-02` (Easter, category `catechism`, subtype `faithfulness_case`, key facts from catechism2 pp. 251–252, notes listing the four checked claims), `PRD-03` (Catholic/Coptic differences table, category `task`; key facts are only the differences the catechism states: the Pascha computation, the Archangel Michael feast date, handbells, the sacred-heart symbol, the fifth-century isolation, plus "says the sources do not give a full comparison").
  - **15 task-style questions** `TSK-01…15`, category `task`, `subtype` and a new `expected_format` field: tables (fasts and lengths, seven sacraments, church tunes, Egyptian vs Julian calendar), lists (martyrs in Egypt, Coptic months, saints named Gregory, three bullets on the Jesus Prayer, the three archangels), comparisons (baptism vs chrismation; the Michael feast in Coptic/Byzantine/Catholic use, where the sources do describe every side), summaries (baptism, St. Moses the Black) and study guides (Holy Trinity, a fasting quiz). Every page was opened and every key fact located. For broad lists (`PRD-01`, `TSK-02`, `TSK-11`) the key facts are a *sample* of correct entries plus the fact "the answer says the list may be incomplete", so a partial, honest list can score well and a padded or silent one cannot.
  - **5 task-style out-of-corpus requests** `OOC-34…38` (subtype `task_style`): a table of Catholic teaching on purgatory, a study guide on sola scriptura, a table of St. Francis of Assisi's miracles, a Coptic/Catholic filioque table, a bullet list on the Immaculate Conception. Absence was established in phase 3 (OOC-13, 20, 22, 23, 24).
  - **Split:** `make_split.py` now stratifies `task` by subtype as it does `out_of_corpus`. Result: 81 tune / 38 holdout (task 10/7, out-of-corpus 26/12; PRD-01..03 landed in tune, TSK-01 — the fasts table — in holdout).
  - **Harness:** `--split tune` and `--coverage-only` (skips the faithfulness and legacy judges) for the per-step runs; `scoring.format_check` tests mechanically whether an answer has the requested shape (a markdown table with a separator row; ≥ 3 list items; a comparison as a table or ≥ 4 structured lines; a study guide as ≥ 3 headings/items); new summary rows: answerable refused for short (keyword) and task-style questions, out-of-corpus refused split into easy (no subtype), near-miss (the four phase-3 subtypes) and task-style, format followed, completion/analysis tokens and retrieval time. In coverage-only runs the legacy judge is left empty rather than scoring refusals as 1.
- **Baseline (`20260916-210222`, tune only, coverage-only, threshold 1.1, prompt v2):**

| metric | tune |
|---|---|
| coverage (all answerable, n=55) | 60.5% |
| off-target | 9.1% |
| answerable refused | 9.1% |
| … short (n=7) | 14.3% (KW-08 "confession", distance 1.246) |
| … task-style (n=10) | 40.0% (PRD-01, PRD-03, TSK-09, TSK-14) |
| out-of-corpus refused (n=26) | 80.8% |
| … easy (n=7) / near-miss (n=16) / task-style (n=3) | 100% / 68.8% / 100% |
| format followed (task, answered, n=5) | 60.0% |
| task coverage (all) | 33.5% |
| recall@8 | 71.8% |
| mean answer length | 1,828 chars |
| mean latency | 2.6 s |

  Keyword best distances on tune: KW-01 "What is prayer" 1.059 (the production value), KW-02 "fasting" 0.912, KW-07 "eucharist" 0.965, KW-08 "confession" **1.246** (refused at 1.1), others 0.67–0.83. The two model-refused tables TSK-09 (tunes) and TSK-14 (calendars) had best distances of 0.75 and 0.74 and recall 50–100 %: the passages were there and the model refused the task. TSK-02 (martyrs) answered with coverage 10 % and no list.
- **Files changed:** `eval/questions.jsonl`, `eval/make_split.py`, `eval/run_eval.py`, `eval/scoring.py`, `eval/compare_results.py`, `eval/results/20260916-210222.json`.
- **Concept to learn:** *Behavioural test coverage.* An eval measures only the kinds of requests it contains; users ask for tasks ("make a table …"), not just questions, and the task wording changes both retrieval and generation. A cheap structural check (does the output have the requested shape?) complements the semantic judges. Search: "behavioral testing NLP CheckList", "LLM output format compliance".
- **Revisit if:** the saints index is rebuilt (the G-saints reference pages may change) or the UI adds new task buttons (add a question for each).

## Retrieval

### RET-001: A saint-index miss falls through to retrieval instead of refusing
- **Date / Part:** 2026-09-15, Phase 2 Step 1 (commit f1e6f0c)
- **Audit ref:** C17, EVAL-006
- **Context:** Six of the seven answerable refusals in the baseline came from `_extract_saint_chat_intent`. Tracing the six showed two separate faults:
  1. The regex captured everything after "who was", so the index was asked for `"St. Demiana and how was she martyred"` or `"St. Abanoub, and how old was he when his parents died"`, which can never match.
  2. The runtime saint index (built by `_build_saint_record_index` from ALL-CAPS heading lines) never contains Bishoy, Demiana or Rebecca: their headings are `BISHOY, ST. ABBA`, `DEMIANA AND THE FOURTY VIRGINS, SS.` and `REBECCA AND HER FIVE CHILDREN`, and the name-plausibility heuristics reject any name containing "and" or a leftover "St." token. `St. Barbara` *is* indexed, but the query `"St. Barbara the martyr"` failed every scoring rule because the descriptor is not part of the indexed name.
  In all six cases an empty match list ended the request with "I could not find a dedicated saint entry", so retrieval, which had the pages, was never tried.
- **Options considered:**
  1. *Rebuild the index properly at ingestion* (the real fix for fault 2). Deferred by instruction to the re-ingestion phase.
  2. *Delete the intent path entirely and always retrieve.* Simplest, but loses the useful disambiguation menu for bare first names and the entity-based query expansion that helps the Saints tab.
  3. *Keep the path but make it advisory*: a miss or an unconfident match can add information (an entity) but can never end the request.
- **Decision:** Option 3.
  - The captured candidate is cut at the first clause boundary (`,`, `and`, `how`, `when`, ...) so the index sees `St. Demiana`, not the whole sentence.
  - `_find_saint_record_matches` now returns a `match_score` per record and gains one rule: if the first name token matches (`barbara martyr` vs `barbara`) that is a medium match. Scores are banded: strong (0–1, exact name/alias), medium (2, prefix or shared core name), weak (3–4).
  - Routing: two or more strong matches, or a bare first name shared by three or more indexed saints ("St. John"), shows the menu. Exactly one strong match (or one medium match) becomes the `entity`, which only *adds* query variants; the user's own question is kept as the retrieval query unless the phrasing was an explicit lookup (`search saint: X`, `learn more about X`), where the old descriptive query is still used. Anything else falls through to normal retrieval with no entity and no refusal.
  - The separate "ambiguous bare name" path now triggers only for single-word names and only when there are strong/medium matches.
  - `_saint_missing_response` was deleted; no code path refuses on an index miss any more.
- **Why:** The index is a heuristic cache, not the source of truth; the vector store is. A cache miss should degrade to the slower path, never to a wrong answer. Keeping the user's wording as the retrieval query also fixes multi-part saint questions, which used to have their second half discarded.
- **Result (eval `20260915-171208.json` vs baseline `20260915-170734.json`):** answerable refusals 13.5 % → 1.9 % (7 → 1); saints category 69 % → 100 % answered, recall@8 54 % → 82 %; multi-part 50 % → 100 % answered; overall recall@8 62.2 % → 73.1 %; judge all-answerable 4.15 → 4.54. The one remaining refusal (FU-01) is the keyword filter, addressed in Step 3. Nothing got worse: out-of-corpus refusals stayed 10/10 and no category dropped.
- **Files changed:** `api.py`.
- **Concept to learn:** *Fail-soft routing / graceful degradation.* When a fast path (a regex + lookup table) cannot decide confidently, hand the request to the general path rather than answering from the fast path's ignorance. Also *precision vs recall of a classifier*: the intent regex had high recall (it fired on every "who was") and low precision (it decided wrongly), so its decisions must not be terminal. Search: "graceful degradation", "intent classification confidence threshold fallback".
- **Revisit if:** the saint index is rebuilt at ingestion with proper names and aliases; then strong matches become reliable and the menu thresholds can be simplified.

### RET-002: The keyword relevance filter is deleted; results are merged by vector distance
- **Date / Part:** 2026-09-15, Phase 2 Step 3 (commit 9fcf9dd)
- **Audit ref:** C11, C12
- **Context:** After vector search, `_is_relevant_chunk` required two raw-substring keyword hits from the question in each chunk (no stemming, tiny stopword list), and `_retrieve_documents` concatenated the results of up to eight queries in *query order*, truncating to `top_k` without ever looking at the similarity scores Chroma returned. The filter caused the one remaining refusal (FU-01: correct page retrieved, then rejected) and starved FU-02; the ordering meant multi-query expansion could not improve the top-k (recall_any equalled recall@k in every run).
- **Options considered:**
  1. *Improve the filter* (stemming, bigger stopword list). Still a second, cruder relevance model competing with the embedding model.
  2. *Delete the filter, keep query-order merge.* Fixes the refusals but leaves ranking arbitrary.
  3. *Delete the filter and rank by distance.* Uses the signal the retriever already computes; each unique chunk keeps its best distance across queries; the entity-based "saints PDF first" boost is dropped because distance is now the single ranking key.
- **Decision:** Option 3. `_retrieve_documents` returns `(docs, metas, distances)` sorted ascending by best distance; `_filter_relevant_documents`, `_is_relevant_chunk`, `_relevance_terms`, `_question_keywords`, `RELEVANCE_STOPWORDS` and the retry-on-empty-filter block are deleted; the "kept" ids in logs and eval now equal the merged list.
- **Why:** The embedding similarity *is* the relevance estimate; a substring gate on top of it removed correct chunks far more often than it removed noise. With distance ranking, a chunk found by a secondary query can outrank a weak hit from the primary query, which is the whole point of issuing several queries.
- **Files changed:** `api.py`.
- **Concept to learn:** *Rank fusion.* When several queries (or several retrievers) each return a ranked list, merge them by a comparable score, never by list order. With one embedding model the raw distance is comparable across queries; with mixed retrievers (BM25 + vectors) you need reciprocal-rank fusion instead. Search: "reciprocal rank fusion", "multi-query retrieval".
- **Revisit if:** a lexical/BM25 retriever is added for English (then use RRF), or a reranker is added (then distance only shortlists candidates).

### RET-003: "No relevant source" is decided by a distance threshold chosen from the eval data
- **Date / Part:** 2026-09-15, Phase 2 Step 3 (commit 9fcf9dd)
- **Audit ref:** C11
- **Context:** With the keyword filter gone, something has to stop the pipeline from handing eight unrelated chunks to the model for an off-topic question and relying on the model to refuse.
- **How the threshold was chosen:** From the Step 1 results file (`20260915-171208.json`, which stores every vector hit with its distance), I computed for each question the *best* distance across all its queries. Distances are Chroma's squared L2 between unit vectors (0 identical, 2 opposite; equal to `2 − 2·cosine`). Distribution: expected-page hits ranged 0.434–1.155 (median 0.766); the best distance for every answerable English question was ≤ 0.971; the best distance for every English out-of-corpus question was ≥ 1.053 (the two on-topic-sounding traps, cryptocurrency and the papal message, sat exactly at 1.053; the rest were 1.45–1.84). A sweep showed 1.0 blocks 0 of 42 answerable questions and lets 0 of 9 out-of-corpus questions through, while 0.9 would block 5 answerable ones and 1.1 would pass 2 traps. So `VECTOR_DISTANCE_THRESHOLD = 1.0`, applied to the best distance only (individual weaker chunks are still passed to the model, which cites only what it uses).
- **Arabic:** the Arabic collection's distances do not separate at all (answerable best distances 1.34–1.75, the Arabic off-topic question 1.75) because the stored text is un-normalised glyph soup (AUDIT C2). `ARABIC_VECTOR_DISTANCE_THRESHOLD` defaults to 0 (off); Arabic refuses only when nothing is retrieved, and otherwise relies on the prompt's refusal rule, which handled the Arabic trap correctly in every run.
- **Why:** The margin is thin (0.03 on each side), so this is a first setting, not a law: it is an env var, it is logged (`best_distance`, `distance_threshold`) on every request, and the eval reports it, so drift will be visible.
- **Files changed:** `api.py`, `request_log.py` (debug fields).
- **Concept to learn:** *Threshold selection from a labelled set.* Plot the score of true positives against the score of known negatives and pick the cut that maximises separation; report both error types (answerable questions wrongly refused vs off-topic questions wrongly answered) rather than one accuracy number. With only nine negatives the estimate is noisy; more out-of-corpus questions would tighten it. Search: "ROC curve threshold selection", "cosine similarity threshold retrieval".
- **Result of Step 3 (eval `20260915-172546.json` vs Step 2 `20260915-171939.json`):** judge all-answerable 4.67 → 4.77; FU-01 fixed (1 → 5: with distance ranking the correct St. Moses the Black page outranks the other St. Moses), FU-02 2 → 3; follow-up category 3.60 → 4.60; recall_kept 71.2 % → 74.0 % (nothing is filtered any more), recall_shown 66.3 % → 69.6 %; refusals stayed at 0 % and all 10 out-of-corpus questions were still refused, now by the threshold (best distances 1.05–1.83, all above 1.0) before any model call, which also saves the generation cost on off-topic input. **Costs:** mean prompt tokens rose 5,908 → 6,900 because every retrieved chunk is now passed through; four catechism answers moved 5 → 4 and four others 4 → 5, which is within run-to-run generation noise at temperature 0.2 rather than a ranking effect (their retrieved pages did not change). recall@8 itself is unchanged at 73.1 %: the expected pages were already in the top 8; ranking changed their order, not their presence.
- **Revisit if:** re-ingestion changes the embedding text (thresholds must be re-derived: cleaner chunks generally give *smaller* distances for true hits), the embedding model changes, or Arabic is re-embedded from normalised text (then enable the Arabic threshold).

### RET-004: The distance threshold stays at 1.0; near-miss refusals need a different mechanism
- **Date / Part:** 2026-09-15, Phase 3 Step 3 (commit 3f0cb4c)
- **Audit ref:** RET-003, EVAL-012
- **Context:** RET-003 chose 1.0 on nine easy negatives. The hardened set adds 23 near-miss negatives; the threshold had to be re-derived on the tune split only (`eval/threshold_analysis.py`, results `20260915-190224.json`).
- **What the tune split shows (English, 29 answerable, 21 out-of-corpus):** answerable best distances 0.434–0.971 (median 0.691); out-of-corpus best distances 0.454–1.741 (median 0.999). The two populations now overlap heavily: "Who was St. Anthony of Padua?" sits at 0.454 (its nearest chunks are St. Anthony the Great's pages), "St. Anthony on Mount Athos" at 0.744, "Cyril's brother Methodius" at 0.751, "Ignatius of Loyola" at 0.763. No threshold separates them: the minimum-error value is 0.99 with 10 errors (0 answerable blocked, 10 of 21 negatives passed); 0.90 would already block 3 answerable questions while still passing 9 negatives. Holdout check at 0.99: 0/13 answerable blocked, 4/9 negatives passed, consistent with tune.
- **Decision:** keep `VECTOR_DISTANCE_THRESHOLD = 1.0` (0.99 vs 1.0 is noise); it remains the guard against genuinely off-topic input (all ten original negatives are still refused before any model call) and is *not* a guard against near misses. The six near-miss questions that were answered (18 % of all negatives, 17 % tune / 20 % holdout) fall into two kinds: (a) four doctrine questions (purgatory, sola scriptura, Immaculate Conception, filioque) answered from the model's general knowledge with a Coptic framing, i.e. hallucinated positions; (b) two entity questions, one of which correctly corrected the premise ("St. Paul the First Hermit did not have a wife…", counted as a false answer by the classifier but arguably right) and one which merged two different saints Moses into one biography (OOC-30, the exact failure the set was built to catch).
- **Why not tune further now:** a vector distance measures topical closeness, not whether the *specific entity or doctrine* is in the books; a question about Anthony of Padua is topically as close to the corpus as a question about Anthony the Great. The fix belongs to the entity/doctrine layer: e.g. checking that the named saint or term actually occurs in the retrieved passages before answering, or asking the model to state explicitly whether the passages mention the subject. That is a Phase 4 item (open question 13); changing the prompt or routing now would contaminate this step's before/after numbers.
- **Files changed:** `eval/threshold_analysis.py`, `eval/questions.jsonl` (splits), `DECISIONS.md`.
- **Concept to learn:** *Topical similarity vs entity grounding.* Embedding distance answers "is this about the same subject?", not "is this fact in the corpus?"; near-miss negatives expose the difference. Refusal needs an *entity-level* check (does the retrieved text mention the thing asked about?) or an answer-level check (faithfulness flags claims with no support). Search: "hallucination near-miss negatives RAG", "entity linking grounding check".
- **Revisit if:** re-ingestion changes distances (re-run the analysis on tune), or once an entity-presence check exists (then the threshold can be raised to reduce false refusals of paraphrased questions).

### RET-005: Raise the distance threshold to 1.1 after a production false refusal on a short query
- **Date / Part:** 2026-09-16, after the phase 1–3 deploy (analysis only; no code change, no new eval run)
- **Audit ref:** RET-003, RET-004, open question 8
- **Context:** In production, "What is prayer" was refused before any model call: its best distance was 1.058, above `VECTOR_DISTANCE_THRESHOLD = 1.0`. An off-topic sourdough question in production scored 1.619. The eval never showed this failure because every answerable question in the set is a full sentence: the largest answerable best distance on tune is 0.971 (FU-02). Short keyword queries embed further from 3,500-character page chunks than full questions do, so the eval set did not include the kind of input that was refused.
- **Data:** best distances already stored in `eval/results/20260915-192113.json` (the latest full run), **tune split only, English only** (30 answerable, 21 out-of-corpus). Arabic is excluded because its threshold is off (`ARABIC_VECTOR_DISTANCE_THRESHOLD = 0`, RET-003). The check in `api.py` refuses when `best_distance > threshold`. For out-of-corpus questions that pass a threshold, "what the stored answer did" is only known for questions at or below 1.0, because everything above 1.0 was refused by the threshold with no model call in that run (`prompt_tokens` is empty and there is no `generation` stage). For those, the only earlier evidence is phase-2 runs from before the threshold existed.

| threshold | answerable refused | out-of-corpus passing | … model refused | … model answered | … never sent to the model (outcome unknown) |
|---|---|---|---|---|---|
| 1.00 (current) | 0 / 30 | 11 / 21 | 7 | 4 | 0 |
| 1.05 | 0 / 30 | 13 / 21 | 7 | 4 | 2: OOC-12 (1.003), OOC-15 (1.036) |
| **1.10** | 0 / 30 | 14 / 21 | 7 | 4 | 3: + OOC-06 (1.053) |
| 1.15 | 0 / 30 | 16 / 21 | 7 | 4 | 5: + OOC-13 (1.111), OOC-21 (1.131) |
| 1.20 | 0 / 30 | 16 / 21 | 7 | 4 | 5 |
| 1.30 | 0 / 30 | 16 / 21 | 7 | 4 | 5 |

  - **The four model answers at ≤ 1.0 (unchanged at every threshold):** OOC-20 purgatory, OOC-22 sola scriptura, OOC-24 filioque (0.9995): invented doctrine positions from general knowledge; OOC-26 "St. Paul the First Hermit's wife": correctly rejects the premise but is scored as an answer (RET-004). **The seven model refusals:** OOC-16, 25, 29, 18, 11, 27, and OOC-31, which says the passages do not give the year or place and is counted as a refusal.
  - **What the newly admitted questions would probably do**, judged from their subtype, not from a stored answer:
    - OOC-12 (Therese of Lisieux), OOC-15 (Herman of Alaska) and OOC-13 (Francis of Assisi) are *saints not in the books*. At ≤ 1.0 the prompt refused 3 of 3 such questions (OOC-11, 16, 18), so a refusal is likely.
    - OOC-06 (cryptocurrency) was refused by the model in all three phase-2 runs (`20260915-170734`, `-171208`, `-171939`). Those runs used a keyword-filtered context of about 1,950 prompt tokens, and one of them used the v2 prompt, so this is supporting evidence, not proof.
    - OOC-21 (papal infallibility) is a *non-Coptic doctrine* question. At ≤ 1.0 the model answered 3 of 3 such questions with invented content, so admitting it will most likely produce another invented answer.
  - Nothing on tune lies between 1.131 and 1.454; the easy negatives (Harry Potter 1.454, nirvana 1.455, sourdough 1.605…) are refused at every value in the table. That range is unmeasured, not safe.
- **Options considered:**
  1. *Keep 1.0.* Short keyword questions are wrongly refused in production, which is the product's most basic use.
  2. *1.05.* Still refuses "What is prayer" (1.058).
  3. *1.1.* Admits the production case with a 0.04 margin; the extra negatives it admits are two saints-not-in-books questions and the cryptocurrency question, the kinds the prompt has refused so far.
  4. *1.15–1.3.* Same answerable result on tune, but admits OOC-21, a doctrine question of the kind the prompt has answered with invented content every time, plus OOC-13; beyond 1.131 there is no tune data at all.
- **Decision:** recommend `VECTOR_DISTANCE_THRESHOLD = 1.1`, set as a Railway env var (no code change; the default in `api.py` stays 1.0 until phase 4 re-measures). Treat it as provisional.
- **Why:** it is the smallest listed value that fixes the observed false refusal, and every question it newly admits is of a kind the prompt has refused so far. Going higher buys nothing measurable on tune and admits the one question type the model is known to get wrong. The real guard for near misses is the entity-presence check (phase 4 Step 2), not this threshold.
- **Weak points:** (a) one production data point: single-word queries such as "fasting" may sit above 1.1, in which case they are still refused; (b) the cryptocurrency, Herman of Alaska and Therese of Lisieux cases have never been answered under the current prompt with the full context; (c) 21 negatives is a small sample.
- **Follow-up:** 10 keyword-style answerable questions (`KW-01`…`KW-10`, category `keyword`, 7 tune / 3 holdout, `verified: false` until hand-checked) were added to `eval/questions.jsonl`. They include a bare noun ("fasting"), a question with no question mark ("What is prayer"), a missing period ("St Bishoy") and a name not used in the book's heading ("Anthony the Great"). Phase 4 runs will record their best distances; re-derive the threshold on tune from those distances. If they sit between 1.1 and 1.3, raise the threshold only once the Step 2 entity check is in place to catch OOC-21-type doctrine questions.
- **Files changed:** `DECISIONS.md`, `eval/questions.jsonl`.
- **Concept to learn:** *Distribution shift between the eval set and production.* A threshold can only be trusted over the kinds of input it was tuned on; an eval written as full sentences says nothing about keyword queries. When production shows a new input shape, add examples of it to the set before moving the threshold very far. Search: "query length embedding similarity", "eval set coverage distribution shift".
- **Revisit if:** the KW questions have been run (re-derive on tune), the entity-presence check exists, the query rewrite (phase 4 Step 3) turns short queries into full questions (distances should drop), or re-ingestion changes chunk size.

### RET-006: One analysis call separates the retrieval query from the requested task
- **Date / Part:** 2026-09-16, Phase 4 Step 2
- **Audit ref:** EVAL-014, GEN-003 revisit, open question 18, FU-02 (EVAL-009)
- **Context:** The embedded query was the user's raw words. "make a table of the fasts and their lengths" embedded at distance 1.405 from pages that answer it; "make a table with the differences …" pulled table-of-contents chunks; bare keywords ("confession", 1.246) fell outside the threshold; follow-ups were rewritten only by a regex that looked for a bold name in the previous answer, and only outside catechism mode, so FU-02 ("What does St. Anthony say about practicing it?") searched for the pronoun. The saint-list regex also replaced unmatched "list …" requests with a canned biography query.
- **Options considered:**
  1. *Strip formatting words with a regex.* Cheap, but the phrasing space is open ("put it in a table", "give me five quiz questions"), and it cannot resolve pronouns or expand keywords.
  2. *Embed the question twice (raw and cleaned) and merge.* Keeps the raw noise in the candidate set.
  3. *One small LLM call before retrieval* that returns a standalone query, the requested format and a broad flag. One extra request per turn (~0.9 s, ~700 tokens of gpt-4o-mini), but it handles formatting words, pronouns and short keywords in one place.
- **Decision:** Option 3, in a new module `task_analysis.py`. The call (JSON mode, temperature 0, 8 s timeout, no retries) returns `retrieval_query`, `output_format` (prose/table/list/comparison/summary/study_guide/other) and `broad`. The same prompt also returns `sub_queries`, `saint_name_filter` and `named_subjects`, which are logged now and used by Step 3 (RET-007) and Step 5; putting them in the prompt now keeps the prompt identical across Steps 2–6, so later step deltas are not prompt changes. The conversation (last 4 turns, 600 chars each) is only included when there is history. The whole result goes into the request log as `task_analysis`, with `analysis_tokens` and an `analysis` stage time. On any failure (timeout, API error, bad JSON, empty query) the raw question is used with format `prose`, and the error is logged; `search saint: X` lookups skip the call. Config: `TASK_ANALYSIS_MODEL` (default `gpt-4o-mini`), `TASK_ANALYSIS_ENABLED` (default on), `TASK_ANALYSIS_TIMEOUT_SECONDS` (default 8).
  - Retrieval (English and Arabic) now embeds `retrieval_query`; the answer prompt still receives the user's original words, so the format request reaches generation.
  - The saint-intent patterns still run on the user's words (they recognise Saints-tab lookups), but only a *lookup* with no index match is rewritten into the descriptive biography query; an unmatched *list* request keeps the analysed query.
  - Removed: the regex history rewrite (`_rewrite_question_with_history`, `_extract_entity_from_history`, `_question_has_followup_reference`, `_history_messages`) and an unused earlier LLM rewrite (`_build_english_retrieval_query` and its hint helpers), which was never called.
  - Model refusals are now logged with `refusal_reason=model_refusal` (EVAL-014 showed they were indistinguishable in the log).
- **Model choice:** on eight sample requests gpt-4.1-mini labelled the Catholic-differences table as `prose` and was ~0.2 s slower; gpt-4o-mini got the formats right but sometimes keeps a command word ("What are some quiz questions about fasting?" for TSK-13) and sometimes adds a `saint_name_filter` to a one-saint question (fixed in the prompt: "only when the user wants SEVERAL saints").
- **Result (tune, coverage-only; `20260916-210222` → `20260916-211037`):**

| metric | step 1 baseline | step 2 |
|---|---|---|
| coverage (all answerable) | 60.5% | 62.5% |
| off-target | 9.1% | 10.9% |
| answerable refused | 9.1% | 7.3% |
| … short / task-style | 14.3% / 40.0% | **0.0%** / 40.0% |
| out-of-corpus refused (easy / near-miss / task) | 80.8% (100 / 68.8 / 100) | 84.6% (100 / 75.0 / 100) |
| format followed (task) | 60.0% (n=5) | 80.0% (n=5) |
| follow-up coverage | 63.3% | 80.2% |
| keyword coverage | 75.6% | 80.4% |
| recall@8 | 71.8% | 73.3% |
| mean latency | 2.6 s | 3.4 s |
| analysis call | — | 869 ms, 689 tokens (mean), 0 failures |

  - **Fixed:** FU-02 (coverage 0 → 0.90; query "What does St. Anthony say about practicing the Jesus Prayer?", distance 0.971 → 0.741); KW-08 "confession" answered (distance 1.246 → 0.984); KW-01 "What is prayer" 1.059 → 0.972; KW-02 "fasting" 0.912 → 0.624; TSK-02 now produces a list (format ok) but of different martyrs than the sampled key facts (coverage 0). OOC-31 (St. Barbara's move to Egypt) went from an answer to a refusal. On the holdout-only TSK-01 fasts table the probe distance fell from 1.405 to 0.865 and the table was produced.
  - **Not fixed:** the four task refusals (PRD-01, PRD-03, TSK-09, TSK-14) are now all **model refusals** with good distances (PRD-03 retrieves catechism1 pp. 104, 17, 33 and the Coptic website pages instead of contents pages) — a prompt problem (Step 4). PRD-01 still retrieves the index pages (Step 3).
  - **Worse / noise:** CAT-11 (0.67 → 0.33) and CAT-13 (0.50 → 0.17, now off-target) have *identical* retrieval in both runs, so their drop is generation variance at temperature 0.2, not this change; the 9.1 → 10.9 % off-target rise is CAT-03 and CAT-13 (same retrieval) and TSK-02 (different but valid martyrs). Latency +0.8 s per request.
- **Files changed:** `task_analysis.py` (new), `api.py`, `request_log.py`.
- **Concept to learn:** *Query understanding / query rewriting.* Production RAG systems usually put a small, fast model in front of retrieval to produce a clean, self-contained search query (resolving coreference from the conversation) and to classify the request; the big model then answers with the original wording. Search: "conversational query rewriting", "HyDE query expansion", "query intent classification RAG".
- **Revisit if:** analysis latency matters more than quality (cache by question text, or run it in parallel with a raw-question retrieval), or the analysis model is changed (re-run the eight-request comparison above).

### RET-007: Broad requests retrieve wider; saint lists are built from the saint index
- **Date / Part:** 2026-09-16, Phase 4 Step 3
- **Audit ref:** EVAL-014 (causes 1 and 3), RET-001, RET-006
- **Context:** Eight chunks from one query cannot answer "list saints who were martyred in Egypt" or "the differences between two churches": the answer needs many separate entries. For saint lists selected by name ("saints whose names start with G") the vector search returns the Encyclopedia's alphabetical index (saints4 pp. 404–440), which lists names only, so the only possible table column was "noted in the index".
- **Options considered:**
  1. *Just raise top_k for everything.* More tokens on every request, and the extra chunks are the main query's near neighbours, not other aspects.
  2. *Sub-queries for broad requests* (from the RET-006 analysis) with a per-query quota, so each aspect contributes.
  3. *For name-based saint lists, skip similarity search and use the saint record index* (`_build_saint_record_index`, 1,363 entries built from the books' ALL-CAPS headings, each with its page and entry text) to select candidates by name and pass each entry's opening text.
  4. *Parse the alphabetical index pages* for complete name lists. Names only, no text and no page numbers in the extracted text, so it cannot fill a useful column.
- **Decision:** Options 2 and 3.
  - **Broad** (`task_analysis.broad`): queries = analysed query + up to four sub-queries (+ saint variants when an entity is known); `retrieval_top_k = BROAD_RETRIEVAL_TOP_K` (16); each query's best `BROAD_PER_QUERY_MIN` (2) chunks are guaranteed a place before the rest are filled by distance.
  - **Saint list** (`task_analysis.saint_name_filter`, no resolved entity): `starts_with` compares the start of the normalised name (without "St."), `contains` matches whole words; the first `SAINT_LIST_MAX_ENTRIES` (40) matches become passages "HEADING\nfirst 600 characters of the entry" with the entry's PDF page, so the model can say who each saint was and cite the page. The distance threshold does not apply (candidates are exact name matches). A NOTE before the passages tells the model how the list was built, how many matched, and that joint entries may be missing, so it must say the list may be incomplete.
  - **One Chroma call:** `_retrieve_documents` now sends all queries in one `collection.query(query_texts=[…])`, so the embeddings are one OpenAI request instead of one per query; results are merged as before (best distance per chunk, RET-002).
  - Logged: `retrieval_plan` (default / broad / saint_list) and `saint_list` {filter, shown, matched}.
- **Measured cost:**
  - *Broad* (5 tune questions answered in both runs, `20260916-211037` → `20260916-211927`): prompt tokens 6,582 → 11,218 (+70 %, ≈ $0.0007 more per request at gpt-4o-mini input prices), latency 4.47 → 4.79 s, retrieval stage 222 → 303 ms for up to five queries. Non-broad retrieval got faster with the single call (431 → 330 ms mean).
  - *Saint list* (probe "list saints whose names start with G"): 40 entries, prompt 6,889 tokens (vs 5,746 with 12 vector chunks), latency 8.5 s, and **the answer used all 1,200 completion tokens** — a 40-row list is cut off by `ANSWER_MAX_TOKENS`. Fixed in Step 4 (GEN-004).
  - Index coverage: "G" → 42 matched entries (all in vol. 2, pp. 143–219); "Gregory" → all six Gregory entries (TSK-11's reference); "S" → 113 matched (40 shown). The index also contains non-saints with entries in the Encyclopedia ("Sabillius, the Heretic Bishop") and misses joint headings ("GERVASE AND PROTASE, SS."), which is why the note is mandatory.
- **Result (tune, coverage-only; step 2 `20260916-211037` → step 3 `20260916-211927`):**

| metric | step 2 | step 3 |
|---|---|---|
| coverage (all answerable) | 62.5% | 59.1% |
| off-target | 10.9% | 7.3% |
| answerable refused | 7.3% | 9.1% |
| … short / task-style | 0.0% / 40.0% | 0.0% / 40.0% |
| out-of-corpus refused (easy / near-miss / task) | 84.6% (100 / 75.0 / 100) | 80.8% (100 / 68.8 / 100) |
| format followed (task) | 80.0% | 80.0% |
| task coverage | 32.8% | 32.8% |
| recall@8 / recall kept | 73.3% / 75.1% | 73.9% / 78.2% |
| mean latency | 3.4 s | 3.3 s |

  - **Reading:** the headline numbers moved the wrong way, and almost all of it is not this step. (a) SNT-01 became a "refusal" although its answer is correct and complete: the pre-v3 heuristic `_response_grounding_status` treats "could not find"/"does not say" *anywhere* in an answer as a refusal, and this answer ends with a sentence about what the passages omit; OOC-31 flipped the other way for the same reason. Step 4 replaces the heuristic. (b) CAT-08 (0.80 → 0.40), CAT-15 (0.90 → 0.20), CAT-12, PRD-02 moved with **identical retrieval** for the CAT questions (non-broad, same best distance and chunks): generation variance at temperature 0.2 is ±0.3–0.7 coverage per question on these multi-fact answers, i.e. single-run per-step deltas under ~5 points on 55 questions are noise. (c) The four task refusals (PRD-01, PRD-03, TSK-09, TSK-14) are still model refusals under prompt v2: PRD-01 now receives 40 real G entries and still says "I could not find enough", and the same entries produce a good list when the request says "list" instead of "create a table" (probe P1b). That is the prompt (Step 4).
  - **What this step did achieve:** real material for list requests (P1b: forty described G saints with page citations and an incompleteness sentence, instead of index rows; TSK-02 martyrs from four sub-queries); recall kept +3 points; no latency cost overall.
- **Files changed:** `api.py`, `request_log.py`.
- **Concept to learn:** *Query decomposition and structured retrieval.* A "list all X" request is a database query, not a similarity search; when a structured index exists, filter it directly and use vectors only for open-ended aspects. For multi-aspect requests, decompose into sub-queries and reserve slots for each so the merged context covers every aspect. Search: "query decomposition RAG", "multi-query retriever", "structured vs unstructured retrieval".
- **Revisit if:** the saint index is rebuilt at ingestion (then joint entries and aliases are covered and the note can be softened), or broad prompts exceed the latency budget (lower `BROAD_RETRIEVAL_TOP_K`).

### RET-008: Comparisons with another church also retrieve the passages that name it
- **Date / Part:** 2026-09-16, Phase 4 Step 4
- **Audit ref:** EVAL-014 (PRD-03), RET-007
- **Context:** With prompt v3 the Catholic/Coptic table stopped being refused, but the answer paired Coptic teachings with invented Catholic ones: the catechism mentions the Catholic Church only in passing (handbells on cat1 p.512, the Michael feast on cat2 p.304, the Pascha computation on cat2 p.252, the sacred-heart symbol on cat1 p.496), and a similarity search for "differences between Catholicism and Coptic" ranks general pages about the Coptic Church far above those.
- **Options considered:** (1) rely on the prompt alone — the model had nothing true to say about the other side; (2) a lexical scan over the whole collection (like the Arabic path) — slow, unranked; (3) Chroma's `where_document={"$contains": term}` on the same semantic query, so ranking stays semantic but only chunks that name the tradition are eligible.
- **Decision:** Option 3. When the request looks like a comparison (analysis format `comparison`, or "differ/compare/versus/than/between" in the question) and names another tradition, `_compared_tradition_terms` maps it to case-sensitive book terms (Catholic → "Catholic", "Roman"; Protestant; Anglican; Byzantine/Eastern/Greek Orthodox → "Byzantine", "Chalcedonian") and the analysed query is run once per term (`TRADITION_RETRIEVAL_TOP_K` = 6); new chunks are appended to the context and logged as `tradition_terms`. The analysis prompt also gained one line: for such comparisons, one sub-query is the other church's name.
- **Result:** the PRD-03 context now includes cat2 p.252 and cat1 p.496 and pages about Catholic missionary activity (saints2 pp. 405–406, cat1 p.23). It still misses p.512 and p.304 (the word "Catholic" appears in many patristic book titles, which compete). The probe answers moved from invented contrasts to either "Not described in the sources" cells (gpt-4o-mini) or cited statements from those pages (gpt-4.1-mini).
- **Files changed:** `api.py` (`_retrieve_documents(where_document=…)`, `_compared_tradition_terms`), `task_analysis.py`.
- **Concept to learn:** *Filtered / hybrid retrieval.* Combining a metadata or keyword filter with vector ranking retrieves passages that are relevant *and* satisfy a hard constraint, which pure similarity cannot guarantee for rare mentions. Search: "hybrid search keyword filter vector", "Chroma where_document".
- **Revisit if:** a lexical (BM25) index is added for English (then fuse with RRF instead of a contains filter).

### RET-009: Distance threshold 1.25, as an off-topic guard only
- **Date / Part:** 2026-09-16, Phase 4 Step 5
- **Audit ref:** RET-003, RET-004, RET-005, open question 18
- **Context:** The threshold (1.0 in code, 1.1 in production since RET-005) was carrying two jobs: stopping off-topic requests and stopping near misses. It could not do the second (RET-004), and at 1.0/1.1 it refused real short questions ("What is prayer" 1.058; "confession" 1.246). With the request analysis (RET-006) and the named-subject check (GEN-006) in place, it only needs to catch clearly off-topic input.
- **Method (tune only):** a tune run with the threshold switched off (`20260916-215250`, gpt-4.1-mini, entity check on) so that every question has a real answer and an English best distance. A threshold refusal happens before generation, so `eval/threshold_analysis.py --simulate` replays each candidate threshold exactly on those outcomes. The best distance now comes from the *analysed* query (RET-006), not the raw text.
- **Data (tune, English: 47 answerable with a vector search + 1 saint list, 24 negatives):**
  - Largest answerable best distances: KW-08 "confession" 0.984, MP-02 0.976, KW-01 "What is prayer" 0.972, KW-07 "eucharist" 0.952, CAT-12 0.921.
  - Negatives in order: near misses 0.454–1.237 (OOC-16 0.454 … OOC-13 1.237), together with the on-topic-sounding trap OOC-06 (cryptocurrency, 1.053); every one of them refused by the model or the entity check except OOC-25 (0.744, declined with "The sources do not cover …", counted as a refusal after GEN-006) and OOC-26 (0.809, correct premise rejection); the other easy off-topic questions 1.455 (nirvana), 1.480, 1.605 (sourdough), 1.633, 1.741.
  - Sweep: at 0.90 five answerable questions are blocked (CAT-12, MP-02, KW-01, KW-07, KW-08), at 0.95 four; **from 1.00 to 1.40 nothing changes** — 0 answerable blocked, all 7 easy (6 English + the Arabic one, which has no distance check), 14/16 near-miss and 3/3 task-style negatives refused — because everything between 1.0 and 1.45 is a near miss that the entity check and the prompt already decline.
  - Production phrases through the new pipeline (local, same index): "What is prayer" 0.972 (raw 1.059), "fasting" 0.624 (raw 0.912), "eucharist" 0.952 (raw 0.965), "confession" 0.984 (raw 1.246), "create a table with all saints whos names start with g" saint list, no distance (raw 1.042), the Catholic-differences table 0.842 (raw 0.900), the Easter question 0.827 (raw 0.955), "How do I make sourdough bread" **1.582** (raw 1.619) → refused.
- **Options considered:** 1.0 (no gain, least margin: the largest raw keyword distance is 1.246, which production sees whenever the analysis call fails and falls back to the raw text); 1.1 (current production value, same problem for "confession"); 1.25 (above the largest *raw* answerable keyword distance, 0.20 below the nearest easy negative); 1.4 (maximum margin to answerable, only 0.055 below nirvana).
- **Decision:** `VECTOR_DISTANCE_THRESHOLD` default **1.25** in code; set the same value on Railway (or delete the variable to use the default). Arabic stays off (RET-003), with the scope gate (GEN-006) instead.
- **Answerable questions blocked, by either check, on tune: none.** (Threshold: 0 of 47 at 1.25; entity check: 0 of 55.)
- **Result:** the step 5 tune run at 1.25 (`20260916-220035`) matches the simulation: 0 % answerable refused, 96.2 % of negatives refused, easy negatives refused by the threshold before any model call (as before) and near misses by the model/entity check.
- **Weak points:** the analysis call can fail (then the raw question is embedded; 1.25 still passes every raw keyword on tune, the largest being 1.246, a thin 0.004 margin for that fallback case); there is still no tune data between 1.24 and 1.45; 24 English negatives is a small sample.
- **Files changed:** `api.py` (default), `eval/threshold_analysis.py` (`--simulate`), `eval/results/20260916-215250.json`, `eval/results/20260916-220035.json`.
- **Concept to learn:** *Defence in depth for refusals.* Use the cheapest signal (distance) only where it is reliable (clearly off-topic), and give the hard cases (near misses) to a check that can actually see the difference (entity presence). Re-derive a threshold whenever an upstream stage changes the scores it sees (here, the query rewrite lowered them). Search: "cascade classifier thresholds", "answerability RAG".
- **Revisit if:** production logs show answerable requests between 1.2 and 1.25 (raise it), off-topic requests below 1.25 that the model answers, re-ingestion changes chunk size, or the analysis failure rate becomes noticeable.

### RET-010: Namesake menus select by saint ID; a menu only for genuinely shared names
- **Date / Part:** 2026-09-23, production bug (v2 live; the owner also saw it on v1).
- **Bug:**
  - "Who was St. Athanasius the Apostolic?" showed a menu: the martyr or the Apostolic, 20th Pope.
  - Choosing "St. Athanasius the Apostolic, the 20th Pope of Alexandria" brought the same menu back, so the saint could not be reached.
- **Root cause (same code path on v1 and v2):**
  - **Selection by text:** a chip click sent `search saint: <chip text>`, and the backend matched that text against the saints index again, with no saint ID anywhere.
  - **Text cut at the comma:** the intent parser cuts a name at its first comma, so the chip became "St. Athanasius the Apostolic" again.
  - **The same name on two entries:** the hand-written alias table (`SAINT_ALIAS_RECORDS`) had been copied onto namesakes. In v2 the martyr (`athanasius`) inherited the v1 aliases "St. Athanasius the Apostolic" and "St. Athanasius of Alexandria". In v1 both Athanasius records got each other's names through the table. Both entries matched equally, so the menu came back.
  - v2 made it more visible: every namesake is now its own entry.
  - The Agathon chips failed differently: "(The Martyr, vol. 1, p. 105)" was cut at the comma, so two entries became the same text and the request fell through to a text search.
- **Fix (backend, `api.py`):**
  - **Menus carry IDs:** every saint menu returns `option_ids` next to `options`, left out of other replies. `/chat` takes `saint_id` (a menu choice) and `saint_name` (a saints-list or calendar name).
  - **Choice by ID:** `saint_id` selects that entry outright. No index matching runs, and the entry's own chunks lead the context, taken from the chosen record without a lookup by name. An unknown ID falls back to the question.
  - **Saints-list and calendar names:** `saint_name` resolves by exact displayed name, then by the curated owner ("St. Athanasius" is the Apostolic), then by the only entry that carries it. It never produces a menu, so calendar links such as "St. Athanasius" and "St. Mary" still open one saint.
  - **Alias ownership** (`_assign_alias_owners`, v1 and v2):
    - A group of the alias table belongs to its curated saint, else to the one entry whose own name is one of the group's descriptive names.
    - Any other alias of two or more words that several entries carry goes to the entries whose own name starts with it.
    - Bare names stay with every entry that has them.
  - **Straight to one entry:** a full name (taken whole, commas included), an owned alias ("the Apostolic", "of Alexandria", "of Nyssa", "the Great"), or an entry's own descriptor ("St. Athanasius the Martyr", `base_name + descriptor` in v2).
    - "St. George the Great Martyr" is added to the alias table for the Cappadocian; the index had only "St. George, the Capaducian".
  - **Menu only when genuinely ambiguous:**
    - A bare name several entries share ("St. Athanasius": 7 entries, the curated saint first).
    - A name two entries carry equally ("St. Agathon the Martyr": two entries on p. 105).
    - Capped at 12.
  - **Arabic (v2):**
    - Same rules for "من هو / حدثني عن …" questions and saints-tab lookups; the Arabic path had no menu before.
    - A bare name must lead the entry's name: its first word, or its second when the dictionary gives two spellings ("جريجوري (إغريغوريوس)"). "عبد المسيح" is not an answer to "من هو المسيح؟".
    - A single close match counts: "غريغوريوس النزينزي" reaches the entry "إغريغوريوس ( غريغوريوس ) النزينزي القديس".
    - v1 Arabic has no entry IDs and keeps its previous behaviour.
  - The named-subject check (GEN-006) is skipped for a chosen entry, whose own passage leads the context.
- **Fix (frontend):**
  - `lib/message-options.ts` keeps each option's ID from the reply, through the saved conversation, to the request its chip sends. The IDs are stored as `{label, saintId}` in the existing `options` jsonb column: no migration, and old rows still read.
  - Menus saved before this fix have no IDs and are sent by exact name (`saint_name`).
  - The saints pane and its "Learn more" button pass the ID, or the exact name.
  - **No drop cap** on messages without sources (menus, refusals): `is-plain`.
- **Namesake groups (saints index, English):**

  | | v1 | v2 |
  |---|---|---|
  | entries | 1,363 | 1,933 |
  | groups with the same name (2+ entries) | 0 | 25 (53 entries) |
  | groups sharing a first name, which can show a menu | 175 (628 entries) | 249 (1,078 entries) |

  - v1's index kept only the first entry of each name, so it hid namesakes rather than having none.
  - Arabic v2: 2,105 entries, 141 same-name groups (286 entries) and 295 first-name groups (1,201 entries). Many same-name groups are the dictionary repeating an entry in its last pages.
  - So v2 can show a menu for more names, and longer menus, but only for bare or equally shared names.
- **Verification:**
  - **Backend tests:** `tests/test_saint_menus.py`, 17 tests, English and Arabic. Question → menu → choice by ID → answer whose first source is that entry. They use the committed index and chunks, with OpenAI stubbed. They cover Athanasius, the Agathons, the Gregorys, the Anthonys, George, calendar names, unknown IDs, and a v1 test of the alias table. 13 of the 17 fail on the previous code.
  - **Frontend tests:** `lib/message-options.test.ts`, 6 tests. Backend reply → saved message → reload → chip → request fields.
  - **Retrieve-only on the local v2 store** ($0.0032, ledger `eval/results/spend-ret010.json`): 13 questions and 10 choices, all reaching the right entry's first chunk.
  - **Browser** (`ui-audit/tools/saint-menu.mjs`, Chrome, `/api` mocked):
    - the menu has no drop cap (`initial-letter: normal`) and the sourced answer keeps it (`2`);
    - the chip posts `saintId: "athanasius"` in English and Arabic.
  - **`eval/smoke_v2.py` against a local v2 backend:** all 8 pass (~$0.01). Case 3 now expects the "St. George" menu, chooses the Cappadocian by ID and needs an answer led by his entry.
- **Tests:** backend 152, frontend 125.
- **Revisit if:**
  - bare-name menus prove too frequent: a name whose curated saint is overwhelmingly meant (St. Mary, St. Mark) could go straight to him with a "did you mean another?" line;
  - or the saints index is rebuilt: move the alias ownership into ingest and drop the copied v1 aliases there.

### RET-011: Default saints for bare names; hand-written alias audit
- **Date / Part:** 2026-09-23, follow-up to RET-010 before deploying `fix-saint-menu-loop`.
- **OpenAI:** retrieve-only check $0.0052 (pre-approved up to $0.02; ledger `eval/results/spend-ret011.json`); smoke set ~$0.01.
- **1. Defaults for bare names** (`data/saint_defaults.json`, reviewable, a reason per line):
  - **Why:** for a Coptic audience some bare names are not ambiguous. "St. Mary" is the Theotokos and "مارمرقس" is the Apostle, so the RET-010 menu got in their way.
  - **Behaviour:**
    - A question naming only a listed name goes straight to the major saint, in English and Arabic.
    - Titles are ignored: "St.", "القديس", "الأنبا", "مار".
    - The answer ends with a small "Looking for a different St. X?" link, or "هل تبحث عن قديس آخر باسم …؟" in Arabic.
    - The link opens a menu of every other saint of the name (up to 20, IDs attached, the major saint left out), and a choice works as in RET-010.
    - Names not on the list keep RET-010.
  - **The list:**

    | Name | Default |
    |---|---|
    | St. Mary / مريم | the Theotokos; "العذراء" is an epithet that also names her, and its namesakes stay out of the menu |
    | St. Mark / مرقس | the Apostle |
    | St. George / جرجس, جاورجيوس | the Cappadocian |
    | St. Athanasius | the Apostolic |
    | St. Anthony / Antony | Father of the Monks |
    | St. Mina / Menas / Mena | the Wonderworker |
    | St. Cyril | Cyril I of Alexandria |
    | St. Moses | the Black |
    | St. Macarius / مقاريوس, مقار, أبو مقار, مكاريوس | the Great |
    | St. Demiana | her entry |

  - **St. Paul is flagged for the priest and not applied** (`"active": false`). Neither dictionary has an entry for the Apostle. The proposal, Paul the First Hermit, risks answering about the wrong Paul, so "St. Paul" keeps the menu.
  - **Also for review:** "Kyrillos" and "البابا كيرلس" often mean Pope Kyrillos VI. The API reads "Kyrillos" as "Cyril", so they get Cyril I with the link to the others.
  - **v1:** the rows name a v1 entry. v1 has none for Mark the Apostle, Cyril of Alexandria or Demiana, so there those names keep the menu.
  - **Priority:**
    1. An exact dictionary name beats a default: "مينا الشهيد" and "مينا القديس" are two other Minas' entries.
    2. A default beats an entry called just the bare name (v1 "St. Mary").
    3. Saints-list and calendar names use the defaults too, with the link.
  - **No link** when there is no other saint of the name: English Anthony, Demiana.
  - **Link storage:** the link is kept as `{label, namesakesOf}` in the existing `options` jsonb, so there's no migration. `/chat` takes `namesakes_of` and returns `namesakes: {label, name}` on the answer.
- **2. Alias audit** (`eval/alias_audit.py`, read-only, report `eval/results/alias-audit.txt`, before: `alias-audit-before.txt`):
  - **Scope:** every hand-written alias: `api.SAINT_ALIAS_RECORDS`, `arabic_saints_index.py`, the curation seeds, and the frontend display table in `lib/saint-display.ts`.
  - **Method:** each alias is looked up the way the API looks it up, in the v1 English, v2 English and v2 Arabic indexes. Findings:
    - WRONG: reaches another saint;
    - SHARED: a multi-word name shared by several entries;
    - STRAY: carried by another entry;
    - OTHER: is another entry's own name;
    - MISSING: does not reach its saint.
  - **Results:**

    | | issues |
    |---|---|
    | Previous commit | 27 (MISSING 16, SHARED 6, OTHER 3, WRONG 2) |
    | Now | none (202 aliases) |

  - **What changed:**
    - **Mark and Cyril (MISSING 16).** "St. Mark the Evangelist/Apostle" and "St. Cyril of Alexandria" reached no entry in v2, whose entries are "St. Marcus, the Apostle" and "St. Cyril I, the 24th Pope". The table's names were attached only to an entry whose own name matched one of them. Now the owner of a hand-written group always receives the group's names.
    - **v1 Theotokos (SHARED 6).** "St. Mary Theotokos", "Mother of God" and "Holy Virgin Mary" were carried by both v1 "St. Mary" and "St. Mary, the Virgin Theotokos": a menu. Group ownership now goes to the entry matching the group's most specific name. "St. Mary the Virgin" is also a prefix of "St. Mary, the Virgin Confessor".
    - **Seed aliases naming other saints (OTHER 3).** `arabic_saints_index.py` gave the Nehissy entry "أبانوب المعترف" (the Confessor has his own entry) and the Wonderworker "مينا الشهيد" and "مينا القديس" (the own names of two other Minas). They are removed from the seed file.
      - The committed v2 index (built from the seeds at ingest) still lists them.
      - A new Arabic ownership pass drops any alias of two words or more that is the start of another entry's own name, so this takes effect now without a rebuild.
    - **Arianus (WRONG 2, a RET-010 regression, never deployed).** "بولس الرسول" reached Arianus, governor of Ansena. RET-010's single-close-match rule found it inside a garbled index key ("…ارسطوبولس الرسول…"). Matches are now whole words; the Apostle has no entry, so no entry is reached.
    - **Repeated dictionary entries** ("أبانوب المعترف القديس (ص 30، مدخل 2)") count as one saint, so "أبانوب المعترف" reaches the Confessor.
    - **"Pope Cyril" removed** from the backend table and its frontend mirror. It sent a name six Popes share to Cyril I; it now falls back to the ordinary rules.
- **Tests:** backend 183 (`tests/test_saint_defaults.py`, 31 tests):
  - every active row in English and Arabic, with the link present exactly when there are others;
  - link → menu → choice by ID;
  - the epithet, the full link menu, St. Paul inactive;
  - exact names over defaults, calendar names;
  - the audit's v2 checks on the committed index, the fixed aliases, v1 Theotokos ownership.
  - Four RET-010 tests now follow bare "St. Athanasius" and "أنطونيوس" through the default and its link.
  - Frontend 127 (2 new: the link survives a saved conversation and sends `namesakes_of`).
- **Retrieve-only on the local v2 store:** all 11 rows × 2 languages and 6 alias cases correct (the 22 row questions plus the 6 alias cases, all 28 correct).
- **Smoke set (local v2):** 8/8. Case 3 ("search saint: St. George") now expects the Cappadocian with the link, and checks the link's menu (the other two Georges, with IDs).
- **Not done:** no browser check of the new link's look. It uses the menu styles' accent colour, underlined, between the answer and its sources.
- **Revisit if:**
  - the priest decides St. Paul, or the Kyrillos question;
  - a name's second saint is added to a dictionary;
  - the index is rebuilt (the seed fixes then land in `saints_index.json` too, and the Arabic ownership pass becomes a no-op for them).

### RET-012: Where a request's time goes, and what could make it faster (report, not changed)
- **Date / Part:** 2026-09-23, speed branch Part B1–B2. Nothing is changed until the owner approves.
- **Data** (`eval/latency_baseline.py`, no OpenAI calls):
  - **Recorded:** `stages_ms` from the two v2 coverage runs of 22–23 September (`20260923-000307`, `-002553`: v2, gpt-4.1-mini, top-k 16, threshold 1.25, prompt v3, entity check on, the local machine). Also today's local request logs with `ttft_ms` (streamed answers, which record their first token).
  - **Measured locally on the v2 store:** vector search (queried with stored chunk vectors, so no embedding call), the Arabic lexical scan, context assembly and the named-subject check. The embedding function raises if called.
  - **Production logs are not in this report.** The Railway CLI's login has expired and needs the owner's browser. Railway also runs on a different CPU, so the local stages (the lexical scan above all) may be slower there.
- **B1: time per stage** (median / p90, ms; "retrieval" is the query embedding call, the vector search and, for Arabic, the lexical scan):

| | English, answered (n=153) | English, refused (n=67) | Arabic, answered (n=40) | Arabic, refused (n=6) |
|---|---|---|---|---|
| analysis (gpt-4o-mini call) | 1,031 / 1,297 | 1,031 / 1,277 | 1,016 / 1,286 | 984 / 1,188 |
| retrieval | 250 / 344 | 188 / 256 | 790 / 1,081 | 852 / 891 |
| generation (whole answer) | 3,438 / 5,547 | 1,203 / 1,635 (model refusals) | 3,000 / 4,044 | 1,265 / 1,501 |
| total | 4,780 / 7,088 | 2,300 / 2,938 | 4,805 / 6,016 | 2,970 / 3,190 |

  - **Inside retrieval** (local, v2):
    - Vector search: 3.3 ms (English, k 16), 3.0 ms (Arabic), 5–6 ms for three queries at once; k 12 is 2.4 ms.
    - The query embedding is therefore almost all of the English retrieval stage (about 0.25 s).
    - **Arabic lexical scan: 739 ms median, 798 p90** over the 23 Arabic questions. 302 ms is fetching all 4,484 Arabic chunks from Chroma in pages of 500; the rest is normalising and scoring every chunk in Python (AUDIT C13).
  - **Context assembly:** under 0.1 ms. **Named-subject check:** 1.7 ms. **Post-processing:** under 1 ms.
  - **Time to first token** (today's streamed answers, local):
    - English median 2.9 s (n=4), Arabic 4.0 s (n=2).
    - The model's own first token, after analysis and retrieval, took 0.9–1.0 s.
    - Implied first token for the eval runs (analysis + retrieval + about 0.95 s): about 2.2 s for English and 2.8 s for Arabic.
  - **The site** (`/api/chat/stream` and the page, scripted backend): about 0.25 s from the backend's first token to the first word on screen. Creating a new chat's conversation first took 8 ms against the local database; against Neon in production it is unmeasured.
- **What depends on the analysis call** (`TaskAnalysis`), and whether rules could stand in:
  - **`retrieval_query`** (follow-ups, format words removed): rules can keep this for first turns without format words. In tune, 68 of the 80 "simple" questions came back unchanged.
  - **`output_format`** (format note, `max_tokens`): a keyword rule decides "simple" only when no format word appears.
  - **`broad` and `sub_queries`:** list and table words exclude a question from "simple". None of the 80 was broad.
  - **`saint_name_filter`:** already rule-based (`name_filter_from_question`).
  - **`named_subjects`**, the GEN-006 entity check: **no rule stands in.** It was filled for 52 of the 80 simple tune questions, and it is how 16 of the 23 simple out-of-corpus questions get declined ("What is papal infallibility?").
  - **`in_scope`**, the Arabic scope gate: **no rule stands in either.** It was false for 6 of the simple questions.
- **B2: proposals, ranked by expected saving against risk:**

| # | Change | Saves (median, per request) | Applies to | Risk | Recommend |
|---|---|---|---|---|---|
| 1 | **Arabic lexical index kept in memory** (C13): the Arabic chunks normalised once (at startup or on the first Arabic request) and scanned in memory, with the same terms, scoring and order | ~0.5–0.7 s on first token and total | every Arabic question and Arabic saint lookup | low: results identical, which can be checked for every Arabic question without OpenAI; ~10–20 MB memory; ~1 s once at build | **yes** |
| 2 | **Speculative retrieval:** embed and search the user's own question while the analysis call runs; keep the result when the rewritten query is the same after normalising case and punctuation, otherwise search again as today | ~0.25 s (the embedding) | ~70% of requests (68 of 96 on tune; 68 of 80 simple ones) | low: reused only on an exact match, so results are identical; one extra embedding otherwise (~$0.000002) | **yes** |
| 3 | **Analysis cache** for identical first-turn questions (no history), keyed by question, language, mode and the analysis model and prompt; temperature 0 already | ~1.0 s | repeats: the home page's example questions, the 36 catechism prompt cards, common questions | very low | **yes** |
| 4 | **Comparison questions:** one embedding for the main search and the per-tradition searches (today each tradition re-embeds the same query) | 0.25–0.5 s | comparison questions (~5%) | low: identical results | **yes** |
| 5 | **Answer cache for the four home-page example questions:** first-turn only, replayed as a quick stream; invalidated when the corpus, prompt, model, top-k or threshold changes | the whole wait (3–5 s → ~0.1 s) | those four questions in each language | low for correctness; everyone gets the same answer | owner's call |
| 6 | **Create the conversation in the stream route**, not by a separate request before it | one round trip on a chat's first question (8 ms locally; production unmeasured, likely 0.1–0.3 s) | first question of each chat | low–medium: the page's flow changes | after production numbers |
| 7 | **top-k 12 instead of 16** (ING-007's logged option) | est. under 0.1 s of model first token; ~20% cheaper generation | all answers | medium: tune recall was the same (0.91) but answer coverage wasn't measured | only with the B3 eval, as its own change |
| 8 | **A faster analysis model** (e.g. gpt-4.1-nano) | est. ~0.3 s | all | medium–high: `named_subjects` and `in_scope` quality feed the entity check | not now |
| 9 | **Speculative generation:** start the answer while analysis runs, hold its text until analysis confirms the prompt was right, otherwise cancel and restart | ~0.9 s on first token | ~60–70% | medium, and complex; ~+30% generation input cost from cancelled starts | not now |
| 10 | **Skip analysis for simple first-turn questions** | ~1.0 s | 80 of 96 tune questions | **high:** the entity check and the Arabic scope gate lose their inputs (above); near-miss refusals would fall back toward GEN-006's "before" (77% of out-of-corpus refused instead of 96%) | **no** |
| 11 | **English and Arabic retrieval, and sub-queries, in parallel** | ~0 | — | — | nothing to gain: a request searches one collection, and sub-queries already share one embedding call and one 5 ms Chroma query |

  - **Expected with 1–4:**
    - English first token about 2.2 → 1.95 s (−0.25 s when the rewrite is unchanged); repeated first-turn questions a further −1.0 s.
    - Arabic about 2.8 → 2.0 s (−0.8 s).
    - Totals fall by the same amounts, since generation is unchanged.
  - **What remains:** the analysis call (~1.0 s) and the model's first token (~1.0 s) are both OpenAI latency. Only 8–10 go after them, at a quality or cost risk.
- **B3 plan and cost** (after approval):
  - Coverage and refusal on tune, English and Arabic reported separately, with the approved changes. Compare against the two existing tune baselines of the same production config (22–23 September), plus the smoke set.
  - Estimate: one tune run is about $0.59 (from the recorded runs: $0.82 for 134 questions, $0.29 of it the gpt-4.1 judge). Two "after" runs, to judge noise the same way the baselines were judged, come to about $1.20. The smoke set is about $0.04. First token before/after on five streamed questions costs about $0.02. **Total about $1.25.**
  - If the owner prefers fresh baselines on the same day as the "after" runs, add about $1.20.
- **Files changed:** `eval/latency_baseline.py` (new).

### RET-013: The Arabic lexical scan runs over an in-memory copy of the normalised chunks
- **Date / Part:** 2026-09-23, speed branch Part B3, change 1 of RET-012 (approved)
- **Audit ref:** AUDIT C13
- **Context:** every Arabic question and Arabic saint lookup read all 4,484 Arabic chunks from Chroma in pages of 500 and normalised each one in Python before scoring them. That took 0.74 s median locally (RET-012), and it is most of the Arabic retrieval stage. The store doesn't change while the process runs.
- **Decision:**
  - The reading and normalising moved into `_scan_arabic_collection`, and its rows (normalised text, page, document, metadata, in the collection's order) are kept in memory per metadata filter: all, catechism, saints.
  - Scoring, ordering and deduplication are unchanged, so the results are the same.
  - The rows are built in a background thread at startup (1.5 s for all three filters locally), so no visitor waits for them. If that thread hasn't finished, the first request builds what it needs.
  - A different collection object (a test's fake, a rebuilt store) starts a fresh index.
  - Memory is roughly the Arabic text twice, about 20 MB.
  - `ARABIC_LEXICAL_CACHE=0` goes back to the scan.
- **Checks:**
  - `eval/check_arabic_lexical_cache.py` (no OpenAI) ran on the real v2 store with the 23 Arabic eval questions and 20 Arabic saint lookups, each in all three modes. **All 129 comparisons returned the same chunks in the same order.** Median time went from 538 to 23 ms, p90 from 723 to 39 ms.
  - `tests/test_speed.py`: the same results with and without the index for three questions and three filters; the collection is read once per filter; a new collection is read again.
  - Backend suite: 199 passed.
- **Files changed:** `api.py`, `tests/test_speed.py` (new), `eval/check_arabic_lexical_cache.py` (new).

### RET-014: Each query text is embedded once per request, and the search is given the vectors
- **Date / Part:** 2026-09-23, speed branch Part B3, change 4 of RET-012 (approved)
- **Context:** Chroma embedded `query_texts` on every search. A comparison question searched the same rewritten question again once per tradition named (RET-008), so it paid for the same embedding (~0.25 s each) two or three times. The prefetch in RET-015 also needs somewhere to put a vector computed early.
- **Decision:**
  - `_retrieve_documents` gets its vectors from `_embed_queries`. That calls the collections' own embedding function (`embed_fn`, kept from startup) once for the texts it hasn't seen in this request, remembers them in a request-scoped memo (a context variable set around `_chat_prepare` by both `/chat` and `/chat/stream`), and passes `query_embeddings` to Chroma.
  - Nothing is kept between requests.
  - A value in the memo may be a future (RET-015). If it failed, the text is embedded again.
  - Without an embedding function (tests with fake collections), Chroma embeds `query_texts` as before.
  - The trace records a new sub-stage, `stages_ms.embedding` (time spent embedding, inside `retrieval`), and `embeddings_reused`.
- **Why the results can't change:** Chroma's `query_texts` path calls the same embedding function and searches with its output. A test on the real v2 store, with a deterministic stand-in embedding, shows the same IDs and distances, in the same order, for both collections.
- **Checks:** `tests/test_speed.py` covers three searches of one text in a request (one embedding call; the second search keeps its `where_document`), a new request embedding again, a failed prefetch being embedded again, the fallback without an embedding function, and the real-store equivalence. Backend suite: 203 passed.
- **Files changed:** `api.py`, `tests/test_speed.py`.

### RET-015: The question is embedded while the analysis call runs, and reused when the analysis leaves it unchanged
- **Date / Part:** 2026-09-23, speed branch Part B3, change 2 of RET-012 (approved)
- **Context:** the query embedding (~0.25 s) waited for the analysis call (~1.0 s), although most analyses return the question unchanged. On tune, 67 of 92 first-turn questions came back exactly as asked.
- **Options considered:** reuse when the rewrite matches after normalising case and punctuation (proposed in RET-012), or only on an exact match. On tune, normalising adds a single question ("What is prayer" → "What is prayer?"), and a vector for different text can shift the results slightly.
- **Decision:**
  - Just before the analysis call, `_chat_prepare` puts a future for the question's embedding into the request's memo (RET-014), under the text exactly as retrieval would send it: canonicalised, with whitespace collapsed. The future runs in a small thread pool.
  - Retrieval finds it only when its first query is that same text, so **results are identical**. Anything else is embedded as before, and the prefetched vector goes unused.
  - No prefetch when the analysis call won't run ("search saint:", or analysis switched off): there is nothing to overlap.
  - A failed prefetch is embedded again.
  - The trace records `embedding_prefetch`: "reused" or "unused".
  - `EMBEDDING_PREFETCH=0` switches it off.
- **Cost:** an unused prefetch is one embedding of about 15 tokens, about $0.0000003.
- **Checks** (`tests/test_speed.py`):
  - An unchanged question makes one embedding call and records "reused".
  - A rewritten question embeds the rewrite and records "unused".
  - "search saint:" doesn't prefetch.
  - Through `_prepare_or_http_error` with a stub analysis, the prefetch is already under way when the analysis starts, and retrieval doesn't embed the question again.
  - Backend suite: 207 passed, three times over.
- **Files changed:** `api.py`, `tests/test_speed.py`.

### RET-016: A first-turn question asked before reuses its analysis
- **Date / Part:** 2026-09-23, speed branch Part B3, change 3 of RET-012 (approved)
- **Context:** the analysis call (~1.0 s median) is the largest stage before the answer starts. A first message is analysed on its own, without history, at temperature 0, so the same question gets the same analysis every time. Many questions arrive as exactly the same text: the home page's example questions, the 36 catechism prompt cards, and the questions everyone asks.
- **Decision:**
  - `AnalysisCache` (`task_analysis.py`) keeps successful first-turn analyses in the process's memory, keyed by the analysis model, a hash of the analysis prompt, and the exact question. Changing the model or the prompt misses the cache.
  - Up to 2,000 entries, least recently used dropped first. Each is a few hundred bytes.
  - Not cached: follow-ups (their analysis depends on the conversation), failed or timed-out analyses, and "search saint:" lookups (which make no call anyway).
  - A hit returns a copy with no token counts, so spend accounting stays right, and the trace records `analysis_cached: true`.
  - A redeploy or restart starts empty.
  - `ANALYSIS_CACHE=0` switches it off.
- **Why quality can't drop:** everything downstream (the entity check's `named_subjects`, the Arabic scope flag, format, broad lists) receives exactly what the first call returned, which is what a second call returns at temperature 0.
- **Checks** (`tests/test_speed.py`):
  - A repeated question makes one call, the copy has no tokens and can't alter the cache.
  - Follow-ups call every time, and a failure isn't cached.
  - Another model or prompt misses.
  - The least recently used entry is dropped first.
  - Backend suite: 211 passed.
- **Files changed:** `task_analysis.py`, `api.py`, `tests/test_speed.py`.

### RET-017: The home page's example questions keep their answer, replayed as a stream
- **Date / Part:** 2026-09-23, speed branch Part B3, change 5 of RET-012 (approved by the owner: still play the streaming fade-in; invalidate when the corpus or prompt changes)
- **Context:** the four example questions shown on the home page and in an empty chat are the most-asked texts on the site. Each one waits 3–5 s for an answer that comes out the same every time.
- **Decision:**
  - **Which questions:** `data/cached_answer_questions.json` lists the four shown per language. A frontend test (`lib/cached-questions.test.ts`) fails if it drifts from `lib/home-content.ts`.
  - **Which requests:** only a chat's first message in chat mode, with the exact text, in the language of its list. Not follow-ups, saint selections, catechism or saints mode, or the eval harness's `debug` requests, so evals always measure a freshly generated answer.
  - **What is kept:** the first finished answer with sources (`answer_cache.py`, in memory). A refusal, a menu, a stopped or failed answer is never stored.
  - **Invalidation:** the key includes a fingerprint of everything that shapes the answer: corpus version and the v2 manifest's hash, prompt version and the text of both answer prompts and the analysis prompt, both models, temperature, top-k, thresholds, answer lengths and the entity-check switch. Change any of them and the next ask generates afresh; older answers for that question are dropped. A restart or redeploy starts empty, so the first visitor after a deploy waits as today.
  - **`/chat/stream`:** a hit skips analysis, retrieval and generation. The answer is replayed as `delta` events of three words every 25 ms (about twice the model's pace), then the usual `done` with the same payload. The page fades it in, saves the turn and shows the sources exactly as for a written answer.
  - **`/chat`:** returns the payload directly.
  - **Logging:** the trace records `answer_cache`: "hit" or "stored".
  - `ANSWER_CACHE=0` switches it off.
- **What the reader loses:** a fresh wording on each ask. Everyone asking an example question in the same deploy gets the same answer.
- **Checks** (`tests/test_speed.py`, frontend test):
  - Replay pieces rejoin exactly, including Arabic and Markdown.
  - A second ask makes no model call and returns the same payload.
  - The stream replays it in several pieces, then `done` equal to the stored payload.
  - Non-example, follow-up, debug, catechism-mode and wrong-language requests aren't cached; a refusal isn't stored.
  - A prompt-version or corpus change misses.
  - The backend list equals the page's.
  - Backend 217, frontend 169 passed.
- **Files changed:** `answer_cache.py`, `data/cached_answer_questions.json`, `orthodox-site/lib/cached-questions.test.ts` (new); `api.py`, `tests/test_speed.py`.

### RET-018: Each hop of a question is timed: the site's routes and the backend write lines that join up
- **Date / Part:** 2026-09-23, speed branch Part B3 (owner's request: time every hop, browser to backend and back, before deciding on RET-012's change 6)
- **Context:** the backend already logs its stages and `ttft_ms`, but nothing recorded the site's side: the conversation-creation request, the Neon reads and writes, the Vercel → Railway hop, or the relay back to the browser.
- **Decision:**
  - **Site routes** (`lib/route-timing.ts`) write one JSON line per request to stdout (`event: "route_timing"`, in the Vercel logs), with the route's wall-clock start, the backend's request ID and these durations in ms:
    - `/api/chat/stream` and `/api/chat`: `history` (Postgres read), `backend_request` (when the backend fetch started), `backend_headers` or `backend` (until the backend replied), `first_delta` and `done` (since the route started), `save` (Postgres write), and `history_messages` (0 on a chat's first question).
    - `/api/conversations` POST: `db` (the insert).
    - `/api/saint-detail/stream`: the backend and relay steps.
  - The steps done before a response starts also go to the browser in a `Server-Timing` header, and the backend's `X-Request-ID` is passed on, so a browser trace can find both log lines.
  - It writes with `process.stdout` rather than `console.log`: a structured line, not the debug logging UI-010 removed.
  - **Backend:** the request line gains `start_epoch_ms` (wall clock) and, for streams, `headers_ms` (when the stream's headers went out).
  - **`ui-audit/tools/hops.mjs`** wraps the page's `fetch` to record when each request starts, when its headers arrive and when the first streamed chunk arrives, and records when the first word is painted. It joins that with both log lines to print every hop, for a new chat and a follow-up. Across machines (production) only the durations are comparable, because the clocks differ.
- **Checks:** against the scripted backend, the hops add up to the measured click-to-first-word time (723 ms). Hops between different clocks can read a few ms negative from rounding. Backend 217 and frontend 169 tests passed; typecheck and lint clean.
- **Files changed:** `orthodox-site/lib/route-timing.ts` (new), `orthodox-site/lib/stream-proxy.ts`, `orthodox-site/lib/chat-proxy.ts`, `orthodox-site/app/api/chat/route.ts`, `orthodox-site/app/api/chat/stream/route.ts`, `orthodox-site/app/api/saint-detail/stream/route.ts`, `orthodox-site/app/api/conversations/route.ts`, `request_log.py`, `api.py`, `ui-audit/tools/hops.mjs` (new).

### RET-019: Verification of the speed changes: quality holds; Arabic answers start ~0.7 s sooner, English ~0.1 s, repeated example questions at once
- **Date / Part:** 2026-09-23, speed branch Part B3 (checks RET-013 to RET-017)
- **Setup:**
  - The local backend in the production configuration: v2, gpt-4.1-mini, top-k 16, threshold 1.25, prompt v3, entity check on, with all five changes on.
  - Coverage and refusal on tune, twice (`20260923-181810`, `-182812`), restarting the backend before each so neither run starts with the other's cached analyses. Compared with the two existing tune baselines (`20260923-000307`, `-002553`) as the owner asked, using `eval/speed_compare.py` (new).
  - The smoke set. Time to first text before/after measured in the browser (`ui-audit/tools/hops.mjs`, RET-018) with the five changes switched off and then on.
- **Quality (tune; mean of two runs, per-run values in brackets):**

| | English before | English after | Arabic before | Arabic after |
|---|---|---|---|---|
| coverage (all answerable) | 0.745 (0.744, 0.746) | 0.757 (0.750, 0.763) | 0.734 (0.735, 0.733) | 0.713 (0.745, 0.682) |
| answerable refused | 0% | 0% | 0% | 0% |
| out-of-corpus refused | 93.8% (95.8, 91.7) | 95.8% (95.8, 95.8) | 100% | 100% |
| near misses refused | 90.0% (93.3, 86.7) | 93.3% (93.3, 93.3) | 100% | 100% |
| off-target answers | 7.7% | 4.8% | 0% | 0% |

  - **Entity check:** in both runs it declined 12 questions and noted a missing subject for 3.
  - **Refusal changes:** the only question whose refusal changed is OOC-31. It was refused in one baseline and answered in the other; now it was refused in both runs.
  - **Arabic coverage** dipped in run 2. Of the 17 answerable Arabic tune questions, 14 retrieved identical passages in all four runs. On those, coverage was 0.733 and 0.715 before and 0.737 and 0.694 after: the same range, from generation and the judge (AR-16 scored 0.7, 0.3, 0.4 and 0.4 on identical passages).
  - **The other 3 (AR-02, AR-03, AR-13) retrieve differently, but not because of these changes.** With all five switched off (`ARABIC_LEXICAL_CACHE=0 EMBEDDING_PREFETCH=0 ANALYSIS_CACHE=0 ANSWER_CACHE=0`, retrieve-only, `20260923-182920`), today's code retrieves exactly what the "after" runs did. The baselines predate RET-010, RET-011 and ING-007, which put an Arabic saint's own entry first in the context.
  - **Found along the way:** AR-03 scored 0.94 and 1.0 in the baselines and 0.81 and 0.56 since those commits. Worth a look under RET-010/011, separately from this branch.
  - **Smoke set:** 8/8 passed with the five changes on.
- **Speed** (answered tune questions; median / p90 ms):
  - **Time before generation starts** (analysis + retrieval; the model's first token follows about 0.4–1.0 s later):
    - English: 1,297 / 1,625 → **1,211 / 1,469**.
    - Arabic: 1,890 / 2,140 → **1,211 / 1,477**.
  - **Retrieval stage:**
    - English 235 → 203 ms overall. It was 16 ms for the 58% of questions whose rewrite matched and the prefetch was reused; the other 42% were rewritten, as the tune set has many format requests and follow-ups.
    - Arabic 899 → 78 ms.
  - **Analysis:** unchanged (1,031 → 1,016 ms). No tune question repeated, so the analysis cache never hit.
  - **Generation and total** can't be compared across these days: OpenAI took 10.3–12.2 ms per output token today, against 7.8–8.7 ms on 22 September, with similar answer lengths. The total rose for that reason alone; none of the changes touch generation.
  - **Browser, first word after click** (6 questions each: 2 English and 1 Arabic new chats with a follow-up each; same session, changes off then on):
    - Median 2.68 s → 1.43 s. But the model's own first token also fell (~720 → ~420 ms) and the analysis varied, both OpenAI latency.
    - The part the changes explain is retrieval: 170–1,140 ms (English) and 940 ms (Arabic) → 0–140 ms and 80–250 ms.
  - **A home-page example question asked a second time** (RET-017): first word at **49 ms** instead of 1.9 s, faded in as usual, with the whole answer by 3.5 s.
  - **Keep-alive** (checked because the first request after startup spent 1.1 s on one embedding): with the default 5 s idle timeout and with 120 s, embeddings took 231 vs 214 ms after 12 s idle and 240 vs 199 ms after 1 s, within noise. Reconnecting is cheap; the 1.1 s was a first-request cost after startup. **Not changed.**
- **OpenAI spend:** eval runs $0.6023 and $0.5971, retrieve-only check $0.0006 (ledger `eval/results/spend-speed.json`: $1.2000), browser timing runs $0.0634, smoke set $0.0252, keep-alive check under $0.0001. **Total $1.29** against the ~$1.25 approved; the $0.04 over is the hop timing the owner asked for in the same message. No quota or key errors.
- **Files changed:** `eval/speed_compare.py` (new); `eval/results/20260923-181810.json`, `-182812.json`, `-182920.json`, `spend-speed.json`; `.gitignore` (`ui-audit/hops/`).

### RET-020: The path from click to first word, hop by hop, and what creating the conversation in the stream route would save (report)
- **Date / Part:** 2026-09-23, speed branch, before RET-012's change 6. Nothing changed; the owner decides.
- **The question:** Step 4 of the streaming work (UI-027) measured ~4.9 s to the first text in the browser, while RET-012 estimated ~2.2 s to the backend's first token. Is ~2.5 s spent outside the backend?
- **No.** In that same Step 4 request, the backend's own first token came at 4.36 s: its analysis call took 2.7 s (usually 1.0 s), retrieval 0.8 s and the model's first token 0.9 s. About 0.5 s was outside the backend. The ~2.2 s was a median over many eval questions; that request was a slow one.
- **Every hop, measured locally** (`ui-audit/tools/hops.mjs`, RET-018; site, backend and a local PGlite database on one machine, so the clocks agree; 6 questions with the speed changes off and 8 on, ms):

| hop | new chat | follow-up |
|---|---|---|
| page: click → first request | 25–38 | 28–40 |
| conversation create (browser round trip) | 13–15 | — |
| … of which the database insert | 2–4 | — |
| page: conversation created → stream request | 0–1 | — |
| browser → site route starts | 1–2 | 1–2 |
| history read (database) | 2–3 | 2–3 |
| site → backend request arrives | 0–2 | 0–1 |
| **backend: analysis + retrieval (until headers)** | 828–3,063 | 875–1,953 |
| **backend: headers → model's first token** | 390–1,359 | 407–718 |
| backend headers → site receives them | −7–13 (clock rounding) | |
| backend first token → site relays it | 0–9 | |
| site relays → browser receives first chunk | 0–5 | |
| first chunk → first word painted | 2–9 | |
| save (database, after the answer) | 5–11 | |

  - Everything outside the backend adds **about 50–60 ms** locally. The rest is the analysis call, retrieval and the model's first token: OpenAI latency and our own stages.
- **Production** (the Railway CLI's login has expired, so there are no backend or Vercel logs yet). These probes cost nothing and write nothing, run from the owner's machine, each opening a new TLS connection (70–290 ms of each figure, which a browser reuses):
  - **Vercel function + one Neon read** (`GET /api/conversations`, a fresh visitor): 0.16–0.36 s warm. **2.06 s after 7 minutes idle** and 0.78 s after 5.5 minutes: Neon's compute suspends after about 5 minutes without queries and takes up to ~2 s to wake. The site's Neon database is in AWS us-east-1.
  - **Vercel function + Railway backend lookup, no database or OpenAI** (`GET /api/saints?limit=1`): 0.22–0.60 s, with or without idle time (one 0.89 s). No Vercel cold start showed in these samples.
  - The home page and the chat page both fetch the past-chats list on load, which wakes Neon then. A reader who takes a couple of seconds before asking never waits for it; one who clicks an example question the moment the page opens after a quiet spell can.
- **What change 6 would save** (the stream route creates the conversation when it saves the answer, instead of the page creating it first):
  - It removes, before a new chat's first question reaches the backend, the page's `POST /api/conversations` (a Vercel function run and a Neon insert) and the empty history read. Warm: about 0.1–0.2 s in production (a function round trip; locally 15 ms). With Neon asleep: up to ~2 s, because the database would first be touched after the answer is on screen.
  - Follow-ups are unaffected; they read their history, usually from a warm database.
  - Design points if approved:
    - The saved conversation reaches the page in the final event, as it already does for a stream.
    - The page must not wait for a conversation ID before asking, and it takes the URL and sidebar entry from the final event.
    - The final event currently waits for the save. So that the sources don't wait for a waking database, the answer and sources should go out first and the saved IDs just after.
    - Stop and failures behave as today: nothing is saved, and now no empty conversation is left behind either.
  - **Recommendation: do it.** Small on a warm path, large on a cold one, and it removes a second request from every new chat. Risk low–medium: the page's send flow changes, and the browser checks would cover it.
- **Anything else in the path:**
  - **Neon's 5-minute suspend** is the largest cost outside the backend on a quiet site, partly hidden by the page-load fetch. A longer suspend timeout or none (paid Neon plans) would remove it. A keep-warm ping every few minutes would keep the compute running around the clock and use up the free plan's compute hours. Change 6 takes it off the question's path either way. *Owner's call on the Neon plan.*
  - **Railway's region** isn't in the repo (it's set in the dashboard). If it isn't US East, every Vercel → Railway request crosses the continent: ~60–70 ms, paid once per question (the stream then flows). Worth checking in the Railway dashboard.
  - **OpenAI keep-alive:** checked (RET-019); no gain.
  - **Nothing else outside the backend costs more than a few tens of ms locally.** The remaining time to first text is the analysis call (~1.0 s) and the model's first token (~0.4–1.0 s).
- **To finish the production picture** (after `railway login`): run `hops.mjs` against the production site (3 new chats and 3 follow-ups, about $0.03, writing 3 conversations to the production database under a fresh anonymous visitor), then join it with `railway logs` by request ID. The per-hop split inside Vercel (history, save, relay) needs RET-018's route timing deployed; until then, the browser's timings and the backend's log give the Vercel → Railway and database hops by difference.

### RET-021: A new chat's conversation is created when its first answer is saved; the answer and sources arrive before the IDs; a failed save is retried, then said plainly
- **Date / Part:** 2026-09-23, speed branch, RET-012's change 6 (approved by the owner after RET-020, with two conditions: say what happens when the database write fails after the answer is on screen, and send the answer and sources before the conversation IDs)
- **Context:** the page used to create a conversation (`POST /api/conversations`, a Vercel function run and a Neon insert) before sending a new chat's first question, and the stream route then read that conversation's empty history. Both sat on the path before the backend was even asked: about 0.1–0.2 s warm in production, and up to ~2 s when Neon was waking (RET-020).
- **Decision:**
  - **No conversation first.** The page sends a new chat's first question without a conversation ID. The route skips the history read, and saving the finished turn creates the conversation (`saveChatTurn` already could).
  - **Two final events.** `done` carries the answer and its sources as soon as the backend finishes. `saved` follows after the database write, with `{conversation, userMessage, assistantMessage, saved}`. A single event can't show the answer before its own IDs, so the owner's "answer and sources before the IDs in the final event" became two events in that order.
    - The page shows the finished answer, links its citations and announces it on `done`.
    - It takes the conversation ID, URL and sidebar entry from `saved`.
    - Stop disappears once the answer is complete; only the save is left.
  - **If the write fails after the answer is on screen:**
    - **Retry:** `saveTurn` (`lib/chat-proxy.ts`) makes three attempts, pausing 0.4 s and 1.2 s (`lib/retry.ts`). A missing database configuration fails at once.
    - **No duplicates:** the conversation and message IDs are fixed before the first attempt, and `saveChatTurn` first checks whether this answer's message is already stored. A retry after a write that committed but lost its reply returns the stored turn instead of saving a second copy.
    - **Never silent:** if every attempt fails, `saved` says `saved: false` and the answer stays on screen with a note under it, also read out by screen readers: "This answer couldn't be saved, so it won't appear in your past chats, and a follow-up question won't take it into account."
      - With no conversation ID, the next question starts a new conversation. The unsaved turn stays visible above it; the draft keeps its local ID, so the screen isn't cleared.
      - In an existing conversation, the next question continues it; its history lacks the unsaved turn, as the note says.
    - The same holds when the stream ends after `done` without a `saved`: the answer counts as not saved, not as an error.
    - `/api/chat` (the fallback) and JSON replies (refusals, menus) save the same way and return `saved: false` instead of a 500 error.
  - **Stop and failures before the answer** save nothing, as before, and a new chat no longer leaves an empty "New Chat" conversation behind.
  - The page's `createConversationRequest` is removed. `POST /api/conversations` stays for now, unused.
- **Checks:**
  - Frontend unit tests 169 → 176:
    - `withRetry`: success at once; two failures then success, with the given pauses; the last failure thrown; configuration errors not retried.
    - The stream client: `done` reported before `saved`; `saved: false` passed through; a stream that ends after `done` resolves as not saved.
  - Browser (`ui-audit/tools/save-failure.mjs`, new; scripted backend and local PGlite):
    - A new chat sent **0** conversation requests. The URL and sidebar entry arrived with the answer, the follow-up carried the same ID, and 4 messages were stored.
    - Stop on a new chat left **0** conversations.
    - With the database stopped mid-answer: the answer and its sources still showed, then the note (announced); no Stop after the answer. The next question went without an ID and was saved once the database came back, and the unsaved turn stayed on screen above it. A first version cleared it (each question made a new draft ID); fixed so a draft keeps its ID until a save gives it a real one.
  - `streaming.mjs MODE=fake` (scroll, saints pane, Stop, errors, both fallbacks, reduced motion) passes on the new events; axe finds 0 violations in 13 states. Its Stop check now expects no conversation at all.
  - Typecheck and lint clean.
- **Files changed:**
  - `orthodox-site/lib/retry.ts` (+ test), `orthodox-site/lib/conversations.ts`, `orthodox-site/lib/chat-proxy.ts`, `orthodox-site/lib/stream-proxy.ts`
  - `orthodox-site/app/api/chat/route.ts`, `orthodox-site/app/api/chat/stream/route.ts`, `orthodox-site/app/api/saint-detail/stream/route.ts`
  - `orthodox-site/lib/chat-client.ts` (+ test), `orthodox-site/lib/chat-types.ts`, `orthodox-site/lib/i18n.ts`, `orthodox-site/app/chat/chat-page.tsx`, `orthodox-site/app/globals.css`
  - `ui-audit/tools/save-failure.mjs` (new), `ui-audit/tools/streaming.mjs`

### RET-022: Owner's decisions after RET-020, and how small a regression one tune run can catch (proposal)
- **Date / Part:** 2026-09-23, speed branch
- **Owner's decisions:**
  1. **Change 6: go ahead,** with two conditions: a failed write after the answer is on screen must be retried or must not silently break the next turn, and the answer and sources go out before the conversation IDs. Done in RET-021: it retries, and if the save still fails the reader is told plainly.
  2. **Production hop timing:** first check Railway's region in the dashboard and report it. Then, after the owner's `railway login`, run 3 new chats and 3 follow-ups on the live site (~$0.03). *Status:* the Railway CLI's login has expired, and the dashboard needs the owner's sign-in too, so both steps wait for `railway login`.
  3. **AR-03** (0.94/1.0 before the RET-010/011 saint commits, 0.81/0.56 after, RET-019): investigate separately from this branch, and don't let it block merging. Run AR-03 alone at least 3 times with those commits on and off; no full tune run.
     *Result* (RET-023, branch `ar03-check`): 4 runs each; on 0.89, off 0.84 mean coverage. No regression; the 0.56 was noise.
  4. **Neon:** stay on the free plan, with no keep-warm ping for now. Its ~2 s wake after 5 minutes idle stays; RET-021 has taken it off a new chat's first question.
- **How small a regression one tune run can catch:**
  - Estimated from the two pairs of same-code runs (the two baselines, and the two RET-019 "after" runs), per question, so the comparison is paired. The per-question run-to-run spread is about 0.09 (English) and 0.11 (Arabic) in coverage.
  - Noise band is 95%; "caught" means a drop that size is detected 80% of the time.

| comparison on tune | English (53 answerable) | Arabic (17 answerable) |
|---|---|---|
| 1 run vs 1 baseline run | ±3.4 pts; caught ≈ 4.9 pts | **±7.2 pts; caught ≈ 10.3 pts** |
| 2 vs 2 (averaged) | ±2.4; ≈ 3.5 | ±5.1; ≈ 7.3 |
| 3 vs 3 | ±2.0; ≈ 2.8 | ±4.2; ≈ 5.9 |

  - So a single run can't reliably see a drop of a couple of points in either language, and Arabic's 0.745 → 0.682 between two runs of the same code (RET-019) is inside its noise.
  - The judge runs at temperature 0, so most of the noise is the answer itself (temperature 0.2).
- **Proposal (not implemented; costs from RET-019's measured $0.60 per tune run, about $0.006 per English question and ~$0.008 per Arabic one):**
  1. **Two runs per side, compared question by question** for any change that can alter answers. Stored baselines are reused while their configuration still matches production. **+$0.60 per check.** English: ±2.4 pts. Arabic: still ±5.1.
  2. **Arabic needs more than repetition:** 17 answerable questions is too few. Either:
     - **(a)** run the 19 Arabic tune questions 4 times per side (~$0.15 a run, **+$0.45 per side**): Arabic ±3.6, caught ≈ 5.1; or
     - **(b)** grow the Arabic tune set to ~50 answerable questions (writing and checking them against the PDFs is the cost; +~$0.25 per run afterwards): with 2 vs 2, Arabic ±3.0, caught ≈ 4.2.

     (a) for now; (b) over time.
  3. **Report a paired difference with its noise band** in `eval/speed_compare.py` and `eval/phase5_compare.py`, so a report reads "−1.2 ± 3.4 pts" rather than two means. Free.
  4. **Optional, $0.21 once:** re-judge one stored tune run (`run_eval.py --rejudge`) to confirm the judge's share of the noise is small. If it isn't, averaging two judgings is cheaper than generating twice.
  - A cheaper-looking option was rejected: comparing both sides at generation temperature 0. It would cut the noise, but it measures a setting production doesn't use.
  - **Recommendation:** 1 + 2(a) + 3. A typical check then costs about $1.65 instead of $0.60, and catches about 3.5 pts in English and 5 in Arabic.

### RET-024: Production, hop by hop: ~0.25–0.45 s outside the backend; the slow parts are in the backend; Railway runs across the continent from Vercel and Neon
- **Date / Part:** 2026-09-23, speed branch (owner's request after RET-022: the Railway region first, then 3 new chats and 3 follow-ups on the live site, compared with the local numbers)
- **Where things run:**
  - Railway `web` service: **us-west2 (US West)**, one replica (from `railway status --json`; the edge log says `edgeRegion: us-west2`).
  - Vercel functions: **iad1 (Washington, D.C.)**, from the `x-vercel-id` header `iad1::iad1::…`.
  - Neon: **AWS us-east-1**.
  - So the site and its database sit together in the US East, and every call from the site to the backend crosses the continent. Railway's edge log shows the calls coming from `3.81.189.165`, an AWS us-east-1 address.
- **Method:**
  - `ui-audit/tools/hops.mjs` against https://learnorthodoxy.net: 2 English and 1 Arabic new chats, each with a follow-up.
  - The live site runs the code before RET-018 and RET-021: it creates the conversation first, and it has no route timing or forwarded request ID. The browser's timings were therefore joined to the backend's request lines (`railway logs --json`) by question and order, and to Railway's edge log (`railway logs --http --json`).
  - Plus warm probes on one reused connection, which make no OpenAI call and write nothing: a static file, `/api/conversations` (Vercel + Neon) and `/api/saints` (Vercel + Railway).
- **Results (ms):**

| turn | click → first word | backend first token (analysis / retrieval / model's first token) | outside the backend | of which conversation create |
|---|---|---|---|---|
| English new chat 1 | 4,308 | 3,184 (1,810 / 654 / 720) | **1,124** (cold) | 126 |
| English follow-up 1 | 1,854 | 1,610 (769 / 433 / 409) | 244 | — |
| English new chat 2 | 2,499 | 2,038 (1,007 / 579 / 452) | 461 | 187 |
| English follow-up 2 | 1,832 | 1,582 (975 / 188 / 419) | 250 | — |
| Arabic new chat | 5,844 | 5,411 (1,602 / **2,904** / 904) | 433 | 164 |
| Arabic follow-up | 2,663 | 2,358 (747 / **1,095** / 515) | 305 | — |

  - **Warm probes** (from the owner's machine):
    - static file through Vercel's edge: ~35 ms;
    - Vercel function + Neon read: 66–78 ms;
    - Vercel function + Railway lookup: 126–168 ms, with Railway's edge timing the backend part at 24–31 ms.
    - So one Vercel → Railway round trip is **~90 ms**: ~65 ms across the continent plus ~25 ms at Railway's edge. A Neon call from the same region is ~30–40 ms.
  - **A follow-up's ~250 ms outside the backend, piece by piece:** the page (~30), to Vercel (~35), history read (~35), to Railway and its edge (~65), the first chunk back through Vercel to the browser (~50), and drawing (~5). About 220 ms estimated against 244–305 measured.
  - **A new chat adds creating the conversation:** 126–187 ms as a browser round trip, plus the empty history read.
  - **The first question of the run spent ~950 ms more outside the backend** than the others. That points to a cold start: a new Vercel function instance for the stream route and a first connection to Railway. The site's route timing (RET-018, not yet deployed) will split it.
- **Compared with local (RET-020):**
  - Outside the backend: **~50–60 ms locally, ~250–460 ms in production.** The difference is the real network (browser → Vercel, Vercel → Railway across the continent, Neon) and the conversation-create round trip.
  - Inside the backend, production is slower where our own code runs: **Arabic retrieval took 2.9 s and 1.1 s on Railway**, against ~0.8 s locally, which suggests a slower CPU scanning the Arabic collection. The analysis call ranged 0.75–1.8 s and the model's first token 0.4–0.9 s, as locally.
- **The "~2.5 s gap outside the backend" doesn't exist.** Outside the backend is ~0.25 s on a follow-up and ~0.45 s on a new chat, with a one-off ~1.1 s on a cold start. What makes production feel slow is inside the backend: the analysis call (~1 s), Arabic retrieval (1–3 s) and the model's first token (~0.5 s).
- **What would help, in order:**
  1. **Deploy the speed branch.** RET-013 (the in-memory Arabic index) should save more in production than locally, where it saved ~0.8 s; the Arabic scan takes 1.1–2.9 s on Railway. RET-015 overlaps the embedding with analysis, and RET-021 removes the conversation create and the empty history read (~160–220 ms on every new chat). Then rerun `hops.mjs` against production: with RET-018's route timing live, every hop, including the cold start, becomes visible.
  2. **Move the Railway service to US East** (us-east4, Virginia) to sit with Vercel and Neon: **~60–70 ms saved per question** (one cross-continent round trip, plus half of one on the first byte back). The v2 Chroma store lives on a volume in us-west2, and volumes are tied to their region, so a move means building or copying the store in the new region (DEPLOY_V2.md's background build) and a short cut-over. Worth doing at the next redeploy, not urgently.
  3. **Cold starts** (one of six turns here) can't be measured further until RET-018 is live. Vercel's fluid compute keeps instances warm while there is traffic.
- **Spend:** $0.0292 (6 answers with gpt-4.1-mini plus analysis calls). 3 conversations were saved to the production database under a new anonymous visitor.

### RET-025: Checks of answer changes use two runs per side, Arabic four, and report the change with its noise band; the judge's share of the noise is small
- **Date / Part:** 2026-09-23, speed branch (the owner approved RET-022's items 1, 2 and 3 and the one-off re-judge check. Item 2: Arabic tune questions 4 runs per side for now, and the Arabic set grown gradually, each question checked against the PDFs.)
- **Decision:**
  - **Procedure** for a change that can alter answers, written into `eval/run_eval.py`'s usage notes. Each side gets:
    - 2 coverage runs on tune, restarting the backend between them;
    - 2 Arabic-only runs (`--split tune --language ar --coverage-only`), for 4 Arabic runs per side in all.
    - Stored baselines are reused while their configuration matches production. About $1.50 per side.
  - **`--language en|ar`** (new) limits a live run or a re-judge to one language.
  - **`--rejudge`** now honours `--coverage-only`, `--split` and `--language`. Before, it always ran the legacy and faithfulness judges on every record, several times the cost.
  - **`eval/paired.py`** (new) reports a change question by question: each side's runs averaged, the mean of the per-question differences, and a 95% band.
    - With at least two runs per side, the band is the measured re-run noise: each question's spread across its repeats, pooled (RET-022's method).
    - With single runs it falls back to a t-interval over questions, labelled "conservative". That interval also counts real question-to-question differences in the change: for the RET-019 comparison it gave ±6.0 pts in English, against ±2.4 from the repeats.
  - `eval/speed_compare.py` and `eval/phase5_compare.py` print it, e.g. `-2.1 ± 5.1 pts (95%, re-run noise; 17 questions, 2 vs 2 runs); within noise`.
  - **Growing the Arabic set** is ongoing: small batches, each question checked against the Arabic PDFs (pages, reference answer, key facts) and marked `verified`. No questions added yet.
- **Results with the new report:**
  - The speed changes (RET-019): English **+1.2 ± 2.4 pts**, Arabic **−2.1 ± 5.1 pts**; both within noise.
  - v1 → v2 (ING-006): English −0.4 ± 2.5 on tune; **Arabic +13.3 ± 4.4 on tune (better)**, matching ING-006's +13 points.
- **Judge-noise check** (the approved one-off): the answers of `20260923-181810` were re-scored with the same coverage judge (gpt-4.1, temperature 0), tune only (`20260923-195912`).
  - The judge changed its score on 9 of 52 English answers and 1 of 17 Arabic. Mean shifts were +0.9 and +0.6 pts.
  - Its per-question spread (0.032 English, 0.017 Arabic) is **~13% and ~3% of the run-to-run variance** (0.090 and 0.107 per question). Almost all the noise comes from generating the answer.
  - So averaging two judgings would buy little; repeated runs are the right lever, as proposed.
  - Cost: 69 judge calls, about $0.20. `--rejudge` doesn't keep a spend ledger, so this is estimated from RET-019's judge spend per question.
- **Files changed:** `eval/paired.py`, `tests/test_paired.py` (new); `eval/speed_compare.py`, `eval/phase5_compare.py`, `eval/run_eval.py`; `eval/results/20260923-195912.json`.

### RET-023: AR-03 with the RET-010/011 saint commits on and off: no regression
- **Date / Part:** 2026-09-23, own branch (`ar03-check`), apart from the speed work, as the owner asked (RET-022 on the `speed` branch)
- **Question:** RET-019 (on the `speed` branch) found AR-03 ("من هو الأنبا بولا أول السواح؟", "Who is Anba Paul, the first hermit?") at 0.94 and 1.0 coverage in the 22 September baselines, and 0.81 and 0.56 since RET-010/011 put an Arabic saint's own dictionary entry first in the context. Is that a regression?
- **Method:** AR-03 alone, 4 times each, coverage only (the same gpt-4.1 judge and harness), against a local v2 backend with gpt-4.1-mini:
  - **off:** `c47acff`, the last commit before RET-010;
  - **on:** `33b8ff9`, with RET-010 and RET-011 and nothing later.
  - Each ran from its own worktree against the same v2 store. The "on" retrieval is identical to today's code (the same chunks as RET-019's runs).
- **Result:**

| | run 1 | run 2 | run 3 | run 4 | mean |
|---|---|---|---|---|---|
| saint commits off | 0.81 | 0.88 | 0.88 | 0.81 | **0.84** |
| saint commits on | 1.00 | 0.81 | 1.00 | 0.75 | **0.89** |

  - **No regression:** with the entry first, AR-03 scores at least as well. The fact most often missed with the commits off, his brother Peter's claim to the inheritance, was missed in 4 of 4 runs off and 2 of 4 on.
  - The 0.56 in RET-019 was a low draw. This one question ranges from 0.75 to 1.00 across runs of the same code, as RET-022's noise estimate predicts (per-question spread ~0.11 in Arabic).
- **Spend:** $0.0814 (ledger `eval/results/spend-ar03.json`).
- **Files:** `eval/results/20260923-193224.json` … `-193328.json` (8 runs), `eval/results/spend-ar03.json`.

## Prompting & Generation

### GEN-001: System prompts live in versioned files under prompts/
- **Date / Part:** 2026-09-15, Phase 2 Step 2 (commit 124c744)
- **Audit ref:** C21, C22, A7
- **Context:** Both system prompts were inline f-strings in `api.py`, with a dead Arabic branch inside the English prompt and per-request padding (`MATCHED MANUAL SAINT ALIAS`, an Arabic alias table) that never affected English answers.
- **Options considered:** keep them inline but tidy; a Python constants module; Markdown files selected by a `PROMPT_VERSION` env var.
- **Decision:** `prompts/english_v2.md` and `prompts/arabic_v2.md`, loaded once at import; `PROMPT_VERSION` (default `v2`) picks the file set, so an experiment is a new file plus an env var and a prompt diff shows up as a readable text diff in git. The generation model, temperature and number of history turns are env vars (`OPENAI_CHAT_MODEL`, `OPENAI_CHAT_TEMPERATURE`, `HISTORY_TURNS_FOR_MODEL`).
- **Why:** Prompts are product copy and behaviour specification at once; they change more often than code and deserve their own review history and A/B switch.
- **Files changed:** `prompts/english_v2.md`, `prompts/arabic_v2.md`, `api.py`.
- **Concept to learn:** *Prompt versioning.* Treat a prompt like a schema: version it, keep the old one runnable, and pair every change with an eval run. Search: "prompt versioning", "prompt management".
- **Revisit if:** you want per-mode prompts (saints vs catechism); add `prompts/<mode>_<version>.md` and a lookup.

### GEN-002: A learner-oriented prompt with one refusal rule, numbered passages and inline [n] citations
- **Date / Part:** 2026-09-15, Phase 2 Step 2 (commit 124c744)
- **Audit ref:** C19, C21, C22, A4, A7
- **Context:** The old prompt forbade citations, forced numbered lists ("ALWAYS use numbered format"), repeated the refusal instruction three times, and never asked for depth or synthesis; answers were terse lists. The Arabic prompt had no partial-answer rule at all.
- **Decision:** The v2 prompts describe the reader (a learner of the Coptic Orthodox faith), ask for explanation with brief definitions, synthesis across passages, short quotations where wording matters, paragraphs by default with lists only for list-shaped content, an explicit partial-answer behaviour, and *one* refusal sentence used only when no passage is relevant. Context is passed as numbered passages (`[3] Encyclopedia of the Saints and Fathers of the Church, Volume 1, p. 329`) and the model must cite `[n]` inline. `_cited_sources()` parses the citations and the response's `sources` now lists only the cited passages, in first-citation order, each with `n` and a human `label` (falling back to the first six retrieved sources if the model cited nothing, so the UI is never empty). The Arabic prompt is the same design in Arabic.
- **Why:** Citations make the answer checkable and let the UI link to pages later without changing the backend again; a single refusal rule reduces the model's bias toward refusing when only part of the context is on-topic; the list ban was the visible cause of shallow answers.
- **Files changed:** `prompts/*.md`, `api.py` (`_build_numbered_context`, `_parse_citations`, `_cited_sources`, `Source.n/label`).
- **Concept to learn:** *Grounded generation with attribution.* Numbering the evidence and requiring inline references gives a cheap, automatic way to know which retrieved chunk actually supported each claim; it is the basis for later hallucination checks (a claim with no citation, or a citation that does not support it). Search: "attributed question answering", "citation grounding RAG".
- **Revisit if:** the model over-cites or cites wrong numbers; then validate citations against the passage text, or ask for a structured JSON answer with claims and supporting passage ids.

### GEN-003: Conversation history is sent as real messages
- **Date / Part:** 2026-09-15, Phase 2 Step 2 (commit 124c744)
- **Audit ref:** C20, A5
- **Context:** History was pasted as text into the prompt only when a regex found a bolded name in the previous answer; otherwise the model saw an empty `CONVERSATION SO FAR:`. The frontend compensated by appending the previous answer to the question.
- **Options considered:** keep text-pasting but always include it; send the last N turns as `user`/`assistant` messages; summarise history with a separate model call.
- **Decision:** The last `HISTORY_TURNS_FOR_MODEL` (default 6) sanitised turns are sent as real chat messages before the final user message that holds the numbered passages and the question. The retrieval query still uses the regex rewrite from Phase 1 (an LLM rewrite is a later step). Applies to the Arabic path too, which had no history at all.
- **Why:** Chat models are trained on multi-turn message structure; pronoun resolution and "as I said before" work without any regex. It also removes the frontend's answer-pasting hack as a requirement (that code is still there and harmless; removing it is a frontend task).
- **Result of Step 2 as a whole (eval `20260915-171939.json` vs Step 1 `20260915-171208.json`):** answerable refusals 1.9 % → 0 %; judge all-answerable 4.54 → 4.67 (answered-only 4.61 → 4.67); every one of the 52 answers carries citations (mean 3.3 distinct passages cited); answers are longer (mean 1,743 chars, 381 completion tokens) and latency rose 2.5 s → 3.3 s. Retrieval metrics are unchanged by design. **Regression to note:** FU-01 ("How did he die?" after a St. Moses the Black turn) moved from a refusal to a confident wrong answer about a *different* St. Moses (a martyr under Decius) whose page ranks first for the rewritten query; the keyword filter used to block that page. Score 1 either way, but a wrong answer is worse than a refusal; Step 3's distance ranking and the later LLM query rewrite are the fixes, and a citation-consistency check is a candidate guard.
- **Files changed:** `api.py` (`_build_chat_messages`).
- **Concept to learn:** *Conversation state in stateless APIs.* Each request must carry the history it needs; bounding it (turn count and per-message size, SEC-006) keeps cost predictable. Search: "chat completions message roles", "context window management".
- **Revisit if:** history dominates the prompt (add summarisation), or when the retrieval rewrite moves to an LLM (then the rewritten standalone question can also be shown to the model).

### GEN-004: Prompt v3 — flexible about format and task, strict about content
- **Date / Part:** 2026-09-16, Phase 4 Step 4
- **Audit ref:** EVAL-014 (cause 4), GEN-002, open questions 11 and 14, production examples 1–3
- **Context:** Prompt v2 had one refusal rule ("if none of the passages is relevant, reply with exactly …") and a paragraphs-by-default style rule. After Steps 2–3 gave the model the right material, it still refused four task requests (G-saints table, Catholic/Coptic table, tunes table, calendar table) and wrote tables as numbered lists. It also let general knowledge in: the Easter answer's Julius Caesar date, year length and "Demetrius at Nicaea" (EVAL-014), and the phase-3 filler ("a significant figure"). Any "does not say" anywhere in an answer was logged as a refusal (SNT-01 in RET-007).
- **Options considered:** edit v2 in place (loses the comparison baseline; GEN-001 says never); add rules to v2's end (the refusal rule would still dominate); a new v3 organised around the product rule "flexible about format and task, strict about content".
- **Decision:** `prompts/english_v3.md` and `prompts/arabic_v3.md` (same structure in Arabic), `PROMPT_VERSION` default `v3`; v2 files are unchanged and still selectable.
  - *Content:* every factual statement must be in a passage and cited; no general-knowledge filler even when true (no extra dates, numbers, names, background); copy dates exactly; no generic characterisations; do not merge same-name people; for partial coverage do the covered part and say in one sentence what is not covered.
  - *Comparisons:* only what passages say about each side; every statement about the other church needs a citation to a passage that names it, otherwise the cell says exactly "Not described in the sources"; only differences a passage states; say the sources do not give a full comparison.
  - *Format and task:* never decline because of the format; Markdown tables/lists; citations inside cells; no placeholder cells ("noted in the index"); incomplete lists get one sentence saying so; paragraphs when no format was asked.
  - *Length:* match the request; short factual questions get a few sentences.
  - *Declines:* flexibility is about format, not topic (off-topic requests are declined even if a passage shares a word). If no passage is about the named subject, begin with "I could not find …" naming it, then optionally say what the sources cover nearby, with citations, and suggest a question; if nothing is related, a one-line decline.
  - *Pipeline support:* the analysed format is passed as a NOTE ("Requested format: table."); tables/lists/comparisons/study guides and broad requests get `ANSWER_MAX_TOKENS_TASK` (2,400) because a 40-row list was cut at 1,200 (RET-007); saint lists now show 30 entries (40 took 12.3 s, near the 20 s proxy timeout) and name each entry with its index name plus heading. The distance-threshold refusal text (`_no_source_answer`) now says what the sources cover and suggests topics.
  - *Refusal detection:* `_response_grounding_status` decides a refusal only from the answer's opening ("I could not find …", "The sources/passages do not mention …", the Arabic marker); phrases such as "the sources do not say" elsewhere mark a *partial* answer. A decline returns only the sources it cites for nearby material. The eval harness now trusts the backend's `answered` verdict instead of re-scanning the answer for refusal words.
- **Iterations during the step (probes, not the tune set):** the first v3 draft still produced a Catholic column of invented contrasts ("the Catholic Church has historically had significant political influence"); the comparison rules above were then made explicit, and RET-008 added passages that name the other church. The Arabic off-topic question (OOC-10) was answered from a passage about Poitiers ("the capital of France is Poitiers") under the first draft; the "flexibility is about format, not topic" line was added; gpt-4o-mini then refused it, gpt-4.1-mini still did not (handled in Step 5).
- **Result (tune, coverage-only; step 3 `20260916-211927` → v3 with gpt-4o-mini `20260916-213838` / v3 with gpt-4.1-mini `20260916-213948`):**

| metric | step 3 (v2, 4o-mini) | v3, 4o-mini | v3, 4.1-mini |
|---|---|---|---|
| coverage (all answerable) | 59.1% | 63.5% | **73.0%** |
| off-target | 7.3% | 10.9% | **5.5%** |
| answerable refused | 9.1% | 1.8% (AR-04) | **0.0%** |
| … task-style | 40.0% | 0.0% | 0.0% |
| out-of-corpus refused | 80.8% | **92.3%** | 76.9% |
| … easy / near-miss / task | 100 / 68.8 / 100 | 100 / 87.5 / 100 | 85.7 / 75.0 / 66.7 |
| format followed (task) | 80.0% (n=5) | 100% (n=9) | 100% (n=9) |
| task coverage | 32.8% | 57.8% | 63.0% |
| keyword coverage | 82.1% | 78.6% | 92.9% |
| catechism coverage | 52.1% | 55.1% | 71.1% |
| mean answer length | 1,875 chars | 1,156 | 1,860 |
| prompt / completion tokens | 7,051 / 297 | 7,699 / 205 | 7,775 / 328 |
| mean latency | 3.3 s | 2.9 s | 3.7 s |

  - **Production examples (4.1-mini):** PRD-01 answered as a Markdown table of G saints with real descriptions and an incompleteness sentence (coverage 0.64); PRD-02 coverage 0.42 → 0.83 (Demetrius in the second century, Nicaea approving it, the thirteen-day divergence, all cited); PRD-03 answered as a table (coverage 0.25, below the off-target line: it cites real Catholic-mention passages but not the four differences in the reference). TSK-09 (tunes) 0 → 1.00 and TSK-14 (calendars) 0 → 0.75.
  - **Regressions:** with gpt-4.1-mini, out-of-corpus refusals dropped (OOC-10 Arabic off-topic answered; OOC-21, 22, 24, 38 doctrine questions answered from general knowledge with a Coptic framing, the phase-3 failure mode; OOC-26 correctly says Paul had no wife but does not open with a decline). With gpt-4o-mini, AR-04 (St. Anthony in Arabic) was refused and answers became 38 % shorter; TSK-12 ("three bullet points") coverage 0.83 → 0.33 under 4.1-mini because three bullets hold fewer facts than a paragraph. The doctrine answers are the target of the Step 5 check.
- **Files changed:** `prompts/english_v3.md`, `prompts/arabic_v3.md` (new), `api.py`, `eval/run_eval.py`.
- **Concept to learn:** *Separating style latitude from grounding constraints.* Refusal-heavy prompts conflate "I can't do this format" with "the sources don't say this"; stating the two policies separately, and giving the model an explicit, checkable way to decline ("begin with …"), makes both behaviours measurable. Search: "grounded generation instructions", "refusal calibration RAG".
- **Revisit if:** the faithfulness numbers in Step 6 show the stricter content rules are not followed (then add a post-generation claim check).

### GEN-005: Generation model: gpt-4.1-mini recommended over gpt-4o-mini
- **Date / Part:** 2026-09-16, Phase 4 Step 4
- **Audit ref:** DEP-001, GEN-004
- **Context:** The v3 content and comparison rules are instructions a small model has to follow over a 10k-token context. On the probes gpt-4o-mini wrote "The Catholic Church also practices seven sacraments … Not described in the sources" in one cell, and dropped the passages' facts for Easter; gpt-4.1-mini followed the rules and cited the right pages.
- **Options considered:** keep gpt-4o-mini (cheapest, fastest, stricter declines); gpt-4.1-mini (better instruction following, ~2.7× the token price); a larger model (gpt-4.1 or newer) — not tested, several times the price again.
- **Decision:** run Steps 5–6 with `OPENAI_CHAT_MODEL=gpt-4.1-mini` and recommend it for Railway; the code default stays `gpt-4o-mini` so the switch is an env var and reversible. The request-analysis model stays gpt-4o-mini (RET-006).
- **Why:** on tune it answers more of what is asked (coverage +9.5 points, catechism +16, task +5), is off-target half as often and refuses no answerable question; its weakness (answering near-miss doctrine questions) is exactly what the Step 5 entity check targets, while gpt-4o-mini's weaknesses (short answers, a wrongful Arabic refusal, poorer comparisons) have no such guard. Cost at list prices (gpt-4o-mini $0.15 / $0.60 per million input/output tokens, gpt-4.1-mini $0.40 / $1.60; check current OpenAI pricing): ~7,800 prompt + ~330 completion tokens per answer ≈ $0.0017 vs $0.0036 per request, plus ≈ $0.0001 for the analysis call. Latency +0.8 s mean.
- **Files changed:** none (env var); evaluated in `eval/results/20260916-213838.json` and `20260916-213948.json`.
- **Concept to learn:** *Model selection by eval, not by vibes.* Swap one component, rerun the same set, and compare the metrics you care about, including the failure modes the cheaper model avoids. Search: "LLM model selection evaluation cost quality tradeoff".
- **Revisit if:** Step 6 faithfulness is worse for 4.1-mini, the monthly bill matters more than coverage, or a newer small model is available (rerun the tune set).

### GEN-006: Named-subject check before generation, plus a scope gate for Arabic
- **Date / Part:** 2026-09-16, Phase 4 Step 5
- **Audit ref:** RET-004, open question 12, GEN-004/GEN-005 regressions
- **Context:** Distance measures topical closeness, not whether the specific saint or doctrine is in the books (RET-004). With gpt-4.1-mini and prompt v3, four doctrine questions (papal infallibility, sola scriptura, filioque, Immaculate Conception) were answered from general knowledge with a Coptic framing, and the Arabic "capital of France" question (no Arabic threshold, RET-003) was answered from a passage about Poitiers.
- **Options considered:**
  1. *Ask the model to decide* (prompt only) — it already had that rule and still answered.
  2. *A second LLM call judging "is X in these passages"* — robust, but another ~1 s and a second opinion from a similar model.
  3. *Deterministic presence check* of the subjects the analysis call already extracts (`named_subjects`, RET-006), plus a decline instruction and a hard fallback.
  4. *Block on any unmatched word of the question* — would block formats and broad categories, which the brief forbids.
- **Decision:** Option 3, in `entity_check.py`.
  - *Subjects:* the analysis prompt now always fills `named_subjects` with named saints, people, doctrines, councils, feasts, rites or terms (with worked examples: "the Catholic doctrine of papal infallibility" → ["papal infallibility"]), and never with presentation words, broad categories ("saints", "differences", "fasts") or the churches being compared. On the tune set it extracted a subject for every near-miss negative and for no format/category request (checked on all 81 tune questions before wiring it in).
  - *Matching:* titles and filler words dropped (St., Saint, Abba, Anba, Pope, the, of …, Arabic القديس/الانبا/البابا …); roman numerals and words under three letters dropped; each remaining word stemmed (≥ 7 letters: last three dropped; 5–6: last one; Arabic: leading ال dropped); text compared with all spaces and punctuation removed (pypdf's "sufferin g" still matches) after NFKC and Arabic letter folding. A subject is present when one passage contains all its core words (all but one when it has three or more).
  - *Action:* no subjects → nothing. All subjects absent → a NOTE tells the model the subject is not in any passage and to begin with "I could not find anything about X in the loaded sources." (it may add what the sources cover nearby, with citations); if the reply nonetheless does not open with a decline, it is replaced by that sentence (`decline_enforced`). Some absent → a NOTE to say those are not covered. Saint lists (RET-007) are exempt; they are selected by name already. Logged as `entity_check` {present, absent, action}. `ENTITY_CHECK_ENABLED` (default on).
  - *Scope gate (Arabic only):* the analysis also returns `in_scope` (false only for requests clearly outside Christian faith and life, including topics the catechism itself treats); in the Arabic path an out-of-scope request is declined before generation (`refusal_reason=out_of_scope`). It is not used for English: it flagged TSK-14 ("the ancient Egyptian calendar and the Julian calendar") as out of scope even after the prompt listed calendars, and English off-topic requests are already stopped by distance (≥ 1.45 on tune, RET-009).
  - *Refusal detection:* "The sources do not cover …" at the start of a reply now also counts as a decline (OOC-25 declined with that wording).
- **Result (tune, coverage-only, gpt-4.1-mini; step 4 `20260916-213948` → step 5 `20260916-220035`, threshold 1.25):**

| metric | step 4 (4.1-mini) | step 5 |
|---|---|---|
| coverage (all answerable) | 73.0% | 71.3% |
| off-target | 5.5% | 7.3% |
| answerable refused | 0.0% | **0.0%** |
| out-of-corpus refused | 76.9% | **96.2%** |
| … easy / near-miss / task | 85.7 / 75.0 / 66.7 | **100 / 93.8 / 100** |
| format followed | 100% | 100% |
| mean latency | 3.7 s | 3.8 s |

  - Newly refused: OOC-10 (scope gate), OOC-21, 22, 24, 38 (entity check: papal infallibility, sola scriptura, filioque, Immaculate Conception absent from the passages; the model complied with the note in every case, so the hard fallback never fired). The only negative still answered is OOC-26 ("St. Paul the First Hermit did not have a wife … There is no mention of a wife"), which is a correct premise rejection that does not open with a decline.
  - **Answerable questions blocked by the entity check: none** (0 of 55 on tune). Actions on tune: 13 declines, all on negatives; 4 "note missing" (OOC-13, OOC-25, OOC-29 and one answerable, AR-08, where "بركات المعمودية" — "the blessings of baptism" — was treated as a named subject; the answer was still given).
  - Coverage moved within the generation noise measured in RET-007 (KW-01 0.83 → 0.50 and KW-08 1.00 → 0.67 with identical retrieval; SNT-11 0.57 → 0.93).
- **Files changed:** `entity_check.py` (new), `task_analysis.py`, `api.py`.
- **Concept to learn:** *Entity grounding / attribution gating.* Before generating, confirm that the thing the user named is in the evidence; if it is not, the honest answer is a decline, and a cheap lexical check is enough because the analysis step already isolated the names. Search: "entity linking RAG hallucination", "answerability detection".
- **Revisit if:** the saint index gains aliases (then match subjects against aliases too), a false block appears in production logs (`entity_check.action=decline` on an answerable question), or phrase-level subjects like AR-08's cause visible hedging.

### GEN-007: Streaming answers — plan: SSE from FastAPI through the Next.js route, /chat unchanged
- **Date / Part:** 2026-09-23, streaming branch Step 1 (plan)
- **Audit ref:** A6, C25 (priority 7)
- **Context:** An answer takes 3–8 s and nothing appears until the whole reply is written. Most of that is generation, so the reader waits for text that already exists at OpenAI.
- **Options considered:**
  1. *Server-Sent Events* (`text/event-stream`, read with `fetch()` and a stream reader in the browser). One HTTP response, plain text, passes through Railway, Vercel and the Next.js route as ordinary bytes.
  2. *A raw streamed body* (bare tokens, then a sentinel and JSON). Simpler to write, but the final sources and an error need an ad-hoc framing anyway.
  3. *WebSockets.* Two-way, which we don't need, and not supported by Vercel functions.
- **Decision:** option 1, with named events. `EventSource` is not used (it only does GET and can't send the body); the browser reads the POST response with `fetch()`.
  - **Path:** OpenAI (`stream=True`, with usage in the last chunk) → FastAPI `POST /chat/stream` → Next.js `POST /api/chat/stream` → browser.
  - **Events:** `delta` `{"t": "..."}` for each piece of text; `done` with everything `/chat` returns (answer, sources, entities, options, `can_learn_more`, namesakes); `error` `{"message", "retryable"}`.
  - **Before generation nothing changes.** `/chat/stream` runs the same code as `/chat` (analysis, retrieval, entity check, threshold, saint menus), moved into one shared function that stops where the model would be called. A refusal, a menu or an HTTP error (400, 429, 503) comes back at once as ordinary JSON with its normal status code, exactly as `/chat` would send it. Only a real answer is streamed. `/chat` itself keeps its code path and response, so the eval harness and smoke tests are unaffected.
  - **The `done` event is authoritative.** Post-processing (grounding, cited sources, follow-ups, the entity-check decline) runs on the full text, as now. If the entity check expects a decline (GEN-006), the first ~48 characters are held back until the opening can be checked. If it opens with a decline, streaming continues; if not, generation is stopped and the enforced decline is sent in `done`, so a from-memory answer is never shown.
  - **Auth and rate limiting:** the new path sits behind the same `X-Internal-Key` middleware (every path except `/health`) and calls the same `_enforce_chat_rate_limit` with the forwarded `X-Client-IP`. The key stays in the Vercel function; the browser only talks to `/api/chat/stream`.
  - **Next.js route:** the same checks, history lookup and error mapping as `/api/chat` (the shared parts move into one module). A JSON reply is saved and returned exactly as `/api/chat` does. A stream is passed on event by event with no buffering (`Cache-Control: no-cache, no-transform`, `X-Accel-Buffering: no`). When the backend's `done` arrives, the route saves the turn to Postgres as today and sends its own `done` with the saved `conversation`, `userMessage` and `assistantMessage`, so saved chats hold the final answer and sources as now. Timeouts: 20 s for the backend to start replying (as today), then 30 s of silence at most between events; `maxDuration` 60 s.
  - **Disconnects:** the browser's Stop (or closing the tab) aborts its fetch. The Next.js route then aborts its backend fetch. On the backend, the next write fails; the generator closes the OpenAI stream, which stops generation, and the request log line records `outcome="client_disconnected"`. A stopped answer is not saved: it stays on screen marked as stopped, but it isn't part of the stored conversation or of the history sent with later questions.
  - **Errors mid-stream:** an OpenAI failure after the stream started becomes an `error` event with the usual generic text. The frontend drops the partial answer and shows the existing alert with Retry. If the Next.js route loses the backend (a network error or the 30 s silence), it sends the same `error` event.
  - **Fallback:** if `/api/chat/stream` can't be reached, or answers 404/405/502/504 (for example, the backend isn't deployed yet), the page sends the same request to `/api/chat` and shows the whole answer when it arrives. It doesn't fall back on 400, 429, 500 or 503: those are real answers from the backend, and repeating the request would count twice against the rate limit.
  - **Logging:** one request line per stream, as now (`endpoint="chat_stream"`), plus `stream=true`, `ttft_ms` (request start to the first token sent), `generation_ms`, the token usage from the final chunk and `disconnected`.
- **Risks checked before building:** Starlette 1.0's `StreamingResponse` notices a disconnect only when the next write fails. That is fine here, because text is written many times a second. Railway and Vercel both pass streamed responses through; the headers above stop proxies from buffering or compressing them. Both are checked end to end in Step 4 (local only; production is checked after deploy).
- **Concept to learn:** *Server-Sent Events over fetch.* One long HTTP response carries small framed messages (`event:` / `data:` lines, a blank line between messages). It works through ordinary proxies, and the final message can carry structured data. Search: "server-sent events fetch ReadableStream", "OpenAI stream_options include_usage".

### GEN-008: /chat/stream — one shared preparation, the answer streamed, the log line written when the stream ends
- **Date / Part:** 2026-09-23, streaming branch Step 2 (backend)
- **Audit ref:** A6; builds on GEN-007
- **Context:** GEN-007's plan needs the streaming endpoint to make exactly the decisions `/chat` makes. It must not become a second copy of 500 lines that drifts from the first.
- **Decision:**
  - **One preparation, two ways to generate.** `_chat_impl`'s body became `_chat_prepare`. It returns either a finished payload (refusal, saint menu, retrieve-only) or a `PendingAnswer`: the messages, `max_tokens`, whether the entity check expects a decline, and `finish(reply)`, the post-processing that used to follow the model call, unchanged. `/chat` (`_chat_impl`) makes the same single OpenAI call as before and passes the text to `finish`. The error mapping moved into `_chat_errors`, and `/chat`'s responses are unchanged.
  - **`POST /chat/stream`** runs `_chat_prepare` in the thread pool, since it is blocking code (Chroma, the analysis call). The request trace stays current there, which the entity check relies on (tested). A finished payload comes back at once as JSON, serialised through `ChatResponse` like `/chat`. HTTP errors keep their status (400, 429, 503). Otherwise it returns `text/event-stream` with `delta`, then `done` (the `/chat` payload) or `error`.
  - **Generation** uses an `AsyncOpenAI` client with the same timeout and retry settings as the sync one, `stream=True` and `stream_options.include_usage`, so the token counts still reach the log.
  - **Held opening for expected declines (GEN-006).** When the entity check has told the model to decline, nothing is sent until 48 characters exist. A reply that opens with a decline is then released and streams on. Any other reply is cut off there; `finish` replaces it with the enforced decline, which arrives in `done` (`finish_reason="decline_enforced"`). Nothing written from memory reaches the screen.
  - **Disconnects:** Starlette closes or cancels the generator when a write fails. The generator then closes the OpenAI stream (shielded from the cancellation, so the close itself isn't cancelled), which ends generation, and it logs `outcome="client_disconnected"`, `disconnected=true` and `streamed_chars`.
  - **Errors after the first byte** can't change the HTTP status, so they become an `error` event with the usual generic text (`GENERIC_BUSY_ERROR` for OpenAI outages, `GENERIC_SERVER_ERROR` otherwise) and `retryable: true`. The log line records `outcome="error"`, the error type and the status `/chat` would have used.
  - **One log line per request, as before.** `RequestTrace.hand_off()` keeps the `with` block from writing it when the response is a stream, and the stream writes it when it ends, however it ends. New fields: `endpoint="chat_stream"`, `stream`, `ttft_ms` (request start to the first text sent), `streamed_chars`, plus the usual `stages_ms.generation`, token counts and `finish_reason`.
- **Checks:**
  - `tests/test_chat_stream.py` (10 tests, no OpenAI):
    - an answer arrives as deltas, then `done`, which equals `/chat`'s serialisation;
    - a menu comes back as JSON;
    - a 400 keeps its status;
    - the internal key and the rate limit apply;
    - an expected decline streams after the hold;
    - a non-declining reply is cut off and never sent;
    - an OpenAI failure mid-stream becomes an `error` event;
    - a client leaving closes the OpenAI stream and logs `client_disconnected`;
    - `/chat` makes the same non-streamed call;
    - the trace stays current in the thread pool.
  - Existing suite: 184 → 194 passing.
  - **Real server:** uvicorn with the auth middleware and a slow fake model. The client read two events and closed the connection. The fake had given 2 of its 42 chunks, its stream was closed, and one log line said `client_disconnected`.
- **Files changed:** `api.py`, `request_log.py`, `tests/test_chat_stream.py` (new), `README.md`.
- **Concept to learn:** *Async generators and cancellation.* A streamed response is a generator the server pulls from. If the client leaves, the server stops pulling and closes the generator, so cleanup belongs in `finally`, and work that must finish during a cancellation needs a shield. Search: "python async generator aclose finally", "anyio CancelScope shield".

## Frontend

_(See also SEC-003, SEC-005, SEC-006 for the Next.js route changes.)_

### FE-001: Follow-up chips are ordinary user turns in the conversation's own mode
- **Date / Part:** 2026-09-15, Phase 3 Step 4 (commit 24c5ee7)
- **Audit ref:** C14, C31, open question 10
- **Context:** Clicking a follow-up chip used to (1) append up to 1,200 characters of the previous answer to the question before sending it, (2) hide the user turn so it was never stored, and (3) force `mode: "catechism"` whatever the conversation was doing. (1) polluted the retrieval query and the keyword filter (the audit's C14); (2) meant the server-side history never contained the follow-up itself; (3) sent saints-tab follow-ups down the catechism path. Since GEN-003 the backend receives the last six stored turns as real messages, so none of this is needed.
- **Options considered:** keep pasting but shorter; send the chip as a hidden turn but include the previous answer id; or make the chip a normal message.
- **Decision:** A chip click now calls `handleSendMessage(option, { mode: conversationMode })`: the chip text ("I would like to know what chrismation means") is stored as a real user turn, nothing from the previous answer is pasted, and the request uses `conversationMode`, a new piece of state set to the mode of the most recent request in that conversation (catechism cards set it to `catechism`, saint lookups to `saints`, typed questions to the tab's mode). `followUpBackendQuestion` and `compactFollowUpContext` are deleted. The `hideUserMessage` plumbing stays in the API but is no longer used by chips.
- **Eval:** `FU-06` in `eval/questions.jsonl` has exactly the request shape the frontend now sends for a catechism chip: the previous user/assistant turns (assistant text with `[n]` markers) as `history`, the chip text as `question`, `mode: catechism`, expected pages catechism1 p.553–554, three key facts. There is no JS test runner in the project, so the production request shape is asserted through the eval rather than a unit test.
- **Result (`20260915-192113.json`):** FU-06 is answered from the right pages (recall@8 100 %, faithfulness 100 % supported, legacy 5/5) with coverage 50 %: it explains chrismation as receiving the Holy Spirit but omits the growth/maturity role and the "broad sense of baptism" point, so the server-side history resolves the follow-up correctly and the remaining loss is generation depth, not context. Overall numbers moved within noise (coverage 66.3 %, faithfulness 87.5 % supported).
- **Files changed:** `orthodox-site/app/chat/page.tsx`, `eval/questions.jsonl`.
- **Concept to learn:** *Single source of truth for conversation state.* Once the server stores the turns and replays them to the model, the client must not smuggle context through the question text; two channels for the same information drift apart and the model gets duplicated or stale context. Search: "stateless client stateful server chat history".
- **Revisit if:** the UI adds threads that mix modes in one conversation; then the mode should be stored per message and chosen per request explicitly.

### FE-002: Answers are rendered as Markdown (GFM tables), wide tables scroll inside the bubble
- **Date / Part:** 2026-09-16, Phase 4 Step 4
- **Audit ref:** production example 1 (raw pipes and dashes in the chat)
- **Context:** `InteractiveAnswer` split the answer on newlines and only recognised `**bold**`, so a Markdown table showed as raw `| … |` lines, lists showed their `1.`/`-` characters verbatim, and bold text that was not a clickable saint name was rendered as a plain `<span>` (not bold at all). The bubble also used `white-space: pre-wrap`, which would double every blank line once real paragraphs are rendered.
- **Options considered:** extend the hand-written parser to tables and lists (fragile, a Markdown parser in miniature); `marked` + `dangerouslySetInnerHTML` (HTML injection risk from model output); `react-markdown` + `remark-gfm` (renders to React elements, no raw HTML by default, GFM tables/strikethrough/autolinks).
- **Decision:** `react-markdown@10` with `remark-gfm@4`. Custom renderers keep the existing behaviour and add containment: `strong` still turns backend-extracted saint names into the "search saint" button (other bold text is now real `<strong>`); `table` is wrapped in `.answer-table-wrap` (`overflow-x: auto`, focusable region) so wide tables scroll horizontally inside the bubble; links open in a new tab with `rel="noopener noreferrer"`. CSS: the answer container uses `white-space: normal` with paragraph/list/heading spacing; table cells have borders, a shaded header, `max-width: 28rem` (14rem under 640 px) and wrap long words; `.message-stack` and `.message-bubble` get `min-width: 0` so a wide table cannot widen the message column. The unused `.answer-line`/`.answer-spacer` rules were removed.
- **Verification:** `tsc --noEmit`, `eslint` and `next build` pass. A temporary preview route (not committed) rendered real v3 answers (the 30-row G-saints table, the fasts table, a numbered Easter answer, and a bold/list/raw-HTML sample) inside the chat bubble markup, screenshotted with headless Chrome at 1280 px and, via a 390 px iframe (headless Chrome will not size a window below ~485 px), at a true 375 px viewport. Results: tables render with header and borders and scroll inside the bubble with a visible scrollbar; the page's scroll width equals the viewport at both widths (only the table's own wrapper overflows); numbered and bulleted lists, bold, italics and the clickable saint-name button render correctly; `<script>` in the answer is shown as text. The real chat page was not opened because `.env.local` points at a remote Neon database, and a test conversation would have been written there.
- **Files changed:** `orthodox-site/components/InteractiveAnswer.tsx`, `orthodox-site/app/globals.css`, `orthodox-site/package.json`, `orthodox-site/package-lock.json`.
- **Concept to learn:** *Rendering untrusted Markdown safely.* Parse Markdown to a React tree (no `innerHTML`), keep raw HTML disabled, and contain overflowing blocks in their own scroll box so one wide element cannot break a responsive layout (flex children need `min-width: 0` for that). Search: "react-markdown remark-gfm", "flexbox min-width 0 overflow".
- **Revisit if:** answers start using headings or code blocks heavily (style them), or right-to-left tables look wrong in Arabic (not screenshotted in this step).

## UI/UX

_(Audit write-up: [UI_AUDIT.md](UI_AUDIT.md); screenshots in `ui-audit/before/`.)_

### UI-001: UI refresh on its own branch, frontend only, shipped with Phase 4
- **Date / Part:** 2026-09-16, UI refresh Step 0 (base commit 36e6c5b)
- **Audit ref:** none (new workstream)
- **Context:** Phase 4 (retrieval and prompt changes) is finished but not deployed. People reviewing the project will look at the site, and the frontend has not had a design pass. Backend and RAG work is paused.
- **Options considered:** branch off `main` (the UI would then need rebasing onto Phase 4, and FE-002's Markdown rendering exists only on the Phase 4 branch); keep working on `audit-phase-4` (mixes two reviews); a new branch off `audit-phase-4`.
- **Decision:** `ui-refresh` is branched from `audit-phase-4` and the two ship together. Before branching, the pending README/.env.example documentation for the Phase 4 settings was committed on `audit-phase-4` (36e6c5b), and the two partial eval result files from an interrupted run (`20260916-224032.json`, `20260916-224325.json`) were deleted so the branch starts clean. Only `orthodox-site/` changes on this branch; no Python file is touched.
- **Concept to learn:** *Stacked branches.* A branch built on an unmerged branch keeps review units small, but has to be rebased if the base changes. Search: "stacked pull requests".
- **Revisit if:** Phase 4 needs changes after review (rebase `ui-refresh` onto the new tip), or the UI must ship first (cherry-pick onto `main`, which needs FE-002 as well).

### UI-002: Audit screenshots use browser-level API mocks filled with real eval answers
- **Date / Part:** 2026-09-16, UI refresh Step 1
- **Audit ref:** none
- **Context:** Screenshots of realistic chat states (long answer, table, refusal, Arabic) normally need the backend, which costs OpenAI calls. They also need Postgres, and `orthodox-site/.env.local` points at the remote Neon database (see FE-002), so test conversations would be written to real storage.
- **Options considered:** run the backend and ask a handful of real questions (costs money, writes to Neon, answers change between runs); a temporary preview route with hard-coded markup (the FE-002 approach; doesn't exercise the real page); intercept `/api/*` in the browser.
- **Decision:** A production build is started with `POSTGRES_URL`, `DATABASE_URL` and `ORTHODOX_API_URL` overridden to dead local addresses. Playwright intercepts every `/api/*` request and answers from `ui-audit/tools/fixtures.json`. The fixtures are real answers, sources and options copied from the Phase 4 eval runs (`CAT-06`, `PRD-03`, `TSK-09`, `KW-03`, `SNT-08`, `AR-08`, `AR-02`, `OOC-03`, and `OOC-10` from the latest run, after GEN-006). The saint lists are the real English (1,363) and Arabic (1,936) indexes, read from the local Chroma store with `collection.get` (no embeddings). The loading, error and saint-detail-loading states are produced by delaying or failing the mocked responses. Only the Arabic table is synthetic (no real Arabic table answer exists). The saint-detail fixture returns the same answer for any saint. **OpenAI calls: 0.** The tooling (Playwright 1.55, axe, Lighthouse) was installed in a scratch directory, not in `orthodox-site/package.json`. The scripts are kept in `ui-audit/tools/` so the "after" pass can be captured the same way.
- **Findings about the method:** A 390 px viewport works with Playwright's device emulation (FE-002 had needed an iframe). Chromium's page screenshot of a very wide RTL document comes out blank, which is how the Arabic contact overflow was found (UI_AUDIT §4). Element positions were checked separately to separate the real bug from the capture artifact.
- **Files changed:** `ui-audit/before/*`, `ui-audit/tools/*`, `UI_AUDIT.md`.
- **Concept to learn:** *Network-level mocking for UI tests.* Intercepting requests at the browser boundary tests the real page, routing and rendering while making the data deterministic and free. Search: "playwright page.route mock API".
- **Revisit if:** the API response shapes change (update the fixtures), or the screenshots should become a visual regression test (commit the tooling with a `package.json` and compare images automatically).

### UI-003: Accessibility and performance measured with axe and Lighthouse on a production build
- **Date / Part:** 2026-09-16, UI refresh Step 1
- **Audit ref:** none
- **Context:** Scores measured on `next dev` are misleading: the dev bundle is unminified and has overlays.
- **Decision:** axe (`wcag2a`, `wcag2aa`, `wcag21aa`, `best-practice`) ran on 34 page states across both languages and viewports. Lighthouse 12 ran on `/`, `/chat`, `/credits` and `/contact` with the mobile and desktop presets. Contrast of `opacity`-dimmed text was computed by hand, because neither tool reports it reliably. Baseline: Lighthouse accessibility 100 and SEO 100 everywhere. Performance 81–90 mobile and 98–99 desktop. Best Practices 96, which is an artifact: console errors from the dead local API. axe found 4 rules: `nested-interactive` (serious), `page-has-heading-one`, `landmark-one-main`, `region`.
- **Why the scores are not the headline:** a perfect Lighthouse accessibility score coexists with the problems these tools can't see: 3.07:1 subtitle text, removed focus outlines on every text input, no live region for new answers, and 21 px tall language buttons. UI_AUDIT §6 lists those manually.
- **Concept to learn:** *Automated accessibility testing catches only part of the issues.* Contrast through opacity, focus visibility and screen-reader announcements need manual checks. Search: "automated accessibility testing coverage", "WCAG 2.4.7 focus visible".
- **Revisit if:** the design lands; then rerun the same pages and compare `_lighthouse.json` before and after.

### UI-004: Fixes ranked by first-time-visitor impact; showing sources is priority one
- **Date / Part:** 2026-09-16, UI refresh Step 1
- **Audit ref:** UI_AUDIT "Prioritized fixes"
- **Context:** The audit found about 40 issues. They range from a broken Arabic page to dead CSS.
- **Options considered:** rank by severity (bugs first); rank by effort (quick wins first); rank by how much a first-time visitor's impression improves, with effort as the tiebreaker.
- **Decision:** Rank by first-time-visitor impact. The top five: (1) render the `sources` the backend already returns, with linked `[n]` markers; (2) a landing page that says what the site is, that answers come from Fr. Tadros Malaty's books, and shows example questions; (3) fix the broken states (Arabic contact overflow, error shown twice with raw developer text, stripped question marks, fixed-height composer, default 404); (4) typography and tokens (`next/font`, Arabic face, contrast, focus); (5) share/SEO polish (the missing `og-image.png`, per-page titles and canonicals, one site URL, the 17 `console.log`/`console.debug` calls). The Arabic contact overflow is a one-line fix, so it goes in the first pass regardless of rank.
- **Why sources first:** the site's promise is answers from trusted books. Right now every answer shows `[1][2]` markers that lead nowhere, which makes that promise look broken. The data is already in each stored message (`ChatMessage.sources`), so this is frontend-only work.
- **Concept to learn:** *Impact/effort prioritisation.* Score each change by the user outcome it moves, not by how bad the code looks. Search: "impact effort matrix", "RICE prioritization".
- **Revisit if:** analytics show most visitors are returning users (then chat ergonomics outrank the landing page).

### UI-005: Three design directions proposed; the choice is pending
- **Date / Part:** 2026-09-16, UI refresh Step 1
- **Audit ref:** UI_AUDIT "Design directions"
- **Context:** The current look (parchment, umber, Merriweather, the Coptic cross) has an identity worth keeping. Its problems are inconsistency, missing Arabic typography, and a chat-bubble layout that doesn't suit long doctrinal answers.
- **Options considered:** A, illuminated manuscript (parchment, Coptic red, gold; Cormorant/EB Garamond, Amiri); B, clean modern reader (warm paper, umber, red citation accents; Source Serif 4 + Inter, Noto Naskh Arabic + IBM Plex Sans Arabic; answers as full-width articles with a sources list); C, calm minimal (near-white, one umber accent; Newsreader + Inter, Noto Naskh/Kufi Arabic).
- **Decision:** B is recommended, optionally with A's red and gold accents and one ornamental divider. **Pending the owner's choice**; no site code changes until then.
- **Concept to learn:** *Design tokens.* Naming colors, type sizes and spacing once (`--color-ink`, `--text-lg`) makes a direction swappable and gives dark mode almost for free. Search: "design tokens CSS custom properties".
- **Revisit if:** the owner picks A or C, or a church or diocesan style guide exists that the site should follow.
- **Outcome (2026-09-16):** the owner chose B with A's Coptic red and gold used sparingly (cross, headings, citation markers, focus rings), built as tokens so dark mode can come later; dark mode itself is out of scope. Domain: learnorthodoxy.net. PDFs: not linked or served for now (UI-006).

### UI-006: Citations link to a per-answer Sources list; books shown as text, not PDF links
- **Date / Part:** 2026-09-16, UI refresh fix 1
- **Audit ref:** UI_AUDIT §3 "Citations and sources", prioritized fix 1
- **Context:** Every answer carries `[n]` markers, and the backend already returns `sources` with `n` (the passage number), `pdf`, `page` and a `label`. The frontend stored them and never showed them.
- **Options considered:** show the backend `label` verbatim; map file names on the client; regex-replace markers in the answer string before Markdown parsing (breaks inside tables, links and code); a remark plugin that works on the Markdown tree.
- **Decision:** `lib/sources.ts` maps file names to a title and volume (`catechism1.pdf` becomes "Catechism of the Coptic Orthodox Church", Vol. 1; `saints3.pdf` becomes "Encyclopedia of the Saints and Fathers of the Church", Vol. 3; the two Arabic books by their Arabic titles) and shows the page as text. Unknown files fall back to the backend label. `lib/remark-citations.ts` turns markers into `<sup class="cite-group">` nodes, merging adjacent markers (`[2][5]` becomes one group) and skipping links and code. Each number that has a Sources entry renders as a real link (`href="#src-…"`). Clicking, tapping, or pressing Enter scrolls to the entry, highlights it for about 2 seconds, and moves focus to it, so screen readers read the source. The accessible name and tooltip give the full source ("Source 17: Encyclopedia…, Vol. 2 · p. 406"). Lists longer than six collapse to five with a "Show all" button, and a marker pointing at a hidden entry expands the list first. In Arabic, the group follows the page direction and uses "،" as the separator; `unicode-bidi: isolate` stops markers from scrambling surrounding parentheses. The same component is used in the saint detail panel.
- **PDFs:** the owner decided not to link or serve the full books until permission is confirmed. The list is text only and `public/pdfs/` is untouched (open question 20). Website sources (Mind of Christ Light articles) keep their link, since those pages are public.
- **Known limits:** (1) The backend lists each page once (`_cited_sources` dedupes by page), so a second marker for the same page has no entry of its own; it renders as a muted, non-link number. (2) The backend doesn't send a saint entry name for a source. `SourceRef.entry` is shown when present, so it will appear as soon as the backend adds it (open question 22). (3) Messages saved before numbered citations have no `n` and are numbered in list order.
- **Verification:** a Playwright check on the production build with real eval answers: CAT-06 (13 markers, all linked, 5 sources); PRD-03 table (keyboard focus plus Enter highlights and focuses source 17); AR-08 on a 390 px phone (tap highlights source 1, and the group reads right-to-left); a 9-source answer collapses to 5 and expands when marker 24 is tapped. `tsc` and `eslint` are clean.
- **Files changed:** `orthodox-site/lib/sources.ts` (new), `orthodox-site/lib/remark-citations.ts` (new), `orthodox-site/components/AnswerWithSources.tsx` (new), `orthodox-site/components/InteractiveAnswer.tsx`, `orthodox-site/lib/chat-types.ts`, `orthodox-site/lib/i18n.ts`, `orthodox-site/app/chat/page.tsx`, `orthodox-site/app/globals.css`, `ui-audit/tools/fixtures.json` (sources now keep `n` and `label`).
- **Concept to learn:** *AST transforms for rendered Markdown.* Changing the syntax tree (mdast) instead of the raw string keeps the change out of code spans and link text and survives tables. `data.hName` tells the HTML step which element to emit. Search: "remark plugin mdast hName".
- **Revisit if:** the backend starts returning one entry per cited passage, or an entry name; or permission to publish the PDFs is granted (then add `#page=` links).

### UI-007: Design foundation — self-hosted fonts, color and type tokens, logical CSS, real icons
- **Date / Part:** 2026-09-16, UI refresh fix 2
- **Audit ref:** UI_AUDIT §2, §6 (contrast, focus), prioritized fix 4
- **Context:** Merriweather loaded through a render-blocking CSS `@import`. There was no Arabic font. `globals.css` had 71 hard-coded `rgba()` values, subtitles were dimmed with `opacity` (3.07:1), and text inputs removed their focus outline. "x" and "→" were used as icons, and the layout was forced left-to-right even in Arabic.
- **Options considered:** patch the existing 2,100-line stylesheet; move to Tailwind utilities (Tailwind 4 is installed but unused, and moving means rewriting every component); rewrite `globals.css` around CSS custom properties while keeping the existing class names.
- **Decision:**
  - **Fonts.** `app/fonts.ts` loads three families through `next/font/google`, self-hosted at build time with size-adjusted fallbacks: Source Serif 4 (reading and headings), Inter (interface), and Noto Naskh Arabic (Arabic, not preloaded, so English pages never download it). Inter wasn't in the owner's list but is part of direction B; it keeps small UI text (labels, buttons, tables) crisp.
  - **Font stacks.** `--font-reading` and `--font-ui` put Naskh second, so Arabic glyphs always get Naskh. Under `:lang(ar)` Naskh comes first, and sizes and line height step up (reading 19px / 1.9).
  - **Tokens.** One `:root` block defines surfaces, ink, brand, lines, focus and status colors, a type scale, spacing, radii, shadows and layout sizes. A future dark theme only has to redefine the `--color-*` tokens.
  - **Accents.** Coptic red (`#9a2f24`) is used only for citation markers, the active-nav underline, focus rings and the active drawer item. Gold (`#b08a3e`) is used only for the cross, the rule under page titles, list bullets and the source highlight.
  - **Contrast.** Every text token passes AA on the backgrounds it's used on (ink 16.3:1, soft 7.1:1, faint/placeholder 5.5:1, red 7.0:1). Gold is never used for text.
  - **Focus.** A global `:focus-visible` outline in red, including text inputs. The composer draws its ring on the whole field (`:focus-within`).
  - **Layout.** The header is the same full-width bar on every page, and the chat sidebar now sits under it instead of beside it, so the brand no longer moves between pages. All spacing uses logical properties (`inset-inline-start`, `padding-inline`, `border-inline-end`) and the old `direction: ltr` overrides are gone. In Arabic the whole shell mirrors: sidebar on the right, the user's messages on the left, and a drawer that slides in from the right.
  - **Answers.** Assistant answers are article cards (full column width, 46rem measure, 17px serif at 1.7 line height). The user's question is an umber bubble. Tables use the UI font, sit in a bordered scroll box with edge shadows that hint at more columns, and follow-up suggestions are real chips.
  - **Icons.** `components/Icons.tsx` holds inline SVG icons (send, close, trash, copy, check, menu, plus, chevron, search, retry, arrow, book, alert); they inherit `currentColor`. The send icon is an up arrow, so it doesn't need flipping in Arabic. Directional icons get `.icon-directional`, which mirrors under `[dir=rtl]`.
  - **Other.** Catechism prompt cards drop the uppercase pill labels that repeated the question. `public/cross-mark.png` is a trimmed square 512 px version of the cross, made with `sharp` (already a Next dependency), so the 30 px header mark isn't mostly transparent padding. The header language toggle is a `role="group"` with `aria-pressed`, and the nav links carry `aria-current`. Reduced motion is respected globally.
- **Not done here:** dark mode (owner: tokens only), the nested sidebar button and the other state fixes (fix 3), and the landing page (fix 4). `public/cross.png` and `public/icons/*.svg` are now unused and can be deleted in a cleanup pass.
- **Files changed:** `orthodox-site/app/fonts.ts` (new), `orthodox-site/components/Icons.tsx` (new), `orthodox-site/public/cross-mark.png` (new), `orthodox-site/app/globals.css` (rewritten), `orthodox-site/app/layout.tsx`, `orthodox-site/components/Navbar.tsx`, `orthodox-site/components/ChatShell.tsx`, `orthodox-site/components/ChatSidebar.tsx`, `orthodox-site/app/chat/page.tsx`, `orthodox-site/app/contact/page.tsx`, `orthodox-site/app/page.tsx`, `orthodox-site/lib/i18n.ts`.
- **Concept to learn:** *CSS logical properties.* `margin-inline-start` means "the side where lines start", which is left in English and right in Arabic, so one stylesheet serves both directions without `[dir=rtl]` overrides. Search: "CSS logical properties RTL".
- **Revisit if:** dark mode is requested (add a `[data-theme="dark"]` / `prefers-color-scheme` block that redefines the color tokens), or Tailwind is adopted (map the tokens into `@theme`).

### UI-008: Broken states fixed; language remembered in a cookie and rendered on the server
- **Date / Part:** 2026-09-16, UI refresh fix 3
- **Audit ref:** UI_AUDIT §3 (errors, question marks, composer), §4–§6 (Arabic contact overflow, 404, nested button, live regions, English first paint), prioritized fix 3
- **Decisions:**
  - **Honeypot.** It's hidden with `clip-path: inset(50%)` and `opacity: 0` at `inset-inline-start: 0` inside the (now `position: relative`) form. Nothing is placed off-screen, so there's no sideways scroll in either direction: the Arabic contact page's document width is 390 px on a 390 px phone (was 10,390). The field stays in the DOM, so bots still fill it.
  - **Question marks.** `followUpToUserMessage` (which strips "?" and rewrites "Would you like to…" as "I would like to…") now runs only on follow-up chips, not on what the user types.
  - **Composer.** The textarea resizes to its content on every change (a layout effect sets `height` from `scrollHeight`) up to the CSS `max-height`, then scrolls. It has an accessible name. While empty it takes the page direction, so the Arabic placeholder reads right-to-left; typed text keeps `dir="auto"`.
  - **Errors.**
    - A failed send no longer turns the typing placeholder into a fake answer, and no longer repeats the error as a top banner. It shows one `role="alert"` card under the question, with a Retry button that resends the same question and options (the failed optimistic message is replaced, not duplicated).
    - `lib/chat-client.ts` throws `ApiError` with the HTTP status, and `lib/errors.ts` maps it to a translated message: 429 means busy, 400 "too long" means shorten your question, a network failure means check your connection, and anything else gets a generic message. Server text is never displayed, so strings like "Set ORTHODOX_API_URL" can't reach a visitor.
    - The same rule applies to loading chats, deleting chats, the saints list and saint details (the saints list previously showed the "unable to load chats" text).
    - The contact form maps the route's error codes. Validation messages are shown as written in English (and a generic translated message in Arabic); rate-limit and captcha messages are translated; configuration and provider errors show the generic message.
  - **Auto-open loop (found while testing).** `/chat` opens the most recent conversation when no `?chat=` is given. If that request failed, the effect ran again on every render and repeated the request forever. It's now attempted once per page load (`autoOpenAttemptedRef`).
  - **404.** `app/not-found.tsx` is a server component: cross, "404", a heading, and "home" / "ask a question" buttons, in the visitor's language, inside `<main>`, `noindex`, and it returns HTTP 404.
  - **Nested interactive.** Each sidebar chat is an `<li>` holding two sibling buttons (open, delete), with `aria-current` on the open chat.
  - **Screen readers.**
    - A visually hidden `role="status"` region announces "Searching the books…" when a question is sent and "Answer ready." when it arrives. Errors use `role="alert"`.
    - The chat page has a visually hidden `<h1>` naming the current tab, and the Sources heading level follows the outline (h2 in chat, h3 under a saint title).
    - The typing indicator shows the same "Searching the books…" text visibly.
    - The contact status line is a polite live region.
  - **Language.** `LanguageProvider` writes the choice to a `lo_lang` cookie (one year, `SameSite=Lax`) as well as localStorage. The root layout reads the cookie with `cookies()` and renders `lang`, `dir` and every translated string on the server, so an Arabic visitor never sees English first. Visitors who chose Arabic before this change only have localStorage; on their first visit the provider copies it into the cookie and switches once, and from then on the server renders Arabic.
  - **Hard-coded English removed.** The "Learn more" button (now "Ask more about this saint"), the typing label, the table region label and the navigation labels are translated.
- **Trade-off:** reading a cookie in the root layout makes every page dynamically rendered instead of static. These pages are small and already client-heavy, so the cost is a few milliseconds of server time per request on Vercel. The alternative (locale URLs such as `/ar/...`) is a bigger routing change and was not requested.
- **Verification:** Playwright on the production build: Arabic `/contact` scroll width equals the viewport (390 and 1440); with JavaScript disabled and the Arabic cookie, the home page is served as `lang="ar" dir="rtl"` with Arabic text; `/no-such-page` returns 404 with the Arabic heading; a four-line question grows the composer from 26 to 104 px; a mocked 500 whose body names `ORTHODOX_API_URL` shows one translated alert, keeps "What is fasting?" with its question mark, and never puts the server text in the page; Retry sends the same question once more, leaving one user message and no alert; the live region reads "Searching the books…" and then "Answer ready."; axe on that page reports no violations (after the heading-level fix).
- **Files changed:** `orthodox-site/lib/errors.ts` (new), `orthodox-site/lib/request-language.ts` (new), `orthodox-site/app/not-found.tsx` (new), `orthodox-site/app/layout.tsx`, `orthodox-site/components/LanguageProvider.tsx`, `orthodox-site/components/ChatShell.tsx`, `orthodox-site/components/ChatSidebar.tsx`, `orthodox-site/components/AnswerWithSources.tsx`, `orthodox-site/app/chat/page.tsx`, `orthodox-site/app/contact/page.tsx`, `orthodox-site/app/page.tsx`, `orthodox-site/app/credits/page.tsx`, `orthodox-site/lib/chat-client.ts`, `orthodox-site/lib/i18n.ts`, `orthodox-site/app/globals.css`, `ui-audit/tools/capture.mjs` and `extra.mjs` (set the cookie too).
- **Concept to learn:** *Error messages are UI, not logs.* Map failures to what the user can do next (wait, shorten, reconnect, retry) and keep diagnostic text in server logs. Search: "error message UX guidelines", "WAI-ARIA live regions".
- **Revisit if:** the site adds locale URLs (then the cookie becomes a redirect hint only), or the backend starts returning structured error codes (map those instead of HTTP status).

### UI-009: A landing page that explains the site; the empty history column is hidden for new visitors
- **Date / Part:** 2026-09-16, UI refresh fix 4
- **Audit ref:** UI_AUDIT §1 (first impression), prioritized fix 2
- **Context:** The home page was a cross, the site name, one faint sentence and a text box. On desktop, a new visitor's first view also included a 300 px "No saved chats yet" column.
- **Decision:** The home page is a single centered reading column, in this order:
  1. **Hero.** The cross, then a red eyebrow line ("An AI study guide to the Coptic Orthodox faith"), the name, and one lead sentence: answers come only from Fr. Tadros Malaty's books and the Coptic Orthodox catechism, and every answer shows its book and page. Then the composer, then six example questions (four on phones) that start a chat when tapped.
  2. **"Explore".** Two cards linking to the Catechism topics and the Saints browser.
  3. **"How it works".** Three steps: ask in English or Arabic; it reads a fixed library, named; answers cite book, volume and page.
  4. **"Before you start".** A gold-edged note with three honest limits: it's an AI and can misread, so check the cited pages; it only knows these books and says so when they don't cover a question; it's a study aid, not a spiritual father. It links to Credits.

  The copy lives in `lib/home-content.ts` in both languages. The example questions come from the eval set, where the library answers them well (CAT-01/08/15/18, SNT-08, KW-03; AR-01/02/04/07/08/10). The desktop history column appears only once the visitor has conversations (`ChatSidebar desktopHidden`); the mobile drawer is always available for navigation. On wide screens, the column no longer pushes the centered page; only narrower desktops (821–1320 px) reserve room for it. On `/chat`, a new visitor sees "What would you like to learn?" with four example questions instead of "Start by asking a question below.", and the empty history column says conversations will be saved there in this browser (they are stored server-side under this browser's anonymous cookie).
- **Wording check:** the English index also contains 207 passages from Mind of Christ Light, which publishes translations of Fr. Tadros's writings (Credits page). The "How it works" step names it, so "only from Fr. Tadros Malaty's books and the catechism" stays accurate. The Arabic library is the Arabic catechism and Fr. Tadros's قاموس آباء الكنيسة وقديسيها, and the Arabic copy names those.
- **Also:** `priority` on `next/image` is deprecated in Next 16. The hero cross uses `loading="eager"` with `fetchPriority="high"`, the header mark uses `loading="eager"`, and the below-the-fold Credits portrait lazy-loads. The drawer's full-screen backdrop is now `aria-hidden` and out of the tab order; the drawer's close button is the keyboard path.
- **Verification:** screenshots at 1440 and 390 px in both languages (no horizontal overflow). Tapping "Who was St. Moses the Black?" on the home page opens `/chat` and sends exactly that question, in `chat` mode with `language: en`.
- **Files changed:** `orthodox-site/lib/home-content.ts` (new), `orthodox-site/components/ExampleQuestions.tsx` (new), `orthodox-site/app/page.tsx` (rewritten), `orthodox-site/app/chat/page.tsx`, `orthodox-site/components/ChatSidebar.tsx`, `orthodox-site/components/Navbar.tsx`, `orthodox-site/app/credits/page.tsx`, `orthodox-site/app/contact/page.tsx`, `orthodox-site/lib/i18n.ts`, `orthodox-site/app/globals.css`.
- **Concept to learn:** *Set expectations before the first interaction.* For AI tools, saying what the system can use, how to verify it, and where it stops builds more trust than a bare prompt box. Search: "AI UX onboarding expectations", "Google PAIR guidebook mental models".
- **Revisit if:** the library grows (update the "fixed library" step and the example questions), or analytics show most traffic lands directly on `/chat`.

### UI-010: Sharing and SEO — one site URL, per-page metadata, a real social card, no debug logging
- **Date / Part:** 2026-09-16, UI refresh fix 5
- **Audit ref:** UI_AUDIT §7–§8, prioritized fix 5, open question 19
- **Context:** Every page had the title "Learn Orthodoxy" and a canonical URL pointing at the home page. `/og-image.png` returned 404. The domain was hard-coded in three files. `robots.txt` had a non-standard `Host:` line. The sitemap listed the orphan `/about` page. The chat page printed 17 debug lines (including the full question) to every visitor's console.
- **Decisions:**
  - **Domain.** Owner's decision: learnorthodoxy.net. It is defined once, in `lib/site.ts` (`SITE_URL`, with the name, tagline and description), and used by the layout, sitemap and robots. It's a constant rather than an environment variable because it is the same in every environment and the canonical URL must not change on preview deployments.
  - **Per-page metadata.** Pages that run in the browser can't export `metadata`, so `app/page.tsx`, `app/chat/page.tsx`, `app/credits/page.tsx` and `app/contact/page.tsx` are now small server components that export metadata and render the client component (moved to `home-page.tsx`, `chat-page.tsx`, `credits-page.tsx`, `contact-page.tsx` with `git mv`). `pageMetadata()` builds the title, description, canonical and a full `openGraph`/`twitter` block for each page, because Next.js replaces rather than merges those objects between segments. The root layout sets `metadataBase`, a title template ("%s · Learn Orthodoxy"), a descriptive default title for the home page, and a theme color. Results:
    - Home: "Learn Orthodoxy — An AI study guide to the Coptic Orthodox faith"
    - Chat: "Ask a question · Learn Orthodoxy"
    - Credits: "Sources and credits · Learn Orthodoxy"
    - Contact: "Contact · Learn Orthodoxy"
    - 404: "Page not found · Learn Orthodoxy"
    - Each page's canonical is its own URL on learnorthodoxy.net.
  - **Social card.** `public/og-image.png` (1200×630, 48 KB) uses the new design: Source Serif title, Arabic name in Naskh, gold rule, the cross in a medallion, a red citation marker and the domain. Its source is `ui-audit/tools/og-image.html`, rendered by `og-image.mjs` with Playwright, so it can be regenerated when the wording changes. `app/icon.png` (192 px) and `app/apple-icon.png` (180 px, on paper) come from the trimmed cross, and `app/manifest.ts` adds a basic web manifest. The existing `favicon.ico` stays.
  - **Crawling.** `robots.txt` allows everything except `/api/` and points at the sitemap; the `Host:` line is gone. The sitemap lists `/`, `/chat`, `/credits` and `/contact`. The 404 page is `noindex` (Next.js default).
  - **Old pages.** `/about` (an unstyled, unlinked draft) and `/sources` now permanently redirect (308) to `/credits` from `next.config.ts`, and their page files are deleted.
  - **Console.** All `console.log` and `console.debug` calls in the site are removed: 17 in the chat page, the per-request language log in `api/chat`, and the success log in `api/contact` (it printed the sender address to Vercel logs). `console.warn` for misconfiguration stays. An ESLint `no-console` rule (warn and error allowed) on `app/`, `components/` and `lib/` stops them coming back. `scripts/migrate-postgres.mjs` is a command-line tool and keeps its output.
- **Build note:** the first build failed because `.next/dev/types` still held type stubs for `/about` from a May dev session. That generated folder was deleted and the build passed.
- **Verification:** `curl` against the production build shows the titles, descriptions, canonicals, `og:url` and `og:image` listed above. `/og-image.png`, `/icon.png`, `/apple-icon.png` and `/manifest.webmanifest` return 200 with the right types, and `/about` returns 308 to `/credits`. `robots.txt` and `sitemap.xml` use learnorthodoxy.net. No `console.log` or `console.debug` remains in `app/`, `components/` or `lib/`.
- **Files changed:** `orthodox-site/lib/site.ts` (new), `orthodox-site/app/{page,chat/page,credits/page,contact/page}.tsx` (new server wrappers), `orthodox-site/app/{home-page,chat/chat-page,credits/credits-page,contact/contact-page}.tsx` (moved), `orthodox-site/app/layout.tsx`, `orthodox-site/app/sitemap.ts`, `orthodox-site/app/robots.ts`, `orthodox-site/app/manifest.ts` (new), `orthodox-site/app/icon.png`, `orthodox-site/app/apple-icon.png`, `orthodox-site/public/og-image.png` (new), `orthodox-site/app/not-found.tsx`, `orthodox-site/next.config.ts`, `orthodox-site/eslint.config.mjs`, `orthodox-site/app/api/chat/route.ts`, `orthodox-site/app/api/contact/route.ts`, `ui-audit/tools/og-image.html` and `og-image.mjs` (new); `orthodox-site/app/about/page.tsx` and `app/sources/page.tsx` deleted.
- **Concept to learn:** *Canonical URLs.* A canonical tag tells search engines which URL is the original. Pointing every page at the home page tells them the other pages are duplicates, which can drop them from the index. Search: "rel canonical best practices", "Open Graph protocol".
- **Revisit if:** Arabic gets its own URLs (add `alternates.languages` / `hreflang`), or the domain changes (edit `SITE_URL` and the Google verification token).

### UI-011: Font loading trimmed after the first "after" measurement
- **Date / Part:** 2026-09-17, UI refresh follow-up (found by the after-pass Lighthouse run)
- **Context:** With fixes 1–5 in place, mobile first paint halved (about 2.9s to 1.4s) and layout shift fell to 0. But Lighthouse's simulated mobile LCP rose from 3.1–3.6s to 4.1–4.4s on `/chat`, `/credits` and `/contact`. The real (unthrottled) LCP was about 0.1s; the estimate was driven by font downloads. English pages preloaded three font files (Source Serif `latin` and `latin-ext`, Inter `latin`), and the "العربية" label in the language toggle made every English page download the 92 KB Noto Naskh Arabic file.
- **Decision:** Source Serif loads the `latin` subset only (the English books and answers don't need `latin-ext`; any rare accented letter falls back to Georgia). On English pages the toggle's Arabic label uses the system Arabic face; Arabic pages keep Naskh. English pages now load two font files.
- **Result (Lighthouse mobile, two runs each):** home 90–92, chat 90–91, credits 92–93; FCP 0.8s; LCP 3.2–3.6s. The full before/after table is in the UI refresh summary.
- **Files changed:** `orthodox-site/app/fonts.ts`, `orthodox-site/app/globals.css`.
- **Concept to learn:** *Font subsetting and `unicode-range`.* The browser downloads a web font file only when the page uses a character in that file's range, so a single Arabic word on an English page pulls in the whole Arabic file. Search: "unicode-range font loading", "Lighthouse LCP font preload".
- **Revisit if:** English answers start showing missing accented letters (add `latin-ext` back without preloading it).

### UI-012: Traditional redesign on its own branch; logo redrawn as outlined SVG (proposal)
- **Date / Part:** 2026-09-17, design-traditional Step 1
- **Context:** The owner felt parts of the refreshed site look "AI-generated" and asked for a look based on liturgical books and printed catechisms. The owner's logos (`orthodox-site/public/brand/*2.png`) mixed two type families, the candlestick base overlapped the "O" of ORTHODOXY, the files had wide empty margins, and there was no small icon.
- **Decision:** Work on `design-traditional` (off the deployed `main`), frontend only, no OpenAI calls. `ui-audit/tools/brand.mjs` rebuilds the logo as SVG with the letters converted to outlines, so the files display the same everywhere without a font:
  - **Wordmark:** "Learn" and "ORTHODOXY" are set in EB Garamond SemiBold. The tagline "A Coptic Orthodox Study Guide" is in spaced small caps, tracked to the width of ORTHODOXY. The candlestick is redrawn so it stands clear of the letters, and the margins are trimmed. The original wording, "A Coptic Orthodox Catechism Resource", is kept as `wordmark-alt`.
  - **Lettermark:** both letters are EB Garamond ExtraBold, and the O gets a speech-bubble tail. There are two cross versions: a Latin budded cross (as in the original) and an equal-armed Coptic cross with three points per arm.
  - **Icon:** the O bubble alone. Its counter is filled with the background color, so the cross stays visible on light and dark browser tabs. From 180 px up, the icon uses the lettermark's O. At 16 and 32 px, a separate version is drawn on the pixel grid with whole-pixel strokes and a plain cross. The app icon is the same art on a square background.
  - **Palette:**
    - Paper #F8F3EA.
    - Umber #4B3A22 (9.9:1 on paper).
    - Gold #E4AE48 (1.8:1, large marks only).
    - Antique gold #866426 (4.9:1, for small gold text and hairlines).
    - Rubric red #8E2A1E (7.6:1).
    - Dark versions: night #2A2117 with ivory #F4ECDC and gold (7.9:1); brass #B08A3E for the candlestick.
  - **Dark versions:** every variant also comes light-on-dark.
- **Why:**
  - Outlined SVG stays sharp at any size and needs no font.
  - The mixed type families and the candlestick collision were the most visible flaws.
  - A detailed cross turns into a gray smudge at 16 px, so the smallest sizes need their own drawing rather than a scaled-down copy.
- **Owner feedback, round 1 (2026-09-17):**
  - **Tagline:** "A Coptic Orthodox Study Guide" is the main tagline, including on dark; the original wording stays as the alternate.
  - **Cross:** waiting for the priest. Both versions are kept, and the Coptic cross is shown first by default.
  - **Changes made:**
    - *Tagline spacing:* fixed at 0.094 em (the original tagline's spacing) and centred, not stretched to the width of ORTHODOXY. Taglines are not used below 400 px; a `wordmark-short` version has no tagline.
    - *Weight:* ORTHODOXY is shown at 500, 600, 700 and 800. The current weight was already SemiBold (600), so the default stays at 600 until the owner chooses.
    - *Candlestick:* brass #B08A3E on dark backgrounds (4.9:1).
    - *Crosses:* each arm end is drawn once and rotated, so the arms are symmetric by construction.
      - Latin cross: stroke 9 → 11; top and side arms equal.
      - Coptic cross: straight arms 12 wide, smaller three-point ends, a plain centre.
    - *Lettermark:* the cross is about 12% larger and centred on the counter measured from the glyph outline.
    - *Icon and app icon:* an upright O with an almost even stroke instead of the tilted Garamond O. The O, tail and counter are one compound path (nonzero fill: outer contour and tail clockwise, counter hole counter-clockwise). The counter fill extends halfway under the stroke, so no background line shows at the join.
    - *Favicons:*
      - At 16 px: a 2 px O stroke, a larger counter, a 2 px cross and a solid tail.
      - A version without a tail at 16 and 32 px.
      - A dark rounded-square version: no tail at 16 px, with a tail at 32 px. It stays visible on light browser tabs.
    - *New sheets:* the comparison sheets now include 8× nearest-neighbour zooms, light and dark tab mockups, and a mock site header with the 48 px lettermark.
- **Status:** Proposal only. Renders and comparison sheets are in `ui-audit/brand/`. Nothing on the site uses the new files yet, and the original PNGs are kept. Still open:
  - the cross (waiting for the priest)
  - the ORTHODOXY weight
  - which favicon to use (tail, no tail, or dark square)
- **Files changed:** `ui-audit/tools/brand.mjs` (new), `ui-audit/tools/README.md`, `ui-audit/brand/` (new), `orthodox-site/public/brand/` (the owner's original PNGs, now committed), `.gitignore`.
- **Concept to learn:** *Optical sizing and pixel hinting.* Small sizes need heavier strokes and simpler shapes. A stroke aligned to whole pixels stays sharp; one that falls between pixels is drawn as a gray blur. Search: "favicon design pixel grid", "optical size typography".
- **Revisit if:** the owner redraws the logo in a design tool (then keep `brand.mjs` only as a reference), or the site gets a dark theme (the `-dark` files are ready for it).

### UI-013: Classical type and logo colors — EB Garamond for display, Source Serif 4 kept for reading
- **Date / Part:** 2026-09-17, design-traditional Step 2
- **Context:** Inter made the interface look like a generic app. The owner asked for a classical serif system: EB Garamond for headings and UI labels, Amiri and Noto Naskh Arabic for Arabic, colors from the logo, and a comparison of EB Garamond and Source Serif 4 for long answers.
- **Reading-font comparison:** `ui-audit/tools/reading-fonts.mjs` renders a real eval answer (CAT-06) at 390 px wide and measures it. The screenshots are `ui-audit/typography/reading-fonts-2x.png` and `-1x.png`.

  | Face and size | x-height | Characters per full line | Answer height |
  |---|---|---|---|
  | Source Serif 4, 17 px / 1.7 (today) | 8.1 px | 43 | 1784 px |
  | Source Serif 4, 18 px / 1.65 | 8.5 px | 40 | 2015 px |
  | EB Garamond, 19 px / 1.6 | 7.6 px | 45 | 1793 px |
  | EB Garamond, 20 px / 1.55 | 8.0 px | 43 | 1926 px |

- **Decision:**
  - **Long answer text:** Source Serif 4 stays, at 17 px. EB Garamond's x-height is 0.40 em, against 0.475 em for Source Serif, so Garamond needs 20 px to be as legible. At 20 px it gives the same 43 characters per line but makes answers 8% taller. On 1× screens its thin strokes also turn faint at body sizes, while Source Serif's stay solid.
  - **Display face:** EB Garamond (variable weight, Latin subset) is used for headings, the site name, and the navigation, labels and buttons. Labels, navigation and buttons are set in all-small-caps with 0.06 em tracking (`--caps-label`, `--tracking-label`).
  - **EB Garamond Italic:** a separate file that is not preloaded; it is used for questions in Step 3. (Dropped in UI-016: italic is now only used inside answers, in the reading face.)
  - **Small functional text:** tables, sources, sidebar titles and alerts use `--font-text` (Source Serif 4).
  - **Arabic:** Amiri Regular for headings and Noto Naskh Arabic for everything else. Arabic turns off small caps and letter-spacing. `font-synthesis: none` stops the browser from faking a bold Amiri.
  - **Colors (from the logo):**
    - Paper: #f8f3ea.
    - Text: ink #3b2d1b, soft #5e4d36 and faint #6b5a42. Each is at least 5.2:1 on every surface.
    - Umber #4b3a22: headings and primary buttons.
    - Rubric red #8e2a1e: accent and focus.
    - Antique gold #866426: hairlines and small ornament, 4.9:1 on paper. It is never used for text on the hover background (4.3:1).
    - Gold #e4ae48: large ornament only.
    - Control borders: #8f7a57, at least 3.3:1 on every surface.
    - The browser theme color and manifest colors match the new paper.
  - **Inter** is removed.
- **Result:**
  - English pages still preload two font files: 93 KB, against 98 KB before.
  - Arabic fonts and the italic load only when used.
  - Lighthouse on the production build (one run, Step 2) against the Step 0 baseline (two runs):
    - Mobile performance: home 92 (baseline 92–94), chat 94 (94–95), credits 96 (96), contact 93 (93–96).
    - Desktop performance: 100 on every page, before and after.
    - Layout shift: 0 everywhere.
- **Files changed:** `orthodox-site/app/fonts.ts`, `orthodox-site/app/globals.css`, `orthodox-site/app/layout.tsx`, `orthodox-site/app/manifest.ts`, `ui-audit/tools/reading-fonts.mjs` (new), `ui-audit/tools/lighthouse.mjs` (new), `ui-audit/tools/capture.mjs` (`BASE_URL`), `ui-audit/typography/` (new), `.gitignore`.
- **Concept to learn:** *x-height and optical size.* Two fonts at the same pixel size can look very different in size; the height of the lowercase letters decides legibility. Search: "x-height legibility screen", "font-variant-caps all-small-caps".
- **Revisit if:** the owner prefers Garamond for answers anyway (use 20 px, weight 450, and check the 1× rendering), or a dark theme is added (the color tokens are the only thing to redefine).

### UI-014: Book-style layout replaces the app patterns; logo assets wired in through one switch
- **Date / Part:** 2026-09-17, design-traditional Step 3
- **Context:** Several parts of the refreshed site looked templated rather than designed: the pill chips, the icon tiles in rounded cards, the red eyebrow above the title, the answer cards with shadows, and the pill-shaped buttons and language switch. The owner chose the logo (Bold ORTHODOXY, dark-square favicon). The cross is still waiting for the priest, so the Coptic cross is the default.
- **Decision:**
  - **One switch for the cross.**
    - `lib/brand.ts` holds `BRAND_CROSS = "coptic"` and every logo path. The lettermark, the ornament cross, the favicon, the apple icon and the manifest icons all come from it.
    - The icons are declared in the root layout's `metadata.icons` instead of `app/icon*` files, because file-based icons can't follow a constant.
    - `/favicon.ico` is rewritten to the current favicon for clients that request it directly.
    - `ui-audit/tools/brand.mjs` (with `SITE_DIR`) writes both crosses' files into `public/brand/`, so switching is that one line. It was tested by switching to `"latin"` and back.
    - The social card uses no cross, so it never needs regenerating.
  - **Header:** the lettermark next to "Learn Orthodoxy" in EB Garamond, with a double hairline under the header. The navigation is in small caps; the current page is underlined in red instead of filled.
    - The language switch is two words split by a hairline, and both are now 44 px tall on phones (they were 36 px).
  - **Hero:**
    - The wordmark (without its tagline) is the `h1`. The tagline is set underneath as real text, in spaced small caps. It stays readable below 400 px, and on Arabic pages it is translated ("دليل دراسي قبطي أرثوذكسي").
    - On Arabic pages the Arabic name is the heading text and the English wordmark is decorative.
    - The red eyebrow is gone. A quiet italic note sits under the question box: "Answers are prepared by AI from these books, with sources shown." It has an Arabic version.
  - **"Begin with a question":** a table-of-contents list (Garamond, dotted leaders, hairline rules, each row a full-width button) replaces the pill chips. Follow-up suggestions and catechism prompts use the same rows. (Set in italic at first; roman since UI-016.)
  - **Explore:** two columns of text divided by a hairline, each with a small-caps heading, a short description and a text link. The icon tiles are gone, and `IconBook` and `IconUsers` were removed.
  - **How it works:** numbered with Roman numerals in rubric red; Arabic uses Arabic-Indic digits. "Before you start" is a ruled note with em-dash markers instead of a tinted box.
  - **Ornament:** `components/Ornament.tsx` draws two antique-gold rules around the brand cross. It is used only between the home page's major sections and under the 404 title.
  - **Answers:**
    - No card for the answer. The question sits in a warm panel (surface tone, hairline border, 3 px corners) in the site serif, aligned to the end of the line, so it stays clearly apart from the answer; each new question is also separated from the previous answer by a hairline. (Set in italic beside a gold rule at first; the owner asked for a filled panel before the branch was pushed.)
    - The first paragraph of a left-to-right answer gets a two-line drop cap in rubric red (`initial-letter`, with a float fallback). Arabic gets none, because it would break the joined letters.
    - Headings are in Garamond, with small caps for the minor levels. Numbered-list markers are red, bullet markers gold.
    - Tables use book rules (a heavy rule above and below, a light rule under the header, no grid).
    - Sources look like footnotes: a short gold rule, small type, red numbers and italic titles.
  - **Controls:** buttons are rectangles (2 px radius) in small caps, umber or outlined. The composer and inputs have 2–4 px corners with a 3.3:1 border and no shadow. The focus ring is still 2 px rubric red. The only shadow left is the phone drawer's.
  - **Other pages:**
    - Saints: the selected saint is a ruled encyclopedia entry, and the names are a ruled index.
    - Catechism: topics are ruled chapter rows.
    - Credits: the portrait sits in a thin frame and the doxology is in centered italic.
    - Contact: the form is set on the page without a card.
    - 404: red "404", the title and the ornament. `public/cross-mark.png` and the old `app/favicon.ico`, `icon.png` and `apple-icon.png` are removed.
  - **Social card:** redrawn as a framed page with the wordmark, the Arabic name, a small rule and one line of copy (`ui-audit/tools/og-image.*`).
- **Why:** These patterns come from printed liturgical books and catechisms: rules, small caps, rubrics, contents pages and footnotes. They replace the chat-app vocabulary without losing any function.
- **Result (production build, mocked API, no OpenAI calls):**
  - axe finds 0 violations in all 32 captured states.
  - Tap targets under 44 px on phones: before, the site name, both language buttons, an example chip and "About the sources"; after, only the text field inside the 44 px composer.
  - The Lighthouse numbers are in the design-traditional summary in UI_AUDIT.md.
- **Files changed:**
  - New: `orthodox-site/lib/brand.ts`, `orthodox-site/components/Ornament.tsx`, `orthodox-site/public/brand/*` (generated).
  - Changed:
    - `orthodox-site/app/globals.css`
    - `orthodox-site/app/home-page.tsx`, `orthodox-site/app/layout.tsx`, `orthodox-site/app/manifest.ts`, `orthodox-site/app/not-found.tsx`
    - `orthodox-site/components/ExampleQuestions.tsx`, `orthodox-site/components/Navbar.tsx`, `orthodox-site/components/ChatSidebar.tsx`, `orthodox-site/components/Icons.tsx`
    - `orthodox-site/lib/home-content.ts`, `orthodox-site/lib/site.ts`, `orthodox-site/next.config.ts`
    - `orthodox-site/public/og-image.png`
    - `ui-audit/tools/brand.mjs`, `ui-audit/tools/og-image.html`, `ui-audit/tools/og-image.mjs`
  - Removed: `orthodox-site/app/favicon.ico`, `orthodox-site/app/icon.png`, `orthodox-site/app/apple-icon.png`, `orthodox-site/public/cross-mark.png`.
- **Concept to learn:** *Book typography on the web.* Rules (hairlines), small caps, rubrication, drop caps (`initial-letter`) and running heads carry structure without boxes. Search: "CSS initial-letter", "booktabs table style", "rubrication".
- **Revisit if:**
  - The priest picks the Latin cross: change `BRAND_CROSS`.
  - Firefox gains `initial-letter` (then drop the float fallback).
  - A dark theme is added: the logo's `-dark` files are in `ui-audit/brand/svg/`.

### UI-015: Verification of the traditional design; the italic font is preloaded only where it is used
- **Date / Part:** 2026-09-17, design-traditional Step 4
- **Superseded by UI-016:** the italic face was removed altogether, so no route preloads it and every page loads two font files.
- **Context:** The owner asked for screenshots, axe and Lighthouse runs, a comparison with the deployed design, and a list of anything that got worse. The baseline was built from the same branch before any site change; at that point its site code was identical to `main`.
- **Finding:** The first Lighthouse run of Step 3 showed three regressions against the baseline:
  - Mobile first paint went from 0.75 s to 1.2 s on home, chat and credits.
  - Desktop first paint went from 0.20 s to 0.33 s.
  - Layout shift went from 0 to 0.007–0.009 on home and chat.

  The cause was EB Garamond Italic. It was not preloaded, so its request started about 40 ms after the others. It sat in the render path of the simulated first paint, and its swap moved the question rows.
- **Decision:**
  - The italic moves to `app/font-italic.tsx`, with preloading on. Its CSS variable is set by a `display: contents` wrapper in the home, chat and credits page files, so next/font preloads it on those three routes only.
  - `.font-scope` redefines `--font-display-italic`, because a custom property is resolved where it is declared. The `:root` token falls back to the roman file.
  - Contact and 404 load two font files, as before.
- **Result:**
  - Layout shift is 0 on every page again.
  - Mobile first paint is 0.9 s and desktop 0.24 s on the three pages that use the italic; contact is unchanged.
  - Mobile performance: home 92–97, chat 92–93, credits 94–97, contact 95–99. Desktop stays at 100.
  - axe: 0 violations in all 32 states.
  - The full table and the list of what got worse are in the design-traditional section of UI_AUDIT.md.
- **Files changed:** `orthodox-site/app/font-italic.tsx` (new), `orthodox-site/app/fonts.ts`, `orthodox-site/app/page.tsx`, `orthodox-site/app/chat/page.tsx`, `orthodox-site/app/credits/page.tsx`, `orthodox-site/app/globals.css`, `ui-audit/tools/compare.mjs` (new), `ui-audit/tools/README.md`, `UI_AUDIT.md`.
- **Concept to learn:** *Route-scoped font preloading.* next/font preloads a font on the routes whose files use it, so calling it in the root layout preloads it everywhere. Search: "next/font preloading", "Lighthouse lantern simulated FCP".
- **Revisit if:**
  - The italic is dropped from above the fold; then it no longer needs preloading.
  - Arabic pages get their own routes; then they can skip the Latin italic.

### UI-016: Italic reserved for quoted matter inside answers; the italic font file is dropped
- **Date / Part:** 2026-09-17, after Step 4 (owner review before pushing)
- **Context:** The owner found too much italic on the home page. Italic had been used for the question rows, the two placeholders, the AI note, the typing indicator, follow-up suggestions, catechism prompts, the credits doxology and the portrait caption. Used that widely, it stopped meaning anything and made the page look mannered.
- **Decision:**
  - Every piece of interface text is roman EB Garamond: the "Begin with a question" rows, the composer and saints placeholders, the AI note under the question box, "Searching the sources…", follow-up suggestions, catechism prompts, the doxology and the portrait caption.
  - Italic is kept only inside an answer, where it carries meaning: emphasis from the Markdown, block quotes, and book titles in the Sources list. These use the reading face.
  - With nothing left using EB Garamond Italic, the font, the `WithItalic` wrapper, `app/font-italic.tsx`, the `.font-scope` rule and the `--font-display-italic` token are all removed. Every page is back to two font files.
  - This supersedes UI-015, which preloaded the italic on the three routes that used it.
- **Result (production build, mocked API, 0 OpenAI calls; two Lighthouse runs per page):**
  - Every page now matches or beats the deployed design.
    - Mobile performance: home 94–96 (deployed 92–94), chat 94–95 (94–95), credits 96 (96), contact 94–96 (93–96).
    - Desktop performance: 100 everywhere, as before.
    - Mobile first contentful paint: 0.75 s on every page, the same as the deployed design.
    - Layout shift: 0 everywhere.
    - Font files: 2 (93 KB) on every page, against 2 (98 KB) deployed.
    - Page weight is 50–65 KB lower per page than the deployed design.
  - axe: 0 violations across the 32 captured states.
- **Why the italic is not missed:** emphasis inside answers still renders italic; the browser slants the reading face, since Source Serif 4's italic file is not loaded. That costs a little quality on the few italic words in an answer, and saves a 47 KB download on every page.
- **Files changed:** `orthodox-site/app/globals.css`, `orthodox-site/app/page.tsx`, `orthodox-site/app/chat/page.tsx`, `orthodox-site/app/credits/page.tsx`, `orthodox-site/app/font-italic.tsx` (deleted), `UI_AUDIT.md`.
- **Concept to learn:** *Synthetic italic.* With no italic file, the browser slants the roman one. It is acceptable for a few words and poor for a paragraph. Search: "font-synthesis", "synthetic oblique typography".
- **Revisit if:** emphasis inside answers needs a true italic; then load Source Serif 4 italic without preloading it, so it arrives only when an answer actually uses it.

### UI-017: Home page order: the hero first, the Today line below the example questions
- **Date / Part:** 2026-09-23, home page declutter (branch `home-declutter`), item 1.
- **Context:** The Today banner sat above the hero, so the first screen opened on a boxed calendar strip before the wordmark. With the header's lettermark and name, the brand also appeared twice before the question box.
- **Decision:**
  - **Order:** header → hero (wordmark, description, question box, AI note) → example questions → Today line → Explore → footer.
  - **Brand:** the header's lettermark and name stay, and the hero's wordmark stays, so the brand appears once in the page.
  - **Example questions** move out of the hero into their own section, at the same distance from the question box as before.
- **Kept, for review:** the "How it works" and "Before you start" sections stay after Explore; the brief's order didn't mention them. So does the tagline under the wordmark (UI-023 lists it).
- **Files changed:** `app/home-page.tsx`, `app/globals.css`.

### UI-018: The Today banner becomes one quiet line
- **Date / Part:** 2026-09-23, home page declutter, item 2.
- **Context:** The banner was two or three lines between two rules: a red "TODAY" label, the date and the fast, then the full Synaxarium title ("The Departure of Pope Mettaos II (Matthew II), 90th Patriarch of the See of St. Mark"), "and 1 more", and an "Ask about this saint" button.
- **Decision:**
  - **One line** below the example questions: "Today · 13 Thout 1743 · Wednesday fast · Pope Mettaos II and 1 more". It is set in the small display size in soft ink, with no rules and no red label.
  - **Links, as before:** the date opens the day in the calendar; the saint opens their entry when the saints index has one; "and 1 more" opens the day. The full title is the saint's tooltip.
  - **Short names:** `lib/calendar/brief.ts` shortens the title to the name. It drops parentheses and everything after the first comma, and in Arabic the patriarchal numbering after "البطريرك" ("البابا متاؤس الثانى").
  - **Removed:** the "Ask about this saint" button. The saint's name already opens the entry, which has its own "Learn more".
  - The links keep a 32 px touch height.
- **Tests:** `lib/calendar/brief.test.ts`, 4 tests, including today's date, 13 Thout 1743.
- **Files changed:** `components/calendar/TodayBannerStrip.tsx`, `lib/calendar/brief.ts`, `lib/calendar/brief.test.ts`, `app/globals.css`.

### UI-019: Navigation cut to Chat, Catechism, Saints and Calendar; Credits and Contact in a footer; one language toggle
- **Date / Part:** 2026-09-23, home page declutter, item 3.
- **Context:** The header carried seven links and both language names ("English | العربية", the current one underlined), so it competed with the hero for attention.
- **Decision:**
  - **Header navigation:** Chat, Catechism, Saints and Calendar. "Saints Search" becomes "Saints" / "القديسون"; the chat page's own tabs keep "Saints Search".
  - **Page footer:** Credits and Contact move to a new footer (`components/SiteFooter.tsx`, a `nav` labelled "About this site"). It sits after `main` on the home, calendar, credits and contact pages.
  - **Chat page:** no footer, because it is a full-height app. Its sidebar still lists Credits and Contact, on desktop and in the phone drawer. The drawer keeps them because on a phone it is the navigation. Its "Saints" label matches the header.
  - **Language toggle:** a single button named in the other language, "العربية" on English pages and "English" on Arabic pages. It keeps `lang` for screen readers, and on English pages the system face, so Arabic fonts aren't downloaded (UI-011). The styles for the active state and the second button are removed.
- **Files changed:** `components/Navbar.tsx`, `components/SiteFooter.tsx` (new), `components/ChatSidebar.tsx`, `lib/i18n.ts`, `app/home-page.tsx`, `app/calendar/calendar-page.tsx`, `app/credits/credits-page.tsx`, `app/contact/contact-page.tsx`, `app/globals.css`.

### UI-020: Past chats open as a drawer on the home page; repeated titles listed once; phone header padding
- **Date / Part:** 2026-09-23, home page declutter, item 4.
- **Context:**
  - On desktop, once there was history, the home page showed a full-height past-chats column beside the hero. It was a second column of text on a page meant to lead to one question box.
  - Asking the same question twice made the list repeat itself: "What is prayer?" three times.
  - On phones the menu button sat 4 px from the window edge.
- **Decision:**
  - **Home page: no history column.** A small "Past chats" button under the AI note opens the history as a drawer. It only appears once there is history. The phone menu button opens the same drawer.
  - **The drawer at every width.** `ChatSidebar drawer` gives it a title, a close button and a dimmed backdrop on desktop. The section links stay phone-only, since the desktop header has them.
  - **Drawer focus.** Focus moves to the close button when the drawer opens, and Escape closes it. This applies only to this drawer, and only on opening, so a later update (a deleted chat) doesn't pull focus back.
  - **The chat page keeps its sidebar.**
  - **Repeated titles, everywhere the list appears** (`lib/chat-sessions.ts`): one line per title, compared without case, extra spaces or a final "?"/"؟". The newest chat of each title is kept, and the open chat is always shown, in its title's place. Older chats of the same title are only hidden from the list; nothing is deleted. Untitled chats are not merged.
  - **Phone header:** the navbar's side padding goes from 4 px to 12 px. On desktop the logo is 24 px from the edge and the sidebar's content 16 px; the chat sidebar column itself meets the edge by design.
- **Tests:** `lib/chat-sessions.test.ts`, 4 tests. The declutter check found axe 0 in the drawer states, and the drawer lists 3 chats for 6 with repeated titles.
- **Files changed:** `app/home-page.tsx`, `components/ChatSidebar.tsx`, `lib/chat-sessions.ts`, `lib/chat-sessions.test.ts`, `app/globals.css`.

### UI-021: A two-line hero description; "sources shown" said once
- **Date / Part:** 2026-09-23, home page declutter, item 5.
- **Context:** The description ran four lines at the large size and ended "…and every answer shows the book and page it drew on". The AI note under the question box then said "…with sources shown" again.
- **Decision:**
  - **English description:** "Ask about Church teaching and the lives of the saints. Answers come only from Fr. Tadros Malaty's books and the catechism, with sources shown."
  - **Arabic:** "اسأل عن تعليم الكنيسة وسير القديسين. تأتي الإجابات فقط من كتب القمص تادرس يعقوب ملطي والتعليم الكنسي، مع ذكر مصادرها."
  - **Size:** the reading size instead of the large one (1.0625 rem, Arabic 1.25 rem), with slightly tighter margins. It is two lines on desktop, and the phone size is unchanged.
  - **AI note:** "Answers are prepared by AI from these books." / "يُعِدّ الذكاء الاصطناعي الإجابات من هذه الكتب." The sources are mentioned once, in the description.
- **Files changed:** `lib/home-content.ts`, `app/globals.css`.

### UI-022: Four example questions, without dotted leaders
- **Date / Part:** 2026-09-23, home page declutter, item 6.
- **Context:** The home page listed six example questions on desktop (four on phones), each with a dotted leader running to its arrow, like a table of contents.
- **Decision:**
  - **Four questions at every width:** the first four of the list, three teaching questions and one saint in English, two of each in Arabic. The phone-only rule that hid the rest is gone.
  - **Rows:** the hairline rules between rows stay; the dotted leaders go. The question now takes the row, and the arrow sits at its end.
  - The chat page's empty state already showed four and loses its leaders the same way.
  - "Begin with a question" is centred on desktop, as when it was part of the hero, and left-aligned on phones as before.
- **Files changed:** `components/ExampleQuestions.tsx`, `app/home-page.tsx`, `app/globals.css`.

### UI-023: Home page declutter: what still competes on the first screen (report, not changed)
- **Date / Part:** 2026-09-23, home page declutter, item 7, for the owner's review. Screenshots are in `ui-audit/declutter/before` and `after` (desktop 1440 and mobile 390, English and Arabic; not committed).
- **Checks after UI-017 to UI-022:**
  - axe finds 0 violations in every state: home, past-chats drawer, chat page.
  - Lighthouse on the home page, 3 runs each (before → after):
    - mobile performance 95/98/98 → 95/98/98, median LCP 2.33 s both, CLS 0, TBT under 12 ms;
    - desktop 100 → 100, LCP ≈ 0.58 s;
    - page weight ~300 kB both.
  - Nothing scrolls sideways.
- **Still competing, not changed:**
  1. **Arabic pages show the brand three times** before the question box: the header's Arabic name, the English "Learn ORTHODOXY" wordmark (decorative there), and the large Arabic name set under it as the page title. A single Arabic wordmark, or the Arabic title at a smaller size, would bring it to the one mention English pages have.
  2. **The tagline** "A Coptic Orthodox Study Guide" / "دليل دراسي قبطي أرثوذكسي" adds a fourth line between the wordmark and the description, and in Arabic it is set large. The brief's hero order left it out.
  3. **The desktop header keeps its vertical rule** between Saints and Calendar. It used to separate the chat modes from the pages; with four links it reads as a stray mark.
  4. **The Arabic pages' "English" toggle** is set in the Latin face at the base size, so it looks heavier than the Arabic navigation links beside it.
  5. **On phones, the description is four lines** in English and three in Arabic (two on desktop). One sentence ("Answers come only from Fr. Tadros Malaty's books and the catechism, with sources shown.") would make it two.
  6. **On phones the Today line** wraps to two lines in Arabic and is below the first screen in both languages; that seems right for a quiet line.
  7. **"How it works" and "Before you start"** stay between Explore and the footer. The brief's order ended "Explore → footer"; removing them is a content decision.
  8. **"Past chats"** is a second underlined control under the question box. It only appears for returning visitors.

### UI-024: The Today banner goes back to the top, as a full-width band
- **Date / Part:** 2026-09-23, owner's review of the declutter.
- **Owner's request:** "keep the banner toward the top and make it more banner style." This replaces UI-017's placement below the example questions and UI-018's unruled quiet style. UI-018's one-line content stays.
- **Decision:**
  - **Placement:** a full-width band right under the header, above the hero, outside the content column.
  - **Content:** one line, "Today · 13 Thout 1743 · Wednesday fast · Pope Mettaos II and 1 more". It wraps to two lines on narrow phones in Arabic.
  - **Style:** a tinted ground (`--color-surface-muted`) with a hairline below, the "Today" label in rubric red, the date in semi-bold, and the links in umber. Text contrast is about 7:1 on the band.
  - **Links, as before:** the date and "and 1 more" open the day in the calendar; the saint opens their entry when the index has one.
  - **Unchanged:** the header, then the hero with the wordmark as the only brand mark in the page body; examples, Explore and the footer follow.
- **Checks:**
  - axe finds 0 violations in every declutter state.
  - Lighthouse mobile, six runs each on the same build setup: Today line at the bottom 94–96 (median 96, LCP median 2.84 s); banner at the top 94–98 (median 95, LCP median 2.92 s). The difference is inside the run-to-run spread; the LCP element is the hero description in both, and the font requests are the same.
  - Desktop: 100, LCP ≈ 0.49–0.58 s.
- **Files changed:** `app/home-page.tsx`, `app/globals.css`, `components/calendar/TodayBannerStrip.tsx` (comment).

### UI-025: A collapsible past-chats sidebar shared by the home and chat pages; a four-link header without divider; the language toggle set like the links
- **Date / Part:** 2026-09-23, owner's review of the declutter. This replaces UI-020's "Past chats" button and its desktop drawer.
- **Owner's request:** a sidebar for past chats instead of the drawer button, collapsible, on both pages; proper padding; no divider between Saints and Calendar; the language toggle the same size and style as the other links.
- **Decision:**
  - **One sidebar for both pages** (`components/useChatSidebar.ts`, `ChatSidebar`). It is shown only once the visitor has chats. Its contents are unchanged: "New chat" at the top, then past chats listed once per title (UI-020).
    - **Desktop:** open by default. A toggle at the start of the header (a panel icon, "Hide past chats" / "Show past chats", `aria-expanded`, `aria-controls="chat-sidebar"`) hides and shows it. The choice is remembered in this browser (`localStorage`); if storage is unavailable, it stays open.
    - **Phones:** a slide-in drawer from the header's menu button, as before. Focus moves into the drawer, and Escape closes it.
  - **Padding:** on desktop the panel is inset 12 px from the window edges (`--sidebar-gap`), with a hairline all round, and it is narrower (256 px, was 280).
    - **Chat page:** fixed under the header. The chat column makes room only while the panel is shown.
    - **Home page:** in the page's own layout, below the Today banner, and it stays in view as the page scrolls. The layout is three columns (panel, content, and an empty column as wide as the panel), so the content stays centred in the window. Below 1320 px there is no room for the empty column, and the content takes the rest of the row.
  - **Header:** Chat, Catechism, Saints and Calendar, with no divider after Saints.
  - **Language toggle:** set as a header link.
    - **"العربية" on English pages:** the system Arabic face (no Arabic font download, UI-011), one step smaller than the links (0.9375 rem) and at normal weight, so full-height Arabic letters read at the small capitals' size.
    - **"ENGLISH" on Arabic pages:** capitals at small-capital height (0.8125 rem, tracked). The Garamond file loaded on Arabic pages has no small capitals.
- **Removed:** the "Past chats" button and the UI-020 desktop drawer (`ChatSidebar drawer`) with their styles; the old two-word toggle's styles.
- **Checks:**
  - axe finds 0 violations in all 21 captured states. `ui-audit/tools/declutter.mjs` now captures, at 1440 and 390 px in English and Arabic: the home page (first screen, full page), the sidebar open and collapsed on desktop, and the drawer open on phones; the chat page likewise.
  - Screenshots are in `ui-audit/declutter/sidebar-before` and `sidebar-after` (not committed). The chat page's "Unable to load chat" notice in both sets comes from the check's mocked `/api`, which answers 404 for a single chat.
  - Tests: frontend 135; typecheck and lint clean.
- **Files changed:** `components/useChatSidebar.ts` (new), `components/ChatSidebar.tsx`, `components/Navbar.tsx`, `components/Icons.tsx`, `app/home-page.tsx`, `app/chat/chat-page.tsx`, `lib/i18n.ts`, `app/globals.css`, `ui-audit/tools/declutter.mjs`.

### UI-026: Streamed answers in the chat page: words fade in, tables wait for their last row, Stop, Jump to latest, one announcement
- **Date / Part:** 2026-09-23, streaming branch Step 3 (Vercel route and frontend)
- **Audit ref:** A6; the transport is GEN-007 and GEN-008
- **Context:** GEN-008 streams the answer from the backend. This entry covers how it reaches the reader: through the Next.js route, then into the chat page, without the page flickering, jumping or talking over itself.
- **Decision:**
  - **`POST /api/chat/stream`:** it runs the same checks, history and error replies as `/api/chat`, now shared in `lib/chat-proxy.ts`; `/api/chat` itself behaves as before.
    - A JSON reply from the backend (refusal, menu, error status) is saved and returned exactly as `/api/chat` does.
    - A stream is relayed one event at a time. When the backend's `done` arrives, the turn is saved, and the route sends its own `done` with `{conversation, userMessage, assistantMessage}`.
    - If saving fails, the answer is still delivered, unsaved (`conversation: null`), rather than replaced by an error after the reader has seen it.
    - The internal key stays in `lib/backend.ts`. `backendFetch` now accepts the caller's abort signal, so the route can apply its own timeouts: 20 s to the first byte, then 30 s of silence at most. `maxDuration` is 60 s.
    - The browser leaving (Stop or a closed tab) aborts the backend fetch, which stops generation (GEN-008).
  - **`lib/sse.ts`:** one SSE parser, used by the route and by the browser. Chunks may split an event, a line or an Arabic letter's bytes anywhere.
  - **`streamChatRequest`** (`lib/chat-client.ts`) resolves with the same saved turn as `sendChatRequest` and hands text to the page as it arrives.
    - It falls back to `/api/chat` when the stream route can't be reached, or answers 404, 405, 502 or 504.
    - It doesn't fall back on 400, 429, 500 or 503, which are the backend's real answers.
  - **Drawing:** text is collected in a ref and drawn at most every 50 ms; the first piece is drawn at once. `InteractiveAnswer` is memoised, so earlier answers aren't parsed again on every draw.
  - **Word fade-in** (`lib/rehype-stream-words.ts`, `StreamingAnswer`):
    - Every word gets its own span, at a stable position. A word keeps the `stream-word` class for its first 450 ms, a 0.4 s fade. After that only the class changes, so later renders never replay the fade. (First an opacity fade; since UI-027 a colour fade, which never fails contrast.)
    - With `prefers-reduced-motion`, the animation is off and text simply appears.
    - The drop cap is kept while streaming, since most answers end with sources.
  - **What is shown mid-stream** (`lib/stream-markdown.ts`):
    - A table at the end of the text is held back until a line that isn't a row follows it, or the stream ends. "Preparing the table…" stands in its place.
    - A citation marker cut in half ("[1", "[1,") is hidden until it closes.
    - Open `**` is closed, so bold never flashes as asterisks.
    - Citation numbers show unlinked while streaming. When `done` arrives, the answer is replaced by the usual `AnswerWithSources`, with linked `[n]` and the Sources list.
  - **Auto-scroll** (`useFollowBottom`, `lib/follow-scroll.ts`; replaced in UI-028, which no longer follows the text): the list follows the bottom while an answer is on its way, and once more when it completes, so the Sources list comes into view.
    - Scrolling up stops following at once, on wheel up, touch drag down or ArrowUp/PageUp/Home, or on a scroll that moves up out of the bottom 48 px. "Jump to latest" then appears above the composer.
    - Scrolling back down to the bottom, or pressing the button, resumes following.
    - The first version waited for the view to leave the bottom zone. In the browser, a wheel scrolls in small animated steps, and the next draw pulled the view back down every time, so upward input now counts directly.
  - **Stop:** while an answer is on its way, the send button becomes Stop in the same place, and focus stays on it.
    - Stop aborts the request. Text already shown stays, followed by "Stopped.".
    - A stopped answer is not saved, so it isn't part of the conversation or of the history sent with the next question. A turn in the database is always a finished answer.
  - **Errors:** an `error` event (or a dropped stream) removes the partial answer and shows the existing alert with Retry.
  - **Screen readers:** the answer in progress is `aria-busy`, and the message list isn't a live region, so nothing is read word by word. When the answer completes, the polite status region announces "Answer ready." followed by the answer as plain text (`plainAnswerText`: no citation numbers, Markdown marks or table rules). A stopped answer announces "Stopped."
  - **Arabic and phones:** the answer keeps `dir="auto"`. The fade is per word, so Arabic letters within a word stay joined. The Jump button is centred with physical `left` and `transform`, which reads the same both ways. Stop sits at the end of the composer in both directions.
- **Checks:**
  - Unit tests: frontend 135 → 161, with new files for the SSE parser, the stream view (table hold, citations, bold, announcement text), follow-scroll and the stream client (text in order, Stop before and during the reply, JSON replies, `error` events, a truncated stream, fallback and no-fallback statuses). Typecheck and lint are clean.
  - Browser, production build: a local PGlite database (so no hosted database was written to) and the real `api.py` with a scripted model (no OpenAI).
    - The stream arrived in 280 chunks; Next.js didn't buffer or compress it.
    - Table: 0 of 98 samples showed a partial table.
    - Stop kept 179 characters and saved 0 messages.
    - Jump to latest held the view, then brought it back.
    - A mid-stream error showed the alert with Retry.
    - A 404 from the stream route fell back to `/api/chat`.
    - Arabic at 390 px.
- **Files changed:**
  - `app/api/chat/stream/route.ts` (new), `app/api/chat/route.ts`
  - `lib/chat-proxy.ts`, `lib/sse.ts`, `lib/stream-markdown.ts`, `lib/follow-scroll.ts`, `lib/rehype-stream-words.ts` (new, with tests), `lib/chat-client.ts` (+ test), `lib/backend.ts`, `lib/chat-types.ts`, `lib/i18n.ts`
  - `components/StreamingAnswer.tsx`, `components/useFollowBottom.ts` (new), `components/InteractiveAnswer.tsx`, `components/ChatShell.tsx`, `components/Icons.tsx`
  - `app/chat/chat-page.tsx`, `app/globals.css`
- **Concept to learn:** *Rendering a stream without jank.* Batch updates to the frame rate, keep DOM positions stable so animations don't restart, hold back structures that are wrong until they are complete, and treat user input, not scroll position, as the sign of what the user wants. Search: "streaming markdown rendering LLM", "scroll anchoring chat auto scroll", "aria-busy live region".

### UI-027: Verification of streaming: time to first text against v2, a colour fade instead of an opacity one, axe at 0
- **Date / Part:** 2026-09-23, streaming branch Step 4 (verify)
- **Audit ref:** A6; checks GEN-007, GEN-008 and UI-026
- **Setup:**
  - A production build of the site on port 3217, with its database on a local PGlite (`ui-audit/tools/pg-server.mjs`). `.env.local` points at a hosted Neon database, so no conversation was written there.
  - The real backend ran locally: `CORPUS_VERSION=v2`, `OPENAI_CHAT_MODEL=gpt-4.1-mini` (the production model, GEN-005), the same internal key as the site.
  - The browser was Chromium via Playwright, driven by `ui-audit/tools/streaming.mjs` (new). `MODE=fake` runs the behaviour checks for free against `ui-audit/tools/fake_stream_backend.py` (new: the real `api.py` with a scripted model). `MODE=real` runs the five check questions.
  - Output goes to `ui-audit/streaming/`, which is git-ignored: screenshots, `.webm` recordings and `report.json`.
- **Time to first text vs the whole answer** (real v2 backend, one run each). "Backend" is the request log (`ttft_ms`, `total_ms`); "browser" is click to first text shown and to the finished answer. That includes the Next.js route, and for a new chat, creating the conversation first.

| request | first text, browser | first token, backend | whole answer, backend (≈ what `/chat` makes a reader wait) | whole answer, browser |
|---|---|---|---|---|
| English "What is prayer?" (1440) | 4.9 s | 4.4 s | 7.5 s | 7.8 s |
| Arabic "ما هي الصلاة؟" (390) | 4.4 s | 3.9 s | 5.8 s | 6.2 s |
| Table of the fasts (1440) | 3.9 s ("Preparing the table…") | 3.4 s | 6.2 s | 6.7 s |
| Refusal "Who won the 2018 FIFA World Cup?" | — (JSON, not streamed) | — | stream route 2.8 s; `/api/chat` 1.2 s | — |
| Saint menu "search saint: St. Gregory" | — (JSON, not streamed) | — | stream route 66 ms; `/api/chat` 62 ms | — |

  - **Streaming shows text 1.8–3.1 s before the whole answer is ready.** Before, nothing showed until then.
  - The time to first text is almost all spent before generation: the analysis call (1.5–2.7 s in these runs), retrieval (0.3–1.4 s) and the model's own first token (0.8–1.5 s).
  - `/chat` without streaming, same English question: 4.4 s for a shorter answer (1,111 characters vs 1,215), with a 1.0 s faster analysis call. OpenAI's latency varies that much between identical requests. So the table compares the first token and the whole answer *of the same request*.
  - The refusal's 2.8 s vs 1.2 s is the same variance: the analysis stage took 2.5 s vs 1.0 s. Refusals and menus take the same path either way and are not streamed.
  - **Tables:** this answer opened with its table. The reader saw "Preparing the table…" from 3.9 s, then the whole table at once.
  - The first run of the table case measured only `.stream-word`, so it timed out at 30 s (`firstWordMs: null`). The check now also counts the table note, and only the table case was rerun. The backend's own first run was fine: first token at 2.4 s, whole answer at 5.6 s.
- **Behaviour** (`MODE=fake`, run twice, both passing):
  - **Table:** "Preparing the table…" showed in 55–56 of 92–93 samples, and a partial table showed in 0. The finished table appears (5 rows) once the text after it begins.
  - **Stop:** 217 and 226 characters stayed on screen marked "Stopped." (announced). Send came back, and 0 messages were saved.
  - **Jump to latest** (390 px, English and Arabic): after scrolling up mid-answer the view held still, and the button appeared. Pressing it returned to the bottom (0 px away) and hid the button.
  - **Error mid-answer:** the partial text went, and the alert appeared with one Retry button.
  - **Fallback:** with the stream route answering 404, the page called `/api/chat` and showed the answer with its 4 sources.
  - **Reduced motion:** `animation-name: none`.
- **Found and fixed during verification:**
  - **The opacity fade failed axe `color-contrast`** on the 1–4 words caught mid-fade (5 nodes over 2 states). Words now fade in colour, from `--color-ink-faint` (at least 5.2:1 on every surface, UI-013) to their own colour. A word is readable from its first frame, and the fade stays gentle.
  - **A wheel over an answer that still fitted the view stopped following** and showed "Jump to latest" with nowhere to jump to. Once the answer grew, the view stayed at the top. Upward input now counts only when the list can scroll up (`scrollTop > 0`). The check also waits until the answer overflows before scrolling; before, it passed or failed depending on how long the answer was when it scrolled.
- **axe:** 0 violations in 13 states:
  - real: English streaming and done at 1440, Arabic at 390 (twice; the short answer had finished before the "streaming" scan), the table held and done;
  - fake: the table held, streaming with Stop, stopped, Jump to latest mid-answer in English and Arabic at 390, error with Retry.
- **Screenshots and recordings** (`ui-audit/streaming/`):
  - `real/english-1440-streaming.png`, `real/english-1440-done.png`, `real/english-1440.webm`;
  - `real/arabic-390-streaming.png` (a frame from the recording; this short answer had finished by the time the automatic capture ran), `real/arabic-390-done.png`, `real/arabic-390.webm`;
  - `real-table/table-1440-streaming.png` (the table note), `real-table/table-1440-done.png`, `real-table/table-1440.webm`;
  - `fake/*.png`.
- **Tests:** backend 194 (184 before the branch), frontend 161 (135). Typecheck and lint clean.
- **OpenAI spend (list prices, `eval/spend.py`):**
  - $0.0192 for this check: 4 streamed answers, 1 answer through `/chat`, and 2 analysis calls each for the refusal. The menu makes no model call.
  - About $0.0001 for one accidental call in Step 2: the app's startup replaced a test fake with the real client, and the prompt "q" got a two-word reply.
  - Total about $0.0193, under the $0.03 allowed. No quota or key errors.
- **Not checked here:** Railway's and Vercel's proxies (local only). After deploying, `curl -N` on `/api/chat/stream` should show events arriving one by one, and the backend log should show `endpoint="chat_stream"` with `ttft_ms`.
- **Files changed:** `ui-audit/tools/streaming.mjs`, `ui-audit/tools/fake_stream_backend.py`, `ui-audit/tools/pg-server.mjs` (new), `ui-audit/tools/README.md`, `.gitignore`, `orthodox-site/app/globals.css` (colour fade), `orthodox-site/components/useFollowBottom.ts` (upward input only when the list can scroll up).

### UI-028: The question is scrolled near the top once; the view stays put while the answer streams; a small "↓" jumps to the latest text
- **Date / Part:** 2026-09-23, speed branch Part A.1. This replaces UI-026's auto-scroll.
- **Owner's request:** following the text as it is written makes an answer hard to read from the beginning. Instead, scroll once so the question sits near the top, then leave the scroll position alone. When the answer runs past the bottom of the view, show a small, unobtrusive "↓" that scrolls to the latest text once, without following afterwards. The same in Arabic and on phones, allowing for the keyboard closing after send.
- **Decision** (`lib/answer-scroll.ts` for the rules, `components/useAnswerScroll.ts` for the DOM):
  - **One scroll per question:** on send, the list scrolls smoothly (instantly with reduced motion) so the question sits 96 px below the top of the view (72 px up to 720 px wide), as the old send scroll aimed to. After that, nothing moves the view while the answer streams.
  - **A spacer below the last message** makes that scroll possible while the answer is still short: without it, the question could only go as high as the bottom of the list allowed.
    - It is sized in the same frame as each piece of text, so it shrinks by exactly what the answer grows. The page height stays the same and nothing under the reader moves.
    - It is 0 once the answer is taller than the view. It is kept until the next question or conversation, so a short answer ends with empty space below, as in ChatGPT.
  - **The anchor follows the saved copies:** when the answer finishes, the optimistic messages are replaced by their saved copies, which have new IDs. The anchor moves to the saved question in the same update, so the spacer isn't lost and the view doesn't jump.
  - **Phones:** sending disables the composer, which closes the keyboard, and the view grows. Until the reader scrolls, any resize of the list or of the visual viewport (the keyboard, a rotation) puts the question back at its place. Wheel, touch and scrolling keys hand control to the reader.
  - **"↓"** is a 36 px round button above the composer with an arrow only (accessible name "Jump to latest"). It shows whenever the end of the text is more than 48 px below the view, during streaming or after. Pressing it scrolls to the end of the text once (not into the spacer); the view is not followed afterwards.
  - **Removed:** `useFollowBottom`, `lib/follow-scroll.ts` with its tests, and the old one-off scroll-to-question effect with its refs.
- **Checks:**
  - Unit tests: `lib/answer-scroll.test.ts` (7), covering the question's scroll position, a spacer that shrinks as the answer grows (so the page height stays constant), none for a long answer, one that grows when the keyboard closes, when "↓" shows, and where it scrolls to.
  - Browser (`streaming.mjs MODE=fake`, the scripted backend and a local database; no OpenAI). A second question was sent in a conversation that already had one answer, at 1440 and 390, in English and Arabic:
    - the question landed 96 px (1440) and 72 px (390) from the top of the view;
    - the view held still while the answer streamed;
    - "↓" appeared once the text ran past the view, moved the view down, and the view then stayed put while text kept arriving.
    - At 390 the view was 520 px tall at send (keyboard open) and 844 px straight after (closed), and the question still ended 72 px from the top.
  - axe: 0 violations in the four streaming states.
- **Files changed:** `lib/answer-scroll.ts` (+ test), `components/useAnswerScroll.ts` (new), `app/chat/chat-page.tsx`, `app/globals.css`; removed `components/useFollowBottom.ts` and `lib/follow-scroll.ts` (+ test); `ui-audit/tools/streaming.mjs` (scroll scenario), `ui-audit/tools/fake_stream_backend.py` (a longer English answer, so it runs past the view at 1440).
- **Concept to learn:** *Reading position vs "stick to bottom".* Chat interfaces that follow new text suit short, glanceable replies; for long answers read from the top, anchoring the question and reserving space below it keeps the reader's place stable. Search: "chat UI scroll anchoring question at top", "CSS overflow-anchor".

### UI-029: The saints pane streams its answer like the chat; every place that asks for an answer checked
- **Date / Part:** 2026-09-23, speed branch Part A.2
- **Owner's report:** clicking a saint on the Saints page shows its answer without the streaming animation.
- **Cause:** the saints pane (`loadSaintDetail` in `app/chat/chat-page.tsx`) asked `/api/saint-detail`, which called the backend's non-streaming `/chat` and returned the whole answer at once. UI-026 had only moved the chat's own send path to streaming.
- **Every place that produces an answer, and what it uses now:**

| Where | Path | Streams |
|---|---|---|
| Chat composer, the home page's example questions and composer (handed over through `sessionStorage`), Retry | `handleSendMessage` → `/api/chat/stream` | yes (UI-026) |
| Follow-up suggestions under an answer | `submitMessageOption` → `handleSendMessage` | yes |
| Saint names in an answer (bold, clickable) | `chat:insertAndSubmitText` → the composer → `handleSendMessage` | yes (a menu comes back whole) |
| Saint menu chips in the chat, and "Looking for a different St. X?" in the chat | `submitSaintLookup` / `submitNamesakes` → `handleSendMessage` | yes (menus come back whole) |
| Catechism prompts | `handleSendMessage` with mode `catechism` | yes |
| "Ask more about this saint" (saints pane) | `handleSendMessage` with mode `saints` | yes |
| **A saint in the Saints list** | `loadSaintDetail` → `/api/saint-detail` | **no → yes (this entry)** |
| **Calendar saint links** (`/chat?saint=…#saints`, CAL-005) | the same `loadSaintDetail` | **no → yes** |
| **Menu chips and "Looking for a different St. X?" inside the saints pane** | the same `loadSaintDetail` | **no → yes** |

  Nothing else asks the backend for an answer. The saint search suggestions and the saints list are lookups, not answers.
- **Decision:**
  - **`POST /api/saint-detail/stream`:** the same backend `/chat/stream` and the same relay as the chat. The relay now lives in `lib/stream-proxy.ts`, shared by both stream routes: the first-byte and silence timeouts, an abort when the browser leaves, and the no-buffering headers.
    - Its `done` event carries the saint detail `/api/saint-detail` returns (`lib/saint-detail.ts`, shared by both saint routes). Nothing is saved, as before.
    - A saint menu comes back whole as JSON.
  - **Client:** `streamChatRequest` and the new `streamSaintDetail` share one `streamRequest` (`lib/chat-client.ts`), with the same fallback rule: the whole-reply route on a network error or a 404, 405, 502 or 504. The unused `sendChatRequest` is gone; the fallback posts directly.
  - **Saints pane:** the same `StreamingAnswer` as the chat, so words fade in (not with reduced motion), tables wait for their last row, and citations and sources come with the final event.
    - A "Stop answering" button sits beside Close while the answer arrives. Stop keeps what arrived, marked "Stopped.".
    - Opening another saint, closing the pane, a new saints search or leaving the page stops the answer on its way.
    - The finished answer is announced once to screen readers ("Answer ready." and the text), as in the chat. The pane announced nothing before.
  - **Also:** while streaming, a list item or heading whose text hasn't arrived yet ("2.", "-", "##" alone on the last line) is held back, instead of flashing an empty bullet (`streamView`). The saints pane's first captures showed a bare "2.".
- **Checks:**
  - Unit tests: frontend 162 → 167.
    - `streamSaintDetail`: text in order, then the detail; a menu as JSON; the fallback to `/api/saint-detail`; Stop.
    - `streamView`: empty list and heading markers.
  - Browser (`streaming.mjs MODE=fake`, opened the way a calendar link opens the pane):
    - English at 1440 and Arabic at 390: words streamed, Stop showed while streaming and was gone after, with 4 and 3 sources, announced once.
    - Stop kept 140 characters and announced "Stopped.".
    - With the saints stream route answering 404, `/api/saint-detail` answered.
  - Real v2 backend (`streaming.mjs MODE=real CASES=saints`, gpt-4.1-mini):
    - "St. Athanasius the Apostolic" at 1440: first words 2.9 s after the page loaded, Stop shown while streaming, 5 sources.
    - "الأنبا بولا أول السواح" at 390: first words 4.4 s, 3 sources.
    - The English lookup skips the analysis call ("search saint:" is already a bare name); the Arabic one ran it (1.6 s).
    - axe: 0 violations in the 4 states.
    - OpenAI spend: $0.0109, of the $0.02 allowed for Part A.
  - axe: 0 violations in 13 states, across the chat scroll states (UI-028) and the saints pane streaming, finished and stopped. The first run found `scrollable-region-focusable` on the saints list. The scripted backend has no saints index, so the list held only an error message with nothing focusable; the check now serves three saint names to the browser, as the other audit tools do with fixtures.
- **Files changed:** `app/api/saint-detail/stream/route.ts`, `lib/stream-proxy.ts`, `lib/saint-detail.ts` (new); `app/api/saint-detail/route.ts`, `app/api/chat/stream/route.ts`, `lib/chat-client.ts` (+ test), `lib/chat-types.ts`, `lib/stream-markdown.ts` (+ test), `app/chat/chat-page.tsx`, `app/globals.css`; `ui-audit/tools/streaming.mjs` (saints scenarios, the saints-list fixture, and `load` rather than `networkidle` for a page that starts an answer on load: an open stream keeps the network busy until it ends).

## Code Cleanup

_(Deferred to a later phase; see AUDIT.md §3.)_

## Deployment & Config

### DEP-001: Model name and tuning knobs moved to environment variables
- **Date / Part:** 2026-09-15, Part A (commit 9989d1f)
- **Audit ref:** C24 (model hard-coded in three places)
- **Context:** `gpt-4o-mini` was hard-coded at every call site; timeouts, limits and caps did not exist.
- **Decision:** `OPENAI_CHAT_MODEL`, `ANSWER_MAX_TOKENS`, `OPENAI_TIMEOUT_SECONDS`, `OPENAI_MAX_RETRIES`, `MAX_QUESTION_CHARS`, `CHAT_RATE_LIMIT_PER_MINUTE`, `CHAT_GLOBAL_RATE_LIMIT_PER_MINUTE`, `INTERNAL_API_KEY`, `ENABLE_DEBUG`, all read once at import with safe defaults (`_env_int`/`_env_float`/`_env_flag` helpers ignore malformed values instead of crashing).
- **Why:** Lets you A/B a stronger generation model and tune limits from the Railway dashboard without a deploy. Defaults keep local behaviour unchanged except for the new auth requirement.
- **Files changed:** `api.py`, `.env.example`, `README.md`.
- **Concept to learn:** *Twelve-factor config:* configuration that varies between deployments belongs in the environment, not in code. Search: "12-factor app config".
- **Revisit if:** the number of knobs grows; then group them in a settings object (e.g. `pydantic-settings`).

## Calendar

### CAL-001: Calendar data source — compute feasts and fasts ourselves; saints from Katameros only once permission is given
- **Date / Part:** 2026-09-22, read-only evaluation before the calendar feature is built. No app code changed, no dependencies added to `orthodox-site`, 0 OpenAI calls. The libraries were installed and run in a scratch folder outside the repo.
- **Context:** The planned feature is a slim "Today" banner on the home page (today's saint(s) plus any feast or fast) and a `/calendar` page for Jan 2026 – Dec 2027, in English and Arabic. We compared four sources:
  1. the owner's `.ics` export;
  2. `coptic-calendar` (npm);
  3. coptic.io;
  4. Katameros, which was evaluated for readings but turned out to hold a synaxarium too.

  The `.ics` was not at `orthodox-site/data/calendar/`. The copy used here is `~/Downloads/Coptic Calendar 1743 Coptic.ics`, and it was not added to the repo.

#### Candidates at a glance

| | `.ics` (Coptic year 1743) | `coptic-calendar` 1.0.0 | coptic.io (`@coptic/core`, `@coptic/data`) | Katameros API |
|---|---|---|---|---|
| **Code license** | none (a Google Calendar export) | Unlicense (public domain) | MIT, but `LICENSE.md` names no copyright holder | MIT, "Copyright (c) 2022 katameros" |
| **Content license** | none stated; author unknown | none. Synaxarium text is third-party (see provenance) | none. The data package also bundles the NKJV, which is copyrighted, so the MIT label does not reliably describe the content | none. The database also holds copyrighted Bibles (NKJV, Einheitsübersetzung, HSV, CEI 2008), so again the MIT label does not cover the content |
| **Synaxarium provenance** | unknown. Created 2026-08-27 from a CSV (`CSVConvert` UIDs) | A code comment says St-Takla.org. The English entries are identical, entry for entry on all 366 days, to coptic.io's copy of CopticChurch.net | Scraped from CopticChurch.net (`scripts/scrape-arabic-synaxarium.ts`; English and Arabic full text). English and Arabic were paired using a DeepSeek LLM script | Not stated. Commit history shows English added 2022-12, Arabic 2023-02, both reworked 2026-09. Arabic titles follow the Church's standard Arabic synaxarium wording (as on St-Takla). Unconfirmed |
| **Feast/fast provenance** | none (no feasts) | Rules citing SUS Copts, St-Takla, Coptic Heritage, Tasbeha.org | Rules citing CopticChurch.net and St-Takla, validated by a script against CopticChurch.net | Feast list checked against St-Takla and the LA diocese (commit `22693d9`) |
| **Maintenance** | one-off file | One person (22 commits, 1 star). Created Apr 2026, last commit 2026-06-06. Only release is 1.0.0 (Apr 19); 4 later fixes are unpublished. 0 open issues | Essentially one person (182 of 186 commits). Very active (commits today). No releases, and `@coptic/*` is **not published on npm** (issue #24, open since 2023). 2 open issues, 2 open PRs | One person (169 commits). Active: 78 commits in the last year, the last on 2026-09-15; readings bugs are fixed within days. 1 open issue |
| **Integration** | static file | ESM-only, zero deps, TypeScript types. Core is 4.4 KB min (1.9 KB gz); with the synaxarium and occasions plugins, 56 KB min (16 KB gz). Fully offline | Core has zero deps, 4.9 KB min (2.0 KB gz), and would have to be vendored from source. Synaxarium names only (EN+AR) are 83 KB (25 KB gz); the full text is 3.3 MB. A public API (`api.coptic.io`) is up | .NET + a 94 MB SQLite database, no npm/TS package. Offline use means a one-time export of the titles (EN+AR 149 KB, 30 KB gz). A public API (`api.katameros.app`) is up |
| **Languages** | Coptic script only | English synaxarium only (the Arabic call silently returns English); Arabic for 23 feast/fast names | English and Arabic synaxarium (Arabic misses 13 Baba) | English, Arabic and 7 more; the titles in different languages are linked to the same entry by a shared story id |
| **Can we use it publicly (non-commercial)?** | Unclear; ask the owner where it came from | Code yes. Synaxarium text **unclear** | Code yes, with the MIT notice. Synaxarium text **unclear** | Code yes, with the MIT notice. Synaxarium text **unclear** |

The upstream sites state no license either. CopticChurch.net's synaxarium pages carry only "Sponsored by St. Mark's Coptic Orthodox Church, Jersey City, NJ", and the St-Takla pages fetched showed no terms of use. **None of the candidates has clear licensing for the saint lists.** The feast and fast dates are different: they are facts produced by a published rule (the computus plus fixed Coptic dates), so we can compute them without depending on anyone's data.

#### Accuracy: Gregorian ↔ Coptic conversion
- The `.ics` has 1,095 events:
  - 366 date markers (`* Thoout 1, 1743 *` … `* Nesi 6, 1743 *`), one per day from 2026-09-11 to 2027-09-11;
  - 727 saint entries across 360 days (8 days have none);
  - 2 stray events outside the year: 2026-03-26 "Abba Sarapamon the metropolitan" and 2026-06-18 "Abba Michael the hegumen".
- The test covered all 366 markers plus 4 boundary dates: Thoout 1 1744 = 2027-09-12 (1743 is a leap year, since Nesi 6 exists), Thoout 1 1742 = 2025-09-11, Thoout 1 1740 = 2023-09-12, and 2028-01-01. Every date was checked both ways.
- **Result: 0 mismatches for both libraries in both directions**, including the Sep 11/12 leap-year shift. The published `coptic-calendar` and its GitHub HEAD agree.
- **Time zone traps (integration note).** Each library reads a JS `Date` differently.
  - `coptic-calendar` reads UTC fields. A local-midnight `Date` is off by one day in every zone east of UTC (370/370 wrong in Cairo and Auckland), and a local-noon `Date` still fails in Auckland (190/370).
  - coptic.io reads local fields, so `new Date('2026-09-11')` is off by one in every zone west of UTC (370/370 wrong in Toronto).
  - Rule for the build: always pass a plain `YYYY-MM-DD` string/triple for a date chosen in one explicit time zone. Never pass a `Date` object.

#### Accuracy: synaxarium on 15 sample days
The `.ics` names are Coptic; they were transliterated and glossed by hand. `coptic-calendar` and coptic.io share one English list (CopticChurch.net), so they have one column. ✓ = the `.ics` saint is present; ✗ = missing. The encyclopedia column is the English *Encyclopedia of the Saints and Fathers of the Church* in our corpus, where the entry states a date.

| Coptic day (1743) | Date | `.ics` (transliterated) | `coptic-calendar` / coptic.io EN | coptic.io AR | Katameros EN/AR | Encyclopedia |
|---|---|---|---|---|---|---|
| Thoout 1 | 2026-09-11 | Bartholomew the apostle; Job the righteous; Pope Mark (V); Pope Milius | Nayrouz, Bartholomew ✓, Milius ✓; Job ✗, Mark V ✗ | all 4 ✓ + Nayrouz | all 4 ✓ + Nayrouz | Milius "reposed in the 1st of Tout" ✓ |
| Thoout 26 | 2026-10-06 | John the Baptist | Annunciation of John's birth ✓ | ✓ | ✓ | — |
| Paope 12 | 2026-10-22 | Pope Demetrius I; Archangel Michael; Matthew the evangelist | all 3 ✓ | all 3 ✓ | all 3 ✓ | entry gives no date |
| Hathor 12 | 2026-11-21 | John the Syrian; Michael | Michael ✓; John ✗ | both ✓ | both ✓ | — |
| Hathor 27 | 2026-12-06 | Apa Victor the martyr; James the Persian | James ✓; Victor ✗ | James ✓; Victor ✗ | James ✓; "consecration of the church of St. Victor" ✓ | James the Mangled "on the 27th of Hator" ✓ |
| Koiahk 29 | 2027-01-07 | Martyrs of Akhmim (the `.ics` omits the Nativity) | Nativity only; Akhmim ✗ | Nativity + Akhmim ✓, plus 2 article titles scraped as saints | Nativity + Akhmim ✓ | — |
| Tobe 11 | 2027-01-19 | Pope John (VI); Pope Benjamin (II) | Theophany only; both ✗ | Theophany + both ✓ | Theophany + both ✓ | entries give no date |
| Meshir 8 | 2027-02-15 | Simeon the elder | Presentation in the Temple only; Simeon ✗ | Presentation + Simeon ✓ | Presentation + Simeon ✓ (+ modern Coptic martyrs) | entry gives no date |
| Paremhotep 29 | 2027-04-07 | (none) | Annunciation; Resurrection | same | same | — |
| Parmoute 23 | 2027-05-01 | St George | ✓ | ✓ | ✓ | one sentence in the George entry says "23rd of … Baramhat"; needs a look |
| Pashons 24 | 2027-06-01 | (none) | **"St. Simon the Stylite"** | Entry of the Lord into Egypt; Habakkuk; Pishnouna | same as coptic.io AR | — (SUS also lists "Entry of the Lord into Egypt" on Jun 1, so the English list looks wrong here) |
| Paone 12 | 2027-06-19 | Pope Cyril II; Pope Justus; Michael | all 3 ✓ + Euphemia | Michael ✓ + Euphemia; Cyril II ✗, Justus ✗ | all 3 ✓ + Euphemia | Cyril II ✓, Justus ✓, Euphemia ✓ (all "12th of Paona") |
| Epep 5 | 2027-07-12 | Peter & Paul; Mark the martyr | Peter & Paul ✓; Mark ✗ | Peter & Paul ✓; Mark ✗ | both ✓ ("Mark, governor of el-Borolus, father of St. Demiana") | — |
| Mesore 16 | 2027-08-22 | the Virgin Mary (Assumption); Pope Matthew IV | both ✓ | both ✓ | both ✓ | — |
| Nesi 3 | 2027-09-08 | Pope John (XIV); Andrianus and companions; Archangel Raphael | all 3 ✓ | all 3 ✓ | all 3 ✓ | — |
| **`.ics` saints found** | | **27** | **18 / 27** | **23 / 27** | **27 / 27** (Victor through his church's consecration) | |

Across the whole year, the English list has 697 entries, coptic.io's Arabic 856 (14 with raw HTML entities such as `&quot;`), and Katameros 868 English / 867 Arabic. The `.ics` is not complete either: it leaves out feasts by design, and on Paone 12 it omits Euphemia, whom all three sources and the encyclopedia give.

#### Accuracy: feasts and fasts, 2026 and 2027
The reference is suscopts.org/coptic-orthodox/fasts-and-feasts, rendered with Playwright for 2026, 2027 and 2028.

| | SUS 2026 | SUS 2027 | `coptic-calendar` | coptic.io |
|---|---|---|---|---|
| Nativity | Jan 7 | Jan 7 | ✓ ✓ | ✓ ✓ |
| Theophany | Jan 19 | Jan 19 | ✓ ✓ | ✓ ✓ |
| Jonah's Fast | Feb 2–4 | Feb 22–24 | ✓ ✓ | ✓ ✓ |
| Great Lent | Feb 16 – Apr 3 | Mar 8 – Apr 23 | start ✓ ✓; "Great Lent" runs on to Holy Saturday (Apr 11 / May 1) | start ✓ ✓; season ends Apr 4 / Apr 24 (takes in Lazarus Saturday), then "Holy Week" |
| Pascha | Apr 12 | May 2 | ✓ ✓ | ✓ ✓ |
| Pentecost | May 31 | Jun 20 | ✓ ✓ | ✓ ✓ |
| Apostles' Fast | Jun 1 – Jul 11 | Jun 21 – Jul 11 | ✓ ✓ | ends **Jul 12** both years (the feast day itself) |
| St. Mary's Fast | Aug 7–21 | Aug 7–21 | ✓ ✓ | ✓ ✓ |
| Nativity Fast (extra check) | Nov 25 – Jan 6 | Nov 26 – Jan 6 | ✓ ✓ | ✓ ✓ |

Mismatches:
1. **Great Lent end date** is off in both libraries: `coptic-calendar` runs it 8 days long, coptic.io 1 day. Both get the start right.
2. **Apostles' Fast** ends a day late in coptic.io.
3. **Annunciation 2026** (Apr 7, Tuesday of Holy Week): SUS says "Not celebrated this year". Both libraries still show it.
4. **Lazarus Saturday and the Holy Pascha days** are listed by SUS. `coptic-calendar` has neither; coptic.io has only a "Holy Week" season.
5. **Outside our range, but a trap:** SUS gives the Nativity in 2028 as Jan 7–8 and ends the 2027 Nativity Fast on Jan 6. Both libraries put the Nativity only on Jan 8, 2028 (Koiahk 29 after the 1743 leap year). This must be handled before the calendar extends past 2027.

#### Name quality (10 days, first entry of each; the `.ics` first entry is not always the same saint)

| Day | `.ics` (Coptic → transliterated) | EN: `coptic-calendar` = coptic.io | AR: coptic.io | EN: Katameros | AR: Katameros |
|---|---|---|---|---|---|
| Paope 3 | ⲡⲓⲁⲅⲓⲟⲥ Ⲓⲱⲁⲛⲛⲏⲥ ⲡⲓⲙⲁⲧⲟⲓ (piagios Iōannēs pimatoi) | The Departure of St. Simon II, 51st Pope of the See of St. Mark. | نياحة البابا سيمون الثاني 51 سنة 546ش | The Departure of St. Siemon II, 51st Pope of the See of St. Mark | نياحة البابا سيمون الثاني البطريرك الحادي والخمسون من بطاركة الكرازة المرقسية |
| Hathor 8 | ⲡⲉⲛⲓⲱⲧ Ⲛⲓⲕⲁⲛⲇⲣⲟⲥ ⲡⲓⲟⲩⲏⲃ (peniōt Nikandros pioyēv) | The Commemoration of the Four Incorporeal Beasts | تذكار الاربعة حيوانات الغير متجسدين | The Commemoration of the Four Incorporeal Creatures | تذكار الأربعة المخلوقات غير المتجسدين |
| Koiahk 4 | Ⲁⲛⲇ̀ⲣⲉⲁⲥ ⲡⲓⲁ̀ⲡⲟⲥⲧⲟⲗⲟⲥ (Andreas piapostolos) | The Martyrdom of St. Andrew the Apostle, the Brother of St. Peter. | استشهاد القديس اندراوس أحد الاثنى عشر رسولا | The Martyrdom of St. Andrew, One of the Twelve Apostles | إستشهاد القديس أندراوس أحد الاثنى عشر رسولاً |
| Tobe 22 | ⲁⲃⲃⲁ Ⲁⲛⲧⲱⲛⲓⲟⲥ … (avva Antōnios pikhēvs nte timetmonachos) | The Departure of St. Anthony the Great (Antonius). | نياحة القديس العظيم انبا **انطونبوس** اب جميع الرهبان (typo) | The Departure of the Great Saint Anba Anthony (Antonius) the Father of all Monks | نياحة القديس العظيم الأنبا أنطونيوس أب جميع الرهبان |
| Meshir 15 | Ⲁⲃⲃⲁ ⲡⲁⲫⲛⲟⲩⲑⲓ ⲡⲓⲙⲟⲛⲁⲭⲟⲥ (Avva Paphnoythi pimonachos) | The Departure of St. Zechariah, the Prophet. | نياحة القديس بفنوتيوس الراهب | The Departure of St. Paphnoute, the Monk | نياحة القديس بفنوتيوس الراهب |
| Paremhotep 9 | Ⲁⲃⲃⲁ Ⲕⲟⲩⲑⲱⲛ ⲡⲓⲟ̀ⲙⲟⲗⲟⲅⲓⲧⲏⲥ (Avva Koythōn piomologitēs) | The Departure of St. Konan. | نياحة القديس **كوش** المجاهد العظيم | The Departure of St. Konan, the Confessor | نياحة القديس كونن المعترف |
| Parmoute 17 | Ⲓⲁⲕⲱⲃⲟⲥ ⲡϣⲏⲣⲓ ⲛ̀ⲅⲉⲃⲉⲇⲉⲟⲥ (Iakōvos pshēri ngevedeos) | The Martyrdom of St. James the Apostle Brother of St. John the Apostle. | استشهاد القديس يعقوب بن زبدى الرسول | The Martyrdom of St. James One of the Twelve Apostles and the Brother of St. John the Beloved | أستشهاد القديس يعقوب الكبير أحد الإثني عشر رسولاً وشقيق القديس يوحنا الحبيب |
| Pashons 2 | ⲡⲓⲁ̀ⲅⲓⲟⲥ Ⲫⲓⲗⲟⲑⲉⲟⲥ ⲡⲓⲙⲁⲣⲧⲩⲣⲟⲥ (piagios Philotheos pimartyros) | The Departure of the righteous Job. | نياحة أيوب البار | The Departure of the Righteous Job | نياحة أيوب الصديق |
| Paone 20 | ⲁⲃⲃⲁ Ⲕ̀ⲗⲟϫ ⲡⲓⲡ̀ⲣⲉⲥⲃⲩⲧⲉⲣⲟⲥ (avva Kloj pipresvyteros) | The Departure of Elisha, the Prophet. | نياحة القديس اليشع النبى | The Departure of Elisha, the Prophet | نياحة القديس أليشع النبى |
| Epep 26 | ⲡⲁⲡⲁ ⲁⲃⲃⲁ Ⲧⲓⲙⲟⲑⲉⲟⲥ ⲡⲓϩⲟⲩⲓⲧ (papa avva Timotheos pihoyit) | Repose of St. Joseph the **Carpentar** | نياحة القديس يوسف البار | The Departure of the Upright St. Joseph, the Carpenter | نياحة القديس يوسف البار، خطيب القديسة مريم العذراء وخادم سر التجسد الإلهي |

`coptic-calendar` has no Arabic synaxarium to sample. Its Arabic covers only 23 occasion names, which read correctly: عيد النيروز، عيد الصليب، عيد الميلاد، عيد الختان، عيد الغطاس، عرس قانا الجليل، دخول السيد المسيح الهيكل، عيد البشارة، دخول السيد المسيح أرض مصر، عيد التجلي.

In summary:
- The CopticChurch.net English list is terse and has typos ("Carpentar", "Incorporeal Beasts", "Lord christ").
- coptic.io's Arabic is fuller but raw: typos, HTML entities, pope numbers and years pasted into titles, and article headings scraped as if they were saints. Its English and Arabic are separate lists, and they disagree on some days (e.g. Meshir 15).
- Katameros is the cleanest in both languages, and its English and Arabic are linked entry by entry.

#### Decision (recommendation)
1. **Feasts, fasts and the Coptic date: compute them ourselves at build time into a static JSON** for Jan 2026 – Dec 2027. There are no runtime calls and nothing third-party ships to the browser.
   - Use `coptic-calendar` (Unlicense, zero deps, TS) as a build-time dependency, or copy its ~100 lines of conversion and computus. It matched SUS on every date except the end of Great Lent, and it has Arabic names for the feasts.
   - Add our own rules for:
     - Great Lent ending the Friday before Lazarus Saturday;
     - Lazarus Saturday and the Holy Pascha days;
     - the Annunciation not being celebrated when it falls in Holy Week or the Holy Fifty;
     - the Jan 7 Nativity after a Coptic leap year (needed from 2028).
   - Then diff the generated file against the SUS tables for 2026 and 2027 in a test.
2. **Saints: the Katameros synaxarium titles (English + Arabic) are the best data.** They found all 27 `.ics` saints on the sample days, agree with the encyclopedia wherever it gives a date, and have linked, clean bilingual titles.
   - They should be exported once from its SQLite into a static JSON (~30 KB gz), **only after written permission** from the maintainer, who should also state where the text came from.
   - Until then, the banner and `/calendar` show the Coptic date, feasts and fasts only, with no saint names.
3. **coptic.io: not recommended.** It isn't on npm, and its Arabic needs cleaning. It adds nothing over (1) and (2), and its synaxarium has the same unclear rights.
4. **The `.ics`: keep it as a cross-check only.** It has Coptic-script names only, covers one year, has no license and an unknown author.
5. **Katameros daily readings (optional add-on): defer.** Showing them means either a runtime call to `api.katameros.app` or bundling Bible text, and the English Bible there is the NKJV, which needs Thomas Nelson's permission. Reading *references* only (e.g. "Luke 1:1–25") are facts and could be added later from the same export, with the same permission.

#### Attribution to show
- `coptic-calendar`: none required (Unlicense). A courtesy credit on the credits page is still good practice.
- Katameros (if permission is given): "Saints of the day: Katameros synaxarium (katameros.app), used with permission". Also include the MIT notice "Copyright (c) 2022 katameros" wherever the exported data file lives, plus whatever upstream credit the maintainer names (e.g. St-Takla.org).
- Dates: "Feast and fast dates checked against the Coptic Orthodox Metropolis of the Southern United States calendar" is a courtesy credit, not a license requirement.

#### What to ask permission for
1. **Katameros maintainer (Pierre Said, github.com/pierresaid):** permission to publish the English and Arabic synaxarium *titles* (not the stories) as a static file on a non-commercial educational site, the required credit line, and where the text came from.
2. **If he points upstream:** CopticChurch.net (St. Mark's Coptic Orthodox Church, Jersey City) and/or St-Takla.org, for the same use.
3. **The `.ics` author,** via the owner: who produced it, and whether its Coptic names may be shown. This matters only if we ever want Coptic-script names.

#### Needs the priest's review before launch
- Which saint(s) the banner shows on days with 3–7 entries, and whether monthly commemorations (Michael on the 12th, the Virgin on the 21st, "Annunciation, Nativity and Resurrection" on the 29th) count.
- English spellings and titles (Katameros uses forms such as "Siemon II", "Youannes", "Kyrillos") and the Arabic titles.
- The Great Lent, Holy Week and Holy Pascha labels; the Annunciation-in-Holy-Week rule; whether to show Paramoun days, the Jonah's Fast feast day and the Wednesday/Friday fasts.
- When "today" rolls over: at midnight or at sunset (the liturgical day), and in which time zone.
- The discrepancies found above:
  - Pashons 24 (Simon the Stylite vs the Entry into Egypt);
  - Hathor 27 (the `.ics` has St Victor);
  - Epep 5 (Mark of el-Borolus);
  - the encyclopedia's "23 Baramhat" sentence in the St George entry.
- **Concept to learn:** *Facts vs expression in copyright.* A feast date computed from a rule is a fact anyone can use. A particular translated list of saint titles is someone's compilation and wording, and may be protected. An MIT or Unlicense file on the code does not grant rights to data its author scraped from elsewhere. Search: "copyright facts vs expression", "database compilation copyright", "license of scraped data".
- **Revisit if:** the Katameros maintainer declines or can't confirm provenance. Then either ask CopticChurch.net directly or build our own title list from the `.ics` and the encyclopedia with the priest. Also revisit if the calendar extends beyond 2027 (the Jan 7 Nativity rule becomes mandatory).

### CAL-002: Feasts and fasts generated from written-out rules into a static file; coptic-calendar only converts dates
- **Date / Part:** 2026-09-22, calendar Step 1 (branch `calendar`)
- **Context:** CAL-001 recommended computing the calendar ourselves rather than trusting either library's feast list. Both libraries got the core dates right but differed from the SUS table on the end of Great Lent, the Apostles' Fast, Holy Week and the 2026 Annunciation.
- **Decision:**
  - `coptic-calendar@1.0.0` (public domain) is a **devDependency**. It is used only for Gregorian ↔ Coptic conversion and the Alexandrian computus (Pascha), always called with plain `YYYY-MM-DD` strings.
  - Every other rule is spelled out in `orthodox-site/lib/calendar/rules.ts`, so it can be read against the Church's tables:
    - **Fixed feasts** on Coptic dates: Nayrouz; the Feast of the Cross (Thout 17–19, three days as SUS lists it); Circumcision; Theophany; Cana; the Entrance into the Temple; the Appearance of the Cross (Paremhat 10); the Annunciation; St. Mark (Parmoute 30); the Entry into Egypt; the Apostles; the Transfiguration; the Assumption.
    - **Days counted from Pascha:** the Jonah feast, Holy Week days, Thomas Sunday, the Ascension and Pentecost.
    - **Fasts:** Jonah; Great Lent; the Holy Week fast; the Apostles (to Epip 4); St. Mary (Mesori 1–15); the Nativity (Hathor 16 to Jan 6).
    - **Fast-free periods:** the Holy Fifty, and from the Nativity to Theophany.
    - **Wednesday/Friday fasts:** every Wednesday and Friday, except in a fast-free period, on a major feast of the Lord, or inside a longer fast.
  - The four CAL-001 rules:
    1. Great Lent ends at Pascha − 9, the Friday before Lazarus Saturday. Lazarus Saturday to Holy Saturday is its own "Holy Week fast".
    2. Lazarus Saturday, Monday–Wednesday of Holy Pascha, Covenant Thursday, Good Friday and Joyous Saturday are listed.
    3. The Annunciation is not celebrated between Palm Sunday and Holy Saturday. The day records it under `suppressed`, so the page can say why.
    4. The Nativity is always Jan 7. When Kiahk 29 falls on Jan 8 (the year after a Coptic leap year, next in 2028), both days are marked and the fast still ends Jan 6.
  - `npm run calendar:generate` writes `lib/calendar/data/calendar-2026-2027.json`. It has 730 days, one per line so rule changes show up as readable diffs, and it is committed. The site reads the JSON only. Month names are copied from the library's locale (a test keeps them in step), except that Arabic Nasie is spelled نسيء (the library has نسيئ).
  - **Tests** use Node's built-in runner (`npm test`, Node 24 runs the `.ts` files directly), so no test framework was added. `tsconfig.json` gains `allowImportingTsExtensions` because Node needs the `.ts` in import paths. 110 tests pass:
    - every row of the SUS 2026 and 2027 tables, stored as a fixture (`lib/calendar/fixtures/sus-2026-2027.json`), including each fast's day before and day after;
    - the four rules;
    - Wednesday/Friday and fast-free days;
    - conversion edge cases (Thout 1 on Sep 11 or 12, Nasie 6 in 1743, round trips);
    - a day-by-day continuity check over both years;
    - the whole calendar regenerated in five time zones (UTC−12 to UTC+14) with identical output;
    - a check that the committed JSON is up to date with the rules.
- **Chosen without the priest, for his review:**
  - the name "Holy Week fast" for Lazarus Saturday to Holy Saturday;
  - Wednesday/Friday fasts kept on Nayrouz and minor feasts;
  - Paramoun days not shown;
  - Joyous Saturday listed;
  - English month spellings (Thout, Paopi … Mesori, from the library).
- **Why:** the rules are few and well known. Written out, they can be tested line by line against the SUS table and corrected in one place. A library's feast list would hide them.
- **Files:** `orthodox-site/lib/calendar/{rules,dates,observances,types,coptic-months}.ts`, `lib/calendar/data/calendar-2026-2027.json`, `lib/calendar/fixtures/sus-2026-2027.json`, `lib/calendar/calendar.test.ts`, `scripts/calendar/generate-calendar.ts`, `package.json`, `tsconfig.json`.
- **Concept to learn:** *Computus.* Pascha is computed from a fixed 19-year lunar cycle on the Julian calendar, not from astronomy, so it can be generated for any year. Search: "Alexandrian computus", "Julian Paschalion".
- **Revisit if:** the calendar is extended past 2027. Rerun the generator with a new range and add that year's SUS table to the fixture.

### CAL-003: Katameros saint titles extracted once into one swappable file, linked conservatively to our saints index
- **Date / Part:** 2026-09-22, calendar Step 1
- **Context:** The owner decided to use Katameros's English and Arabic saint titles now: bundled statically, titles only, credited with a link, while a courtesy permission request is pending. The data must be removable or replaceable without touching UI code.
- **Decision:**
  - `npm run calendar:saints -- <katameros-api clone>` reads the `Synaxarium` table from the repository's SQLite file with Node's built-in `node:sqlite`, reading the **Title column only**. English (LanguageId 2) and Arabic (3) are paired by `StoryId`. The output is `lib/calendar/data/saints.katameros.json`. The live API is never called.
  - **Source recorded in the file:** repository, commit `87461f3266697d927a5f58792605ef6b9e25224c` (2026-09-15), file, table, license note, permission status, and the saints-index snapshot it was linked against.
  - **Contents:** 366 days, 868 entries; one entry (Habib Girgis) has no Arabic title and shows its English one. Each entry is classified so the UI can choose what to show:
    - 709 **saints**;
    - 28 **monthly** commemorations (Michael on the 12th, the Virgin on the 21st, the three feasts on the 29th);
    - 117 **events** (consecrations, relic translations, councils);
    - 14 **feasts** that the rules already mark, which the UI hides so a feast doesn't appear twice.
  - **Swappable:** UI code reads saints only through `lib/calendar/calendar.ts` → `commemorationsFor()` and `view.ts`. Replacing or removing the source means a new JSON of the same shape (or an empty `days`) plus the credit line.
  - **Links to our saints index.** The index is built at runtime from Chroma, so `scripts/calendar/snapshot-saints-index.py` snapshots it (1,363 English and 1,937 Arabic names) through the backend's own index builders. It reads the local store only, creates no OpenAI client and makes no backend changes. The matcher is deliberately strict, because a wrong link is worse than none:
    - every word of the index name must appear in the title;
    - both must start with the same name;
    - pope numbers must agree (Arabic ‑ون/‑ين endings unified);
    - an entry that is only "name + the Bishop/Monk…" must match exactly unless the name is unique in both the index and the synaxarium;
    - a one-word name must match the whole title and be unique;
    - an index name claimed by two different saints is dropped.

    Early drafts linked John the Baptist to "St. John", Pope Macarius II to Macarius of Alexandria, and St. Justus to St. Samuel; the rules above exclude all three. 21 hand-checked overrides with reasons (`scripts/calendar/saint-link-overrides.json`) cover major saints the index spells differently, such as the Virgin Mary, St. George, St. Mark, St. Athanasius, St. Mina and St. Shenouda. The extractor fails if an override names something not in the index. **Result: 87 English and 165 Arabic links.**
  - **Tests:**
    - the 15 CAL-001 sample days;
    - Pashons 24 shows the Entry of the Lord into Egypt, and Simon the Stylite is on Pashons 29;
    - the feast isn't repeated in the commemorations;
    - source and commit present;
    - titles only;
    - every link exists in the snapshot and belongs to a saint;
    - the hand-checked links.
- **Why:** one file with its provenance in it keeps the licensing question contained. Titles alone are the minimum that serves the feature.
- **Files:** `orthodox-site/scripts/calendar/{extract-katameros-saints.ts,snapshot-saints-index.py,saints-index.snapshot.json,saint-link-overrides.json,node-sqlite.d.ts}`, `lib/calendar/data/saints.katameros.json`, `lib/calendar/saints.test.ts`.
- **Concept to learn:** *Precision over recall in entity linking.* When a false match misleads the reader, tune the matcher to link fewer items, and link those correctly. Search: "entity linking precision recall trade-off".
- **Revisit if:** the maintainer answers (update `source.permission`, or remove the file); the saints index is rebuilt (retake the snapshot and rerun the extractor); or the priest wants more saints linked (add overrides).

### CAL-004: "Today" comes from the visitor's clock, picked before first paint; the day boundary and saint order are one setting each
- **Date / Part:** 2026-09-22, calendar Step 2
- **Context:** The server can't know the visitor's date. At any instant the world spans three civil dates (UTC−12 to UTC+14). Rendering "today" on the client only would either flash or shift the layout. Rendering it on the server would show the wrong day to many visitors.
- **Decision:**
  - The server renders every date that is "today" somewhere right now (`possibleTodays`: yesterday, today and tomorrow in UTC; one more with a sunset boundary). All but its own UTC date are `hidden`.
  - A few lines of inline script placed right after the strip compute the visitor's local date and un-hide that one before the first paint.
  - After hydration, `useSyncExternalStore` reads the same local date. The server snapshot equals the server's choice, so there is no hydration mismatch. React then agrees with what the script already did, and the date is rechecked every minute so an open tab rolls over.
  - The script is generated from the same function the component uses (a test runs both). A client-side navigation to `/` skips the script and gets the right date straight from the component.
  - `lib/calendar/config.ts` holds the two choices left to the priest:
    - `DAY_BOUNDARY`: `"midnight"` (default) or `"sunset"`. Sunset is approximated as 18:00 local time, because we don't ask for the visitor's location.
    - `BANNER_SAINT_ORDER`: `"source"` (default, Katameros's order) or `"linked-first"`.
  - In both orders, the day's saints come before the monthly commemorations and events.
  - `lib/calendar/view.ts` turns a day into a plain bilingual object. Pages pass the browser only the days they show; the 250 KB of JSON stays on the server.
- **Verified:** production build, Playwright with the browser's time zone set to Toronto, Kiritimati (UTC+14), Pago Pago (UTC−11) and Tokyo:
  - the visible day always equals the local date;
  - no hydration warnings;
  - layout shift 0 to 0.002 across runs;
  - no horizontal overflow at 390 px.
- **Files:** `orthodox-site/lib/calendar/{today,config,view,strings}.ts`, `lib/calendar/today.test.ts`.
- **Concept to learn:** *Hydration and time.* Server HTML must match the first client render, so values that differ between the two (time, locale, random numbers) need a server snapshot plus a client update, or a pre-paint script. Search: "useSyncExternalStore getServerSnapshot", "hydration mismatch dates".
- **Revisit if:** the priest chooses sunset. Then consider asking for or estimating the visitor's location for true sunset times.

### CAL-005: Today strip at the top of the home page, linking the date to the calendar and the saint to our saints index
- **Date / Part:** 2026-09-22, calendar Step 2
- **Decision:**
  - A slim strip between two hairlines sits above the wordmark on the home page (`components/calendar/TodayBanner.tsx` on the server, `TodayBannerStrip.tsx` in the browser). It uses the existing book style: a small-caps rubric "Today", the Coptic date in the display face, then the day's feasts and its fast or fast-free period. The day's first commemoration is below it in the reading face, followed by "and N more" (Arabic uses its dual and plural forms).
  - The date links to `/calendar?d=YYYY-MM-DD`.
  - When the first saint has an index entry in the page's language, its title links to `/chat?saint=<index name>#saints`. The chat page now opens that saint's entry when it sees `?saint=`. An "Ask about this saint" button then starts a chat with "Tell me about {name}." (Arabic "حدثني عن {name}.", which reads correctly for men and women). It uses the same pending-question hand-off as the home page's question box, now shared in `lib/pending-chat.ts`.
  - The strip is fully server-rendered, not wrapped in Suspense, so nothing streams in late. `connection()` marks it as request-time.
  - Text links in the strip are at least 32 px tall, which is above WCAG 2.5.8's 24 px. A full 44 px would double the strip's height; the calendar page uses 44 px throughout.
  - The one Katameros entry with no Arabic title is shown in English and marked `lang="en"`.
- **Files:** `orthodox-site/components/calendar/{TodayBanner.tsx,TodayBannerStrip.tsx,labels.ts}`, `app/page.tsx`, `app/home-page.tsx`, `app/chat/chat-page.tsx` (the `?saint=` effect), `lib/pending-chat.ts`, `lib/i18n.ts`, `app/globals.css`.
- **Revisit if:** the priest sets the ordering rule, or wants monthly commemorations left out of the strip.

### CAL-006: /calendar — one server-rendered month at a time, a keyboard grid, and a detail panel with saint links
- **Date / Part:** 2026-09-22, calendar Step 3
- **Decision:**
  - **URL and data:** `/calendar?d=YYYY-MM-DD` opens a day and `?m=YYYY-MM` a month. Dates outside Jan 2026 – Dec 2027 are moved to the nearest end with a note; invalid dates are ignored. The server sends only that month's days (`lib/calendar/month.ts`), already in both languages, so switching language needs no request. Selecting a day updates the URL with `history.replaceState`, so a selected day can be shared. Without a date in the URL, the page follows the visitor's own today (CAL-004) and moves to another month only when that today is in it.
  - **Navigation:**
    - previous/next month links (disabled at the ends);
    - a month jump built as a plain GET form with `next/form`, so it works before JavaScript loads;
    - a Today button;
    - "Calendar" added to the header nav, the phone drawer and the sitemap.
  - **Grid semantics and keyboard:**
    - a `<table role="grid">` with weekday column headers (short labels shown, full names for screen readers) and `aria-selected` on the selected gridcell;
    - one tab stop, a roving `tabIndex` on the day buttons;
    - arrows move by day and week, reversed left/right in Arabic;
    - Home/End go to the start or end of the week, PageUp/PageDown to the previous or next month;
    - a move past the edge of the month loads the neighbouring month and focuses the target day;
    - selection follows focus, so the detail panel always shows the focused day;
    - each day's accessible name reads "Tuesday, 7 April 2026, 29 Paremhat 1742, Tuesday of Holy Pascha, Holy Week fast"; today adds "today" and `aria-current="date"`.
  - **Cells:** the Gregorian day and Coptic day (with the month name on the 1st), a red dot for a feast and a ring for a fast day, a lighter background for fast-free days (legend below the grid), and on wide screens the day's first feast and a short saint preview. The preview drops "The Departure of" / "نياحة" so the name fits.
  - **Detail panel:** sticky beside the grid on wide screens and below it otherwise. It shows the date in both calendars, feasts and holy days, the fast or fast-free period, the "not celebrated this year" note when a feast is suppressed, and every commemoration in the source's order. A saint with an index entry gets "Read about this saint" (`/chat?saint=…#saints`) and "Ask about this saint".
  - **Mobile:** at 390 px the grid keeps seven columns of about 51 × 56 px; previews are hidden (the panel has them) and the toolbar stacks. The phone drawer is a new reusable `components/PageDrawer.tsx`, the same behaviour as the one built into the credits page. Credits and contact could move to it in the cleanup phase.
  - **Attribution** at the foot of the page: dates calculated from the Coptic calendar rules and checked against the Coptic Orthodox Metropolis of the Southern United States (linked); saint commemorations from Katameros (katameros.app, linked).
  - **Metadata:** title "Coptic Calendar", its own description, canonical `/calendar`.
- **Verified before Step 4** (production build, Playwright, mocked APIs):
  - no console errors and no horizontal overflow at 1440 and 390 px in English and Arabic;
  - every control is at least 44 px except inline text links inside the sources paragraph, which WCAG 2.5.8 exempts;
  - keyboard moves, a cross-month move and RTL arrows behave as described;
  - the saint link opens St. George's entry;
  - "Ask about this saint" sends "Tell me about St. George, the Capaducian." to the chat.
  - 115 unit tests pass, including month building, URL handling, short titles and weekday fast names.
- **Files:** `orthodox-site/app/calendar/{page.tsx,calendar-page.tsx}`, `lib/calendar/{month.ts,month.test.ts}`, `components/PageDrawer.tsx`, `components/calendar/useLocalToday.ts`, `components/Navbar.tsx`, `components/ChatSidebar.tsx`, `app/sitemap.ts`, `app/globals.css`.
- **Concept to learn:** *The ARIA grid pattern.* A grid is one tab stop; arrow keys move inside it. That keeps a 31-day month from costing 31 Tab presses. Search: "WAI-ARIA APG grid pattern", "roving tabindex".

### CAL-007: Verification of the calendar feature
- **Date / Part:** 2026-09-22, calendar Step 4
- **Setup:** production build with dead database and backend addresses (as in UI-003). Every `/api/*` call is mocked in the browser, and there were 0 OpenAI calls. Tools: `ui-audit/tools/calendar.mjs` (new) for screenshots, axe and a layout report; `ui-audit/tools/lighthouse.mjs`, which now includes `/calendar` and accepts `PAGES=calendar,home`. Output goes to `ui-audit/calendar/`, which is git-ignored like the other audit folders and can be regenerated with the tools (README updated).
- **Results:**
  - **Tests:** `npm test` passes 115 of 115. `tsc` and `eslint` are clean, and `next build` succeeds.
  - **Screenshots:** 28 of them: 7 states (home strip; this month; Holy Week 2026 with the Annunciation note; St. George 2027 with index links; Nativity 2027; keyboard focus; out-of-range date) × English/Arabic × 1440/390 px.
  - **axe** (WCAG 2.0/2.1 A–AA and 2.2 AA): **0 violations in all 28 states**, no console errors, no horizontal overflow.
  - **Tap targets:** every control on `/calendar` is at least 44 px, apart from inline text links in running text, which are exempt. On the home strip the date and "and N more" links are 32 px tall, by design (CAL-005).
  - **Lighthouse, 2 runs each:**

    | Page | Performance | Accessibility | SEO | Layout shift | Mobile first paint |
    |---|---|---|---|---|---|
    | `/calendar` mobile | 96–99 | 100 | 100 | 0 | 0.75 s |
    | `/calendar` desktop | 100 | 100 | 100 | 0.001 | — |
    | Home mobile | 95 | 100 | 100 | 0 | — |
    | Home desktop | 100 | 100 | 100 | 0 | — |

    Home mobile is within the 94–96 measured in UI-016, so the Today strip costs nothing measurable. Both pages still load 2 font files (93 KB). Best practices is 96 only because the test setup's dead database makes `/api/conversations` return 500; this is not a calendar issue.
- **Still for the priest** (collected from CAL-002 to CAL-005):
  - the saint ordering rule and whether monthly commemorations count in the strip;
  - midnight or sunset for the day boundary;
  - the "Holy Week fast" name;
  - Wednesday/Friday fasts on Nayrouz and minor feasts;
  - Paramoun days;
  - English month spellings;
  - the 21 hand-picked saint links.
- **Not done here:** the Katameros permission reply (pending), and moving the credits and contact pages to `PageDrawer`.

### CAL-008: Calendar saint links regenerated from v2 (runbook step 3.5)
- **Date / Part:** 2026-09-23, after the v2 switch (Phase 5 live, production smoke set passing).
- **Branch:** `calendar-v2-links`. Katameros is at the same commit (87461f3), so every change comes from the index.
- **OpenAI:** none.
- **Steps:**
  1. v2 snapshot of the saints index.
  2. `migrate-overrides-v2.py`: the 19 existing override names moved to v2 names.
  3. Overrides for every link the regeneration would lose.
  4. `npm run calendar:saints`.
  5. `compare-saint-links.py` (new): per language, kept / changed / new / lost against the committed data. It also checks that every link opens the entry it names, through the backend's own saint-name lookup (RET-010/011).
- **Result:**

  | | linked | kept | changed | new | lost | from overrides | link problems |
  |---|---|---|---|---|---|---|---|
  | English | 156 (was 87) | 83 | 4 | 69 | 0 | 20 | 0 |
  | Arabic | 196 (was 165) | 160 | 5 | 31 | 0 | 29 | 0 |

  - **New links** are mostly the numbered Popes and joint entries that v2 names ("St. Cyril I, the 24th Pope", "Sts. Cyriacus and Julitta").
  - **"Changed"** means the old v1 name could not be shown to be the same v2 entry:
    - one correction: Sophia, below;
    - one better target: "John and James, Bishops of Persia" now links their joint entry, not "St. John of Persia";
    - the rest are the same saint under the v2 name: Philotheus, Irene, Abibus, Joseph of Arimathea, Abaskhiron, Abanoub the Confessor, and Alexander of Jerusalem with his fuller name.
- **Overrides added for the links that would be lost** (v2 names; the default saints as in `data/saint_defaults.json`):
  - **Anthony (Tobi 22):** "St. Anthony, Father of the Monks", his default entry.
  - **Sophia (Thout 5):** "St. Sophia, Buried in 'Hagia Sophia' Church". Her entry says she was martyred on 5 Tout. The v1 link went to "St. Sophia", who reposed on 21 Toba.
  - **Basilissa (Thout 6):** "St. Basilissa", as v1. **To confirm:** her entry gives 6 Hator.
  - **Philotheus (Tobi 16):** the martyr of vol. 3, p. 457, whose Synaxarion reference is 16 Toba.
  - **Irene (Mesori 21):** vol. 2, p. 304, who "reposed … on the 21st of Mesra".
  - **Arabic (9):**
    - Abibus, the Egyptian martyr of Hermopolis (ص 98). **To confirm:** neither Abibus entry gives a date.
    - Herwag, Hanania and Khozi (ص 79, 16 Kiahk).
    - Euphrosyne (her entry: 9 Amshir).
    - Abu Fana (ص 66), Joseph of Arimathea (ص 331), Abaskhiron (ص 53), Abamon of Tukh (ص 30), Abanoub the Confessor (ص 30, 23 Paona) and Abanoub of Nahisa (ص 31).
  - **Why most Arabic links were lost:** the dictionary repeats these entries in its last pages ("مدخل 2"), and the matcher took the repeats for namesakes.
  - The preview's other three Arabic losses (Philip the Apostle, Milius, Balana) now link automatically.
  - **Also added:** Mark the Apostle's English link (83001, "St. Marcus, the Apostle"), his default entry, now that v2 has an English entry for him.
- **Also changed:**
  - **The exact-name lookup** (`api._find_saint_record_exact`) now ignores trailing punctuation on the index names too. The Theotokos is listed as "St. Mary, the Virgin Theotokos.", so her calendar link was found only through an alias. Test added.
  - **The v2 snapshot's Arabic aliases** are only those the API still accepts (RET-011 drops seed aliases that are another entry's own name).
  - **`migrate-overrides-v2.py`** now writes the overrides file in its own one-line-per-story layout.
  - **`lib/calendar/saints.test.ts`** pins the v2 names (George, the Theotokos, Anthony, Kyrillos II).
- **Tests:** frontend 127, backend 184.
- **Index issue seen, not fixed here:** the two Abibus entries' IDs are swapped relative to their Arabic texts: `abibus-of-edessa` carries the Hermopolis martyr. That's an EN↔AR link in `saints_index.json`, for the next index rebuild.
- **Revisit if:** the Basilissa or Abibus choice is corrected, or Katameros or the index changes. Rerun step 3.5 and `compare-saint-links.py`.

## Ingestion

### ING-001: Re-ingestion design (Phase 5 Step 0) — PyMuPDF for English, pypdf + NFKC for Arabic, structure-aware units, v2 alongside v1
- **Date / Part:** 2026-09-22, Phase 5 Step 0 (branch `phase-5-ingest`). The full design is `INGEST_PLAN.md`.
- **Approval (2026-09-22):**
  - D1 PyMuPDF; D2–D6, D8 and D9 as recommended.
  - **Changes from the owner:**
    1. On Railway the volume is mounted at `/app/chroma_db`, so the proposed `<chroma root>/../chroma_v2` would have resolved to `/app/chroma_v2`, **outside the volume**, and v2 would have been lost on the next redeploy. v2 now lives at `/app/chroma_db/v2` (`CHROMA_DIR_V2`, default `<CHROMA_DIR>/v2`). The v1 checksum check excludes that subdirectory. Startup refuses `CORPUS_VERSION=v2` when the v2 path is not on the volume's filesystem.
    2. D7 must also evaluate a background build inside the API process, triggered by a one-time `BUILD_CORPUS_V2=1`, with resume and log progress. It will be compared with `railway ssh` in the Step 6 runbook, which recommends one of them.
    3. Before any OpenAI step, the owner confirms the Railway volume size and the OpenAI budget limit.
  - *Lesson:* a path that is correct on one machine can be wrong on another, and I derived the v2 location from a local layout without checking the volume mount. The same-filesystem startup check makes that mistake fail loudly instead of silently losing data.
- **Audit ref:** A1, C1–C8, C33, S9; RET-001/RET-007/RET-009 revisits; UI-006 limit 1; open questions 9 and 22.
- **Context:** v1 stores one pypdf page per chunk: intra-word splits, running headers and footnotes in the text, Arabic stored as presentation forms, and no section, question or saint metadata. Retrieval, citations, the runtime saint index, the eval and the calendar's saint links all depend on that shape.
- **Evidence gathered** (local only, 0 OpenAI calls; three extractors on 20 sample pages, Arabic repeated on 79 random pages):
  - **English:** pypdf splits 1–6 words on 11 of 14 pages ("sufferin g", "fath er", "co nfessed"). PyMuPDF and pdfplumber split none, and fix all 7 artefacts found in the v1 store. PyMuPDF is ~10× faster than pypdf and ~15× faster than pdfplumber, and exposes font, size and position per line. That is enough to strip running headers (top 5 %, 10–11 pt), page numbers and footnotes (10 pt, numbered, bottom), and to find saint entry headings (14 pt bold) and sub-headings (12 pt bold ending ":").
  - **Arabic:** pdfplumber returns visual (reversed) order. PyMuPDF returns base letters in logical order but reverses every lam-alef ligature ("ال تريد", "ألنها"; repairable from the zero-width alef glyph). It also misplaces punctuation, and it **drops letters** in some spans: after repair it still disagrees with pypdf on > 5 % of words on 17/39 catechism and 10/40 saints pages. pypdf + NFKC is complete, keeps logical order and ligatures correct, and only needs Persian ی/ھ folded to ي/ه and its word-per-line output joined.
  - **Structure available:**
    - catechism bookmarks index every question (English vol. 1 Q1–877, vol. 2 Q878–1452; Arabic Q1–1452);
    - the Encyclopedia's alphabetical index pairs 1,598 English entry headings with their Arabic names;
    - the Arabic dictionary marks entries with ✞ (2,149).
  - **Size and pages:** the corpus is ≈ 2.5 M English + 4.6 M Arabic cl100k tokens; cl100k spends 2.9× more tokens per Arabic character. Catechism printed page = PDF index − 10.
- **Proposed decision** (details and the nine decision points D1–D9 are in `INGEST_PLAN.md` §0):
  - PyMuPDF for English (AGPL; offline ingestion only, never imported by the API; pdfplumber is the MIT fallback);
  - pypdf + NFKC + folding for Arabic, with PyMuPDF used only to locate page numbers and Latin footnotes;
  - one unit per catechism question and per saint entry (split by sub-heading) or web section;
  - 300–600-token chunks on sentence boundaries with in-unit overlap across pages, and the same word budget for Arabic;
  - a contextual header on every chunk;
  - a flat, versioned metadata schema with page ranges and reserved scripture-reference fields;
  - an ingest-time bilingual saints index that keeps every v1 name as an alias;
  - `CORPUS_VERSION` selecting a separate Chroma directory and `_v2` collection names;
  - a one-off Railway build instead of boot ingestion, with verify-or-exit at startup;
  - page-range-aware recall compared at equal context budget;
  - one source per cited passage;
  - a quota-safe embedder that stops on `insufficient_quota`/401/403.
- **Estimated OpenAI cost for Phase 5:** ≈ $0.17 per v2 embedding build; ≈ $1 per coverage run on tune+holdout; ≈ $5.5–6.5 in total.
- **Files changed:** `INGEST_PLAN.md` (new), `DECISIONS.md`.
- **Concept to learn:** *Structure-aware chunking.* Retrieval quality is bounded by the unit you index: a chunk should be one coherent answer (a Q&A, a saint's entry section), carry enough context to stand alone (a header naming the question or saint), and keep its provenance (page range, section) so it can be cited precisely. Search: "semantic chunking RAG", "contextual chunk headers", "parent-child chunking".
- **Revisit if:** you choose differently on D1–D9, or Step 2's counts (questions or entries found vs expected) show the structure rules miss more than a few percent.

### ING-002: One ingestion package; extraction and cleaning verified corpus-wide; v1 rebuild proven identical; old scripts deleted
- **Date / Part:** 2026-09-22, Phase 5 Step 1. **No OpenAI calls.**
- **Audit ref:** C1–C4, C33, §3 "three identical chunk_text functions"; ING-001 D1, D2, D4, D8.
- **What was built:** the `ingestion/` package.
  - `sources.py`: a registry keyed by `doc_id`.
  - `extract_en.py`: PyMuPDF lines with size, bold and position, and the cleaning rules.
  - `extract_ar.py`: pypdf text, with PyMuPDF used only to locate zones.
  - `textnorm.py`: Arabic and whitespace normalisation.
  - `web.py`: sections split at h2/h3.
  - `legacy.py`: the exact v1 rebuild.
  - `embed.py`: the quota-safe embedder.
  - `samples.py` and the CLI (`python -m ingestion extract | samples | verify-legacy | build`).

  `ingest.py`, `ingest_arabic_sources.py`, `ingest_web.py`, `ingest_all_sources.py`, `ingest_embeddings.py` and `website_sources.py` are deleted. `start_backend.py`'s v1 auto-ingest now calls `ingestion` (`build_v1_legacy`).
- **Cleaning rules, as finally implemented (English):**
  - A **running header** is a line in the top 7.5 % of the page whose text, with digits folded, repeats on ≥ 3 pages.
    - A first version also treated any *small* top line as a header. The corpus run showed that it removed bibliographic references from 10–18 pages per saints volume ("[The Synaxarion: 4 Paona]", "[Butler: March 3]"): they carry commemoration dates. Repetition alone is now required.
    - Result: the catechism loses its "Book N: …" / "Catechism … Volume N" headers on 668 of 737 and 564 of 624 pages; the saints volumes lose none.
  - **Page number:** a digits-only or roman-numeral line that is the page's first or last line. It is kept as `printed_page`; the printed page was found on 729/737, 623/624 and every saints page.
  - **Footnotes:**
    - the footnote block is the run of lines below body size at the page bottom whose first line starts with a number;
    - a new note must follow the previous number by +1 to +3, otherwise the line is a continuation ("30 on Jesus' promise," is a wrapped line);
    - markers are the body's raised digit spans (the PyMuPDF superscript flag, 8 pt); superscript words such as "4th" are kept.
    - Totals: 1,839 + 1,389 notes and 1,801 + 1,350 markers in the catechism; ~100 real notes per saints volume.
  - **Letter dividers** (a single capital ≥ body + 6 pt) are removed. Paragraphs break on a new PyMuPDF block or a style change; a line-end hyphen joins a lower-case continuation.
- **Arabic:** pypdf + NFKC + folding (ی→ي, ھ→ه, ک→ك, tatweel and invisible marks removed, diacritics kept). The corpus run found three more pypdf behaviours, all now handled and tested:
  1. **Multi-digit Arabic-Indic numbers are reversed**, in PyMuPDF too: "مت ٨٢: ٠٢" is Matthew 28:20 and "أف ٤ : ١١ - ٢١" is Ephesians 4:11–12. Every run of 2+ Arabic-Indic digits is reversed back; ASCII digits ("1215.", "1 تي 2 : 1 - 3") are correct and untouched.
  2. **Brackets come out mirrored, inconsistently** (")نظام الدولة(", "(كاثوليكية(؟"). A balancing pass fixes them: in logical order, a closer with nothing open is an opener, and a second opener of the same kind is a closer.
  3. **Footnote markers** remain as bare numbers ("إليك 175 [", "أغسطينوس 176 وجود", "شيءٍ 593 ]"). A marker is one of the page's footnote numbers directly after Arabic text (vowel marks included), never a number with "." attached (question numbers, "944.").

  **Latin footnotes** are located with PyMuPDF and removed from the pypdf text by a whitespace-insensitive match. A fallback strips a trailing non-Arabic run containing Latin words, because pypdf emits footnotes after the body. Corpus result:
  - **0 of 2,867 pages** still contain presentation forms (v1: 74 % of letters);
  - page numbers were removed on 805 of 807 (catechism) and 1,994 of 1,995 (saints) pages;
  - 1,734 markers removed;
  - residue: 47 footnote-shaped fragments on 41 of 818 catechism pages (**0.08 % of its text**), which pypdf placed mid-page.
- **v1 rebuild (D8), proven with `python -m ingestion verify-legacy`,** read-only against the local store, no API calls:
  - **all 7,581 v1 chunks are reproduced with identical IDs and identical text:** English 3,567, Arabic 3,807, web 207 (the five pages are unchanged since v1 was built);
  - Arabic metadata is identical;
  - the live English PDF chunks carry only `pdf/page/chunk_index` because they predate the current scripts, which (like the rebuild) also write `source_type/title/language/source_group`. That is a compatible superset: the API already defaults those fields.

  So deleting the old scripts loses nothing, and a lost Railway volume can still be rebuilt as v1.
- **Embedder:**
  - `insufficient_quota`, 401 and 403 raise `FatalOpenAIError` on the first occurrence (the old code retried any "429" ten times, and `insufficient_quota` is a 429);
  - only transient 429, 5xx, timeouts and connection errors are retried;
  - the OpenAI SDK's own retries are off, so they can't retry a quota error behind our back;
  - batches are sized with cl100k (chars/4 underestimated Arabic by ~3×);
  - any input over 8,191 tokens is refused;
  - `--resume` skips IDs already stored.
- **Pins:**
  - `chromadb==0.6.3`, so local and Railway write the same on-disk format;
  - `pypdf==5.9.0`, because v1-legacy exactness and the Arabic text depend on its output; the Step 0 experiments used 6.19, and the Arabic behaviour was re-verified on 5.9;
  - `pymupdf==1.28.2`, ingestion only (the API process was checked not to load it);
  - `tiktoken` added; `pytest` in `requirements-dev.txt`.
- **Tests:** `pytest tests/ingestion`, **66 passed**, ~12 s.
  - Golden before/after files for the 20 sample pages, with `tests/ingestion/SAMPLES.md` as the readable report.
  - Explicit checks: every pypdf split in the samples is fixed; headers, page numbers and footnotes are separated; saint headings survive; Arabic invariants (no presentation forms, no reversed lam-alef, ligatures and logical order, verse numbers, brackets, markers, the page PyMuPDF mangles is complete).
  - Normalisation unit tests; embedder error handling with a fake client (quota, 401, 403 fatal after one call; transient retried; resume); web section splitting from offline HTML; three pages of the v1 rebuild against the live store.
- **Performance:** English ≈ 1.2–1.9 s per volume, Arabic ≈ 55 s (catechism) and 133 s (saints) because pypdf is slower. That is fine offline, and it bounds the Railway build time (§9.3).
- **Known limits, handled in Step 2:**
  - a footnote marker whose note is printed on the next page (cat2 p.16 marker 11): notes are attached per question, so this resolves there;
  - saint headings split across a heading line and "(The martyr)": merged by the saints segmenter;
  - the alphabetical index and TOC pages are still extracted: excluded from chunks there.
- **Files:** `ingestion/*` (new), `tests/ingestion/*` (new), `requirements.txt`, `requirements-dev.txt` (new), `start_backend.py`, `request_log.py` (comment), `README.md`, `.gitignore`, `INGEST_PLAN.md` (approval changes, §9), and the six deleted scripts.
- **Concept to learn:** *Golden-file (snapshot) testing* for data pipelines. Keep the exact expected output for a small, deliberately chosen sample next to the test, so any change to the pipeline shows up as a diff a human reviews, alongside targeted assertions for the properties that must never regress. Search: "golden file testing", "snapshot testing data pipelines".
- **Revisit if:** pypdf or PyMuPDF is upgraded (re-run `samples --write` and `verify-legacy`, and review the diff), or Step 2 finds cleaning errors inside questions or entries.

### ING-003: Per-source segmenters, chunker, ingest-time saints index and the v2 dry run
- **Date / Part:** 2026-09-22, Phase 5 Step 2. **No OpenAI calls** (`build --corpus v2` refuses to run without `--dry-run` until Step 3 is approved).
- **Audit ref:** A1, C5–C8 (C7a headers, C7b one source per chunk, C8 saints index); ING-001 §5–§7.
- **What was built:**
  - `structure.py`: units per source.
    - Catechism: one unit per numbered question from the bookmarks, with Book/chapter `section_path`, and notes collected per question.
    - Saints: one unit per entry. English entries come from 14 pt bold heading groups, with sub-headings and reference lines; Arabic entries split at ✞, with the heading matched from pypdf font runs.
    - Web: one unit per h2/h3 section; endnote lists become a separate "Notes" unit.
  - `chunk.py`: sentence packing, 300/450/600 cl100k tokens for English and 230/345/460 words for Arabic (D3).
    - Overlap of up to 15 % within a unit only, dropped when it would push a chunk over the maximum.
    - A thin last chunk is merged into the previous one, or rebalanced with it when the two don't fit together.
  - `saints_index.py`: see below.
  - `corpus.py`: headers, the §6 metadata, IDs `v2:{doc_id}:{unit_id}:c{n}`, and the outputs `manifest.json`, `stats.json`, `saints_index.json`, `SAMPLES.md` (plus `build/corpus/v2/chunks.jsonl`, gitignored).
  - `snapshot_v1_names.py`: writes `data/corpus/v1_saint_names.json`, the 1,363 English and 1,937 Arabic v1 names with pages.
- **Result (`python -m ingestion build --corpus v2 --dry-run`, ~6 min):** **10,563 chunks**, 6,079 English and 4,484 Arabic (plan: ~6,000–6,500 and ~4,000), 6.64 M embedding tokens (≈ $0.13 with text-embedding-3-small).

  | type | chunks | units | body size p10 / p50 / p90 / max | over max |
  |---|---|---|---|---|
  | catechism-en | 2,263 | 1,475 | 125 / 384 / 554 / 600 tokens | 0 |
  | catechism-ar | 1,754 | 1,451 | 55 / 201 / 444 / 460 words | 0 |
  | saints-en | 3,375 | 1,933 | 140 / 372 / 543 / 610 tokens | 3 (≤ 610) |
  | saints-ar | 2,730 | 2,105 | 45 / 213 / 449 / 460 words | 0 |
  | web | 441 | 238 | 117 / 457 / 554 / 637 tokens | 2 (≤ 637) |

  The 5 over-maximum chunks are over by at most 6 %, because token counts are not additive across joined sentences. Short units stay whole by design: a 120-token Q&A is one chunk.
- **Coverage against the books' own indexes:**
  - English catechism: **1,452 / 1,452 questions**. Q88 has no bookmark and was recovered from its "88 Have the rites…" heading. There are also 23 section introductions.
  - Arabic catechism: **1,451 / 1,452**.
    - The PDF is vol. 2, then vol. 1's table of contents (pp. 345–382, with two stray question bookmarks, 665 and 867), then vol. 1 from Book 3. Contents pages are detected by their "question؟ page" density (21+ per page vs ≤ 10 on body pages) and skipped. Without that, Q1452 absorbed 35 pages and two IDs collided.
    - Six unbookmarked questions (264, 269, 275, 792, 794, 1037) are split out of their predecessor at their "N. …؟" heading.
    - Q214 is not in the Arabic text at all.
  - English saints: 1,987 entries. 54 are cross-references ("See the biography of St. Aphraates."): they are not chunked, and their names become aliases of the target (40 resolved, English and Arabic together).
  - Arabic saints: **2,128 entries = 2,128 ✞ marks** on entry pages (the other 21 ✞ in v1's text are in the index and appendices). Headings come from font runs for 2,011, the first line for 109, and fallbacks for 8. A ✞ at the foot of a page now takes its heading from the next page (35 entries had empty headings before).
  - **Chunks without a section or saint name: 0.** Every catechism chunk has a `section_path`, and every saints chunk has a `saint_name` and a `saint_id`; saints have no section by design. Three English catechism chunks lack a printed page because they sit on Book opening pages, which carry no page number.
- **Saints index (`data/corpus/v2/saints_index.json`, 2,387 records):**
  - **English ↔ Arabic:** the vol. 4 alphabetical index gives **1,897** "ENGLISH…عربي" pairs. It was read from PyMuPDF's plain-text blocks: its dict output drops the Arabic runs on those pages.
    - 1,868 entries get an index line by best-first one-to-one fuzzy matching, gated on the first name. Regnal numbers must agree ("CYRIL IV" ≠ "CYRIL V", "كيرلس الرابع" ≠ "كيرلس الخامس", "13th" = "XIII").
    - Exact matching managed only 78 %, because spellings differ ("EL-NEHISSY" vs "AL-NEHESSY").
    - The index skips roughly APAMON to ATRASIS.
  - **Arabic entries linked to an English record: 1,730 of 2,128.**
    - 1,596 by the index's Arabic name (threshold 0.8; below it, popes of the same name get confused);
    - 79 by prefix ("مرقس الثاني" heads "مرقس الثاني البابا التاسع والأربعون");
    - 44 by the Latin name printed under the heading;
    - 11 by hand;
    - 398 are Arabic-only.
  - **Hand curation** lives in `data/corpus/saints_curation.json`, with a reason on each line:
    - 11 links (the Athanasius entries, George the Cappadocian, Demiana, Archelaus);
    - where the 17 v1 seed names point. "St. George" is the Great Martyr, not "George and Fronto"; a curated name is removed from other records. Peter and Paul have no entry in either book and are kept as name-only records.
    - `saint_index_overrides.py` is not carried over: it patched v1's runtime parsing of body text, and v2 takes headings from fonts.
  - **v1 names kept as aliases:** 1,357 / 1,363 English by page overlap. The 6 unmapped include junk ("St. Ecclesiastical Terms", "St. Magdi Faris Malek"). All 1,937 Arabic names are kept.
  - **Namesakes:** 172 English and 252 Arabic names point to more than one record (e.g. three St. Agathons). Step 4 must disambiguate, not pick one.
- **Commemoration lines are preserved and captured.**
  - "[The Synaxarion: 4 Paona]" and "[Butler: March 3]" stay in the chunk text as a references block ("[The Synaxarion: 4 Paona]" is in `v2:sts1:saint:dacius-boctor-and-irini:c1`; "[Butler: March 3]" in `v2:sts1:saint:chelidonius-and-emeterius:c1`).
  - They are also parsed into `synaxarion_date` / `western_date`, on the saint record and on every chunk of the entry. 1,500 English entries carry reference lines, but most are bibliography. The parser reads each `[...]` group; day-first and month-first forms, "Synaxariun", Bashons and Baring-Gould all parse. The result is 217 Synaxarion dates and 446 Butler/Baring-Gould dates; the Synaxarion lines left without one contain no date ("[The Coptic Synaxarion]", "Edition of Rene Basset"). On chunks: 335 of 3,375 English saints chunks carry a Synaxarion date and 654 a western date.
- **Header-less catechism pages (the ~10 %):** 129 pages (69 + 60) have no running header removed, and **none of them is a question page**:
  - 10 front matter (title, dedication, acknowledgments, TOC);
  - 13 blank;
  - the 7 "Book N" opening pages;
  - 99 back matter (bibliography, Index of Bible Verses, Index of Questions).

  The header rule missed nothing.
- **Extraction fixes found while reading the samples** (goldens regenerated and reviewed):
  - **English:**
    - a hanging-indent list item's wrapped line is its own PyMuPDF block; it is now joined when it sits right under the item and the item has no sentence end ("…Liturgy of the / Waters is prayed");
    - a footnote continued from the previous page returns to that note, and glued note numbers ("276Anne Fremantle") are parsed;
    - chapter titles lose glued footnote markers ("Divine Grace 552").
  - **Arabic:**
    - Footnotes are cut as one block: the small runs below the lowest body line, which are always the end of pypdf's stream (238/238 sampled pages). This catches Arabic-language notes and notes whose Latin line contains an Arabic comma, both previously left in the text.
    - Quotation brackets are oriented per page, choosing whether a quote was already open from the previous page (openers follow ":", closers follow a marker or period).
    - A line-final period that pypdf put before the last word is moved back ("وسقط . ميتًا" → "وسقط ميتًا."). After a number it becomes the number's own period ("318 .ما" → "318. ما").
    - Markers are removed once per note and never overlap. A duplicated note number had cut a question number.
  - **Known residue:**
    - Some pages where pypdf scrambles the order around nested quotations still show reversed brackets (e.g. Q896).
    - A few markers whose note is on another page remain as bare numbers.
    - Arabic snippets inside English footnotes keep PyMuPDF's reversed lam-alef.
- **Tests:** **104 passed**, ~13 s. New:
  - `test_chunk.py`: sentence guards, maximum and overlap, no thin tail, pages across a break, headers, flat and complete metadata;
  - `test_structure.py`: wrapped list lines, display names, Arabic heading choice, unbookmarked question recovery, web endnotes, punctuation and bracket fixes, vol. 2 finds Q878–1452, vol. 4 keeps reference lines;
  - `test_saints_index.py`: dates, name tokens, regnal numbers, one-to-one matching, cross-references, and the committed index (unique IDs; St. George → the Great Martyr with both languages).
- **Files:**
  - `ingestion/structure.py`, `chunk.py`, `saints_index.py`, `corpus.py`, `snapshot_v1_names.py` (new);
  - `extract_en.py`, `extract_ar.py`, `textnorm.py`, `__main__.py`;
  - `data/corpus/v1_saint_names.json`, `data/corpus/saints_curation.json`, `data/corpus/v2/*`;
  - tests and goldens; `README.md`, `.gitignore` (`build/`).
- **Concept to learn:** *Record linkage* (entity resolution). Blocking (only compare names that share a first name), a similarity score, one-to-one assignment best-first, hard constraints that veto (regnal numbers), and a small hand-reviewed list for the residue. Search: "record linkage blocking", "entity resolution one-to-one matching".
- **Revisit if:** Step 5 shows questions or saints that retrieval misses because of segmentation, or the namesake count causes wrong saint answers in Step 4.

### ING-004: v2 embedded locally into chroma_db/v2; v1 byte-identical before and after
- **Date / Part:** 2026-09-22, Phase 5 Step 3. **OpenAI: embeddings only, approved at ~$0.13.** The owner confirmed the Railway volume (5 GB, ~0.3 GB used) and that a budget limit is set.
- **What ran:** `python -m ingestion build --corpus v2`.
  - It embeds `build/corpus/v2/chunks.jsonl`, and refuses unless those chunks hash to the committed `manifest.json`, so what is embedded is exactly what was reviewed in Step 2.
  - The target is `CHROMA_DIR_V2`, defaulting to `<CHROMA_DIR>/v2`, i.e. `chroma_db/v2/` locally and `/app/chroma_db/v2` on Railway (`chroma_store.get_chroma_path_v2`).
  - Collections are `orthodox_pdfs_v2` (6,079 chunks) and `orthodox_arabic_pdfs_v2` (4,484), in Chroma's default L2 space like v1, so distances stay comparable.
  - IDs from an older v2 build that are no longer in the corpus are deleted before the upsert.
- **Cost and run:** 6.64 M tokens, about $0.13.
  - 47 transient per-minute rate-limit retries were handled by the embedder.
  - There was no quota, 401 or 403 error.
- **Checks:**
  1. SHA-256 of all 11 v1 files under `chroma_db/` (excluding `v2/`) are **identical** before the build, after it, and after opening v1 again.
  2. v1 still opens with **3,774 / 3,807** chunks. A query with a stored vector returns that chunk first. `list_collections()` on v1 shows only v1's two collections: the nested `v2/` is invisible to it.
  3. `verify_store` finds **no difference** between the v2 collections and the manifest (count and chunk-ID hash per collection). A self-query on `v2:cat2:q896:c1` returns it first.
  4. `chroma_db/v2` is 240 MB, a little under the 250–350 MB estimate and far inside the 5 GB volume.
- **Manifest:** `collections` now records the name, chunk count and ID hash per language. That is what the startup check compares (§9.1). The verification lives in `corpus_runtime.py`, which the API can import without PyMuPDF.
- **Tests:** 107 (store verification: matching, missing collection, differing IDs; v2 directory missing or empty, outside the volume mount).
- **Revisit if:** the corpus is rebuilt (re-run the dry run, review, then `build --corpus v2 --resume`), or Chroma is upgraded (the pin keeps local and Railway formats equal).


### ING-005: Retrieval on v2 behind CORPUS_VERSION; one source per cited passage; ingest-time saints index; v1 output proven identical
- **Date / Part:** 2026-09-22, Phase 5 Step 4. **OpenAI: pre-approved retrieve-only checks.** 25 analysis calls with gpt-4o-mini ($0.0045) plus query embeddings (well under $0.01). No answer was generated.
- **Selection (§9.1):**
  - `CORPUS_VERSION=v1|v2`, default v1, read by `corpus_runtime.py`, which never loads PyMuPDF.
  - v2 opens `CHROMA_DIR_V2` (default `<CHROMA_DIR>/v2`) and the collections named in the manifest, with `get_collection`, never create.
  - `/health` and `/debug/chroma` report `corpus_version`.
- **Startup (`start_backend.py`):** with v2 it never ingests. It exits non-zero, which keeps the previous Railway deployment serving, when:
  - the v2 directory is missing or empty;
  - on Railway, the directory is outside `RAILWAY_VOLUME_MOUNT_PATH` or on another filesystem (`st_dev`);
  - either collection's count or chunk-ID hash differs from the manifest.

  Tried locally: it passes on the real store and refuses a missing directory.
- **Citations (§11):**
  - **Labels** name the question or saint with printed pages (D5): `Catechism of the Coptic Orthodox Church, Vol. 2 — Q896 “What is prayer?”, p. 21`, `Encyclopedia of the Saints…, Vol. 1 — St. Abanoub El-Nehissy, pp. 33–35`, `كاتيكيزم الكنيسة القبطية الأرثوذكسية — س 896 «ما هي الصلاة؟»، ص 19`.
  - **One source per cited passage:** the source key is the chunk ID, so two saints cited from the same page are two linked sources. This resolves UI-006 limit 1 and open question 22.
  - `Source` gains `chunk_id`, `entry`, `work`, `page_end` and `pages`. `page` stays the PDF page, for the eval and old clients.
  - A serializer omits the new keys when they are empty, so **v1 responses are byte-for-byte unchanged**.
  - `request_log.chunk_id_from_metadata` reads the stored `chunk_id`.
  - Retrieval dedupe keys use the chunk ID for v2.
  - Debug hits carry `pdf`, `page_start` and `page_end` for v2 (§10.1).
- **Frontend:** `lib/sources.ts` shows `entry` (question or saint) and the printed `pages` ("pp. 33–35", "ص 33–35") when present, and falls back to `page` for v1 and saved messages. Website sources name their section. 4 new tests; 119 pass; tsc and eslint are clean.
- **Saints index at runtime** (`data/corpus/v2/saints_index.json`; the v1 heading parser is not used under v2):
  - English records keep the v1 record shape, so lookup, menus, lists, suggestions and `/saints` work unchanged. They carry the index's aliases, and each body is the entry's first chunk.
  - Arabic records are the dictionary's headings, matched on the heading, the index's Arabic name and every alias (the v1 seed and generated names).
  - A confidently identified saint's **own entry leads the context**: up to `SAINT_ENTRY_MAX_CHUNKS=3` chunks fetched by `saint_id`. In v2 this applies in every mode (v1: saints mode only), and in Arabic saints mode.
  - Mode filters use `content_type` in v2.
  - **Namesakes:** a menu option must name one entry, so names that normalise alike get their descriptor and page ("St. Agathon (The Martyr, vol. 1, p. 105)", with ", entry 2" when heading and page are also equal).
    - A curated name belongs to its saint only: "St. Athanasius" resolves straight to the Apostolic; it used to be a three-way menu.
    - The Arabic dictionary repeats some entries on its last pages, where printed page numbers restart, so those get "، مدخل 2".
  - Curated Arabic seed names are now exclusive as well: "جرجس" and "مارجرجس" lead to George the Cappadocian, not Gohary. The rule is in `saints_index.py` for the next build and was applied to the committed JSON (3 aliases removed).
  - Display names are tidied at runtime ("Abba Bishoy, St" → "Abba Bishoy", "Cyril Iii" → "Cyril III"). Doing it at ingest would change chunk IDs and need a re-embed; fold it in with the next corpus build.
- **Retrieve-only mode:** `ChatRequest.retrieve_only` returns right after retrieval with every passage as a labelled source, for the top-k and threshold sweeps of §10.2.
- **v1 unchanged, proven:**
  - The `/chat` flow ran for 9 questions (EN/AR; catechism, saints, chat; a menu and a saint lookup) under the pre-Step-4 `api.py` from git and under the new code, both on v1.
  - Task analysis was off and a stub replaced the chat model, so only query embeddings were called.
  - **Identical** prompts sent to the model, response payloads, saint name indexes (1,363 EN, 1,937 AR) and suggestions.
- **v2 check (retrieve-only, 25 tune questions, same analyses reused for v1):**
  - Expected-page recall is **0.85 on v2 vs 0.64 on v1** across the 23 answerable questions. It is range-aware for v2, which favours multi-page chunks; §10.2's budget-matched recall is Step 5's job.
  - Arabic is 7/7 fully or half covered on v2 vs 4/7 on v1, with best distances ~1.0–1.2 vs ~1.4–1.7.
  - English context is ~30 % smaller.
  - The two out-of-corpus questions stay far above the answerable ones (1.43–1.73 vs ≤ 0.92).
  - These are small-sample sanity checks, not the Step 5 comparison.
- **Known limits carried to Step 5:**
  - The Arabic lexical scan ranks tied single-term matches by collection order (v1 by page). Kept unchanged so Step 5 compares corpora, not code.
  - The eval harness still parses v1 IDs (`CHUNK_ID_RE`); it must read the new debug page ranges.
  - The distance threshold (1.25) and top-k are v1's until the Step 5 sweeps.
- **Tests:** backend **112 passed** (5 new API tests: labels, v1 sources and serialization unchanged, v2 fields, two saints on one page stay two sources, names tidied and namesakes told apart); frontend 119.
- **Files:** `corpus_runtime.py`, `api.py`, `start_backend.py`, `request_log.py`, `chroma_store.py` (earlier), `ingestion/saints_index.py`, `data/corpus/v2/saints_index.json`, `orthodox-site/lib/sources.ts`, `lib/chat-types.ts`, `lib/sources.test.ts`, `tests/test_corpus_v2_api.py`, `README.md`, `.env.example`.
- **Revisit if:** Step 5 shows saint lookups sending the wrong entry first, or v2 needs a different top-k or threshold.


### ING-006: v1 vs v2 evaluation — v2 raises Arabic coverage by 13 points, English is unchanged; v2 top-k 16, threshold stays 1.25
- **Date / Part:** 2026-09-23, Phase 5 Step 5. **OpenAI: approved, ceiling $6; spent $4.08** (ledger `eval/results/spend-phase5.json`; no quota or auth errors).
- **Harness (before any run):**
  - `run_eval.py`: range-aware recall (a v2 chunk covers a page range; identical to the old definition for v1), `passage_tokens`/`passage_spans` per record, `--corpus-label`, `--retrieve-only`, and a spend ledger with `--max-spend`. The ledger is checked before every question; a quota or auth error in the judge stops the run, as does a 500/503 that persists after one retry.
  - `retrieval_sweep.py`: in-process top-k sweep with one cached analysis per question, shared by both corpora.
  - `budget_recall.py`: recall at equal context budget.
  - `faithfulness_subset.py`: the same 15 ids for both corpora, re-judging stored answers.
  - `phase5_compare.py`: the tables below.
  - `scoring.py`: the faithfulness judge's output limit goes 2,500 → 5,000 tokens. Two long v2 saint answers (20+ claims) had cut the judge's JSON off; they were re-judged.
- **D9 questions (tune only), 15 new:**
  - English saints: George, Mina, Shenouda, Athanasius, Macarius.
  - Arabic saints: George, Shenouda, Mina, Athanasius, Bishoy.
  - Arabic catechism: tears of repentance, iconostasis, purpose of the Creed, angels, the Church as God's kingdom.

  The topics were chosen by name before any v2 retrieval was looked at. **Every one of the 84 evidence snippets was checked automatically against the extracted text of its PDF page.** Tune now has 17 Arabic and 14 English saints questions; the set has 134 questions.
- **Top-k (tune, retrieval only, $0.02):**
  - v1 at k=8: recall 0.79, median context 6,683 tokens.
  - v2: recall 0.90 at k=8–10 and 0.91 at k=12–16. Median context is 4,139 at k=8 and **6,631 at k=16**, which matches v1's.
  - Per plan §10.2, **v2 serves k=16** (`TOP_K_V2=16`, `MAX_TOP_K` 16 under v2, where the cap was hard-coded 12; v1 unchanged).
  - k=12 gives the same tune recall with ~20 % less context and is the cheaper production option.
- **Threshold:** re-derived by RET-009's rule; it **stays 1.25**.
  - Answerable questions reach 0.92 on the analysed query and 1.14 on the raw text (the fallback when analysis fails). That margin is 0.11; v1's was 0.004.
  - Easy negatives start at 1.43. The cryptocurrency trap sits at 0.97 on both corpora and is refused by the model.
  - Arabic stays off: answerable questions reach 1.24, and the two negatives sit at 1.21 and 1.46.
- **Coverage runs:** tune + holdout, 134 questions, two runs per corpus, same code and config (gpt-4.1-mini, prompt v3, entity check on, gpt-4.1 judge).
  - Files: v1 `20260922-235126` and `20260923-001435`; v2 `20260923-000307` and `20260923-002553`.
  - Cost: $0.76 per run on v1, $0.82 on v2.

  **Coverage (all answerable, refusals 0; mean ± half the run spread):**

  | | v1 | v2 | n |
  |---|---|---|---|
  | EN tune | 74.9 ± 1.1 | 74.5 ± 0.1 | 53 |
  | EN holdout | 80.4 ± 0.4 | 80.9 ± 0.1 | 23 |
  | **AR tune** | 60.1 ± 0.4 | **73.4 ± 0.1** | 17 |
  | **AR holdout** | 71.7 ± 1.2 | **84.5 ± 1.7** | 3 |
  | all | 73.5 | 76.1 | 96 |

  By category:
  - **Arabic saints:** 46.5 → 73.3.
  - **Arabic catechism:** 77.2 → 76.8.
  - English catechism: 72.9 → 76.7.
  - **English saints:** 79.3 → 78.7.
  - Multi-part: 80.4 → 96.7.
  - Keyword: 86.0 → 82.1.
  - **Task:** 68.1 → 61.4.
- **Recall at equal context budget** (the budget is v1's mean context tokens per category):
  - English: 82.9 → **89.5**.
  - Arabic: 62.5 → **92.5**.
  - All: 78.6 → 90.1.
- **Refusals:**
  - Answerable questions refused: 0 % → 1.0 %. That is TSK-11, "list the saints named Gregory" (see below).
  - Out-of-corpus refused: 93.4 % on both (easy 100, near-miss 89.1, task 100, Arabic 100). The flips roughly cancel:
    - on v2 only, OOC-22 (sola scriptura) was answered in both runs, and OOC-31 in one;
    - on v1 only, OOC-26 and OOC-28 were answered.
- **Faithfulness** (15 answers per corpus, same ids, gpt-4.1 judge): supported claims **94.9 % → 97.8 %**, unsupported 3.8 → 2.2 %, bad citation 1.3 → 0 %, uncited 0.6 → 2.2 % (157 vs 178 claims).
- **Regressions** (coverage down ≥ 0.25, mean of 2 runs):
  - **TSK-11** "list the saints named Gregory" (0.43 → 0, refused on v2). The analysis call turns it into a `starts_with: "G"` filter on both corpora, and the list shows 30 entries. v2's complete index has many more G saints (the Gabriels), so the Gregorys fall past the cap and the model says none were found.
    - This is an analysis-prompt bug the old, sparser index hid.
    - The fix is a `contains` filter for "named X" requests.
  - **TSK-02** "saints martyred in Egypt" (0.35 → 0). Recall is 0 on both. It is a broad list whose key facts name specific saints; v2 lists other, valid martyrs.
  - **PRD-02, AR-07, KW-02, SNT-02, SNT-03, TSK-13:** recall was equal or better on v2 (SNT-02 and SNT-03 went from 0.5 to 1.0). The answers left out key facts that were in context, so this is generation variance on longer contexts, not retrieval.
  - **Saints and Arabic:** English saints are flat (-0.6, within noise). **Arabic saints gained 27 points, and no Arabic saints question regressed** (AR-01 fell in run 1 only).
- **Cost and latency per request:**
  - Generation is about $0.0036 → $0.0041 per answer (+12 %): English +5 %, Arabic +42 % from 16 larger Arabic chunks.
  - Mean latency 3.9 → 4.1 s.
- **Tests:** backend 116 (4 new eval-helper tests).
- **Files:** `eval/run_eval.py`, `eval/scoring.py`, `eval/spend.py`, `eval/retrieval_sweep.py`, `eval/budget_recall.py`, `eval/faithfulness_subset.py`, `eval/phase5_compare.py`, `eval/questions.jsonl`, `eval/results/*` (runs, sweeps, `phase5-compare.txt`, ledger, analysis cache), `api.py` (`MAX_TOP_K`/`TOP_K_V2`).
- **Revisit if:** the saint-list filter is fixed (re-run TSK-11 and PRD-01); production moves to k=12 for cost; or more Arabic negatives are added (then an Arabic threshold may be viable on v2).


### ING-007: "Saints named X" lists by name, Arabic saint lists on v2, top-k 16 kept, Arabic page ranges read in order
- **Date / Part:** 2026-09-23, Phase 5, before Step 6. **OpenAI: retrieve-only checks, $0.0011** (pre-approved up to $0.05; ledger `eval/results/spend-ing007.json`).
- **1. "Saints named X" (the ING-006 regression):**
  - **Cause:** for "List the saints named Gregory" the analysis produced `starts_with: "G"`. Given both keys, the parser took `starts_with` first. The 30-entry list of G saints then ran out before the Gregorys (v2's index has 60 G saints).
  - **Fix (`task_analysis.py`):**
    - `name_filter_from_question` reads the user's own words and wins over the model. "named/called X" gives `contains`; "start/begin with X" gives `starts_with`. Arabic forms are covered: يحملون اسم، باسم، تبدأ أسماؤهم بحرف.
    - When the model returns both keys, `contains` is preferred unless the question asks for a starting letter.
    - The prompt now says: exactly one key, and "named X" is never its first letter.
  - This is shared code, so v1 lists are fixed too.
- **Arabic saint lists (v2):** the Arabic path had no name-list feature. `_arabic_saint_list_entries` selects dictionary entries by name.
  - A `contains` match is a whole word of the heading, the index name or an alias, allowing a leading ا/ال/مار/و: "إغريغوريوس" is "غريغوريوس".
  - A `starts_with` match compares the first letters after titles are dropped.
  - Each entry's opening becomes context, with an Arabic note that the list may be incomplete, as in English.
  - While testing, 18 Arabic entries turned out hidden: their record's *English* side is a cross-reference ("AGREGORIUS … Cf. Gregory of Nyssa"), and the Arabic records skipped every such record. They are included now (2,087 → 2,105 Arabic names).
- **Retrieve-only checks (v2):**

  | request | filter | entries |
  |---|---|---|
  | List the saints named Gregory | contains Gregory | **6** (Nyssa, Spoleto, the Armenian, Nazianzus, the Monk, the Wonder-Maker) |
  | saints named George | contains George | 5 |
  | saints whose names start with G | starts with G | 60 (30 shown) |
  | اذكر القديسين الذين يحملون اسم غريغوريوس | contains | **6** |
  | اذكر القديسين الذين يحملون اسم جرجس | contains | 10 |
  | اذكر القديسين الذين تبدأ أسماؤهم بحرف ج | starts with ج | 81 (30 shown) |

  On v1 the three English requests give 6, 3 and 42 (30 shown).
- **2. Top-k:** production stays at **16** (`TOP_K_V2`, the measured configuration in ING-006). **Future cost optimisation:** k=12 had the same tune recall (0.91) with ~20 % less context. It would cut the Arabic generation cost most (+42 % at k=16). Re-measure coverage before switching.
- **3. Arabic citations right-to-left:** a real v2 Arabic answer (AR-14) was rendered in Chrome with the production build at 1440 and 390 px (`ui-audit/tools/rtl-sources.mjs`).
  - The document and every source are RTL (`dir=rtl`, bidi-isolated).
  - **But page ranges were laid out reversed:** "ص 118–119" displayed as "119–118". A hyphen does the same.
  - `lib/sources.ts` now wraps Arabic page ranges in an LTR isolate (U+2066…U+2069). Measured on screen, the first number is now left of the second in all 10 ranges.
  - The accessible label now joins with the Arabic comma: "المصدر 1: أثناسيوس الرسولي البابا العشرون، قاموس آباء الكنيسة وقديسيها، ص 118–119".
  - The "scrambled" label in the terminal was only the terminal's bidi handling. The stored text is in logical order.
- **Tests:** backend 129 (13 new filter tests); frontend 119 (the RTL isolate and Arabic comma asserted).
- **Files:** `task_analysis.py`, `api.py`, `orthodox-site/lib/sources.ts`, `lib/sources.test.ts`, `tests/test_task_analysis_filters.py`, `ui-audit/tools/rtl-sources.mjs` (+ fixture, README).

### ING-008: Deployment runbook for v2 — background build (option B) recommended over railway ssh
- **Date / Part:** 2026-09-23, Phase 5 Step 6. **OpenAI: none** (the smoke set's chat part, ~$0.04, and the Railway build, ~$0.13, run only at deploy time with the owner's approval). Nothing was pushed or deployed.
- **Runbook:** `DEPLOY_V2.md`. It covers:
  - pre-flight;
  - deploying the code on v1;
  - the build;
  - the switch;
  - the smoke set;
  - browser checks;
  - rollback;
  - the calendar regeneration;
  - v1 retirement;
  - the env var table.
- **D7 decision: option B, `BUILD_CORPUS_V2=1`.**
  - **How it works:**
    - `start_backend.maybe_start_v2_build` launches `python -m ingestion build --corpus v2 --resume --chroma-dir <CHROMA_DIR_V2>` as a separate child process: own session, `nice 10`, output to the service log.
    - Then uvicorn starts as usual on v1.
  - **Why B over A (`railway ssh` + `setsid nohup`):**
    - no interactive session to keep open;
    - a redeploy or crash resumes instead of losing the build;
    - progress shows in the service logs;
    - a crash or quota stop in the build cannot take the API down (separate process, as with A).
  - **Guards:**
    - it does nothing unless the flag is set, or while `CORPUS_VERSION=v2`;
    - it refuses a target outside the volume (`corpus_runtime.outside_volume`, which works before the directory exists);
    - it logs "v2 complete" and does nothing once the store matches the manifest;
    - after a quota or auth error the build writes `<v2>/BUILD_FAILED` and exits 3. Later boots do not relaunch it until someone deletes the marker, so a shared key is never retried into an empty budget.
  - **A remains the fallback** if memory is too tight to build next to the API.
- **The reviewed chunks ship with the code:** `data/corpus/v2/chunks.jsonl.gz` (7.4 MB, gzip mtime 0, so reruns are byte-identical).
  - Railway embeds exactly the chunks reviewed in Step 2 and evaluated in Step 5. It does not re-extract the PDFs on Linux, where library differences could change the text.
  - `load_chunks` prefers a local `build/corpus/v2/chunks.jsonl`, else reads the gz. The build still refuses chunks whose IDs or counts differ from the manifest.
  - The dry run rewrites the gz.
  - **Checked locally without OpenAI:** with `build/` moved aside, `build --corpus v2 --resume` read the gz, found all 6,079 + 4,484 IDs stored (0 to embed), and verified the store against the manifest. `maybe_start_v2_build()` returned "complete".
- **Timing:** the local build (Step 3) took about 5 minutes for 6.64 M tokens, including 47 rate-limit retries. The earlier ~25 min estimate was wrong.
- **Smoke set:** `eval/smoke_v2.py --backend … [--expect v1|v2] [--no-chat]`.
  - `/health` (corpus version, both collections), then `/saints` and `/saint-suggestions` in English and Arabic.
  - Then 8 chat requests (~$0.04): 5 English (2 answered, a saints-mode lookup, "saints named Gregory", an out-of-corpus refusal) and 3 Arabic (a catechism answer, a saints answer, a refusal). Each answered request must return v2-shaped sources.
  - Checked locally: `--no-chat` passes against a v2 backend, and `--expect v1` correctly fails on it.
- **Calendar saint links:**
  - `snapshot-saints-index.py` is corpus-aware: with `CORPUS_VERSION=v2` it snapshots the v2 index with `corpus_version` and `ar_aliases`. v1 output is unchanged apart from the header lines.
  - `migrate-overrides-v2.py` maps the 19 override names to v2 display names; none are unmapped.
  - `extract-katameros-saints.ts` also matches the Arabic aliases. Its v1 output is unchanged: 87 English and 165 Arabic links.
  - **Preview on v2 (not committed):** 149 English links (67 new, 5 lost) and 184 Arabic (31 new, 12 lost). The losses need overrides in the post-switch frontend commit.
  - The generated calendar files stay on v1 until the switch.
- **Tests:** backend 135 (6 new in `tests/test_v2_background_build.py`); frontend 119; `tsc` clean.
- **Files:**
  - `DEPLOY_V2.md`, `start_backend.py`, `corpus_runtime.py`, `ingestion/corpus.py`, `ingestion/__main__.py`;
  - `data/corpus/v2/chunks.jsonl.gz`, `eval/smoke_v2.py`, `tests/test_v2_background_build.py`;
  - `orthodox-site/scripts/calendar/{snapshot-saints-index.py, migrate-overrides-v2.py, extract-katameros-saints.ts}`.
- **Revisit if:** Railway's memory graph shows pressure during the build (use A at a quiet hour), or the build is ever needed again with different chunks. In that case, re-review, regenerate the manifest and the gz together, and rebuild into a fresh directory.

---

## Open questions

1. **Chroma's own OpenAI client.** Query-time embeddings go through `chromadb.utils.embedding_functions.OpenAIEmbeddingFunction`, which constructs its own OpenAI client, so REL-001's timeout/retry settings do not apply to embedding calls. Chroma's wrapper does not expose those settings. Fix belongs with the retrieval rework (embed the query ourselves with the shared client and pass `query_embeddings`).
2. **Vercel function duration.** The proxy aborts backend calls at 20 s. I could not confirm the Vercel plan's maximum function duration; if it is 10 s, the abort never fires and the user sees a platform error instead. Check the project settings and consider exporting `maxDuration` from the chat route.
3. **`chat.html`.** The legacy single-file frontend calls the backend directly from the browser and is now broken by the shared secret (it cannot hold the key safely). It should be deleted in the cleanup phase; left untouched here because cleanup was out of scope.
4. **CORS.** Since browsers no longer call the backend, the CORS middleware could be removed or narrowed. Left as is (S3 was not in this part).
5. **Judge model.** The judge defaults to `gpt-4o-mini`, the same model that writes the answers. For decisions between two prompts or models, run the judge with a stronger, different model (`EVAL_JUDGE_MODEL`) and spot-check ~10 answers by hand; I did not verify the judge's scores against a human pass.
6. **Expected pages are sufficient, not exhaustive.** Several catechism topics are treated on more than one page; a run can "miss" the expected page and still answer correctly from a neighbour. If recall numbers look too harsh, add the neighbouring pages to `expected_sources` rather than loosening the metric.
7. **Citations are not verified.** The model's `[n]` markers are parsed and trusted; nothing checks that passage n actually supports the sentence. A cheap guard would be to reject citations whose passage shares no content words with the sentence, or to ask the judge model to spot-check a sample. (Phase 2)
8. **Threshold margin is thin.** 1.0 sits 0.03 above the hardest answerable question and 0.05 below the two hardest out-of-corpus traps; nine negatives is a small sample. Add more on-topic-sounding out-of-corpus questions before trusting it in production, and re-derive it after re-ingestion. (Phase 2)
9. **Arabic distance check is off.** Until Arabic is re-embedded from normalised text, an off-topic Arabic question reaches the model with ten irrelevant chunks and relies on the prompt to refuse. (Phase 2)
10. **Frontend still pastes the previous answer into follow-up questions** (`orthodox-site/app/chat/page.tsx`, `followUpBackendQuestion`). Now that history goes to the model as messages, that hack pollutes the retrieval query and should be removed in the frontend part. (Phase 2)
11. **Answer length and cost.** v2 answers average ~1,700 characters and ~380 completion tokens; if that is too long for the chat UI, add a length target to the prompt rather than a token cap. (Phase 2)
12. **~~Near-miss refusals (Phase 3).~~ Largely resolved in GEN-006 (tune: 15 of 16 near misses refused, the remaining one a correct premise rejection).** Four doctrine questions and one same-name question were answered from general knowledge although the corpus never discusses them; the distance threshold cannot catch them (RET-004). Candidate fixes: an entity/term-presence check on the retrieved passages before generation, a prompt instruction to state explicitly when the passages do not mention the subject asked about, or using the faithfulness judge's unsupported-claim signal at request time.
13. **Coverage vs recall gap (Phase 3).** CAT-13 and CAT-15 retrieve their expected page at rank 1–4 yet score 10–17 % coverage: the model writes from neighbouring pages. Options: rerank so the best page is passage [1], tell the prompt to prefer passages that answer the question directly, or shrink chunks so the relevant paragraph dominates.
14. **Unsupported claims are mostly filler (Phase 3).** The unsupported 7–11 % of claims are generic characterisations rather than invented facts; a prompt line "do not add general characterisations that the passages do not state" is the cheapest experiment.
15. **Judge cost and rate limits (Phase 3).** Faithfulness sends the full context per answer (~10k tokens); a full run needs ~40 minutes under the 30k tokens-per-minute limit and two runs must not overlap. Consider gpt-4.1-mini for faithfulness after checking agreement with gpt-4.1 on the 10-answer sheet.
16. **Rate-limit keys for shared networks.** 20/min per IP may be too low for a church group on one Wi-Fi network; keying on the anonymous session cookie (forwarded from Next.js) would be fairer.
17. **~~Keyword questions are unverified (RET-005).~~ Resolved in EVAL-015: all ten verified against the PDFs.** KW-01…KW-10 have pages located by searching stored chunk text and key facts drafted from that text; they need a hand check (pages and facts) before their coverage scores are trusted. Until then, read their best distances, not their coverage.
18. **~~Short queries and the threshold (RET-005).~~ Resolved in RET-006/RET-009: the analysis call expands short queries (largest answerable distance 0.984) and the threshold is 1.25.** 1.1 rests on one production data point. Options if single-word queries still sit above it: raise it once the entity check exists, or let the phase 4 query rewrite expand short queries into full questions before embedding (this avoids moving the threshold at all).
19. **~~Which domain is canonical (UI refresh).~~ Resolved in UI-010: learnorthodoxy.net, defined once in `orthodox-site/lib/site.ts`.** If learnorthodoxy.com is also registered, redirect it to .net at the DNS or Vercel level.
20. **Public PDFs (UI refresh, pending permission).** `orthodox-site/public/pdfs/` serves the four English saints volumes and two catechism volumes (34 MB) to anyone, although nothing links to them. Owner's decision (UI-006): don't link to or serve the full books until the publishers' permission is confirmed; citations show book, volume and page as text, and the folder is left untouched for now. Once permission is settled, either add `#page=` links from the Sources list or delete the folder (and ideally purge it from deployments).
21. **Unused `NEXT_PUBLIC_API_URL` in `orthodox-site/.env.local` (UI refresh).** It's no longer read (SEC-003); delete it locally and in Vercel so it can't be reintroduced by accident.
22. **Saint entry names in sources (UI refresh).** The Sources list can show the saint entry a passage belongs to (`SourceRef.entry`), but the backend doesn't send it. The saint record index already knows `name`/`raw_heading`; adding `entry` to `_source_from_metadata` for saints chunks is a small backend change for a later phase.
