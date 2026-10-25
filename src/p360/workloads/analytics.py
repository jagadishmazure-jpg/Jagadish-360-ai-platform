"""Analytics: governed aggregate queries over synthetic sales rows.

Small-cell suppression (groups under k rows are hidden) so aggregates cannot single out a customer.
"""

from __future__ import annotations

from collections import defaultdict

import numpy as np

from ..platform import Platform

REGIONS = ("north", "south", "east", "west")
CATEGORIES = ("grocery", "home", "apparel", "electronics")


def synth(n: int = 3000, seed: int = 3) -> list[dict]:
    rng = np.random.default_rng(seed)
    return [{"region": REGIONS[rng.integers(4)], "category": CATEGORIES[rng.integers(4)], "amount": float(round(rng.gamma(2, 25), 2))} for _ in range(n)]


def group_sum(rows: list[dict], by: str, k_min: int = 10) -> dict[str, dict]:
    acc: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        acc[r[by]].append(r["amount"])
    return {g: ({"n": len(v), "total": round(sum(v), 2), "avg": round(sum(v) / len(v), 2)} if len(v) >= k_min else {"n": len(v), "suppressed": True}) for g, v in sorted(acc.items())}


def run(p: Platform, tenant: str = "retail") -> dict:
    with p.job("analytics", tenant, query="sales_by_region"):
        rows = synth()
        return {"by_region": group_sum(rows, "region"), "rows": len(rows), "data": "synthetic"}
