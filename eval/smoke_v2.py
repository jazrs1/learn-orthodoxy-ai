"""Post-switch smoke set for the v2 corpus (ING-008 runbook, step "Verify").

    INTERNAL_API_KEY=... python eval/smoke_v2.py --backend https://<railway backend> [--expect v2] [--no-chat]

Checks, in order, and stops at the first failure:
  1. /health reports the expected corpus_version and both collections ready (no OpenAI).
  2. /saints and /saint-suggestions answer in English and Arabic (no OpenAI).
  3. Eight /chat requests (~$0.04 with gpt-4.1-mini): each gets HTTP 200, the expected outcome
     (answered / refused / menu), and, when answered, v2-shaped sources (chunk_id, entry, pages) and
     labels that name the question or saint. A namesake menu must carry an entry ID per option; the
     script then chooses one by ID, as the site does, and needs an answer led by that entry (RET-010;
     the menu itself costs nothing). A bare name on data/saint_defaults.json must be answered about its
     major saint and carry the "Looking for a different St. X?" link, whose menu (free) must list the
     other saints with their IDs and not the major one (RET-011). `--no-chat` skips this step.
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
    # A "menu" case names the option to choose after the colon: "menu:<label contains>"; a "default"
    # case names the saint the first source must be: "default:<entry contains>".
    ("What is prayer?", "chat", "en", "answered", "prayer"),
    ("Who was St. Athanasius the Apostolic?", "chat", "en", "answered", "Athanasius"),
    ("search saint: St. George", "saints", "en", "default:Capaducian", "George"),
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

    def post(body):
        response = requests.post(f"{base}/chat", json={"top_k": 8, **body}, headers=headers, timeout=90)
        if response.status_code != 200:
            fail(f"{body['question']!r}: HTTP {response.status_code} {response.text[:200]}")
        return response.json()

    for question, mode, language, expected, must in CHAT:
        started = time.monotonic()
        data = post({"question": question, "mode": mode, "language": language})
        if expected.startswith("menu:"):
            options, ids = data.get("options") or [], data.get("option_ids") or []
            if not options or len(ids) != len(options) or not all(ids) or data.get("sources"):
                fail(f"{question!r}: expected a namesake menu with an entry ID per option, got {data}")
            label = next((o for o in options if expected[5:] in o), None)
            if label is None:
                fail(f"{question!r}: no option contains {expected[5:]!r}: {options}")
            print(f"   menu {len(options)} options: {' | '.join(options)}; choosing {label!r} by id {ids[options.index(label)]}")
            chip = f"من هو {label}؟" if language == "ar" else f"search saint: {label}"
            data = post({"question": chip, "mode": "saints", "language": language, "saint_id": ids[options.index(label)]})
            expected = "answered"
        default = expected[8:] if expected.startswith("default:") else ""
        expected = "answered" if default else expected
        elapsed = time.monotonic() - started
        answer, sources, options = data.get("answer") or "", data.get("sources") or [], data.get("options") or []
        refused = answer.strip().lower().startswith(REFUSALS) or answer.strip().startswith(REFUSALS)
        outcome = "refused" if refused else ("options" if options and not sources else "answered")
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
        if default:
            first_entry = str(sources[0].get("entry") or "") if sources else ""
            link = data.get("namesakes") or {}
            if default not in first_entry or not link.get("label") or not link.get("name"):
                fail(f"{question!r}: expected an answer led by {default!r} with a namesakes link, got {first_entry!r}, {link}")
            menu = post({"question": link["label"], "mode": "saints", "language": language, "namesakes_of": link["name"]})
            names, ids = menu.get("options") or [], menu.get("option_ids") or []
            if not names or len(ids) != len(names) or not all(ids) or menu.get("sources") or any(default in n for n in names):
                fail(f"{question!r}: the link's menu should list the other saints with IDs, without {default!r}: {menu}")
            print(f"   default: {first_entry!r}; link {link['label']!r} -> {len(names)} others: {' | '.join(names)}")
        print(f"ok {elapsed:4.1f}s {outcome:9} {question[:50]:50} sources={len(sources)} "
              f"{(sources[0].get('label') or '')[:70] if sources else ''}")
    print("OK: smoke set passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
