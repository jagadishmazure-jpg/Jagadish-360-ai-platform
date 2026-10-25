"""Cost ledger. Closed-model prices are list prices with an as-of date; local cost is amortised hardware plus power.

Prices change. Check the provider's pricing page before using these numbers for a quote.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

PRICES_AS_OF = "2026-10-25 (gpt-4o-mini list price per 1M tokens as published by the provider; re-check before quoting)"

# USD per 1M tokens (input, output)
PRICES = {
    "gpt-4o-mini": (0.15, 0.60),
    "azure-gpt-4o-mini": (0.15, 0.60),
    # Local models: amortised server cost per 1M tokens, computed in breakeven.local_cost_per_mtok() with the
    # default single-GPU profile. Labelled ESTIMATED: depends on hardware price, power and utilisation.
    "local": (0.0, 0.0),
}


@dataclass
class Budget:
    limit_usd: float
    spent_usd: float = 0.0

    def allow(self, est: float) -> bool:
        return self.spent_usd + est <= self.limit_usd


class CostLedger:
    def __init__(self, local_per_mtok: float = 0.0):
        self.local_per_mtok = local_per_mtok
        self.by_key: dict[tuple[str, str], float] = defaultdict(float)
        self.tokens: dict[str, int] = defaultdict(int)

    def price(self, model: str, tin: int, tout: int) -> float:
        if model in PRICES and model != "local":
            pi, po = PRICES[model]
            return (tin * pi + tout * po) / 1e6
        return (tin + tout) * self.local_per_mtok / 1e6

    def record(self, tenant: str, model: str, tin: int, tout: int) -> float:
        usd = self.price(model, tin, tout)
        self.by_key[(tenant, model)] += usd
        self.tokens[model] += tin + tout
        return usd

    def total(self) -> float:
        return sum(self.by_key.values())

    def report(self) -> dict:
        return {f"{t}/{m}": round(v, 6) for (t, m), v in sorted(self.by_key.items())}
