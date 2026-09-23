"""Command line: `python -m ingestion <command>`.

  extract        --doc cat2 --pages 16,31   print cleaned pages (no API calls)
  samples        [--write]                  regenerate the Step 1 golden files and SAMPLES.md
  verify-legacy  [--lang en|ar|web]         compare the v1-legacy rebuild with the live v1 store (read-only, no API calls)
  build          --corpus v1-legacy [--lang en|ar|web] [--resume] [--dry-run]
                                            rebuild v1 (what boot-time auto-ingest runs); embeds unless --dry-run
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, Iterator, List

from dotenv import load_dotenv


def _cmd_extract(args: argparse.Namespace) -> int:
    from .sources import pdf_source

    source = pdf_source(args.doc)
    pages = [int(p) for p in args.pages.split(",")] if args.pages else None
    if source.language == "ar":
        from .extract_ar import extract_pages
    else:
        from .extract_en import extract_pages
    for page in extract_pages(args.doc, pages):
        print(f"===== {page.doc_id} p{page.page} (printed {page.printed_page})")
        print(page.text)
        if page.footnotes:
            print("----- footnotes")
            for note in page.footnotes:
                print(f"[{note.number}] {note.text}")
    return 0


def _cmd_samples(args: argparse.Namespace) -> int:
    from . import samples

    if args.write:
        samples.write_all()
        return 0
    for sample in samples.SAMPLES:
        print(samples.render_after(sample, samples.after_record(sample)))
    return 0


def legacy_chunks(lang: str) -> Iterator[Dict[str, Any]]:
    from . import legacy

    if lang == "en":
        return legacy.english_pdf_chunks()
    if lang == "ar":
        return legacy.arabic_pdf_chunks()
    if lang == "web":
        return legacy.web_chunks()
    raise ValueError(lang)


def _v1_store(chroma_dir: str) -> Dict[str, tuple]:
    """id -> (document, metadata) for every v1 chunk, read straight from the sqlite file (read-only)."""
    path = Path(chroma_dir) / "chroma.sqlite3"
    con = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    store: Dict[str, tuple] = {}
    rows = con.execute(
        "SELECT e.embedding_id, m.key, m.string_value, m.int_value, m.float_value, m.bool_value "
        "FROM embeddings e JOIN embedding_metadata m ON m.id = e.id"
    )
    for embedding_id, key, s, i, f, b in rows:
        document, metadata = store.get(embedding_id, (None, {}))
        if key == "chroma:document":
            document = s
        else:
            metadata[key] = s if s is not None else i if i is not None else f if f is not None else bool(b)
        store[embedding_id] = (document, metadata)
    return store


def _cmd_verify_legacy(args: argparse.Namespace) -> int:
    store = _v1_store(args.chroma_dir)
    failures = 0
    for lang in args.lang:
        prefix = {"en": lambda i: not i.startswith(("ar::", "website::")), "ar": lambda i: i.startswith("ar::"), "web": lambda i: i.startswith("website::")}[lang]
        live = {i: v for i, v in store.items() if prefix(i)}
        rebuilt = {c["id"]: (c["text"], c["metadata"]) for c in legacy_chunks(lang)}
        missing, extra = sorted(set(live) - set(rebuilt)), sorted(set(rebuilt) - set(live))
        shared = set(live) & set(rebuilt)
        text_diff = [i for i in shared if live[i][0] != rebuilt[i][0]]
        # The live English PDF chunks predate the current scripts and carry only pdf/page/chunk_index;
        # the scripts (and this rebuild) add source_type/title/language/source_group, which the API
        # already assumes as defaults. A live key set that is a subset with equal values is compatible.
        conflict = [i for i in shared if any(rebuilt[i][1].get(k) != v for k, v in live[i][1].items())]
        subset = [i for i in shared if i not in conflict and live[i][1] != rebuilt[i][1]]
        ok = not (missing or extra or text_diff or conflict)
        failures += 0 if ok else 1
        verdict = "IDENTICAL" if ok and not subset else "COMPATIBLE (live metadata is a subset)" if ok else "DIFFERENT"
        print(f"{lang}: live {len(live)}, rebuilt {len(rebuilt)}, missing {len(missing)}, extra {len(extra)}, "
              f"text differs {len(text_diff)}, metadata conflicts {len(conflict)}, live metadata subset {len(subset)} -> {verdict}")
        if subset:
            added = sorted({k for i in subset for k in set(rebuilt[i][1]) - set(live[i][1])})
            print(f"   fields the rebuild adds: {added}")
        for label, ids in (("missing", missing), ("extra", extra), ("text differs", text_diff), ("metadata conflicts", conflict)):
            if ids:
                print(f"   {label}: {sorted(ids)[:5]}")
    return 1 if failures else 0


def build_v1_legacy(langs: List[str], *, resume: bool = False, dry_run: bool = False) -> Dict[str, int]:
    """Rebuild v1 into the configured v1 collections (the old boot-time ingestion, same ids)."""
    from chroma_store import ARABIC_COLLECTION_NAME, get_chroma_client, get_chroma_collection, log_chroma_configuration

    from .embed import upsert_chunks

    log_chroma_configuration("ingestion.v1-legacy")
    counts: Dict[str, int] = {}
    client = None if dry_run else get_chroma_client()
    for lang in langs:
        chunks = list(legacy_chunks(lang))
        counts[lang] = len(chunks)
        print(f"v1-legacy {lang}: {len(chunks)} chunks", flush=True)
        if dry_run or not chunks:
            continue
        if lang == "ar":
            collection = get_chroma_collection(client=client, collection_name=ARABIC_COLLECTION_NAME,
                                               metadata={"source": ARABIC_COLLECTION_NAME, "language": "ar"})
        else:
            collection = get_chroma_collection(client=client, metadata={"source": "orthodox_pdfs"})
        if lang == "web":
            for url in sorted({c["metadata"]["url"] for c in chunks}):
                keep = {c["id"] for c in chunks if c["metadata"]["url"] == url}
                stale = [i for i in (collection.get(where={"url": url}).get("ids") or []) if i not in keep]
                if stale:
                    collection.delete(ids=stale)
        upsert_chunks(collection, chunks, label=f"v1-legacy {lang}", resume=resume)
    return counts


def _cmd_build(args: argparse.Namespace) -> int:
    if args.corpus == "v1-legacy":
        build_v1_legacy(args.lang, resume=args.resume, dry_run=args.dry_run)
        return 0
    if not args.dry_run:
        # Embeds the reviewed dry-run output (~6.6 M tokens, ~$0.13 with text-embedding-3-small).
        from chroma_store import get_chroma_path_v2

        from .corpus import embed_build

        chroma_dir = Path(args.chroma_dir or get_chroma_path_v2())
        print(f"v2 build into {chroma_dir}", flush=True)
        result = embed_build(chroma_dir, resume=args.resume)
        print(f"written: {result['written']}")
        if result["problems"]:
            print("v2 store does not match the manifest: " + "; ".join(result["problems"]), file=sys.stderr)
            return 1
        print("v2 store matches data/corpus/v2/manifest.json")
        return 0
    from .corpus import build as build_v2

    stats = build_v2(with_web="web" in args.lang)
    print(f"v2 dry run: {stats['chunks']} chunks -> build/corpus/v2/chunks.jsonl, data/corpus/v2/"
          "{manifest.json, stats.json, saints_index.json, SAMPLES.md}. No OpenAI calls.")
    for kind, info in stats["by_type"].items():
        print(f"  {kind:14} {info['chunks']:6} chunks  {info['units']:5} units")
    return 0


def main(argv: List[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(prog="python -m ingestion", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("extract", help="print cleaned pages")
    p.add_argument("--doc", required=True)
    p.add_argument("--pages", default="")
    p.set_defaults(func=_cmd_extract)

    p = sub.add_parser("samples", help="render the sample pages")
    p.add_argument("--write", action="store_true")
    p.set_defaults(func=_cmd_samples)

    p = sub.add_parser("verify-legacy", help="compare the v1-legacy rebuild with the live v1 store")
    p.add_argument("--lang", nargs="+", default=["en", "ar"], choices=["en", "ar", "web"])
    p.add_argument("--chroma-dir", default="chroma_db")
    p.set_defaults(func=_cmd_verify_legacy)

    p = sub.add_parser("build", help="build a corpus")
    p.add_argument("--corpus", required=True, choices=["v1-legacy", "v2"])
    p.add_argument("--lang", nargs="+", default=["en", "web", "ar"], choices=["en", "ar", "web"])
    p.add_argument("--resume", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--chroma-dir", default="", help="v2 only; default CHROMA_DIR_V2 or <CHROMA_DIR>/v2")
    p.set_defaults(func=_cmd_build)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
