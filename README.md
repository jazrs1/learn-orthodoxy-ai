# Learn Orthodoxy AI

This project has:

- a Next.js frontend in [`orthodox-site`](/Users/johnazer/orthodox-ai/orthodox-site)
- a FastAPI backend in [`api.py`](/Users/johnazer/orthodox-ai/api.py)
- Postgres-backed durable chat storage through Next.js API routes
- Chroma vector search for the Orthodox PDF corpus

## Architecture

- Browser -> Next.js frontend
- Next.js API routes -> Postgres for chat persistence
- Next.js API routes -> FastAPI `/chat` for retrieval + answer generation
- Browser -> FastAPI `/saints` for saint search and list loading

The frontend uses:

- `ORTHODOX_API_URL` on the server
- `NEXT_PUBLIC_API_URL` in the browser

Do not hardcode localhost URLs in app code. Use environment variables in each environment.

## Required Environment Variables

### Frontend (`orthodox-site`)

Local `.env.local` or Vercel project env vars:

```env
POSTGRES_URL=postgres://USER:PASSWORD@HOST:5432/DATABASE
ORTHODOX_API_URL=https://learn-orthodoxy-api-production.up.railway.app
NEXT_PUBLIC_API_URL=https://learn-orthodoxy-api-production.up.railway.app
```

Notes:

- `POSTGRES_URL` can be replaced with `DATABASE_URL` if your provider uses that name.
- `ORTHODOX_API_URL` is used by Next server routes.
- `NEXT_PUBLIC_API_URL` is used by browser-side saint search requests.

### Backend (repo root / Railway)

Local `.env` or Railway service env vars:

```env
OPENAI_API_KEY=sk-your-openai-key
CHROMA_DIR=/app/chroma_db
AUTO_INGEST_ON_START=1
MIN_CHROMA_DOCUMENTS=1000
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,https://your-project.vercel.app
CORS_ALLOW_ORIGIN_REGEX=https://.*\.vercel\.app
```

Notes:

- `ALLOWED_ORIGINS` is a comma-separated list for exact origins.
- `CORS_ALLOW_ORIGIN_REGEX` is optional and useful for Vercel preview deployments.
- `CHROMA_DIR` defaults to `chroma_db` locally. On Railway, prefer a persistent volume and set `CHROMA_DIR` to the volume-backed path.
- `AUTO_INGEST_ON_START=1` lets the backend populate an empty Chroma collection from the included PDFs and configured websites before starting the API.
- `MIN_CHROMA_DOCUMENTS=1000` makes startup treat tiny or partial Chroma collections as underpopulated and re-run ingestion.

## Local Development

### 1. Backend

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set real values in `.env`, then start FastAPI:

```bash
uvicorn api:app --reload --host 127.0.0.1 --port 8001
```

Health check:

```bash
curl http://127.0.0.1:8001/health
```

### 2. Frontend

From `orthodox-site`:

```bash
npm install
cp .env.example .env.local
```

Set:

```env
POSTGRES_URL=postgres://USER:PASSWORD@HOST:5432/DATABASE
ORTHODOX_API_URL=http://127.0.0.1:8001
NEXT_PUBLIC_API_URL=http://127.0.0.1:8001
```

Run the Postgres migration:

```bash
npm run db:migrate
```

Start Next.js:

```bash
npm run dev
```

Open `http://localhost:3000`.

## Local Test Checklist

1. Open `http://localhost:3000`.
2. Send a first message from the home screen.
3. Confirm a conversation appears in the left chat list.
4. Refresh the page and confirm the conversation persists.
5. Open an old chat and confirm full history reloads.
6. Open the Saints tab and confirm the saint list loads from the backend.
7. Temporarily stop the backend and confirm the UI shows a clear error instead of hanging.

## Git Setup

If the repo is not initialized yet:

```bash
cd /Users/johnazer/orthodox-ai
git init
git branch -M main
git add .
git commit -m "Prepare Learn Orthodoxy AI for Vercel and Railway deployment"
git remote add origin https://github.com/YOUR_GITHUB_USERNAME/learn-orthodoxy-ai.git
git push -u origin main
```

If the repo already exists:

```bash
cd /Users/johnazer/orthodox-ai
git add .
git commit -m "Prepare Learn Orthodoxy AI for Vercel and Railway deployment"
git push
```

## Deploy Frontend to Vercel

### Dashboard steps

1. Push the repo to GitHub.
2. In Vercel, click `Add New` -> `Project`.
3. Import the GitHub repository.
4. Set the root directory to `orthodox-site`.
5. Framework preset should detect `Next.js`.
6. Add environment variables:
   - `POSTGRES_URL`
   - `ORTHODOX_API_URL`
   - `NEXT_PUBLIC_API_URL`
7. Deploy.

### Recommended Vercel env values

```env
POSTGRES_URL=postgres://USER:PASSWORD@HOST:5432/DATABASE
ORTHODOX_API_URL=https://your-railway-service.up.railway.app
NEXT_PUBLIC_API_URL=https://your-railway-service.up.railway.app
```

### After deploy

Copy the Vercel production URL. You will use it in Railway CORS settings.

## Deploy Backend to Railway

### Dashboard steps

1. Push the repo to GitHub.
2. In Railway, create a new project from GitHub repo.
3. Select this repository.
4. Set the service root to the repository root.
5. Railway should detect Python automatically from `requirements.txt`.
6. Attach a persistent volume to the backend service. Recommended mount path:

```bash
/app/chroma_db
```

7. Add environment variables:
   - `OPENAI_API_KEY`
   - `CHROMA_DIR`
   - `AUTO_INGEST_ON_START`
   - `MIN_CHROMA_DOCUMENTS`
   - `ALLOWED_ORIGINS`
   - `CORS_ALLOW_ORIGIN_REGEX`
8. Ensure the start command is:

```bash
python start_backend.py
```

The included `Procfile` and `railway.json` already match that.

The first production boot can take several minutes because the backend may need to embed and index the full document set. `railway.json` sets a longer healthcheck timeout so Railway does not mark that first boot as failed while ingestion is running.

### Recommended Railway env values

```env
OPENAI_API_KEY=sk-your-openai-key
CHROMA_DIR=/app/chroma_db
AUTO_INGEST_ON_START=1
MIN_CHROMA_DOCUMENTS=1000
ALLOWED_ORIGINS=https://your-production-site.vercel.app,http://localhost:3000,http://127.0.0.1:3000
CORS_ALLOW_ORIGIN_REGEX=https://.*\.vercel\.app
```

### Important backend note

Your local `chroma_db/` is intentionally not committed. On Railway, `start_backend.py` checks the configured Chroma collection before starting FastAPI. If the collection has fewer than `MIN_CHROMA_DOCUMENTS` documents and `AUTO_INGEST_ON_START=1`, it ingests the PDFs from `data/pdfs`, attempts website ingestion, writes Chroma data to `CHROMA_DIR`, verifies documents exist, and then starts the API.

Use a Railway volume mounted at `/app/chroma_db` so the first ingestion survives redeploys and restarts. Without a volume, Railway can still ingest at startup, but the generated Chroma database is ephemeral.

## How Production Chroma Is Populated

The backend reads from the existing Chroma collection:

- `COLLECTION_NAME=orthodox_pdfs`
- `CHROMA_DIR` from env if present, otherwise `/app/chroma_db`

The Railway start command runs:

```bash
python start_backend.py
```

This command will:

1. Check the current Chroma collection count
2. Skip ingestion when at least `MIN_CHROMA_DOCUMENTS` documents already exist
3. Ingest all PDFs from `data/pdfs` when the collection is missing or underpopulated
4. Attempt all configured website URLs from [`website_sources.py`](/Users/johnazer/orthodox-ai/website_sources.py)
5. Embed chunks with the existing OpenAI embedding setup
6. Write them into the Chroma collection `orthodox_pdfs`
7. Print the final document count
8. Start FastAPI on Railway's `$PORT`

### Required env vars for ingestion

```env
OPENAI_API_KEY=sk-your-openai-key
CHROMA_DIR=/app/chroma_db
AUTO_INGEST_ON_START=1
MIN_CHROMA_DOCUMENTS=1000
```

The ingestion scripts are designed to be rerun safely:

- PDF chunks use deterministic IDs and are upserted
- Website chunks use deterministic IDs and stale chunks for the same URL are deleted before upsert
- Embeddings are created in smaller rate-limit-safe batches with retry/backoff

### Included source inputs

PDF files included in the repo:

- `data/pdfs/saints1.pdf`
- `data/pdfs/saints2.pdf`
- `data/pdfs/saints3.pdf`
- `data/pdfs/saints4.pdf`
- `data/pdfs/catechism1.pdf`
- `data/pdfs/catechism2.pdf`
- `data/pdfs/full arabic catechism.pdf`
- `data/pdfs/full saints arabic.pdf`

### Arabic source ingestion and saint index

Arabic mode uses a separate Arabic Chroma collection, `orthodox_arabic_pdfs`, for Arabic answers. It also uses a generated Arabic saints list derived from `data/pdfs/full saints arabic.pdf`, with `arabic_saints_index.py` as a small reviewed fallback only.

Run these commands locally or on Railway when rebuilding source data:

```bash
python ingest_all_sources.py
python build_arabic_saints_index.py
```

Verify Arabic source state:

```bash
curl https://your-railway-service.up.railway.app/debug/chroma/ar
curl "https://your-railway-service.up.railway.app/debug/saints?language=ar"
curl "https://your-railway-service.up.railway.app/saints?language=ar&limit=200"
curl "https://your-railway-service.up.railway.app/saints?language=ar&search=انطونيوس"
```

Expected Arabic saints diagnostics:

- `arabic_seed_count` should be the small reviewed fallback count.
- `arabic_generated_count` should be much larger than the seed count when `data/saints_ar_generated.json` is present.
- `arabic_total_count` should include the generated index and optional Chroma headings.
- `full_saints_arabic_pdf.file_exists` should be `true` when the PDF is present in the deployed source files.
- `full_saints_arabic_was_parsed` should be `true` when the generated index is present.

Configured website URLs included in the repo:

- `https://www.mindofchristlight.com/library-blog/blog-post-title-one-4p8fk-wslyt-7kd9z`
- `https://www.mindofchristlight.com/library-blog/blog-post-title-one-4p8fk-wslyt-7kd9z-rzzxd`
- `https://www.mindofchristlight.com/library-blog/blog-post-title-one-4p8fk-wslyt-7kd9z-rzzxd-yspaf`
- `https://www.mindofchristlight.com/library-blog/blog-post-title-one-4p8fk-wslyt-7kd9z-rzzxd-xw8g5`
- `https://www.mindofchristlight.com/library-blog/blog-post-title-one-4p8fk-wslyt-7kd9z-rzzxd-xw8g5-jejkp`

### Expected logs

The ingestion scripts print:

- Chroma dir
- Collection name
- Source extraction progress
- Chunks inserted
- Final document count

## Production Wiring

For production, set the frontend to the deployed Railway backend:

```env
ORTHODOX_API_URL=https://your-railway-service.up.railway.app
NEXT_PUBLIC_API_URL=https://your-railway-service.up.railway.app
```

This removes all localhost assumptions from production.

## Manual Dashboard Actions Still Required

### Vercel

1. Import the GitHub repo.
2. Set root directory to `orthodox-site`.
3. Add the three frontend env vars.
4. Redeploy after Railway gives you the final backend URL.

### Railway

1. Import the GitHub repo.
2. Add the backend env vars.
3. Confirm the service starts and `/health` responds.
4. Add your Vercel production URL to `ALLOWED_ORIGINS`.
5. Attach a Railway volume mounted at `/app/chroma_db`.
6. If you use Vercel previews, keep `CORS_ALLOW_ORIGIN_REGEX` enabled.

## Files Added for Deployment

- `requirements.txt`
- `Procfile`
- `railway.json`
- `start_backend.py`
- `runtime.txt`
- `.env.example`
- `orthodox-site/.env.example`

## Files Updated for Deployment

- `api.py`
- `chat.html`
- `orthodox-site/app/api/chat/route.ts`
- `orthodox-site/app/chat/page.tsx`
- `orthodox-site/README.md`
