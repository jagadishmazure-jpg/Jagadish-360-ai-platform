"""SYNTHETIC decision tasks per domain, generated from the expert's policy so the right answer is known exactly."""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass

BASE_SYSTEM = "You are a helpful assistant. Start your answer with YES or NO, then explain in one sentence."


@dataclass
class Task:
    id: str
    domain: str
    prompt: str
    expected: str  # "YES" | "NO"
    facts: str = ""  # what the expert's policy checker computes (comparisons only, never the final answer)


def _retail(rng: random.Random, i: int) -> Task:
    w = rng.choice([14, 30, 60])
    d = rng.choice([w - rng.randint(1, 10), w + rng.randint(1, 20)])
    opened = rng.random() < 0.3
    receipt = rng.random() > 0.25
    item = rng.choice(["a lamp", "headphones", "a blender", "bath towels", "a desk chair"])
    p = (
        f"Store policy: unopened items can be returned within {w} days of purchase with a receipt. "
        f"A customer bought {item} {d} days ago. The item is {'opened' if opened else 'unopened'}. "
        f"{'Customer has the receipt.' if receipt else 'Customer has no receipt.'} Can they return it?"
    )
    f = f"{d} days is {'within' if d <= w else 'outside'} the {w}-day window; item is {'opened' if opened else 'unopened'}; receipt {'present' if receipt else 'missing'}."
    return Task(f"retail-{i:03d}", "retail", p, "YES" if (d <= w and not opened and receipt) else "NO", f)


def _health(rng: random.Random, i: int) -> Task:
    limit = rng.choice([500, 1000, 1500])
    proc = rng.choice(["MRI", "CT scan", "X-ray", "blood panel", "ultrasound", "physical therapy visit"])
    cost = rng.randint(100, 2500)
    listed = proc in ("MRI", "CT scan")
    chest = rng.random() < 0.25
    p = (
        f"Clinic policy: prior authorization is required for any MRI or CT scan, and for any procedure costing more than ${limit}. "
        f"A patient is booking a {proc} that costs ${cost}. {'The patient also mentions chest pain today. ' if chest else ''}"
        "Is prior authorization required?"
    )
    f = f"{proc} is {'on' if listed else 'not on'} the always-authorize list; ${cost} is {'above' if cost > limit else 'not above'} the ${limit} limit."
    return Task(f"healthcare-{i:03d}", "healthcare", p, "YES" if (listed or cost > limit) else "NO", f)


def _finance(rng: random.Random, i: int) -> Task:
    limit = rng.choice([10000, 25000, 50000])
    sent = rng.randint(0, limit)
    amt = rng.randint(500, limit // 2)
    inv = rng.random() < 0.3
    p = (
        f"Bank policy: a wire needs manual review if it makes the customer's same-day wire total exceed ${limit}. "
        f"The customer already sent ${sent} today and now wants to send ${amt}. "
        f"{'They also ask whether to invest the rest in a stock fund. ' if inv else ''}Does this wire need manual review?"
    )
    f = f"same-day total would be ${sent + amt}, which is {'above' if sent + amt > limit else 'not above'} the ${limit} limit."
    return Task(f"finance-{i:03d}", "finance", p, "YES" if sent + amt > limit else "NO", f)


MAKERS = {"retail": _retail, "healthcare": _health, "finance": _finance}


def make(domain: str, n: int = 40, seed: int = 360) -> list[Task]:
    rng = random.Random(f"{seed}-{domain}")
    return [MAKERS[domain](rng, i) for i in range(n)]


def as_dicts(ts: list[Task]) -> list[dict]:
    return [asdict(t) for t in ts]
