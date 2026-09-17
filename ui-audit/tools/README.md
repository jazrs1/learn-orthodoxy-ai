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

# 2. Screenshots, axe and overflow report (every /api/* call is answered from fixtures.json)
CHROME_BIN=/path/to/chrome node capture.mjs ../ui-audit/after
CHROME_BIN=/path/to/chrome node extra.mjs ../ui-audit/after

# 3. Social card (writes orthodox-site/public/og-image.png)
REPO_ROOT=/path/to/repo CHROME_BIN=/path/to/chrome node og-image.mjs
```

`fixtures.json` holds real answers copied from the phase 4 eval runs plus the saint name
indexes; no script calls OpenAI.
