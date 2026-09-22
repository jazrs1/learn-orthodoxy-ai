"""Snapshot the saints index names for the calendar's saint links (CAL-002).

Reads the local Chroma store through the backend's own index builders, so the names are exactly
the ones /saints returns. No OpenAI client is created and nothing is written to Chroma.

Run from the repository root:
    .venv/Scripts/python.exe orthodox-site/scripts/calendar/snapshot-saints-index.py
"""

import json
import os
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent / "saints-index.snapshot.json"

sys.path.insert(0, str(REPO_ROOT))
os.chdir(REPO_ROOT)
os.environ.pop("OPENAI_API_KEY", None)  # the backend's startup() would create a client; we never call it

import api  # noqa: E402
from chroma_store import ARABIC_COLLECTION_NAME, COLLECTION_NAME, get_chroma_client  # noqa: E402

client = get_chroma_client()
api.collection = client.get_collection(COLLECTION_NAME)
api.arabic_collection = client.get_collection(ARABIC_COLLECTION_NAME)

english = api._build_saint_record_index()
arabic = api._build_arabic_saint_name_index()

snapshot = {
    "source": "Local Chroma store via api._build_saint_record_index / api._build_arabic_saint_name_index",
    "taken": date.today().isoformat(),
    "en": [{"name": r["name"], "aliases": sorted(set(r.get("aliases") or []) - {r["name"]})} for r in english],
    "ar": list(arabic),
}
OUT.write_text(json.dumps(snapshot, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(f"{len(snapshot['en'])} English and {len(snapshot['ar'])} Arabic names -> {OUT}")
