"""Hand-written saint alias audit (RET-011). Read-only, no OpenAI.

    CORPUS_VERSION=v2 python eval/alias_audit.py [--out eval/results/alias-audit.txt]

Every hand-written alias (api.SAINT_ALIAS_RECORDS, arabic_saints_index.py, the curation seeds in
data/corpus/saints_curation.json, the frontend display table in orthodox-site/lib/saint-display.ts)
is looked up the way the API looks it up, in the v1 English index (chroma_db) and the v2 English and
Arabic indexes (chroma_db/v2). The Athanasius loop (RET-010) came from such an alias attached to a
namesake, so for each alias the audit reports:

  WRONG    the alias reaches another entry than the saint it was written for
  SHARED   a name of two words or more that several entries carry (a menu instead of the saint)
  STRAY    an entry other than the intended saint carries the alias (a latent loop, even when the
           lookup happens to pick the right one)
  MISSING  the intended saint does not carry the alias and the lookup does not reach him
  OTHER    the alias is (the start of) another entry's own name: the hand-written list names the
           wrong namesake, whatever the lookup does with it at run time

A saint the dictionaries have no entry for (curation target null: the Apostles Peter and Paul) must
reach no entry at all. An English alias of a saint with only an Arabic entry is reported as such.

Bare names ("مرقس", "St. Mark") that several entries carry are not flagged: RET-010 gives them a menu
and data/saint_defaults.json may send them to the major saint.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
os.environ.setdefault("CORPUS_VERSION", "v2")

import chromadb  # noqa: E402
from chromadb.config import Settings  # noqa: E402

import api  # noqa: E402
from arabic_saints_index import ARABIC_SAINTS_INDEX  # noqa: E402
from chroma_store import get_chroma_path_v2, get_resolved_chroma_dir  # noqa: E402


def load_indexes():
    """v2 English and Arabic records, then v1 English records, as the API builds them."""
    v2 = chromadb.PersistentClient(path=str(get_chroma_path_v2()), settings=Settings(anonymized_telemetry=False))
    names = api.corpus_runtime.v2_collection_names()
    api.CORPUS_V2 = True
    api.collection, api.arabic_collection = v2.get_collection(names["en"]), v2.get_collection(names["ar"])
    api.saint_record_index, api.arabic_v2_saint_records = [], []
    v2_en = list(api._build_saint_record_index())
    v2_ar = list(api._build_v2_arabic_saint_records())
    v1 = chromadb.PersistentClient(path=str(get_resolved_chroma_dir()), settings=Settings(anonymized_telemetry=False))
    api.CORPUS_V2 = False
    api.collection = v1.get_collection("orthodox_pdfs")
    api.saint_record_index = []
    v1_en = list(api._build_saint_record_index())
    return v2_en, v2_ar, v1_en


def frontend_table():
    text = (ROOT / "orthodox-site/lib/saint-display.ts").read_text(encoding="utf-8")
    groups = []
    for block in re.findall(r"\{\s*canonical:.*?\n  \}", text, flags=re.S):
        canonical = re.search(r'canonical:\s*"([^"]+)"', block).group(1)
        english = re.findall(r'"([^"]+)"', re.search(r"englishAliases:\s*\[(.*?)\]", block, flags=re.S).group(1))
        arabic = re.findall(r'"([^"]+)"', re.search(r"arabicAliases:\s*\[(.*?)\]", block, flags=re.S).group(1))
        groups.append({"canonical": canonical, "english_aliases": english, "arabic_aliases": arabic})
    return groups


def hand_written(v2_en, v2_ar):
    """(source, language, alias, intended v2 saint id or None)."""
    seeds = json.loads((ROOT / "data/corpus/saints_curation.json").read_text(encoding="utf-8"))["seeds"]
    by_key = {api._normalize_saint_match_key(s["name_en"]): s.get("target") for s in seeds}
    ar_by_name = {r["name"]: r["saint_id"] for r in v2_ar}

    def resolve(target):
        if target is None:
            return NO_ENTRY
        if target and str(target).startswith("ar:"):
            return ar_by_name.get(api._normalize_arabic_display_text(target[3:]))
        return target

    def group_target(group):
        keys = set()
        for value in [group["canonical"], *group["english_aliases"]]:
            keys |= api._saint_match_keys(value)
        seeded = next((by_key[k] for k in sorted(keys) if by_key.get(k)), None)
        if seeded:
            return seeded
        descriptive = {k for k in keys if len(k.split()) >= 2}
        owners = [r["id"] for r in v2_en if any(o == k or o.startswith(k + " ") for o in api._saint_own_keys(r) for k in descriptive)]
        return owners[0] if len(owners) == 1 else None

    items = []
    for source, groups in (("api.SAINT_ALIAS_RECORDS", api.SAINT_ALIAS_RECORDS), ("saint-display.ts", frontend_table())):
        for group in groups:
            target = group_target(group)
            items += [(source, "en", a, target) for a in [group["canonical"], *group["english_aliases"]]]
            items += [(source, "ar", a, target) for a in group.get("arabic_aliases", [])]
    for row in ARABIC_SAINTS_INDEX:
        target = resolve(next((s.get("target") for s in seeds if s["name_en"] == row["name_en"]), None))
        items += [("arabic_saints_index.py", "ar", a, target) for a in [row["name_ar"], *row.get("aliases_ar", [])]]
        items.append(("arabic_saints_index.py", "en", row["name_en"], target))
    items += [("saints_curation.json", "en", s["name_en"], resolve(s.get("target"))) for s in seeds]
    seen, unique = set(), []
    for item in items:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


NO_ENTRY = "(no entry)"


def english_findings(alias, target, records, corpus):
    keys = api._saint_match_keys(alias)
    carriers = [r for r in records if keys & (api._saint_own_keys(r) | api._saint_alias_keys(r))]
    known = corpus == "v2" and target not in (None, NO_ENTRY) and any(str(r["id"]) == target for r in records)
    strays = [r for r in carriers if not (keys & api._saint_own_keys(r)) and known and str(r["id"]) != target]
    # English headings are "St. X, the Y": another entry is named by the alias only when its own name
    # is exactly the alias ("St. Mary the Virgin" merely begins "St. Mary, the Virgin Confessor").
    others = [r for r in records if known and str(r["id"]) != target and len(api._normalize_saint_match_key(alias).split()) >= 2
              and keys & api._saint_own_keys(r)]
    api.saint_record_index = records
    api.CORPUS_V2 = corpus == "v2"
    kind, decided = api._english_saint_decision(alias)
    bare = len(api._normalize_saint_match_key(alias).split()) <= 1
    issues = []
    ids = [str(r["id"]) for r in decided]
    reached = kind in ("entry", "default")
    if corpus == "v2" and target == NO_ENTRY and reached:
        issues.append("WRONG")
    if known and reached and ids[0] != target:
        issues.append("WRONG")
    if kind == "menu" and not bare:
        issues.append("SHARED")
    if strays:
        issues.append("STRAY")
    if others:
        issues.append("OTHER")
    if known and kind == "none" and not any(str(r["id"]) == target for r in carriers):
        issues.append("MISSING")
    if corpus == "v2" and target not in (None, NO_ENTRY) and not known and not issues:
        kind = "only-arabic-entry" if kind == "none" else kind
    return kind, decided, carriers, strays + others, issues


def arabic_findings(alias, target, records):
    keys = set(api._arabic_saint_query_keys(alias))
    known = target not in (None, NO_ENTRY)
    carriers = [r for r in records if keys & r["keys"]]
    strays = [r for r in carriers if not (keys & r.get("own_keys", set())) and known and r["saint_id"] != target]
    multi = {k for k in keys if len(k.split()) >= 2}
    # Arabic headings end in a title ("أبانوب المعترف القديس"), so a prefix counts. The dictionary
    # repeats some entries in its last pages ("… (ص 31، مدخل 2)"): those are the same saint.
    target_name = next((api._arabic_lookup_name(r) for r in records if r["saint_id"] == target), None)
    others = [r for r in records if known and r["saint_id"] != target and api._arabic_lookup_name(r) != target_name
              and any(o == k or o.startswith(k + " ") for o in r.get("own_keys", set()) for k in multi)]
    kind, decided = api._arabic_saint_decision(alias)
    bare = len(api._normalize_arabic_alias_key(api._strip_arabic_query_titles(alias)).split()) <= 1
    ids = [r["saint_id"] for r in decided]
    reached = kind in ("entry", "default")
    issues = []
    if target == NO_ENTRY and reached:
        issues.append("WRONG")
    if known and reached and ids[0] != target:
        issues.append("WRONG")
    if kind == "menu" and not bare:
        issues.append("SHARED")
    if strays:
        issues.append("STRAY")
    if others:
        issues.append("OTHER")
    if known and kind == "none" and not any(r["saint_id"] == target for r in carriers):
        issues.append("MISSING")
    return kind, decided, carriers, strays + others, issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out")
    args = parser.parse_args()
    v2_en, v2_ar, v1_en = load_indexes()
    items = hand_written(v2_en, v2_ar)
    lines, counts = [], {}

    def name(r):
        return f"{r.get('name')} [{r.get('saint_id') or r.get('id')}]"

    for source, language, alias, target in items:
        if language == "en":
            results = [("v2", english_findings(alias, target, v2_en, "v2")), ("v1", english_findings(alias, target, v1_en, "v1"))]
        else:
            api.CORPUS_V2 = True
            results = [("v2", arabic_findings(alias, target, v2_ar))]
        for corpus, (kind, decided, carriers, strays, issues) in results:
            for issue in issues:
                counts[issue] = counts.get(issue, 0) + 1
            flag = ",".join(issues) or "ok"
            reached = (name(decided[0]) + (" (default, link to %d others)" % (len(decided) - 1) if kind == "default" else "")
                       if kind in ("entry", "default") else (f"menu of {len(decided)}" if kind == "menu" else kind.replace("none", "no entry")))
            line = f"{flag:14} {corpus} {language} {source:24} {alias!r} -> {reached}; intended {target}"
            if strays and corpus == "v2":
                line += "; also carried by / named for " + ", ".join(name(r) for r in strays)
            lines.append(line)
    summary = f"{len(items)} hand-written aliases; issues: " + (", ".join(f"{k} {v}" for k, v in sorted(counts.items())) or "none")
    report = "\n".join([summary, *sorted(lines, key=lambda l: (l.startswith("ok"), l))])
    print(report)
    if args.out:
        Path(args.out).write_text(report + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
