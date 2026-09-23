"""Rewrite saint-link-overrides.json from v1 index names to the v2 names (ING-008, after the switch).

The overrides name saints as the v1 index displayed them ("St. Mary", "السيدة العذراء مريم"). v2 keeps
every v1 name as an alias, so each one maps to exactly the v2 record that carries it; the extractor
needs the record's display name. Run after snapshot-saints-index.py has written the v2 snapshot:

    CORPUS_VERSION=v2 .venv/Scripts/python.exe orthodox-site/scripts/calendar/snapshot-saints-index.py
    .venv/Scripts/python.exe orthodox-site/scripts/calendar/migrate-overrides-v2.py
    cd orthodox-site && npm run calendar:saints -- <path-to-katameros-api clone>

Names that no v2 record carries are listed and left unchanged, so the extractor fails loudly on them.
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
sys.path.insert(0, str(REPO_ROOT))

from api import _normalize_arabic_alias_key  # noqa: E402

snapshot = json.loads((HERE / "saints-index.snapshot.json").read_text(encoding="utf-8"))
if snapshot.get("corpus_version") != "v2":
    raise SystemExit("saints-index.snapshot.json is not a v2 snapshot; run snapshot-saints-index.py with CORPUS_VERSION=v2 first")
index = json.loads((REPO_ROOT / "data/corpus/v2/saints_index.json").read_text(encoding="utf-8"))["saints"]

en_names = {r["name"] for r in snapshot["en"]}
en_by_alias = {}
for record in snapshot["en"]:
    for name in [record["name"], *record["aliases"]]:
        en_by_alias.setdefault(name, record["name"])

ar_names = set(snapshot["ar"])
ar_display = {_normalize_arabic_alias_key(name.split(" (ص")[0]): name for name in snapshot["ar"]}
ar_by_alias = {}
for saint in index:
    display = ar_display.get(_normalize_arabic_alias_key(saint.get("heading_ar") or saint.get("name_ar") or ""))
    if not display:
        continue
    for name in [saint.get("heading_ar"), saint.get("name_ar"), *saint.get("aliases_ar", [])]:
        if name:
            ar_by_alias.setdefault(name, display)

path = HERE / "saint-link-overrides.json"
overrides = json.loads(path.read_text(encoding="utf-8"))
changed, missing = [], []
for story, link in overrides["links"].items():
    for language, known, by_alias in (("en", en_names, en_by_alias), ("ar", ar_names, ar_by_alias)):
        name = link.get(language)
        if not name or name in known:
            continue
        target = by_alias.get(name)
        if target:
            link[language] = target
            changed.append(f"{story} {language}: {name} -> {target}")
        else:
            missing.append(f"{story} {language}: {name}")
def dumps_overrides(data):
    """The file's own layout, one line per story, so a review diff shows only the links that moved."""
    lines = [f'    {json.dumps(story)}: {{ {json.dumps(link, ensure_ascii=False)[1:-1]} }}' for story, link in data["links"].items()]
    return '{\n  "about": ' + json.dumps(data["about"], ensure_ascii=False) + ',\n  "links": {\n' + ",\n".join(lines) + "\n  }\n}\n"


path.write_text(dumps_overrides(overrides), encoding="utf-8")
print(f"{len(changed)} names moved to v2:")
print("\n".join(f"  {line}" for line in changed))
if missing:
    print(f"{len(missing)} names with no v2 record (fix by hand):")
    print("\n".join(f"  {line}" for line in missing))
