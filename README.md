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
CHROMA_DIR=chroma_db
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,https://your-project.vercel.app
CORS_ALLOW_ORIGIN_REGEX=https://.*\.vercel\.app
```

Notes:

- `ALLOWED_ORIGINS` is a comma-separated list for exact origins.
- `CORS_ALLOW_ORIGIN_REGEX` is optional and useful for Vercel preview deployments.
- `CHROMA_DIR` defaults to `chroma_db` if omitted, but setting it explicitly is cleaner in production.

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
6. Add environment variables:
   - `OPENAI_API_KEY`
   - `CHROMA_DIR`
   - `ALLOWED_ORIGINS`
   - `CORS_ALLOW_ORIGIN_REGEX`
7. Ensure the start command is:

```bash
uvicorn api:app --host 0.0.0.0 --port $PORT
```

The included `Procfile` already matches that.

### Recommended Railway env values

```env
OPENAI_API_KEY=sk-your-openai-key
CHROMA_DIR=chroma_db
ALLOWED_ORIGINS=https://your-production-site.vercel.app,http://localhost:3000,http://127.0.0.1:3000
CORS_ALLOW_ORIGIN_REGEX=https://.*\.vercel\.app
```

### Important backend note

Your Chroma data must exist in the Railway filesystem at deploy time, or be recreated there. If the production backend needs the latest PDFs indexed, run your ingestion flow against the production environment before relying on live traffic.

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
5. If you use Vercel previews, keep `CORS_ALLOW_ORIGIN_REGEX` enabled.

## Files Added for Deployment

- `requirements.txt`
- `Procfile`
- `runtime.txt`
- `.env.example`
- `orthodox-site/.env.example`

## Files Updated for Deployment

- `api.py`
- `chat.html`
- `orthodox-site/app/api/chat/route.ts`
- `orthodox-site/app/chat/page.tsx`
- `orthodox-site/README.md`
