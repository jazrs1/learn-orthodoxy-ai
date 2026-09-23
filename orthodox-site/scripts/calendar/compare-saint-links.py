"""Compare the calendar's saint links before and after a regeneration (runbook step 3.5, CAL-008).

    .venv/Scripts/python.exe orthodox-site/scripts/calendar/compare-saint-links.py [--before <git rev>]

Reads lib/calendar/data/saints.katameros.json from git (default: HEAD) and from the working tree,
and, per language, sorts every entry into kept (the same saint), changed (a different saint), new
and lost, marking the links that come from saint-link-overrides.json. Both sides are resolved to v2
entries the way the site resolves a calendar link (the backend's saint-name lookup, RET-010/011),
so a renamed link to the same saint counts as kept. Every new link is also checked to open the entry
it names: a name that the lookup would send elsewhere (a bare name on data/saint_defaults.json, say)
is reported as a problem. Reads the local v2 store; no OpenAI.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA = "orthodox-site/lib/calendar/data/saints.katameros.json"
OVERRIDES = REPO_ROOT / "orthodox-site/scripts/calendar/saint-link-overrides.json"
sys.path.insert(0, str(REPO_ROOT))
os.chdir(REPO_ROOT)
os.environ["CORPUS_VERSION"] = "v2"
os.environ.pop("OPENAI_API_KEY", None)

import chromadb  # noqa: E402
from chromadb.config import Settings  # noqa: E402

import api  # noqa: E402
from chroma_store import get_chroma_path_v2  # noqa: E402


def entries(data):
    days = data["days"].values() if isinstance(data["days"], dict) else data["days"]
    return {str(e["id"]): e for day in days for e in day}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--before", default="HEAD")
    args = parser.parse_args()
    client = chromadb.PersistentClient(path=str(get_chroma_path_v2()), settings=Settings(anonymized_telemetry=False))
    api.collection = client.get_collection(api.COLLECTION_NAME)
    api.arabic_collection = client.get_collection(api.ARABIC_COLLECTION_NAME)

    before = entries(json.loads(subprocess.run(["git", "show", f"{args.before}:{DATA}"], capture_output=True,
                                               text=True, encoding="utf-8", check=True).stdout))
    after = entries(json.loads((REPO_ROOT / DATA).read_text(encoding="utf-8")))
    overrides = json.loads(OVERRIDES.read_text(encoding="utf-8"))["links"]

    def resolve(name, language):
        """The v2 entry a calendar link with this name opens (the saint-name lookup of /chat)."""
        if language == "en":
            record = api._find_saint_record_for_name(name)
            return str(record["id"]) if record else None
        record = api._find_v2_arabic_record_for_name(name)
        return record["saint_id"] if record else None

    def entry_named(name, language):
        """The v2 entry shown under exactly this name (what the generator linked)."""
        if language == "en":
            record = api._find_saint_record_exact(name)
            return str(record["id"]) if record else None
        return next((r["saint_id"] for r in api._build_v2_arabic_saint_records() if r["name"] == name), None)

    problems = 0
    for language in ("en", "ar"):
        kept, changed, new, lost = [], [], [], []
        for entry_id, entry in after.items():
            old = (before.get(entry_id, {}).get("index") or {}).get(language)
            now = (entry.get("index") or {}).get(language)
            title = entry.get(language) or entry.get("en")
            mark = " [override]" if (overrides.get(entry_id) or {}).get(language) else ""
            if now:
                target = entry_named(now, language)
                opens = resolve(now, language)
                if target is None or opens != target:
                    problems += 1
                    print(f"PROBLEM {language} {entry_id} {now!r}: generated for {target}, a link opens {opens}")
            if old and now:
                (kept if resolve(old, language) == entry_named(now, language) else changed).append((entry_id, title, old, now, mark))
            elif now:
                new.append((entry_id, title, None, now, mark))
            elif old:
                lost.append((entry_id, title, old, None, ""))
        overridden = sum(1 for e in after if (overrides.get(e) or {}).get(language) and (after[e].get("index") or {}).get(language))
        print(f"\n{language}: {len(kept) + len(changed) + len(new)} linked (was {len(kept) + len(changed) + len(lost)}): "
              f"kept {len(kept)}, changed {len(changed)}, new {len(new)}, lost {len(lost)}; from overrides {overridden}")
        for label, rows in (("changed", changed), ("lost", lost), ("new", new)):
            for entry_id, title, old, now, mark in rows:
                print(f"  {label:7} {entry_id:>6} {title[:60]!r}: {old!r} -> {now!r}{mark}")
    print(f"\nproblems: {problems}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
