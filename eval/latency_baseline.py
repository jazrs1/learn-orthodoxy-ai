"""Where a request's time goes, without calling OpenAI (RET-012).

1. Stage timings recorded by earlier runs: the v2 coverage evals' `stages_ms` and total latency, and
   request-log lines (a backend's stdout, e.g. `railway logs`) with `stages_ms` and `ttft_ms`.
2. Local timing of the stages that don't need OpenAI, on the v2 store: vector search (queried with
   stored chunk vectors, so no embedding call), the Arabic lexical scan, context assembly and the
   named-subject check. The embedding function raises if anything tries to call OpenAI.

    CORPUS_VERSION=v2 python eval/latency_baseline.py [--logs backend.log ...] [--out report.json]
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

os.environ.setdefault("CORPUS_VERSION", "v2")
os.environ["OPENAI_API_KEY"] = ""  # nothing below may reach OpenAI
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import chromadb  # noqa: E402
from chromadb.config import Settings as ChromaSettings  # noqa: E402

import api  # noqa: E402
from chroma_store import get_chroma_path_v2  # noqa: E402
from entity_check import check_subjects  # noqa: E402
from request_log import RequestTrace  # noqa: E402

EVAL_RUNS = ["eval/results/20260923-000307.json", "eval/results/20260923-002553.json"]
STAGES = ["analysis", "retrieval", "generation", "postprocess"]


class NoEmbedding(chromadb.EmbeddingFunction):
    def __init__(self):
        pass

    def __call__(self, input):  # noqa: A002 - chromadb's signature
        raise RuntimeError("latency_baseline must not call OpenAI")


def pct(values, q):
    values = sorted(v for v in values if v is not None)
    if not values:
        return None
    if len(values) == 1:
        return round(values[0], 1)
    return round(statistics.quantiles(values, n=100, method="inclusive")[q - 1], 1)


def summary(values):
    values = [v for v in values if v is not None]
    return {"n": len(values), "median": pct(values, 50), "p90": pct(values, 90)} if values else {"n": 0}


def recorded_eval_stages():
    out = {}
    for language in ("en", "ar"):
        for kind in ("answered", "refused"):
            rows = []
            for path in EVAL_RUNS:
                data = json.loads((ROOT / path).read_text(encoding="utf-8"))
                rows += [r for r in data["records"] if r["language"] == language and r["outcome"] == kind and r.get("stages_ms")]
            if not rows:
                continue
            entry = {stage: summary([r["stages_ms"].get(stage) for r in rows]) for stage in STAGES}
            entry["total"] = summary([r["latency_s"] * 1000 for r in rows])
            out[f"{language}/{kind}"] = entry
    return out


def recorded_log_stages(paths):
    lines = []
    for path in paths:
        for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
            start = line.find('{"event": "request"')
            if start < 0:
                continue
            record = json.loads(line[start:])
            if record.get("endpoint") in ("chat", "chat_stream"):
                lines.append(record)
    out = {}
    for language in ("en", "ar"):
        rows = [r for r in lines if r.get("language") == language and r.get("outcome") == "answered"]
        if not rows:
            continue
        stages = {stage: summary([(r.get("stages_ms") or {}).get(stage) for r in rows]) for stage in STAGES}
        stages["ttft"] = summary([r.get("ttft_ms") for r in rows])
        stages["model_first_token"] = summary(
            [
                r["ttft_ms"] - sum((r.get("stages_ms") or {}).get(s, 0) for s in ("analysis", "prepare", "retrieval"))
                for r in rows
                if r.get("ttft_ms")
            ]
        )
        stages["total"] = summary([r.get("total_ms") for r in rows])
        out[language] = stages
    return out


def timed(fn, repeat=1):
    samples = []
    result = None
    for _ in range(repeat):
        started = time.perf_counter()
        result = fn()
        samples.append((time.perf_counter() - started) * 1000)
    return result, samples


def local_stages():
    client = chromadb.PersistentClient(path=get_chroma_path_v2(), settings=ChromaSettings(anonymized_telemetry=False))
    english = client.get_collection(api.COLLECTION_NAME, embedding_function=NoEmbedding())
    arabic = client.get_collection(api.ARABIC_COLLECTION_NAME, embedding_function=NoEmbedding())
    api.collection, api.arabic_collection = english, arabic

    questions = [json.loads(line) for line in (ROOT / "eval/questions.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    arabic_questions = [q["question"] for q in questions if q.get("language") == "ar"]
    out = {"collections": {"en": english.count(), "ar": arabic.count()}}

    for label, target in (("en", english), ("ar", arabic)):
        probe = target.get(limit=40, include=["embeddings"])
        vectors = [list(v) for v in probe["embeddings"]]
        target.query(query_embeddings=[vectors[0]], n_results=16)  # warm the index
        for k in (16, 12):
            samples = []
            for vector in vectors:
                _, s = timed(lambda: target.query(query_embeddings=[vector], n_results=k, include=["documents", "metadatas", "distances"]))
                samples += s
            out[f"vector_search_{label}_k{k}"] = summary(samples)
        batch = []
        for i in range(0, 39, 3):
            _, s = timed(lambda: target.query(query_embeddings=vectors[i:i + 3], n_results=16, include=["documents", "metadatas", "distances"]))
            batch += s
        out[f"vector_search_{label}_k16_3queries"] = summary(batch)

    # The Arabic lexical scan as it runs today (AUDIT C13): every Arabic document fetched and scanned.
    scan, fetch_only = [], []
    for question in arabic_questions:
        with RequestTrace("bench"):
            _, s = timed(lambda: api._retrieve_arabic_lexical_documents(question, top_k=16))
        scan += s
    for _ in range(5):
        def fetch_all():
            offset = 0
            while True:
                batch = arabic.get(include=["documents", "metadatas"], limit=500, offset=offset)
                if len(batch["documents"]) < 500:
                    break
                offset += 500
        _, s = timed(fetch_all)
        fetch_only += s
    out["arabic_lexical_scan"] = summary(scan)
    out["arabic_lexical_fetch_only"] = summary(fetch_only)

    # Context assembly and the named-subject check on a realistic 16-chunk context.
    sample = english.get(limit=16, include=["documents", "metadatas"])
    docs, metas = sample["documents"], sample["metadatas"]
    _, s = timed(lambda: api._build_numbered_context(docs, metas), repeat=50)
    out["context_assembly_en_16"] = summary(s)
    _, s = timed(lambda: check_subjects(["papal infallibility", "St. Athanasius"], docs), repeat=50)
    out["entity_check_en_16"] = summary(s)
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--logs", nargs="*", default=[])
    parser.add_argument("--out")
    args = parser.parse_args()
    report = {
        "recorded_eval_v2": recorded_eval_stages(),
        "recorded_logs": recorded_log_stages(args.logs) if args.logs else {},
        "local": local_stages(),
    }
    text = json.dumps(report, indent=1, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
