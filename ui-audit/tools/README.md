# UI audit tools

Scripts used for `UI_AUDIT.md` and the before/after comparison (DECISIONS.md UI-002, UI-003).
Screenshots and reports are written to `ui-audit/before/` and `ui-audit/after/`, which are not committed.

They need `playwright` (1.55), `@axe-core/playwright` and `lighthouse`, installed anywhere outside
the site (they are not site dependencies). Copy the scripts next to that `node_modules`, then:

```sh
# 1. Production build with dead database/backend addresses, so nothing real is touched.
cd orthodox-site && npm run build
POSTGRES_URL=postgres://u:p@127.0.0.1:1/x DATABASE_URL=postgres://u:p@127.0.0.1:1/x \
  ORTHODOX_API_URL=http://127.0.0.1:9 ORTHODOX_API_KEY=dummy npx next start -p 3217

# 2. Screenshots, axe and overflow report (every /api/* call is answered from fixtures.json).
#    BASE_URL overrides http://localhost:3217.
CHROME_BIN=/path/to/chrome node capture.mjs ../ui-audit/after
CHROME_BIN=/path/to/chrome node extra.mjs ../ui-audit/after

# 3. Social card (writes orthodox-site/public/og-image.png from public/brand/wordmark.svg)
REPO_ROOT=/path/to/repo CHROME_BIN=/path/to/chrome node og-image.mjs
```

`fixtures.json` holds real answers copied from the phase 4 eval runs plus the saint name
indexes; no script calls OpenAI.

## Brand assets (design-traditional, UI-012)

`brand.mjs` builds the logo SVGs, PNG renders and comparison sheets in `ui-audit/brand/`. It needs
`fontkit`, `sharp` and `playwright`, and EB Garamond's variable font
(`EBGaramond[wght].ttf` from github.com/google/fonts, `ofl/ebgaramond`, saved as `EBGaramond-VF.ttf`):

```sh
FONT_DIR=/path/to/fonts REPO_ROOT=/path/to/repo CHROME_BIN=/path/to/chrome node brand.mjs ../ui-audit/brand
# add SITE_DIR=/path/to/orthodox-site to install the site assets into public/brand/ (UI-014)
```

## Lighthouse and reading fonts (design-traditional, UI-013)

`lighthouse.mjs` runs Lighthouse (mobile and desktop presets) on the home, chat, credits and contact
pages and writes a summary with scores, paint timings, layout shift and font bytes:

```sh
BASE_URL=http://localhost:3217 CHROME_BIN=/path/to/chrome node lighthouse.mjs ../ui-audit/after-traditional 2
```

`reading-fonts.mjs` renders one eval answer at phone width in EB Garamond and Source Serif 4 and
measures x-height and characters per line (needs `marked`, and the two variable fonts in FONT_DIR):

```sh
FONT_DIR=/path/to/fonts CHROME_BIN=/path/to/chrome node reading-fonts.mjs ../ui-audit/typography
```

`compare.mjs` puts the deployed design and the new one side by side for review (UI-015):

```sh
node compare.mjs ../ui-audit/before-traditional ../ui-audit/after-traditional
```

## Calendar (CAL-007)

`calendar.mjs` captures the Today strip and `/calendar` in seven states, in English and Arabic at 1440 and
390 px, with axe and a tap-target/overflow report (needs `playwright` and `@axe-core/playwright`):

```sh
BASE_URL=http://localhost:3217 CHROME_BIN=/path/to/chrome node calendar.mjs ../calendar
PAGES=calendar,home BASE_URL=http://localhost:3217 CHROME_BIN=/path/to/chrome node lighthouse.mjs ../calendar 2
```

## Arabic citations right-to-left (ING-007)

`rtl-sources.mjs` renders a real v2 Arabic answer and its sources (`rtl-sources.fixture.json`) with every
`/api/*` call mocked, and writes screenshots plus `rtl-report.json`: text direction of each source and,
for every page range, whether the first number is laid out before the second (it must be; without an
LTR isolate Chrome shows "118–119" as "119–118" in RTL text).

```sh
CHROME_BIN=/path/to/chrome node rtl-sources.mjs ../ui-audit/rtl
```

## Namesake menus (RET-010)

`saint-menu.mjs` asks "search saint: St. Athanasius" (English) and "من هو القديس أثناسيوس؟" (Arabic) with
every `/api/*` call mocked by menus captured from the local v2 backend. It records the request body a
chip click posts to `/api/chat` (it must carry `saintId`) and the drop cap of the menu message (none)
and of the sourced answer (English only), and writes screenshots plus `saint-menu-report.json`.

```sh
CHROME_BIN=/path/to/chrome node saint-menu.mjs ../ui-audit/saint-menu
```

## Home page declutter (UI-017 to UI-022)

`declutter.mjs` captures the home page in English and Arabic at 1440 and 390 px (first screen, full
page, past-chats drawer open) and the chat page at 1440, with every `/api/*` call mocked and past
chats that repeat a title, and runs axe on each state. Screenshots and `declutter-report.json` go
to `ui-audit/declutter/<before|after>/` (not committed); `lighthouse.mjs` with `PAGES=home` adds
the performance numbers.

```sh
CHROME_BIN=/path/to/chrome node declutter.mjs ../ui-audit/declutter/after
PAGES=home CHROME_BIN=/path/to/chrome node lighthouse.mjs ../ui-audit/declutter/after 3
```

## Streamed answers (UI-026, UI-027)

`streaming.mjs` drives the chat page while answers stream, with axe on each state, and writes screenshots,
`.webm` recordings and `report.json`. It needs `playwright` and `@axe-core/playwright`, plus
`@electric-sql/pglite` and `@electric-sql/pglite-socket` for `pg-server.mjs`, a local Postgres, so no
hosted database is written to.

```sh
# 1. A local database and a backend on port 8001 (INTERNAL_API_KEY=localkey for the real one).
node pg-server.mjs ../../orthodox-site/migrations/001_create_chat_tables.sql
python fake_stream_backend.py                        # free: the real api.py with a scripted model
# or the real one (about $0.02 per MODE=real run with gpt-4.1-mini):
# CORPUS_VERSION=v2 OPENAI_CHAT_MODEL=gpt-4.1-mini INTERNAL_API_KEY=localkey uvicorn api:app --port 8001

# 2. The site against them.
cd orthodox-site && npm run build
POSTGRES_URL=postgres://postgres:postgres@localhost:5433/postgres ORTHODOX_API_URL=http://127.0.0.1:8001 \
  ORTHODOX_API_KEY=localkey npx next start -p 3217

# 3. Behaviours (fake backend) or the five check questions (real backend; CASES=english,table… for some).
MODE=fake CHROME_BIN=/path/to/chrome node streaming.mjs ../streaming/fake
MODE=real CHROME_BIN=/path/to/chrome node streaming.mjs ../streaming/real
```

`pg-server.mjs` applies every migration it is given, in order; pass `../../orthodox-site/migrations/*.sql`.

## Share links (UI-030 to UI-033)

`share.mjs` checks share links end to end, without OpenAI. It covers:

- the Share flow: English and Arabic, at 1440 (copy) and 390 (share sheet);
- the shared page, in its own language and on a page in the other one;
- the not-found page, reuse of a link, and the rate limit;
- the link-preview tags, as ten preview fetchers' user agents receive them, parsed by `open-graph-scraper`;
- axe on every state.

It needs `playwright`, `@axe-core/playwright` and `open-graph-scraper`. Run it with the fake backend and a fresh `pg-server.mjs` (with both migrations): the rate-limit check counts every link made since the database started.

```sh
CHROME_BIN=/path/to/chrome node share.mjs ../share
```
