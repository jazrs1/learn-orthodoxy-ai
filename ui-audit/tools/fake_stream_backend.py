"""The real api.py (internal key, rate limit, /chat, /chat/stream, logging) with a scripted model.

No OpenAI and no Chroma: `_chat_prepare` is replaced by canned outcomes chosen by the question, and
the model by a stream that sends a canned answer word by word (UI-026, streaming.mjs MODE=fake).

    INTERNAL_API_KEY is set to "localkey"; run the site with ORTHODOX_API_KEY=localkey.
    python ui-audit/tools/fake_stream_backend.py            # port 8001; PORT and FAKE_DELAY (s/word) override

Question contains "menu" -> a saint menu (JSON); "refuse" -> a refusal (JSON); "table" -> an answer
with a table; Arabic text -> an Arabic answer; "fail" -> an OpenAI error after 25 words; otherwise a
long English answer.
"""

import asyncio
import os
import re
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ["OPENAI_API_KEY"] = ""  # startup then opens no Chroma and creates no OpenAI client
os.environ.setdefault("CHAT_RATE_LIMIT_PER_MINUTE", "0")  # repeated check runs would trip the 20/min limit

import httpx  # noqa: E402
import uvicorn  # noqa: E402

import api  # noqa: E402

DELAY = float(os.environ.get("FAKE_DELAY", "0.04"))
EN = (
    "**Prayer** is conversation with God, and the Church calls it the breath of the spiritual life [1]. "
    "The catechism teaches that a Christian prays not only with words but with the whole heart, standing before God "
    "with humility and love [2].\n\nThere are several kinds of prayer:\n\n1. **Praise**, glorifying God for who He is [1].\n"
    "2. **Thanksgiving**, for His gifts [3].\n3. **Repentance**, asking forgiveness [2].\n4. **Intercession**, praying for others [3].\n\n"
    "St. Anthony taught that prayer should be constant, and the Agpeya gives the hours of the day a shape [4]. "
) * 3
TABLE = (
    "Here are the main fasts of the Coptic Orthodox Church [1]:\n\n| Fast | Length | Notes |\n| --- | --- | --- |\n"
    "| Great Lent | 55 days | Before the Feast of the Resurrection [1] |\n| Apostles' Fast | varies | After Pentecost [2] |\n"
    "| Nativity Fast | 43 days | Before Christmas [2] |\n| Fast of Nineveh | 3 days | Two weeks before Lent [3] |\n\n"
    "Fasting is always joined with prayer and almsgiving [3]."
)
AR = (
    "**الصلاة** هي صلة الإنسان بالله، وهي نسمة الحياة الروحية [1]. يعلّم الكاتيكيزم أن المسيحي يصلّي بقلبه كله "
    "وليس بلسانه فقط [2].\n\nومن أنواع الصلاة:\n\n1. **التسبيح** لله [1].\n2. **الشكر** على عطاياه [3].\n3. **التوبة** وطلب الغفران [2].\n\n"
) * 5
SOURCES = [
    {"source_type": "pdf", "pdf": "catechism1.pdf", "page": 30 + n, "n": n, "label": f"Catechism, Volume 1, p. {30 + n}", "entry": "What is prayer?"}
    for n in range(1, 5)
]
AR_SOURCES = [{"source_type": "pdf", "pdf": "full arabic catechism.pdf", "page": 100 + n, "n": n, "entry": "الصلاة"} for n in range(1, 4)]


def prepare(req, trace):
    question = req.question
    trace.lap("analysis")
    if "menu" in question:
        trace.set(outcome="options")
        return {
            "answer": "Several saints are named Athanasius. Which one do you mean?",
            "sources": [],
            "options": ["St. Athanasius the Apostolic", "St. Athanasius II"],
            "option_ids": ["athanasius-the-apostolic", "athanasius-ii"],
        }
    if "refuse" in question:
        trace.set(outcome="refused", refusal=True)
        return {"answer": api._no_source_answer("en"), "sources": [], "entities": [], "options": []}
    arabic = api._contains_arabic(question)
    text = AR if arabic else TABLE if "table" in question else EN
    sources = AR_SOURCES if arabic else SOURCES

    def finish(reply):
        trace.set(outcome="answered")
        return {"answer": reply, "sources": sources, "entities": [], "options": []}

    # The canned text travels in the prompt, where the fake models below read it.
    return api.PendingAnswer(messages=[{"role": "user", "content": text, "fail": "fail" in question}], max_tokens=10, finish=finish)


class FakeStream:
    def __init__(self, text, fail):
        self.pieces = re.findall(r"\S*\s*", text)[:-1]
        self.fail = fail
        self.sent = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        await asyncio.sleep(DELAY)
        if self.fail and self.sent == 25:
            raise api.APIConnectionError(request=httpx.Request("POST", "https://api.openai.test"))
        if self.sent >= len(self.pieces):
            raise StopAsyncIteration
        self.sent += 1
        delta = SimpleNamespace(content=self.pieces[self.sent - 1])
        return SimpleNamespace(usage=None, choices=[SimpleNamespace(finish_reason=None, delta=delta)])

    async def close(self):
        pass


async def create_stream(**kwargs):
    await asyncio.sleep(0.6)  # the model's time to first token
    message = kwargs["messages"][0]
    return FakeStream(message["content"], message["fail"])


def create(**kwargs):
    message = SimpleNamespace(content=kwargs["messages"][0]["content"])
    return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason="stop")], usage=None)


api._chat_prepare = prepare
api.INTERNAL_API_KEY = "localkey"
server = uvicorn.Server(uvicorn.Config(api.app, host="127.0.0.1", port=int(os.environ.get("PORT", "8001")), log_level="warning"))


async def main():
    serving = asyncio.create_task(server.serve())
    while not server.started:
        await asyncio.sleep(0.05)
    # After startup, which would otherwise leave both clients unset.
    api.async_oai_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create_stream)))
    api.oai_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    print("fake backend ready", flush=True)
    await serving


asyncio.run(main())
