"""Preference pairs -> a learned reranker over the open model's sampled answers (best-of-n with a reward model).

This is the CPU-sized version of preference tuning: instead of updating the 0.5B model's weights (DPO/LoRA, planned
for a GPU), a small Bradley-Terry model learns from expert pairs which candidate an expert would choose.
Features never see the expected answer; they use the expert's published rules plus self-consistency.
"""

from __future__ import annotations

import math
import re
from collections import Counter

from .review import decision
from .rules import violations

FEATS = ("has_decision", "agrees_with_majority", "rule_violations", "cites_numbers", "length_50", "expert_phrase")


def features(pack: dict, prompt: str, answer: str, siblings: list[str]) -> list[float]:
    ds = [decision(s) for s in siblings if decision(s)]
    maj = Counter(ds).most_common(1)[0][0] if ds else None
    nums = set(re.findall(r"\d+", prompt))
    expert_terms = [r.pattern for r in pack["rule_objs"] if r.kind == "must_include"]
    return [
        1.0 if decision(answer) else 0.0,
        1.0 if maj and decision(answer) == maj else 0.0,
        float(len(violations(pack, answer, prompt))),
        1.0 if nums & set(re.findall(r"\d+", answer)) else 0.0,
        min(len(answer.split()), 150) / 50,
        1.0 if any(re.search(p, answer, re.I) for p in expert_terms) else 0.0,
    ]


def train(pairs: list[tuple[list[float], list[float]]], epochs: int = 300, lr: float = 0.5, l2: float = 0.01) -> list[float]:
    """Bradley-Terry / DPO-style objective: maximise log sigmoid(w . (chosen - rejected))."""
    w = [0.0] * len(FEATS)
    for _ in range(epochs):
        g = [0.0] * len(w)
        for c, r in pairs:
            diff = [a - b for a, b in zip(c, r, strict=True)]
            z = sum(wi * di for wi, di in zip(w, diff, strict=True))
            s = 1 / (1 + math.exp(-z)) if z > -30 else 0.0
            for j, dj in enumerate(diff):
                g[j] += (1 - s) * dj
        n = max(len(pairs), 1)
        w = [wi + lr * (gi / n - l2 * wi) for wi, gi in zip(w, g, strict=True)]
    return w


def pick(w: list[float], feats: list[list[float]]) -> int:
    scores = [sum(a * b for a, b in zip(w, f, strict=True)) for f in feats]
    return max(range(len(scores)), key=lambda i: (scores[i], -i))
