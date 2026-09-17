# UI/UX Audit — LearnOrthodoxy frontend (`orthodox-site/`)

Branch `ui-refresh` (off `audit-phase-4`), 2026-09-16. Read-only: no site code was changed.
Screenshots are in `ui-audit/before/`, named `{lang}-{viewport}-{nn}-{state}.png`
(`en`/`ar`, `desktop` = 1440×900, `mobile` = 390×844 at 2×). Raw measurements are in
`ui-audit/before/_capture-report.json` (axe, overflow, tap targets, console output, titles) and
`ui-audit/before/_lighthouse.json`.

## How this was captured

- Production build (`next build && next start`) on a local port. `POSTGRES_URL`/`DATABASE_URL` and
  `ORTHODOX_API_URL` were overridden to dead local addresses so nothing could reach the Neon
  database or the backend.
- In the browser (Playwright, Chromium), every `/api/*` request was intercepted and answered from
  fixtures. The chat answers are **real backend answers taken from the Phase 4 eval runs**
  (`CAT-06` long answer, `PRD-03` and `TSK-09` tables, `KW-03`/`SNT-08` saints, `AR-08`/`AR-02`
  Arabic, `OOC-03`/`OOC-10` refusals). The saint lists are the real English (1,363) and Arabic
  (1,936) indexes, read from the local Chroma store without embeddings.
- **OpenAI API calls made: 0.** No eval was run.
- Two fixtures are not real: the Arabic table (no Arabic table answer exists in the eval data) and
  the saint-detail panel, which shows the St. Anthony answer under whatever saint was clicked
  (`en-desktop-16-saint-detail.png`). That mismatch comes from the fixture, not from the site.
- Tools: `@axe-core/playwright` (WCAG 2.0/2.1 A+AA and best practices) on 34 page states, and
  Lighthouse 12 (mobile and desktop presets) on `/`, `/chat`, `/credits`, `/contact`. The scripts
  are in `ui-audit/tools/`, so the "after" pass can be captured the same way.
- Not testable headless: a real on-screen keyboard, iOS Safari's viewport behavior, and real
  screen reader output. Those points are marked *(needs device check)*.

---

## 1. First impression (the 10-second test)

**What is this?** Partly clear. The big cross and "Learn Orthodoxy" say *Orthodox Christian*, and
"Ask questions about Orthodox saints and Coptic Orthodox catechism." says *you can ask questions*
(`en-desktop-01-home.png`). Nothing says it is an **AI assistant**, nothing says the answers come
**only from Fr. Tadros Malaty's books, with page citations** (the site's main trust argument, now
buried on Credits), and nothing shows what a good question looks like.

**Who is it for?** Not stated. The Credits page says "youth and servants" and people curious about
Orthodoxy; the home page doesn't say this.

**What do I do?** Type in the box. That part works. But the box is the only thing on the page:
there are no example questions, no links to the Catechism topics or Saints browser, and the lower
half of the screen is empty on both desktop and mobile (`en-mobile-01-home.png`).

**What gets in the way:**
- On desktop, a new visitor's first view is a 300px sidebar reading "Chats / New Chat / PAST CHATS /
  No saved chats yet." That's app chrome for returning users, and it takes a fifth of the landing
  page.
- The name appears twice within 400px (header and hero).
- The subtitle is faint (contrast 3.07:1, below AA).
- The disabled send button is a grey circle, so the page looks inactive until you type.
- An Arabic visitor first sees the English page, which switches to Arabic after JavaScript loads
  (`ar-mobile-23-first-paint-before-hydration.png`; see §5).

**Verdict:** the look is warm and appropriate, and the cross is a strong asset. But the page reads
as a blank chatbot with a logo, not as a trustworthy learning resource. The home page is the
biggest first-impression opportunity.

## 2. Visual design

**What works and should be kept:**
- The warm parchment background.
- The dark umber accent (`#3a2616`).
- The Coptic cross artwork.
- A serif reading face.
- Rounded, soft surfaces.

The site already has an identity, so the refresh should refine it rather than replace it.

**Typography**
- Merriweather is loaded with a CSS `@import` from Google Fonts. That blocks rendering (Lighthouse
  estimates about 2.2s saved on mobile) and has no `next/font` subsetting or fallback metrics.
- Merriweather is used for everything: headings, body, buttons, nav, labels, and inputs' placeholder
  (but not their typed text). It's a heavy screen serif, and at 16px in long answers it reads dense.
- **The font changes between elements:**
  - The empty state "Start by asking a question below." (`en-desktop-03-chat-empty.png`), the
    "PAST CHATS" label, the contact inputs' typed text (`en-desktop-18-contact.png`), and the whole
    `/about` page (`en-desktop-22-about-orphan.png`) fall back to the system sans (Segoe UI).
  - The 404 page is Next's default, in black Arial on white (`en-desktop-19-404.png`).
- There's no Arabic font. Merriweather has no Arabic glyphs, so Arabic renders in the OS default
  (Times New Roman / Arial on Windows). It looks smaller and lighter than the Latin text around it
  (`ar-desktop-01-home.png`, `ar-desktop-08-chat-table-top.png`).
- There's no type scale: sizes are ad hoc (`0.7rem`, `0.76rem`, `0.78rem`, `0.82rem`, `0.83rem`,
  `0.84rem`, `0.92rem`, `0.95rem`, `0.98rem`, `1.02rem`, `1.05rem`, …).

**Color**
- Only a few tokens exist in `:root`. `globals.css` has 71 hard-coded `rgba()` values, including
  17 different alphas of the same brown (`rgba(58, 38, 22, x)`).
- Text is softened with `opacity` rather than a token, and that's what pushes the subtitles below
  AA (3.07:1 and 3.63:1).
- The Credits links are a generic blue (`#1f5f9e`) that appears nowhere else.
- There's no dark mode. `en-desktop-21-dark-scheme-home.png` is identical to light.

**Hierarchy and layout**
- The header brand moves between pages: it's offset 300px on `/` and `/chat` (the sidebar is fixed)
  and sits at the left edge on `/credits` and `/contact`. Moving between pages feels like switching
  apps.
- The desktop sidebar exists on Home and Chat but not on Credits and Contact.
- Two navigation systems overlap on desktop: header tabs ("Chat · Catechism · Saints Search") and
  the sidebar. On mobile, the same links live only in the hamburger drawer.
- The chat column is capped at 900px, and assistant bubbles at 72% of that (≈650px). At 1440px,
  about half the screen is empty while tables are cut off (`en-desktop-08-chat-table-top.png`).
- Catechism topic cards are well structured (`en-desktop-12-catechism-expanded.png`), but the
  uppercase pill labels ("PRAYER", "RULE") just repeat the question and add noise.

**Things that look unfinished or templated**
- Close and delete buttons are the letter "x" instead of an icon (sidebar, mobile drawer:
  `ar-mobile-10-chat-sidebar-open.png`).
- Send is a "→" text glyph.
- The copy icon is a large grey glyph under every message, including the user's own question.
- The follow-up suggestions are bold underlined sentences that read as body links, not as tappable
  suggestions (`en-desktop-09-chat-long-bottom.png`).
- The saint detail "Learn more" is a bare underlined word and is hard-coded in English.
- The default Next 404 page.
- The `/about` page: unstyled, left-aligned against the viewport edge, linked from nowhere, but
  listed in the sitemap.
- The Saints browser is a flat alphabetical list of 1,363 names with no letter index, count, or
  context (`en-desktop-13-saints-list.png`).

## 3. Chat UX

**Citations and sources (the biggest trust gap).**
- Answers are written with `[1]`, `[2][5]` markers, and the backend returns a `sources` array
  (book, page) with every message. The frontend stores it (`ChatMessage.sources`) and never
  renders it.
- So the reader sees bracketed numbers that go nowhere: `en-desktop-08-chat-long-top.png`,
  `en-desktop-09-chat-long-bottom.png` ("[1][2][4][5][6]"), and the tables' `[17][18]`
  (`en-desktop-08-chat-table-top.png`).
- For a site whose promise is "answers from trusted sources", this is the single most important
  fix. The data is already there: `{ pdf: "saints2.pdf", page: 406 }` maps to readable labels, and
  the English PDFs are already public under `/pdfs/`, so `/pdfs/saints2.pdf#page=406` could open
  the exact page. (Whether those PDFs *should* be public is an open question: see DECISIONS.md.)

**Long answers**
- Rendering is clean (Markdown lists, bold, paragraphs).
- The bubble is narrow (~650px) with 1.6 line height, so a 2,400-character answer is a long, narrow
  scroll.
- A long answer is a document, not a chat bubble. It would read better as a full-width "article"
  block with a comfortable 65–70ch measure and a sources footer.
- New answers scroll so the question sits at the top, which is good.

**Tables**
- The Markdown rendering works, and the scroll containment from FE-002 holds.
- On desktop the table is squeezed into the 650px bubble while about 400px next to it is empty.
  The third column of `PRD-03` is completely hidden, with no visible cue that the table scrolls
  (`en-desktop-08-chat-table-top.png`, `en-desktop-08-chat-table2-top.png`, where the "Source"
  column shows only "[1").
- On mobile, a 292px-wide scroll box shows 1.5 columns (`en-mobile-08-chat-table-top.png`); the
  table is 673px wide inside it.
- Rows are very tall because cells wrap at `max-width: 28rem`.

**Follow-up chips**
- They're phrased as the bot asking a question ("Would you like to ask how this is practiced in
  Church life?"), styled as body-text links, and placed inside the answer bubble.
- On click, the text is rewritten to "I would like to ask how…" before sending. So the chip label
  and the message that appears differ, which is surprising.
- `TSK-09` (tunes table) offers fasting follow-ups. That's a backend relevance issue, noted only.

**Loading** (`en-desktop-05-chat-loading.png`)
- Three animated dots in a small bubble. Answers take several seconds (analysis + retrieval +
  generation), and there's no sense of progress or what's happening.
- The composer is disabled while loading, but it looks the same.
- A "Searching the catechism and saints books…" line would set expectations and reinforce the
  sources story.

**Errors** (`en-desktop-07-chat-error.png`)
- The same message appears twice: as a plain grey line at the top of the thread and as an ordinary
  assistant bubble with a copy button. It isn't styled as an error, and there's no Retry.
- The failed request still leaves an empty "New Chat" entry in the sidebar.
- Error strings from the server are shown raw. Some are developer-facing: "The backend API URL is
  not configured. Set ORTHODOX_API_URL.", "connect ECONNREFUSED …", and "Chat storage is not
  configured. Set POSTGRES_URL…".
- The client-side fallback strings ("Sorry — I could not reach the Orthodox AI server…",
  "Unable to load saint details right now.") are English only.

**Refusals** (`en-mobile-08-chat-refusal-top.png`, `ar-desktop-08-chat-refusal-top.png`)
- The English refusal text is good: it says what the sources cover.
- It looks identical to an answer, and it offers nothing to click. A refusal is where suggested
  starting questions help most.

**Other chat defects**
- **Question marks are stripped from what the user typed.** `followUpToUserMessage()` runs on
  every message, not just chips, and removes a trailing `?`. "What is fasting?" is stored and shown
  as "What is fasting" (`en-desktop-07-chat-error.png`, `en-desktop-05-chat-loading.png`).
- **The composer never grows.** The textarea is fixed at 22px, so a multi-line question shows only
  its last line (`en-mobile-24-multiline-composer.png`).
- **Opening `/chat` with no `?chat=` jumps into the most recent past conversation.** The header's
  "Chat" link therefore doesn't start a new chat for returning users.
- **Deleting a conversation** happens on one click of a small "x", with no confirmation or undo.
- **Clickable saint names** in answers are subtle pill-shaded bold text. There's no hint that
  they're interactive until hover.

**Trustworthiness for learners, overall**
- The tone and look are respectful.
- Four things undercut trust: missing sources, the unlabeled AI nature, the raw error strings, and
  refusals that look like answers.

## 4. Mobile (390px)

- **The Arabic contact page is broken.**
  - Cause: the honeypot field is positioned with `left: -10000px`. In RTL, that creates about
    10,000px of scrollable overflow.
  - Measured: the document is 10,390px wide, the mobile layout viewport widens to 1,560px, and the
    page loads scrolled 1,170px sideways, so the first view is blank (`ar-mobile-18-contact.png`).
    Desktop has the same 11,440px overflow (`ar-desktop-18-contact.png`; the blank capture there is
    partly a Chromium screenshot quirk, but the overflow is real).
  - Fix: one line (`inset-inline-start`, or `clip`/`left: 0` with `opacity: 0`). *(Confirm on a
    real phone.)*
- **The Arabic 404 page** also overflows (420px in a 390px viewport).
- **Tap targets under 44px** (`_capture-report.json` → `tapTargets`):
  - The language toggle buttons are 21px tall. That's the most-used control for Arabic users.
  - The hamburger, drawer close, and drawer home icon are 34×34.
  - The composer textarea is 22px tall.
  - The copy icon and the sidebar delete "x" are about 24px.
- **The keyboard covering the input** *(needs device check)*:
  - The chat page is `height: calc(100dvh - 70px)` with the composer at the bottom of a flex
    column.
  - On iOS Safari, `dvh` doesn't shrink for the on-screen keyboard. The viewport meta has no
    `interactive-widget=resizes-content` and there's no `visualViewport` handling, so the composer
    can end up under the keyboard or the page can jump.
  - Inputs are 16px, so iOS won't zoom on focus. That part is fine.
- **The home page is `height: calc(100vh - 76px); overflow: hidden`.** On a short phone, or in
  landscape, content below the fold is cut off and can't be scrolled to.
- **The header is a hamburger, the centered name, and the language pill.** Chat, Catechism, and
  Saints aren't visible without opening the drawer. On a learning site, those three are the
  product and deserve a visible tab bar or segmented control.
- **The drawer** mixes navigation and chat history in one scrolling panel, which works
  (`ar-mobile-10-chat-sidebar-open.png`).
- **Saint detail on mobile:** the panel appears *above* the search box and pushes the list down
  (`en-mobile-15-saint-detail-loading.png`). There's no back gesture or URL for a saint.
- **No horizontal page scroll in English**, which is good. Tables scroll inside their own box only.

## 5. Arabic / RTL

**Correct**
- `html[dir=rtl]` is set.
- The nav order mirrors.
- Answer text, lists, and the catechism cards are right-aligned.
- **Tables render correctly right-to-left:** the header column is on the right, and the scroll
  starts at the right edge (`ar-desktop-08-chat-table-top.png`, `ar-mobile-08-chat-table-top.png`).
  This closes the open item in FE-002.
- Credits has a real Arabic version (`ar-mobile-17-credits.png`).

**Incorrect or weak**
1. **The Arabic contact page overflow** (see §4). Critical.
2. **There's no Arabic typeface** (see §2), so the Arabic text looks like a fallback.
3. **The first paint is always English.** `layout.tsx` hard-codes `lang="en" dir="ltr"`, and
   `LanguageProvider` reads `localStorage` after hydration, so Arabic users see English, LTR, then
   Arabic on every page load (`ar-mobile-23-first-paint-before-hydration.png`). Search engines only
   ever see English, and there's no `/ar` URL or `hreflang`.
4. **The composer and search placeholder bidi is wrong.** With `dir="auto"` on an empty textarea,
   the Arabic placeholder is laid out LTR, so the ellipsis lands on the wrong side ("...اسأل عن
   قديس", `ar-mobile-09-chat-long-bottom.png`).
5. **The send arrow "→" points away from the reading direction in RTL.**
6. **The layout is only half mirrored.** `.chat-layout`, `.home-layout`, and `.chat-sidebar` are
   forced `direction: ltr`, so the desktop sidebar stays on the left and the user and assistant
   bubbles keep English sides while the text inside is RTL (`ar-desktop-08-chat-table-top.png`).
   Arabic chat apps usually mirror both.
7. **Citation markers inside Arabic text get bidi-scrambled.** "(مقاطع [1][3][4][5][10])" renders
   with the parentheses flipped (`ar-mobile-09-chat-long-bottom.png`). Rendering citations as
   isolated elements (`<sup>`/`<bdi>`) fixes this.
8. **Hard-coded English inside the Arabic UI:**
   - "Learn more" (saint detail).
   - `aria-label`s: "Assistant is typing", "Learn Orthodoxy modes", "Table".
   - The alt text "Coptic cross".
   - The fallback error strings.
   - The honeypot label.
9. **`og:locale`** is always `en_US`.

## 6. Accessibility

**Automated results**
- Lighthouse accessibility scores 100 on every page tested. axe found 4 rule violations, listed
  below.
- Both tools miss opacity-based contrast, focus visibility, and live regions, so the manual
  findings under the table matter more than the scores.

| axe rule | Impact | Where |
|---|---|---|
| `nested-interactive` | serious | Sidebar chat items: a `<span role="button">` delete inside a `<button>` (all chat states, 4–5 nodes each) |
| `page-has-heading-one` | moderate | `/chat` (all tabs): there's no `<h1>` |
| `landmark-one-main`, `region` | moderate | The 404 page has no `<main>` |

**Manual findings**
- **Contrast:**
  - Hero subtitle 3.07:1 and page subtitles 3.63:1 (the text is dimmed with `opacity`). Both fail
    AA for body text.
  - Placeholders 3.44:1.
  - The disabled send button 2.34:1. Disabled controls are exempt, but it's also the resting state
    of the most important button.
  - `--text-soft` on the background is fine (6.16:1).
- **Focus:** there are no custom focus styles.
  - The browser default ring shows on links (`en-desktop-20-keyboard-focus.png`).
  - The composer, saints search, and contact inputs remove the outline (`outline: none`) and
    replace it with a very faint border change. Keyboard users lose their place.
- **Keyboard order:**
  - The header comes first, then main, then the sidebar (which is last in the DOM, although it
    appears on the left).
  - There's no skip link.
  - Catechism topics use `<details>`, which is good.
- **Screen readers:**
  - The message list has no `role="log"` or `aria-live`, so a new answer isn't announced.
  - The typing indicator is a `role="status"` with an English label.
  - The language toggle is a `div` with an `aria-label` but no role, and the buttons don't expose
    their pressed state (`aria-pressed`).
  - The active mode in the header has no `aria-current`. The drawer version does.
  - Clickable saint names are buttons with no hint that they start a search.
  - Copy buttons have labels, which is good.
- **Semantics:**
  - Chat messages aren't grouped as articles.
  - The saint detail title is an `<h2>` with no `<h1>` above it.
  - The `/about` page reuses classes that don't exist in the CSS.
- **Motion:** the typing dots and hover lifts don't respect `prefers-reduced-motion`.
- **Alt text:** the hero cross has "Coptic cross". Fine, though it's decorative next to the site
  name and could be `alt=""`. The Fr. Tadros portrait has alt text.

## 7. Performance and polish

**Lighthouse** (production build, local server; `_lighthouse.json`)

| Page | Perf (mobile / desktop) | A11y | Best practices | SEO | Mobile FCP / LCP | CLS (mobile) |
|---|---|---|---|---|---|---|
| `/` | 81 / 98 | 100 | 96 | 100 | 2.9 s / 4.2 s | 0.008 |
| `/chat` | 90 / 99 | 100 | 96 | 100 | 1.6 s / 3.6 s | 0 |
| `/credits` | 86 / 98 | 100 | 96 | 100 | 2.8 s / 3.1 s | **0.107** |
| `/contact` | 87 / 98 | 100 | 96 | 100 | 2.9 s / 3.4 s | 0.035 |

**Performance issues**
- The Best Practices score of 96 comes from console errors caused by the dead local API. It isn't
  a production issue.
- **Render-blocking Google Fonts `@import`:** about 2.2s on mobile. Move to `next/font` (self-hosted,
  subset, `size-adjust` fallbacks).
- **The LCP image `public/cross.png` is a 2.3 MB, 1024×1536 PNG** used at 260px and 34px.
  `next/image` resizes it, but Lighthouse still flags about 55 KB of savings and a missing
  `fetchpriority`. A trimmed square SVG or WebP source would be better, and would double as the
  favicon and logo.
- **Credits layout shift (0.107):** Lighthouse attributes it to the `<article>` reflowing. The
  likely cause is the late Merriweather swap (`display=swap` from a render-blocking `@import`). For
  Arabic visitors, the English-to-Arabic switch after hydration adds a second, larger shift.
- About 92 KB of unused JavaScript per page. `/chat` is one 1,200-line client component that also
  fetches the first 200 saint names on every visit, even when the Saints tab is never opened.

**Page titles and metadata**
- Every page, including 404, has the same `<title>`: "Learn Orthodoxy".
- Every page's `<link rel="canonical">` points to `https://learnorthodoxy.net`, which tells search
  engines that `/credits` and `/contact` are duplicates of the home page. Each page needs its own
  `metadata` (title template, description, canonical).
- **`/og-image.png` is referenced by Open Graph and Twitter metadata but returns 404**, so every
  shared link shows no preview image. Reviewers will notice this.
- **The favicon** is a 107 KB, 256×256 `.ico`. There's no `apple-touch-icon`, web manifest, or
  `theme-color`.
- **Domain mismatch.** `layout.tsx:6`, `sitemap.ts:3`, and `robots.ts:3` hard-code
  `https://learnorthodoxy.net`, and the Credits text says "LearnOrthodoxy.net". You've referred to
  learnorthodoxy.com. Whichever domain is canonical should come from a single
  `NEXT_PUBLIC_SITE_URL`, and the other should redirect.
- `robots.ts` emits the non-standard `Host:` line with a full URL.
- The sitemap lists `/about` (the orphan page) but not `/chat`.
- Arabic has no alternate URLs.
- The Google site verification token is in `layout.tsx`, which is fine but tied to one domain.

## 8. Leftover scaffolding and console output

- **17 `console.log`/`console.debug` calls in `app/chat/page.tsx`**, visible in any visitor's
  devtools on every page view and message. Examples: `ACTIVE_LANGUAGE`, `ACTIVE_MODE`,
  `SAINTS_ENDPOINT_CALLED`, `SAINTS_REQUEST_URL`, `CREATE_CONVERSATION`, `SAVE_CHAT_TURN`,
  `CALL_BACKEND`, `CHAT_PAYLOAD`, `SAVE_ASSISTANT_MESSAGE`, `SAINT_SELECTED_NAME`, and
  `SAINT_DETAIL_PAYLOAD`.
  - `CHAT_PAYLOAD` and `CALL_BACKEND` print the full question.
  - The full list for each state is in `_capture-report.json` → `console`.
- Two more on the server: `NEXT_CHAT_LANGUAGE_FORWARDED` in `api/chat/route.ts`, and
  `CONTACT_SUCCESS` in `api/contact/route.ts`. These appear in Vercel logs, not in the browser.
- **Unused Create Next App assets:** `public/file.svg`, `globe.svg`, `next.svg`, `vercel.svg`,
  `window.svg`, plus `icons/` (a duplicate of `public/icons/`), `images/creditsformat.png`, and
  `tsconfig.tsbuildinfo` in the tree.
- **`app/about/page.tsx`:** unstyled, unlinked, English only, and says "still developing".
- **`app/sources/page.tsx`:** a redirect to `/credits`. Fine to keep for old links.
- **Unused i18n keys:** `placeholder: "Placeholder"`, `success`, `youMightAlsoAsk`,
  `moreCatechismTopics`, `noSaintsFound`, `english`, `arabic`.
- **Dead CSS:** `.catechism-tab-panel`, `.catechism-inline-panel`, `.message-options-label`,
  `.selected-source-*`, `.source-card*`, `.source-preview-*`, `.chat-page-title/subtitle`. The file
  is 2,100 lines in one global stylesheet with duplicated media-query blocks.
- **Custom DOM events as an app bus:** `chat:insertAndSubmitText`, `chat:openSidebar`, and
  `chat:setMode`. Not visible to users, but they make the UI refactor riskier. That's worth knowing
  before the redesign.
- **`orthodox-site/.env.local` still defines `NEXT_PUBLIC_API_URL`,** which the code no longer
  reads (SEC-003). No leak, just leftover.
- **`chat.html`** (legacy frontend at the repo root) is already tracked as open question 3.

---

## Prioritized fixes

Impact is how much the change improves a **first-time visitor's** sense that the site is
trustworthy, finished, and easy to use. Effort: S ≤ half a day, M ≈ 1–2 days, L = several days.

### Top 5

| # | Fix | Impact | Effort | Evidence |
|---|---|---|---|---|
| 1 | **Show the sources.** Render `[n]` as small linked markers and add a "Sources" footer under each answer: book title, page, and a link to that PDF page where one exists. Isolate the markers for bidi. | Very high | M | `en-desktop-09-chat-long-bottom.png`, `ar-mobile-09-chat-long-bottom.png` |
| 2 | **Rebuild the landing page.** One-line value proposition ("Ask about Coptic Orthodox teaching and the saints. Every answer is drawn from Fr. Tadros Malaty's books, with page references."), 4–6 example questions, entry cards for Catechism and Saints, and a short "how it works / what it can't do" note. Hide the empty chat-history sidebar for visitors with no chats. | Very high | M | `en-desktop-01-home.png`, `en-mobile-01-home.png` |
| 3 | **Fix the broken and embarrassing states.** Arabic contact overflow, error shown twice and unstyled with no Retry, raw developer error strings, stripped question marks, fixed-height composer, English "Learn more", and a branded 404. | High | S | `ar-mobile-18-contact.png`, `en-desktop-07-chat-error.png`, `en-mobile-24-multiline-composer.png`, `en-desktop-19-404.png` |
| 4 | **Typography and design tokens.** `next/font` for a reading serif plus a UI sans plus an Arabic face. A type scale. Color tokens replacing 71 hard-coded `rgba()` values. AA contrast. Visible focus rings. Consistent icons instead of "x" and "→". | High | M | `ar-desktop-01-home.png`, `en-desktop-18-contact.png`, Lighthouse render-blocking |
| 5 | **Share and SEO polish.** Real `og-image.png`, per-page titles and canonicals, one site-URL setting (.net vs .com), favicon set and manifest, remove or merge `/about`, and remove the 17 `console.log` calls. | High for reviewers | S | `_lighthouse.json`, `_capture-report.json` → `console` |

### The rest

| Fix | Impact | Effort |
|---|---|---|
| Answer layout: a wider reading column for assistant answers (article style, about 70ch), with tables allowed to use the full chat width and a visible scroll hint. | High | M |
| Loading state with a message ("Searching the catechism…"), and a clearly disabled composer. | Medium | S |
| Follow-up suggestions as real chips below the answer, with labels matching the sent text. Starter suggestions on refusals. | Medium | S |
| Server-rendered language (cookie-based, `lang`/`dir` on `<html>`) to remove the English flash and the Arabic layout shift. Optional `/ar` routes with `hreflang`. | Medium (high for Arabic users) | M |
| Arabic polish: placeholder `dir`, mirrored send icon, full layout mirroring, and translated aria labels, alt text, and error strings. | Medium | S |
| Mobile: visible Chat / Catechism / Saints switcher, 44px tap targets, keyboard-safe composer (`interactive-widget`, `visualViewport`), and a scrollable home page. | Medium | M |
| Consistent app shell: the same header and sidebar behavior on every page, and one navigation model instead of header tabs plus sidebar. | Medium | M |
| Saints browser: letter index, result count, saint detail as its own view with a URL (`/saints/[name]`), "Ask about this saint" call to action, and the list not pushed down. | Medium | M |
| Accessibility: fix nested delete button (and add confirm/undo), `role="log"` + `aria-live` on messages, `<h1>` on chat, `aria-pressed` on the language toggle, skip link, `prefers-reduced-motion`. | Medium | S |
| "New chat" semantics: the header "Chat" link opens a new chat, and history lives in the sidebar. | Low–medium | S |
| Dark mode, via tokens once #4 lands. | Low–medium | M |
| Replace the 2.3 MB cross PNG with an optimized square source (SVG or WebP) and use it for the favicon and app icons. | Low–medium | S |
| Delete leftover assets, unused i18n keys, and dead CSS. Split `app/chat/page.tsx` into components before restyling. | Low (enables the rest) | M |

---

## Design directions

All three keep the identity that already works: the Coptic cross, a serif for reading, and warm
umber as the anchor color. They differ in how much ornament and warmth they add. Every font listed
has Latin and Arabic coverage through a paired face and is available through `next/font/google`.

### A. Illuminated manuscript (warm, iconographic)

The feel of a well-made church book: parchment, ink, gold, and Coptic red.

- **Palette:**
  - Parchment `#F4EBDD` (background) and vellum `#FBF6EE` (surfaces).
  - Iron-gall ink `#2A1A10` (text) and faded ink `#6B5646` (secondary).
  - Coptic red `#8E2A1E` (accent, citation markers, active states).
  - Burnished gold `#B08A3E` (ornament only, never text).
  - Lapis `#23406B` (links).
- **Type:**
  - Headings: *Cormorant Garamond* (display).
  - Reading: *EB Garamond* or *Literata*.
  - Arabic: *Amiri* (a classical naskh, for both headings and reading).
  - UI labels: *Inter* / *IBM Plex Sans Arabic*, used sparingly.
- **What changes:**
  - A thin ornamental rule drawn from the cross's knotwork frames the header and section breaks.
  - Answers get a small red drop cap and read like a page, with sources set as numbered
    "marginal notes" in a footer.
  - Catechism topics become illuminated index cards with red initials.
  - The Saints browser gets a letter index styled like a manuscript alphabet, and saint pages get
    a simple icon-frame header.
  - The landing page puts the cross over a parchment band with a one-line verse-like tagline.
- **Risk:** ornament can look kitsch or slow if overdone, and it needs restraint on mobile. Dark
  mode is "night vellum" (`#1C1510` background, `#EADFCB` text) and needs care to stay legible.

### B. Clean modern reader (calm, editorial). **Recommended**

A reading app that happens to be Orthodox: typography and whitespace do the work.

- **Palette:**
  - Warm paper `#FAF7F2` (background) and white `#FFFFFF` (reading surface).
  - Ink `#1E1915` (text), `#5E5249` (secondary, 7:1).
  - Umber `#3A2616` (kept: primary buttons, the user's messages).
  - Coptic red `#9A2F24` (citation markers, focus rings, and the one highlight color).
  - Gold `#C29A4B` (the cross and small accents only).
  - Hairlines `#E7DFD4`.
- **Type:**
  - Reading: *Source Serif 4* (or *Literata*), 17–18px with 1.65 line height, a 68ch measure.
  - UI: *Inter*.
  - Arabic: *Noto Naskh Arabic* for reading and *IBM Plex Sans Arabic* for UI.
  - Merriweather is retired, since its role moves to Source Serif.
- **What changes:**
  - Assistant answers stop being bubbles and become full-width article blocks. Each has a small
    "Answer from the catechism" label, inline red citation numbers, and a collapsible *Sources*
    list (book, page, open-PDF link).
  - The user's question sits above the answer as a quiet umber pill.
  - Tables get the full column width with sticky headers.
  - The landing page becomes a centered hero: cross, tagline, composer, example-question chips, and
    two entry cards (Catechism topics, Saints). Chat history only appears once you have some.
  - The header is one consistent shell on every page with Chat / Catechism / Saints as a segmented
    control, which also shows on mobile.
  - Dark mode falls out of the tokens.
- **Why recommended:** it fixes the most important problems (sources, long answers, tables, Arabic
  type, consistency) directly. It keeps the existing warmth and cross. It's the most readable
  option for long doctrinal answers. It's also the least likely to look dated or templated to
  reviewers.

### C. Calm minimal (quiet, liturgical)

Almost monastic: lots of white, one color, very little chrome.

- **Palette:**
  - Near-white `#FCFBF8` (background), stone `#EEEAE3` (surfaces).
  - Charcoal `#232323` (text), `#6A6660` (secondary).
  - A single accent, deep umber `#3A2616`, for buttons and links.
  - Gold `#B8964F` for the cross only.
- **Type:**
  - Headings and reading: *Newsreader* (or *Crimson Pro*).
  - UI: *Inter*, small caps for labels.
  - Arabic: *Noto Naskh Arabic* (reading) and *Noto Kufi Arabic* (UI).
- **What changes:**
  - No cards, shadows, or pills. Sections are separated by space and hairlines.
  - The sidebar collapses to an icon rail.
  - Answers are plain text on the page, with sources as a quiet footnote list.
  - Catechism is a simple two-level list.
  - The landing page is just the small cross, one sentence, the composer, and three example
    questions.
- **Risk:** it can feel cold or generic, and it drops some of the warmth that currently says
  "Coptic". It's the fastest to build.

A hybrid is natural: B's structure and reading layout with A's red and gold accents and one
ornamental divider. I'd suggest that unless you want the full manuscript look.

---

**Next step:** pick a direction (A, B, C, or a hybrid) and tell me which of the top-5 fixes to
include in the first implementation pass. No site code will change until then.

---

## After the UI refresh (2026-09-17)

The top five fixes and one font follow-up are on `ui-refresh` (DECISIONS.md UI-006 to UI-011). The
same capture scripts produced `ui-audit/after/`, with file names that match `before/`. Neither
folder is committed; rerun `ui-audit/tools` to regenerate them. OpenAI calls: 0.

| Measure | Before | After |
|---|---|---|
| Lighthouse performance, mobile (home / chat / credits / contact) | 81 / 90 / 86 / 87 | 91 / 89 / 91 / 92 |
| Lighthouse performance, desktop | 98 / 99 / 98 / 98 | 100 / 99 / 100 / 100 |
| Mobile first contentful paint | 1.6–2.9 s | 0.8 s |
| Mobile largest contentful paint (simulated) | 3.1–4.2 s | 3.3–3.7 s |
| Layout shift, worst page | 0.107 (credits) | 0 |
| Accessibility / SEO (Lighthouse) | 100 / 100 | 100 / 100 |
| axe violations across 32 states | 4 rules, 64 nodes | 0 |
| Pages with horizontal overflow | Arabic contact (10,000 px), Arabic 404 | none |
| Distinct page titles | 1 | 5 |
| Debug `console.log` lines in the browser | 17 kinds | 0 |

Best Practices stays at 96 on both runs only because the audit server's dead database and
backend return 500s.

**Still open** (not part of the top five):
- The mobile language toggle is 36 px tall.
- Wide tables on phones still show about 1.5 columns; an edge shadow hints that they scroll.
- Deleting a chat has no confirmation or undo.
- The Saints browser has no letter index and no per-saint URL.
- On-screen keyboard behavior on iOS is untested.
- The backend doesn't send saint entry names (open question 22).
- Publishing the PDFs is still pending permission (open question 20).

---

## Traditional redesign: verification (2026-09-17)

The `design-traditional` branch (DECISIONS.md UI-012 to UI-015) was compared with the deployed
design (`main`). Both production builds were measured the same way:

- Dead database and backend addresses.
- Every `/api/*` call answered from `ui-audit/tools/fixtures.json`.
- 0 OpenAI calls.

The screenshots, axe and overflow reports were made with `capture.mjs` (32 states). Lighthouse
was run twice per page with `lighthouse.mjs`, using the mobile and desktop presets. The folders are
not committed; rerun `ui-audit/tools` to regenerate them:

- `ui-audit/before-traditional/`: the deployed design.
- `ui-audit/after-traditional/`: the new design.
- `ui-audit/after-traditional/compare/`: side-by-side images for home, chat with a table and
  citations, saints and 404, at 1440 and 390 px, in English and Arabic.

| Measure | Deployed | design-traditional |
|---|---|---|
| Lighthouse performance, mobile (home / chat / credits / contact) | 92–94 / 94–95 / 96 / 93–96 | 92–97 / 92–93 / 94–97 / 95–99 |
| Lighthouse performance, desktop | 100 on every page | 100 on every page |
| Mobile first contentful paint (home, chat, credits / contact) | 0.75 s / 0.75 s | 0.90 s / 0.75 s |
| Desktop first contentful paint (home, chat, credits / contact) | 0.20 s / 0.20 s | 0.24 s / 0.20 s |
| Mobile largest contentful paint, simulated (home / chat / credits / contact) | 3.1–3.3 / 3.0 / 2.8 / 2.8–3.2 s | 2.6–3.3 / 3.2–3.4 / 2.6–3.1 / 2.3–2.9 s |
| Layout shift, every page | 0 | 0 |
| English font files (home, chat, credits / contact) | 2 files, 98 KB | 3 files, 140 KB / 2 files, 93 KB |
| Page weight, mobile (home / chat / credits / contact) | 360 / 388 / 358 / 336 KB | 342 / 383 / 354 / 283 KB |
| Accessibility / SEO / Best Practices (Lighthouse) | 100 / 100 / 96 | 100 / 100 / 96 |
| axe violations across 32 states | 0 | 0 |
| Mobile tap targets under 44 px (English home) | 6 | 1 (the text field inside the 44 px composer) |
| Visible width of a table on a 390 px phone | 322 px | 358 px |
| Pages with horizontal overflow | none | none |
| Console messages | only the mocked 500 and 404 | only the mocked 500 and 404 |

Best Practices stays at 96 on both builds only because the audit server's dead database and
backend return 500s.

**What got worse**
- **First paint is 0.15 s later on phones** (home, chat and credits; Lighthouse simulation) and
  0.04 s later on desktop. EB Garamond Italic is a third font file (47 KB). In the first
  measurement it was loaded late: first paint was 1.2 s, and its swap caused a layout shift of
  0.009. Preloading it only on the pages that use it (UI-015) brought the shift back to 0 and
  first paint to 0.9 s.
- **Chat on mobile scores 92–93 instead of 94–95**, and its simulated largest paint is 3.2–3.4 s
  instead of 3.0 s. The cause is the same extra font.
- **Arabic pages also preload that italic (47 KB) without using it.** next/font preloads per
  route, not per language. Arabic pages already preloaded the two Latin fonts before this change.
- **Your own questions are no longer in a filled, right-aligned bubble.** They are italic lines
  with a gold rule, like a catechism question. The page reads more like a book, but who said what
  now depends on italic type, the gold rule and the hairline between turns.
- **Small-caps labels in EB Garamond are lighter than the old Inter labels.** On 1× Windows
  screens the navigation, buttons and form labels look thinner, although their contrast is still
  at least 7.3:1.
- **Arabic answers look plainer than English ones.** They get no drop cap or italics, because
  both would break Arabic script.
- **The Saints list shows about one name fewer per phone screen**, because each row is now a
  44 px row with a rule under it.
- **The home page title is an image.** "Learn Orthodoxy" is the wordmark's alt text; it is still
  announced and still in the page title. On Arabic pages the heading text is the Arabic name.
- **Shared links keep the old preview card** until each platform fetches the page again.

**Still open** (unchanged from before):
- Wide tables on phones still show about one and a half columns.
- Deleting a chat has no confirmation.
- The Saints browser has no letter index and no per-saint URL.
- iOS keyboard behavior is untested.
- Open questions 20 and 22 in DECISIONS.md.
- The cross is waiting for the priest's choice: set `BRAND_CROSS` in `orthodox-site/lib/brand.ts`.
