"""The in-memory Arabic lexical index (RET-013) against the scan it replaces, on the real v2 store.

For every Arabic eval question and every mode's filter, both must return the same chunks in the
same order. No OpenAI calls: only the lexical search runs.

    CORPUS_VERSION=v2 python eval/check_arabic_lexical_cache.py
"""

import json
import os
import statistics
import sys
import time
from pathlib import Path

os.environ.setdefault("CORPUS_VERSION", "v2")
os.environ["OPENAI_API_KEY"] = ""
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import chromadb  # noqa: E402
from chromadb.config import Settings as ChromaSettings  # noqa: E402

import api  # noqa: E402
from chroma_store import get_chroma_path_v2  # noqa: E402
from request_log import RequestTrace, request_logger  # noqa: E402

request_logger.setLevel("WARNING")  # the trace lines would drown the report


def main():
    client = chromadb.PersistentClient(path=get_chroma_path_v2(), settings=ChromaSettings(anonymized_telemetry=False))
    api.arabic_collection = client.get_collection(api.ARABIC_COLLECTION_NAME)
    questions = [json.loads(line) for line in (ROOT / "eval/questions.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    arabic = [q["question"] for q in questions if q.get("language") == "ar"]
    # Saint names as the saints pane and calendar links send them ("من هو …؟").
    arabic += [f"من هو {api._arabic_lookup_name(r)}؟" for r in api._build_v2_arabic_saint_records()[:20]]

    started = time.monotonic()
    api._warm_arabic_lexical_index()
    build_ms = (time.monotonic() - started) * 1000

    mismatches, scan_ms, cached_ms, compared = [], [], [], 0
    for mode in ("chat", "catechism", "saints"):
        metadata_filter = api._arabic_metadata_filter_for_mode(mode)
        for question in arabic:
            results = {}
            for cached, samples in ((False, scan_ms), (True, cached_ms)):
                api.ARABIC_LEXICAL_CACHE = cached
                with RequestTrace("check"):
                    t = time.perf_counter()
                    docs, metas = api._retrieve_arabic_lexical_documents(question, top_k=16, metadata_filter=metadata_filter)
                    samples.append((time.perf_counter() - t) * 1000)
                results[cached] = [m.get("chunk_id") for m in metas]
            compared += 1
            if results[False] != results[True]:
                mismatches.append({"mode": mode, "question": question})

    report = {
        "questions": len(arabic),
        "comparisons": compared,
        "mismatches": mismatches,
        "index_build_ms_all_modes": round(build_ms),
        "scan_ms_median": round(statistics.median(scan_ms), 1),
        "scan_ms_p90": round(statistics.quantiles(scan_ms, n=10)[8], 1),
        "cached_ms_median": round(statistics.median(cached_ms), 1),
        "cached_ms_p90": round(statistics.quantiles(cached_ms, n=10)[8], 1),
    }
    print(json.dumps(report, ensure_ascii=False, indent=1))
    raise SystemExit(1 if mismatches else 0)


if __name__ == "__main__":
    main()
