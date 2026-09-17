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
- [Prompting & Generation](#prompting--generation)
  - [GEN-001: System prompts live in versioned files under prompts/](#gen-001-system-prompts-live-in-versioned-files-under-prompts)
  - [GEN-002: A learner-oriented prompt with one refusal rule, numbered passages and inline [n] citations](#gen-002-a-learner-oriented-prompt-with-one-refusal-rule-numbered-passages-and-inline-n-citations)
  - [GEN-003: Conversation history is sent as real messages](#gen-003-conversation-history-is-sent-as-real-messages)
  - [GEN-004: Prompt v3 — flexible about format and task, strict about content](#gen-004-prompt-v3--flexible-about-format-and-task-strict-about-content)
  - [GEN-005: Generation model: gpt-4.1-mini recommended over gpt-4o-mini](#gen-005-generation-model-gpt-41-mini-recommended-over-gpt-4o-mini)
  - [GEN-006: Named-subject check before generation, plus a scope gate for Arabic](#gen-006-named-subject-check-before-generation-plus-a-scope-gate-for-arabic)
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
- [Code Cleanup](#code-cleanup)
- [Deployment & Config](#deployment--config)
  - [DEP-001: Model name and tuning knobs moved to environment variables](#dep-001-model-name-and-tuning-knobs-moved-to-environment-variables)
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
