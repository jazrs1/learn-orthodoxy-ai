# Decision Log — audit-phase-1 and audit-phase-2

This file records the engineering decisions made while working through the
[AUDIT.md](AUDIT.md) action plan on the `audit-phase-1` branch (Parts A–C) and the
`audit-phase-2` branch (Steps 0–3). It is written for
someone who reads code comfortably but may be new to RAG systems, backend security,
or evaluation methodology. Every entry explains what problem was being solved, which
alternatives were realistic, what was chosen and why, and a short "concept to learn"
with a search term to go deeper.

Entries are grouped by category and numbered per category (`SEC-001`, `LOG-001`,
`EVAL-001`, ...). Commit hashes: Part A `9989d1f`, Part B `9a4e345`, Part C `ab1cd8d`; Phase 2 Step 0 `7c90db7`, Step 1 `f1e6f0c`, Step 2 `124c744`, Step 3 `9fcf9dd`.

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
- [Retrieval](#retrieval)
  - [RET-001: A saint-index miss falls through to retrieval instead of refusing](#ret-001-a-saint-index-miss-falls-through-to-retrieval-instead-of-refusing)
  - [RET-002: The keyword relevance filter is deleted; results are merged by vector distance](#ret-002-the-keyword-relevance-filter-is-deleted-results-are-merged-by-vector-distance)
  - [RET-003: "No relevant source" is decided by a distance threshold chosen from the eval data](#ret-003-no-relevant-source-is-decided-by-a-distance-threshold-chosen-from-the-eval-data)
- [Prompting & Generation](#prompting--generation)
  - [GEN-001: System prompts live in versioned files under prompts/](#gen-001-system-prompts-live-in-versioned-files-under-prompts)
  - [GEN-002: A learner-oriented prompt with one refusal rule, numbered passages and inline [n] citations](#gen-002-a-learner-oriented-prompt-with-one-refusal-rule-numbered-passages-and-inline-n-citations)
  - [GEN-003: Conversation history is sent as real messages](#gen-003-conversation-history-is-sent-as-real-messages)
- [Frontend](#frontend)
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
- **Date / Part:** 2026-09-15, Phase 3 Step 1
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

## Frontend

_(See SEC-003, SEC-005, SEC-006 for the Next.js route changes.)_

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
12. **Rate-limit keys for shared networks.** 20/min per IP may be too low for a church group on one Wi-Fi network; keying on the anonymous session cookie (forwarded from Next.js) would be fairer.
