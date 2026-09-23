"""Snapshot of the v1 saint names with their pages, so v2 can keep every one as an alias (§7).

Existing links name v1 saints: calendar links (`/chat?saint=St. George, the Capaducian`), saved chat
chips, and the Saints-tab list people have used. The English names come from the backend's runtime
index built from the local v1 Chroma store (no OpenAI client is created); the Arabic names from the
committed generated list and the reviewed seed table.

    python -m ingestion.snapshot_v1_names   ->  data/corpus/v1_saint_names.json
"""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

OUT = Path("data/corpus/v1_saint_names.json")


def main() -> None:
    os.environ.pop("OPENAI_API_KEY", None)  # startup() would build a client; we never call it
    import api
    from arabic_saints_index import ARABIC_SAINTS_INDEX
    from chroma_store import ARABIC_COLLECTION_NAME, COLLECTION_NAME, get_chroma_client

    client = get_chroma_client()
    api.collection = client.get_collection(COLLECTION_NAME)
    api.arabic_collection = client.get_collection(ARABIC_COLLECTION_NAME)
    english = []
    for record in api._build_saint_record_index():
        meta = record.get("metadata") or {}
        english.append({"name": record["name"], "aliases": sorted(set(record.get("aliases") or []) - {record["name"]}),
                        "pdf": meta.get("pdf", ""), "page": int(meta.get("page") or 0)})
    generated = json.loads(Path("data/saints_ar_generated.json").read_text(encoding="utf-8"))["saints"]
    arabic = [{"name": r["name_ar"], "aliases": r.get("aliases_ar") or [], "page_start": r.get("page_start") or 0,
               "page_end": r.get("page_end") or 0, "source": "generated"} for r in generated]
    arabic += [{"name": r["name_ar"], "aliases": r.get("aliases_ar") or [], "name_en": r.get("name_en", ""),
                "page_start": 0, "page_end": 0, "source": "seed"} for r in ARABIC_SAINTS_INDEX]
    runtime_arabic = set(api._build_arabic_saint_name_index())
    known = {r["name"] for r in arabic}
    arabic += [{"name": n, "aliases": [], "page_start": 0, "page_end": 0, "source": "chroma-headings"} for n in sorted(runtime_arabic - known)]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"taken": date.today().isoformat(), "source": "v1 runtime index (local Chroma) + data/saints_ar_generated.json + arabic_saints_index.py",
                               "en": english, "ar": arabic}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(english)} English and {len(arabic)} Arabic v1 names -> {OUT}")


if __name__ == "__main__":
    main()
