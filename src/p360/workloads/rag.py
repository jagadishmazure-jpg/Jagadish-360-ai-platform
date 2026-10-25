"""GenAI/RAG: BM25 retrieval over a small synthetic policy corpus, then a grounded answer through the gateway.

Abstains when the best passage scores below a floor, and returns passage ids as citations.
"""

from __future__ import annotations

import math
import re
from collections import Counter

from ..guardrails import redact
from ..platform import Platform

TOK = re.compile(r"[a-z0-9]+")


def tokens(s: str) -> list[str]:
    return TOK.findall(s.lower())


class BM25:
    def __init__(self, docs: dict[str, str], k1: float = 1.4, b: float = 0.75):
        self.ids = list(docs)
        self.toks = [tokens(docs[i]) for i in self.ids]
        self.docs = docs
        self.k1, self.b = k1, b
        self.avg = sum(map(len, self.toks)) / max(len(self.toks), 1)
        df = Counter(t for d in self.toks for t in set(d))
        n = len(self.toks)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def search(self, q: str, k: int = 3) -> list[tuple[str, float]]:
        qt = tokens(q)
        scores = []
        for i, d in zip(self.ids, self.toks, strict=True):
            tf = Counter(d)
            s = sum(self.idf.get(t, 0) * tf[t] * (self.k1 + 1) / (tf[t] + self.k1 * (1 - self.b + self.b * len(d) / self.avg)) for t in qt if t in tf)
            scores.append((i, s))
        return sorted(scores, key=lambda x: -x[1])[:k]


def answer(p: Platform, index: BM25, question: str, tenant: str = "default", floor: float = 1.0) -> dict:
    with p.job("rag", tenant):
        hits = index.search(redact(question).text)
        if not hits or hits[0][1] < floor:
            return {"answer": "I can't find that in the provided documents.", "citations": [], "abstained": True}
        ctx = "\n".join(f"[{i}] {index.docs[i]}" for i, _ in hits)
        msgs = [
            {"role": "system", "content": "Answer only from the passages. Cite passage ids in brackets. If the passages do not cover it, say so."},
            {"role": "user", "content": f"Passages:\n{ctx}\n\nQuestion: {question}"},
        ]
        r = p.gateway.chat(msgs, tenant=tenant, workload="rag", max_tokens=160)
        return {"answer": r.text, "citations": [i for i, _ in hits], "abstained": False, "route": r.route, "ok": r.ok}
