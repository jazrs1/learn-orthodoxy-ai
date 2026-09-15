# Decision Log — audit-phase-1

This file records the engineering decisions made while working through the
[AUDIT.md](AUDIT.md) action plan on the `audit-phase-1` branch. It is written for
someone who reads code comfortably but may be new to RAG systems, backend security,
or evaluation methodology. Every entry explains what problem was being solved, which
alternatives were realistic, what was chosen and why, and a short "concept to learn"
with a search term to go deeper.

Entries are grouped by category and numbered per category (`SEC-001`, `LOG-001`,
`EVAL-001`, ...). Commit hashes are filled in after each part is committed.

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
- [Retrieval](#retrieval)
- [Prompting & Generation](#prompting--generation)
- [Frontend](#frontend)
- [Code Cleanup](#code-cleanup)
- [Deployment & Config](#deployment--config)
  - [DEP-001: Model name and tuning knobs moved to environment variables](#dep-001-model-name-and-tuning-knobs-moved-to-environment-variables)
- [Open questions](#open-questions)

---

## Security

### SEC-001: Shared-secret header between Next.js and FastAPI
- **Date / Part:** 2026-09-15, Part A (commit: see git log for "Part A")
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
- **Date / Part:** Part A
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
- **Date / Part:** Part A
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
- **Date / Part:** Part A
- **Audit ref:** S4
- **Context:** `/debug/chroma`, `/debug/chroma/{en,ar}` and `/debug/saints` returned sample documents, paths and counts, and `/debug/saints` scans the whole collection.
- **Options considered:** delete the endpoints; keep them but require the internal key (already true after SEC-001); additionally gate them by an env flag.
- **Decision:** Keep them, require the key *and* `ENABLE_DEBUG=1`; otherwise respond `404 Not found`.
- **Why:** They are genuinely useful when diagnosing a Railway volume problem. 404 instead of 403 so their existence is not advertised in production.
- **Files changed:** `api.py` (`_require_debug_enabled`).
- **Concept to learn:** *Feature flags for operational endpoints.* Debug surfaces are a common source of information leaks; gating them by environment keeps production's attack surface small while keeping the tooling one env var away. Search: "security through obscurity vs defense in depth", "feature flag".
- **Revisit if:** you build real observability (LOG-* entries); most of these endpoints then become redundant and can be deleted.

### SEC-005: Per-user rate limiting via a forwarded client IP
- **Date / Part:** Part A
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
- **Date / Part:** Part A
- **Audit ref:** S2, C26
- **Context:** A 50,000-character question would be embedded (failing at the embedding limit) and pasted into the prompt; history was an untyped list of arbitrary size; `top_k` was client-controlled.
- **Options considered:** validate in Pydantic (returns 422 with a schema error), or validate in code with a plain 400 message; cap only the question vs also history.
- **Decision:** In code: `400 Question is too long…` above `MAX_QUESTION_CHARS` (1000, env-configurable); history sanitised to the last 12 well-formed messages of at most 4000 chars each; `top_k` clamped to 1–12 server-side. The Next.js route checks the 1000-char cap too so the user sees the message without a round trip.
- **Why:** A friendly 400 is better for the UI than Pydantic's 422 structure. Bounding history was not in the task list but falls under S2 (unbounded tokens) and was two lines.
- **Files changed:** `api.py` (`_sanitize_history`, chat handler), `orthodox-site/app/api/chat/route.ts`.
- **Concept to learn:** *Input validation at the trust boundary.* Everything from the network is untrusted; size limits protect cost and availability, not only correctness. Search: "input validation OWASP", "denial of wallet".
- **Revisit if:** the product wants long pasted passages as questions (raise the cap and truncate the retrieval query separately).

### SEC-007: Generic error messages to clients
- **Date / Part:** Part A
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
- **Date / Part:** Part A
- **Audit ref:** C24, C30
- **Context:** Completions had no timeout and no retry; a stalled OpenAI request held the worker until Vercel gave up at 20 s.
- **Options considered:** hand-written retry loop around each call (like `ingest_embeddings.py` does); use the OpenAI SDK's built-in `timeout` and `max_retries`; a generic library such as `tenacity`.
- **Decision:** SDK built-ins: `OpenAI(timeout=25, max_retries=1)`. The SDK retries once, with backoff, on 408/409/429/5xx, connection errors and timeouts.
- **Why:** It is the smallest correct change and covers every call through that client (including the embedding calls Chroma makes are *not* covered — Chroma constructs its own OpenAI client; see Open questions).
- **Files changed:** `api.py` (startup).
- **Concept to learn:** *Timeouts and bounded retries.* A retry is only safe for idempotent operations (a completion request is), and must be bounded or it multiplies load during an outage. The 25 s timeout plus one retry means a worst case of ~50 s, longer than the Vercel proxy's 20 s abort, so the proxy remains the effective ceiling. Search: "exponential backoff retry idempotent", "timeout budget".
- **Revisit if:** streaming is added (per-token timeouts differ), or the proxy timeout changes.

### REL-002: max_tokens on every completion
- **Date / Part:** Part A
- **Audit ref:** S2, C24
- **Context:** No completion had `max_tokens`; the model could in theory run to its maximum output length.
- **Decision:** `ANSWER_MAX_TOKENS` (default 1200, env-configurable) on both answer completions; the dead query-rewrite helper already had 90.
- **Why:** 1200 tokens is roughly 900 words, enough for a thorough theology answer with room for citations later, while bounding cost.
- **Files changed:** `api.py`.
- **Concept to learn:** `max_tokens` caps *output* tokens only; input cost is bounded by the context you assemble (chunk count and size). Search: "OpenAI max_tokens vs context window".
- **Revisit if:** answers get truncated mid-sentence (raise it, or ask the model for a length target in the prompt).

### REL-003: Remove the process-global `last_list` and digit regex
- **Date / Part:** Part A
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
- **Date / Part:** 2026-09-15, Part B
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
- **Date / Part:** Part B
- **Audit ref:** A8, S5
- **Context:** The task requires retrieved chunk ids with distances and which chunks survived filtering, but forbids logging chunk text or the full history.
- **Options considered:** change `_retrieve_documents` to return ids/distances (touches every caller and the merge/filter helpers, risking a behaviour change in a "logging only" part); or reconstruct ids from metadata and record hits inside the retrieval functions via a context variable.
- **Decision:** The second. `chunk_id_from_metadata()` rebuilds the deterministic ingestion id (`saints1.pdf::p329::c0`, `ar::…`, `website::<hash>::c<n>`) so "kept" ids can be derived from the surviving metadata without changing any function signature. Inside `_retrieve_documents` the Chroma response's `ids` and `distances` are attached per query; the lexical Arabic search attaches its integer scores. History contributes only a message count; the question is logged truncated to 300 chars (it is needed to interpret the retrieval queries, which contain it anyway).
- **Why:** Zero change to ranking behaviour in this part, and the ids are enough to look up any chunk in Chroma or the eval tooling.
- **Files changed:** `request_log.py`, `api.py` (`_retrieve_documents`, `_retrieve_arabic_lexical_documents`, filter call sites).
- **Concept to learn:** *Log minimisation.* Logs are a data store with weak access controls; keep identifiers, not payloads. Vector "distance" here is Chroma's default L2 distance between query and chunk embeddings (lower = more similar); logging it lets you later pick a similarity threshold from real traffic. Search: "PII in logs", "cosine vs L2 distance embeddings".
- **Revisit if:** ingestion id formats change (update `chunk_id_from_metadata` in lockstep, or store the id in metadata at ingest time, which is the cleaner long-term fix).

### LOG-003: Refusal detection reuses the existing phrase heuristic, extended to Arabic
- **Date / Part:** Part B
- **Audit ref:** C23
- **Context:** The log needs a "was this a refusal?" flag. The only signal today is `_response_grounding_status`, which sniffs English phrases in the answer; the Arabic refusal sentence was not detected, so an Arabic refusal was logged as `answered`.
- **Decision:** Added the Arabic no-source marker to the heuristic and log `refusal` + `grounding` + a `refusal_reason` for pipeline-level refusals (`nothing_retrieved`, `no_source_after_filter`, `saint_not_in_index`). Did not build a structured "grounded/refused" model output yet (AUDIT C23) because that changes prompting, which is a later part.
- **Files changed:** `api.py`.
- **Concept to learn:** Distinguish *pipeline refusals* (retrieval returned nothing) from *model refusals* (the LLM said it could not find it). They need different fixes, so log which one happened. Search: "RAG failure modes retrieval vs generation".
- **Revisit if:** the prompt is rewritten to return a structured grounding field; then replace the phrase sniffing entirely.

### LOG-004: Per-stage latency via "laps" rather than nested timers
- **Date / Part:** Part B
- **Context:** Per-stage timing (prepare, retrieval, filter, retry, generation, postprocess) was required. The handler is one long function with early returns, so wrapping each stage in a `with` block would have meant re-indenting hundreds of lines.
- **Decision:** `trace.lap("name")` records the time since the previous lap. A `stage()` context manager also exists for new code.
- **Why:** Minimal diff, and laps naturally sum to `total_ms`. Windows' clock resolution (~15 ms) makes sub-millisecond stages show as `0.0`; on Linux (Railway) they will be accurate.
- **Files changed:** `request_log.py`, `api.py`.
- **Concept to learn:** Measuring where time goes is the first step of any latency work; here retrieval (which includes the embedding HTTP call) and generation dominate. Search: "latency budget", "p95 latency".
- **Revisit if:** the handler is refactored into stage functions; then use `stage()` blocks.

## Evaluation

_(Part C entries will be added here.)_

## Retrieval

_(No changes yet; re-ingestion and ranking are out of scope for this phase.)_

## Prompting & Generation

_(No changes yet.)_

## Frontend

_(See SEC-003, SEC-005, SEC-006 for the Next.js route changes.)_

## Code Cleanup

_(Deferred to a later phase; see AUDIT.md §3.)_

## Deployment & Config

### DEP-001: Model name and tuning knobs moved to environment variables
- **Date / Part:** Part A
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
5. **Rate-limit keys for shared networks.** 20/min per IP may be too low for a church group on one Wi-Fi network; keying on the anonymous session cookie (forwarded from Next.js) would be fairer.
