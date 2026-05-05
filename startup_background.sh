#!/usr/bin/env bash
set -euo pipefail

echo "=== Learn Orthodoxy AI background startup ==="
echo "PWD: $(pwd)"
echo "CHROMA_DIR before default: ${CHROMA_DIR:-}"
export CHROMA_DIR="${CHROMA_DIR:-/app/chroma_db}"
mkdir -p "$CHROMA_DIR"

echo "Starting background Chroma check/ingestion..."
(
  set +e
  echo "Background ingest worker started"
  python verify_chroma.py
  VERIFY_EXIT=$?
  echo "verify_chroma exit code: $VERIFY_EXIT"

  COUNT="$(python - <<'PY'
from chroma_store import get_collection_count
try:
    print(get_collection_count())
except Exception:
    print(0)
PY
)"
  echo "Detected Chroma document count: $COUNT"

  MIN_DOCS="${MIN_CHROMA_DOCS:-100}"
  if [ "$COUNT" -lt "$MIN_DOCS" ]; then
    echo "Chroma count $COUNT below $MIN_DOCS. Running ingest_all_sources.py in background..."
    python ingest_all_sources.py
    echo "Background ingestion finished. Verifying..."
    python verify_chroma.py
  else
    echo "Chroma already populated. Skipping ingestion."
  fi
) &

echo "Starting FastAPI immediately so Railway healthcheck passes..."
exec uvicorn api:app --host 0.0.0.0 --port "${PORT}"
