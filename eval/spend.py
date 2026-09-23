"""OpenAI spend accounting for eval runs, with a hard ceiling (Phase 5 Step 5, ING-006).

Every run adds what it spent to a ledger file; before each question the run checks that the ledger
total plus a projection for the next question stays under `--max-spend`, and stops cleanly (partial
results are written) when it would not. Judge calls go through `MeteredClient`, which records their
usage and turns quota and auth errors into `FatalOpenAIError` (never retried: the key is shared with
production). Backend spend comes from the token counts in each /chat debug payload.

Prices are USD per 1M tokens (input, output), list prices as of 2026-09; check before relying on them.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

PRICES = {
    "gpt-4.1": (2.00, 8.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4o-mini": (0.15, 0.60),
    "text-embedding-3-small": (0.02, 0.0),
}


class FatalOpenAIError(SystemExit):
    """Quota or auth failure: stop the whole run (SystemExit so no `except Exception` swallows it)."""


class BudgetExceeded(Exception):
    pass


def price_of(model: Optional[str], prompt_tokens: int, completion_tokens: int = 0) -> float:
    key = next((name for name in sorted(PRICES, key=len, reverse=True) if model and str(model).startswith(name)), None)
    if key is None:
        key = "gpt-4.1"  # unknown model: assume the most expensive one in use
    inp, out = PRICES[key]
    return (prompt_tokens * inp + completion_tokens * out) / 1_000_000


class SpendLedger:
    def __init__(self, path: Optional[Path], max_spend: Optional[float]):
        self.path = path
        self.max_spend = max_spend
        self.entries: list = []
        self.prior = 0.0
        if path and path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            self.prior = float(data.get("total_usd", 0.0))
            self.entries = data.get("entries", [])
        self.run_usd = 0.0
        self.run_by_model: Dict[str, float] = {}

    @property
    def total(self) -> float:
        return self.prior + self.run_usd

    def add(self, model: Optional[str], prompt_tokens: int, completion_tokens: int, what: str) -> float:
        cost = price_of(model, int(prompt_tokens or 0), int(completion_tokens or 0))
        self.run_usd += cost
        name = f"{model}:{what}"
        self.run_by_model[name] = self.run_by_model.get(name, 0.0) + cost
        return cost

    def check(self, projected_next: float = 0.0) -> None:
        if self.max_spend is not None and self.total + projected_next > self.max_spend:
            raise BudgetExceeded(
                f"spend would exceed the ceiling: ledger ${self.total:.4f} + next ~${projected_next:.4f} > ${self.max_spend:.2f}")

    def save(self, label: str) -> None:
        if not self.path:
            return
        self.entries.append({"label": label, "usd": round(self.run_usd, 5),
                             "by_model": {k: round(v, 5) for k, v in sorted(self.run_by_model.items())}})
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"total_usd": round(self.total, 5), "max_spend": self.max_spend,
                                         "entries": self.entries}, indent=1) + "\n", encoding="utf-8")


def _fatal(error: Exception) -> bool:
    text = f"{type(error).__name__} {error}".lower()
    status = getattr(error, "status_code", None)
    return "insufficient_quota" in text or status in (401, 403) or type(error).__name__ in (
        "AuthenticationError", "PermissionDeniedError")


class _Completions:
    def __init__(self, client: Any, ledger: SpendLedger):
        self._client, self._ledger = client, ledger

    def create(self, **kwargs):
        try:
            response = self._client.chat.completions.create(**kwargs)
        except Exception as error:
            if _fatal(error):
                print(f"FATAL OpenAI error in the judge, stopping: {type(error).__name__}: {error}", file=sys.stderr)
                raise FatalOpenAIError(3)
            raise
        usage = getattr(response, "usage", None)
        if usage is not None:
            self._ledger.add(kwargs.get("model"), usage.prompt_tokens or 0, usage.completion_tokens or 0, "judge")
        return response


class _Chat:
    def __init__(self, client: Any, ledger: SpendLedger):
        self.completions = _Completions(client, ledger)


class MeteredClient:
    """Stands in for the OpenAI client inside `scoring.py`: same `chat.completions.create`."""

    def __init__(self, client: Any, ledger: SpendLedger):
        self.chat = _Chat(client, ledger)


def record_backend_spend(ledger: SpendLedger, debug: Dict[str, Any], question_chars: int) -> float:
    """What one /chat call cost: generation + analysis tokens from the debug payload, plus the query
    embeddings (estimated from the retrieval queries; a few hundred tokens at $0.02/M)."""
    cost = 0.0
    if debug.get("prompt_tokens") or debug.get("completion_tokens"):
        cost += ledger.add(debug.get("model"), debug.get("prompt_tokens") or 0, debug.get("completion_tokens") or 0, "generation")
    analysis = debug.get("task_analysis") or {}
    if analysis.get("prompt_tokens"):
        cost += ledger.add(analysis.get("model") or "gpt-4o-mini", analysis.get("prompt_tokens") or 0,
                           analysis.get("completion_tokens") or 0, "analysis")
    queries = debug.get("retrieval_queries") or []
    embed_tokens = sum(len(str(q)) for q in queries) // 3 + question_chars // 3
    cost += ledger.add("text-embedding-3-small", embed_tokens, 0, "embedding")
    return cost
