"""Routing policy: privacy first, then a small confidence model, then budget.

1. Privacy: PII in the prompt, or a tenant/domain marked 'restricted', forces an open (self-hosted) model.
2. Confidence: a tiny logistic model scores how likely the cheap open model answers correctly.
   At or above the threshold the open model takes it; below, the request escalates to a closed model.
   Same idea as the small decision router in the enterprise-agent-usecases repo, rebuilt here for model choice.
3. Budget: if the tenant's closed-model budget is spent, stay on open and flag it.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

HARD = re.compile(r"\b(why|explain|compare|analy[sz]e|reason|plan|draft|write|step[- ]by[- ]step|trade-?offs?|summari[sz]e)\b", re.I)
MATH = re.compile(r"\d+\s*[-+*/x]\s*\d+|percent|ratio|interest|compound", re.I)
CODE = re.compile(r"```|def |SELECT |class |regex|json schema", re.I)

FEATURES = ("bias", "words_scaled", "hard_verbs", "math", "code", "multi_question")


def features(prompt: str) -> list[float]:
    words = len(prompt.split())
    return [
        1.0,
        min(words, 200) / 50.0,
        float(len(HARD.findall(prompt))),
        1.0 if MATH.search(prompt) else 0.0,
        1.0 if CODE.search(prompt) else 0.0,
        float(max(0, prompt.count("?") - 1)),
    ]


@dataclass
class ConfidenceModel:
    weights: list[float]

    def score(self, prompt: str) -> float:
        z = sum(w * x for w, x in zip(self.weights, features(prompt), strict=True))
        return 1 / (1 + math.exp(-z))

    @classmethod
    def fit(cls, prompts: list[str], labels: list[int], epochs: int = 400, lr: float = 0.3, l2: float = 0.01) -> ConfidenceModel:
        """labels: 1 if the open model answered correctly. Plain gradient descent, no dependencies."""
        w = [0.0] * len(FEATURES)
        X = [features(p) for p in prompts]
        n = len(X)
        for _ in range(epochs):
            g = [0.0] * len(w)
            for x, y in zip(X, labels, strict=True):
                p = 1 / (1 + math.exp(-sum(a * b for a, b in zip(w, x, strict=True))))
                for j, xj in enumerate(x):
                    g[j] += (p - y) * xj
            w = [wj - lr * (gj / n + l2 * wj) for wj, gj in zip(w, g, strict=True)]
        return cls(w)


DEFAULT = ConfidenceModel([2.0, -0.6, -1.1, -1.4, -1.2, -0.8])


@dataclass
class Decision:
    target: str  # "open" | "closed"
    reason: str
    confidence: float


def decide(prompt: str, *, pii: bool, restricted: bool, model: ConfidenceModel = DEFAULT, threshold: float = 0.6, closed_budget_ok: bool = True) -> Decision:
    c = model.score(prompt)
    if pii or restricted:
        return Decision("open", "privacy: data stays on self-hosted model", c)
    if c >= threshold:
        return Decision("open", f"confidence {c:.2f} >= {threshold}", c)
    if not closed_budget_ok:
        return Decision("open", "closed-model budget spent; degraded to open", c)
    return Decision("closed", f"confidence {c:.2f} < {threshold}; escalate", c)
