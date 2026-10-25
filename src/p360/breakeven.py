"""Break-even calculator: buy a small inference server once vs pay per token every month.

Every input is an explicit, editable assumption. Defaults are ESTIMATES with the source noted in ASSUMPTIONS;
replace them with a real quote and your own throughput benchmark before advising a customer.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

ASSUMPTIONS = {
    "server_usd": "Estimate for a tower server with one 24 GB data-centre GPU, CPU, 128 GB RAM, NVMe. Replace with a real quote.",
    "gpu_watts": "72 W board power from the published spec sheet of a 24 GB low-profile inference GPU (L4 class); whole server estimated at 350 W under load.",
    "kwh_usd": "0.17 USD/kWh, roughly a US commercial average; use the customer's tariff.",
    "ops_usd_month": "Estimated monthly support, backup and remote-hands allowance for a small business.",
    "tokens_per_s": "ESTIMATED aggregate decode throughput for a 7-8B model at 4-bit with batching on one 24 GB GPU. Benchmark it (scripts/bench_vllm.md).",
    "api_usd_per_mtok": "Blended closed-model price (input 0.15, output 0.60 per 1M, 3:1 in:out mix) from the provider's list prices as of 2026-10-25.",
    "premium_api_usd_per_mtok": "Blended price for a larger closed model (input 2.50, output 10.00 per 1M, 3:1 mix) from list prices as of 2026-10-25.",
    "lifetime_months": "36-month hardware depreciation, a common accounting choice.",
}


@dataclass
class Inputs:
    server_usd: float = 9000.0
    server_watts: float = 350.0
    kwh_usd: float = 0.17
    ops_usd_month: float = 150.0
    tokens_per_s: float = 400.0
    utilisation: float = 0.5
    lifetime_months: int = 36
    monthly_tokens_m: float = 500.0  # millions of tokens per month
    api_usd_per_mtok: float = 0.2625  # (3*0.15 + 1*0.60) / 4


HOURS_PER_MONTH = 730.0
PREMIUM_API_USD_PER_MTOK = (3 * 2.50 + 10.00) / 4


def servers_needed(i: Inputs) -> int:
    return max(1, math.ceil(i.monthly_tokens_m / capacity_mtok_month(i)))


def power_usd_month(i: Inputs) -> float:
    return i.server_watts / 1000 * HOURS_PER_MONTH * i.kwh_usd * max(i.utilisation, 0.2)


def capacity_mtok_month(i: Inputs) -> float:
    return i.tokens_per_s * 3600 * HOURS_PER_MONTH * i.utilisation / 1e6


def local_cost_per_mtok(i: Inputs) -> float:
    monthly = servers_needed(i) * (i.server_usd / i.lifetime_months + power_usd_month(i) + i.ops_usd_month)
    return monthly / max(i.monthly_tokens_m, 1e-9)


def payback_month(i: Inputs) -> int | None:
    """First month where cumulative API spend >= server price + cumulative running cost. None if never (within lifetime)."""
    n = servers_needed(i)
    api = i.monthly_tokens_m * i.api_usd_per_mtok
    run = n * (power_usd_month(i) + i.ops_usd_month)
    if api <= run:
        return None
    m = math.ceil(n * i.server_usd / (api - run))
    return m if m <= i.lifetime_months else None


def report(i: Inputs) -> dict:
    api = i.monthly_tokens_m * i.api_usd_per_mtok
    return {
        "inputs": asdict(i),
        "api_usd_month": round(api, 2),
        "local_running_usd_month": round(power_usd_month(i) + i.ops_usd_month, 2),
        "capacity_mtok_month": round(capacity_mtok_month(i), 1),
        "servers_needed": servers_needed(i),
        "local_usd_per_mtok": round(local_cost_per_mtok(i), 4),
        "payback_month": payback_month(i),
        "label": "ESTIMATED from editable assumptions; not a quote",
    }


def sweep(base: Inputs, volumes_m: list[float]) -> list[dict]:
    out = []
    for v in volumes_m:
        i = Inputs(**{**asdict(base), "monthly_tokens_m": v})
        r = report(i)
        p = Inputs(**{**asdict(i), "api_usd_per_mtok": PREMIUM_API_USD_PER_MTOK})
        out.append(
            {
                "monthly_tokens_m": v,
                "servers": r["servers_needed"],
                "local_usd_per_mtok": r["local_usd_per_mtok"],
                "small_api_usd_month": r["api_usd_month"],
                "payback_vs_small_api": r["payback_month"],
                "premium_api_usd_month": round(v * PREMIUM_API_USD_PER_MTOK, 2),
                "payback_vs_premium_api": payback_month(p),
            }
        )
    return out
