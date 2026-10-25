"""Classic ML: logistic regression (numpy) for churn risk on synthetic customers, with a model card stub."""

from __future__ import annotations

import numpy as np

from ..platform import Platform

FEATURES = ("tenure_months", "monthly_spend", "support_tickets", "late_payments")


def synth(n: int = 1200, seed: int = 7) -> tuple[np.ndarray, np.ndarray]:
    """SYNTHETIC customers; churn generated from a known logistic rule plus noise."""
    rng = np.random.default_rng(seed)
    tenure = rng.integers(1, 72, n)
    spend = rng.normal(60, 20, n).clip(5)
    tickets = rng.poisson(1.5, n)
    late = rng.poisson(0.5, n)
    z = -1.0 - 0.05 * tenure + 0.01 * spend + 0.6 * tickets + 0.9 * late
    y = (rng.random(n) < 1 / (1 + np.exp(-z))).astype(int)
    return np.c_[tenure, spend, tickets, late].astype(float), y


class Logistic:
    def fit(self, X: np.ndarray, y: np.ndarray, epochs: int = 800, lr: float = 0.1, l2: float = 1e-3):
        self.mu, self.sd = X.mean(0), X.std(0) + 1e-9
        Z = np.c_[np.ones(len(X)), (X - self.mu) / self.sd]
        self.w = np.zeros(Z.shape[1])
        for _ in range(epochs):
            p = 1 / (1 + np.exp(-Z @ self.w))
            self.w -= lr * (Z.T @ (p - y) / len(y) + l2 * self.w)
        return self

    def proba(self, X: np.ndarray) -> np.ndarray:
        Z = np.c_[np.ones(len(X)), (X - self.mu) / self.sd]
        return 1 / (1 + np.exp(-Z @ self.w))


def auc(y: np.ndarray, s: np.ndarray) -> float:
    order = np.argsort(s)
    ranks = np.empty(len(s))
    ranks[order] = np.arange(1, len(s) + 1)
    pos = y == 1
    n1, n0 = pos.sum(), (~pos).sum()
    return float((ranks[pos].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def run(p: Platform, tenant: str = "retail") -> dict:
    with p.job("ml", tenant, model="logistic-churn"):
        X, y = synth()
        cut = int(0.75 * len(y))
        m = Logistic().fit(X[:cut], y[:cut])
        s = m.proba(X[cut:])
        base = float(max(y[cut:].mean(), 1 - y[cut:].mean()))
        acc = float(((s >= 0.5) == y[cut:]).mean())
        return {"auc": round(auc(y[cut:], s), 4), "accuracy": round(acc, 4), "majority_baseline": round(base, 4), "n_test": int(len(y) - cut), "data": "synthetic"}
