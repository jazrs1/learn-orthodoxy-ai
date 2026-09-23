"""Snapshot the saints index names for the calendar's saint links (CAL-002, ING-008).

Reads the local Chroma store through the backend's own index builders, so the names are exactly
the ones /saints returns. No OpenAI client is created and nothing is written to Chroma.

Run from the repository root, for the corpus production serves:
    .venv/Scripts/python.exe orthodox-site/scripts/calendar/snapshot-saints-index.py
    CORPUS_VERSION=v2 .venv/Scripts/python.exe orthodox-site/scripts/calendar/snapshot-saints-index.py

With CORPUS_VERSION=v2 the names come from the ingest-time index (data/corpus/v2/saints_index.json)
and the v2 store (chroma_db/v2), whose records keep every v1 name as an alias.
"""

import json
import os
import sys
from datetime import date
from pathlib import Path

import chromadb
from chromadb.config import Settings

REPO_ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent / "saints-index.snapshot.json"

sys.path.insert(0, str(REPO_ROOT))
os.chdir(REPO_ROOT)
os.environ.pop("OPENAI_API_KEY", None)  # the backend's startup() would create a client; we never call it

import api  # noqa: E402
from chroma_store import get_chroma_client, get_chroma_path_v2  # noqa: E402

if api.CORPUS_V2:
    client = chromadb.PersistentClient(path=get_chroma_path_v2(), settings=Settings(anonymized_telemetry=False))
else:
    client = get_chroma_client()
api.collection = client.get_collection(api.COLLECTION_NAME)
api.arabic_collection = client.get_collection(api.ARABIC_COLLECTION_NAME)

english = api._build_saint_record_index()
arabic = api._build_arabic_saint_name_index()

snapshot = {
    "source": f"Local Chroma store ({api.CORPUS_VERSION}) via api._build_saint_record_index / api._build_arabic_saint_name_index",
    "corpus_version": api.CORPUS_VERSION,
    "taken": date.today().isoformat(),
    "en": [{"name": r["name"], "aliases": sorted(set(r.get("aliases") or []) - {r["name"]})} for r in english],
    "ar": list(arabic),
}
if api.CORPUS_V2:
    # The dictionary headings are short ("مرقس الخامس"); the index's full names and the v1 names are
    # aliases, which the extractor matches too (ING-008).
    index = {s["id"]: s for s in json.loads((REPO_ROOT / "data/corpus/v2/saints_index.json").read_text(encoding="utf-8"))["saints"]}
    snapshot["ar_aliases"] = {}
    for record in api._build_v2_arabic_saint_records():
        saint = index.get(record["saint_id"], {})
        aliases = {saint.get("name_ar"), saint.get("heading_ar"), *saint.get("aliases_ar", [])} - {None, "", record["name"]}
        if aliases:
            snapshot["ar_aliases"][record["name"]] = sorted(aliases)
OUT.write_text(json.dumps(snapshot, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(f"{len(snapshot['en'])} English and {len(snapshot['ar'])} Arabic names ({api.CORPUS_VERSION}) -> {OUT}")
