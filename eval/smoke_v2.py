"""Post-switch smoke set for the v2 corpus (ING-008 runbook, step "Verify").

    INTERNAL_API_KEY=... python eval/smoke_v2.py --backend https://<railway backend> [--expect v2] [--no-chat]

Checks, in order, and stops at the first failure:
  1. /health reports the expected corpus_version and both collections ready (no OpenAI).
  2. /saints and /saint-suggestions answer in English and Arabic (no OpenAI).
  3. Eight /chat requests (~$0.04 with gpt-4.1-mini): each gets HTTP 200, the expected outcome
     (answered / refused / options), and, when answered, v2-shaped sources (chunk_id, entry, pages) and
     labels that name the question or saint. `--no-chat` skips this step.
Nothing is written anywhere; the backend's own request log records the calls.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import requests

CHAT = [
    # (question, mode, language, expected outcome, a word the answer or a source entry must contain)
    ("What is prayer?", "chat", "en", "answered", "prayer"),
    ("Who was St. Athanasius the Apostolic?", "chat", "en", "answered", "Athanasius"),
    ("search saint: St. George", "saints", "en", "answered", "George"),
    ("List the saints named Gregory", "chat", "en", "answered", "Gregory"),
    ("Who won the 2018 FIFA World Cup?", "chat", "en", "refused", ""),
    ("ما هي الصلاة؟", "catechism", "ar", "answered", "الصلاة"),
    ("من هو الأنبا بولا أول السواح؟", "saints", "ar", "answered", "بولا"),
    ("ما هي عاصمة فرنسا؟", "chat", "ar", "refused", ""),
]
REFUSALS = ("i could not find", "the sources do not", "لم أجد معلومات كافية")


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    raise SystemExit(1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--backend", required=True)
    parser.add_argument("--expect", default="v2", choices=["v1", "v2"])
    parser.add_argument("--no-chat", action="store_true")
    args = parser.parse_args()
    key = os.getenv("INTERNAL_API_KEY") or os.getenv("ORTHODOX_API_KEY") or ""
    base = args.backend.rstrip("/")
    headers = {"X-Internal-Key": key, "Content-Type": "application/json"}

    health = requests.get(f"{base}/health", timeout=15).json()
    print("health:", health)
    if health.get("corpus_version") != args.expect:
        fail(f"corpus_version is {health.get('corpus_version')!r}, expected {args.expect}")
    if not (health.get("collection_ready") and health.get("arabic_collection_ready")):
        fail("collections not ready")

    for language, query in (("en", "George"), ("ar", "جرجس")):
        saints = requests.get(f"{base}/saints", params={"q": query, "language": language, "limit": 5}, headers=headers, timeout=30)
        suggest = requests.get(f"{base}/saint-suggestions", params={"q": query, "language": language}, headers=headers, timeout=30)
        if saints.status_code != 200 or suggest.status_code != 200:
            fail(f"/saints or /saint-suggestions ({language}) returned {saints.status_code}/{suggest.status_code}")
        print(f"/saints {language}: {saints.json().get('total')} matches, first {saints.json().get('saints', [])[:2]}")
    if args.no_chat:
        print("OK (no chat requests)")
        return 0

    for question, mode, language, expected, must in CHAT:
        started = time.monotonic()
        response = requests.post(f"{base}/chat", json={"question": question, "mode": mode, "language": language, "top_k": 8},
                                 headers=headers, timeout=90)
        elapsed = time.monotonic() - started
        if response.status_code != 200:
            fail(f"{question!r}: HTTP {response.status_code} {response.text[:200]}")
        data = response.json()
        answer, sources, options = data.get("answer") or "", data.get("sources") or [], data.get("options") or []
        refused = answer.strip().lower().startswith(REFUSALS) or answer.strip().startswith(REFUSALS)
        outcome = "refused" if refused else ("options" if options and not answer.strip() else "answered")
        if outcome != expected:
            fail(f"{question!r}: expected {expected}, got {outcome}: {answer[:160]!r}")
        if expected == "answered":
            if not sources:
                fail(f"{question!r}: answered without sources")
            if args.expect == "v2" and not all(s.get("chunk_id") and s.get("entry") for s in sources if s.get("source_type") == "pdf"):
                fail(f"{question!r}: sources are not v2-shaped: {sources[:1]}")
            haystack = answer + " " + " ".join(str(s.get("entry") or s.get("label") or "") for s in sources)
            if must and must.lower() not in haystack.lower():
                fail(f"{question!r}: neither the answer nor a source mentions {must!r}")
        print(f"ok {elapsed:4.1f}s {outcome:9} {question[:50]:50} sources={len(sources)} "
              f"{(sources[0].get('label') or '')[:70] if sources else ''}")
    print("OK: smoke set passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
