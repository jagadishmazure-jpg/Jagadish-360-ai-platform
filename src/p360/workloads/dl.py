"""Deep learning: a two-hidden-layer MLP in numpy (manual backprop) that flags anomalous transactions.

SYNTHETIC data: normal transactions from one distribution, anomalies on a curved boundary a linear model misses.
"""

from __future__ import annotations

import numpy as np

from ..platform import Platform


def synth(n: int = 2000, seed: int = 11):
    rng = np.random.default_rng(seed)
    X = rng.normal(0, 1, (n, 4))
    r = np.sqrt(X[:, 0] ** 2 + X[:, 1] ** 2)
    y = ((r > 1.6) | (X[:, 2] * X[:, 3] > 1.2)).astype(float)
    return X, y


class MLP:
    def __init__(self, d: int, h: int = 16, seed: int = 0):
        g = np.random.default_rng(seed)
        self.W1, self.b1 = g.normal(0, 0.5, (d, h)), np.zeros(h)
        self.W2, self.b2 = g.normal(0, 0.5, (h, h)), np.zeros(h)
        self.W3, self.b3 = g.normal(0, 0.5, (h, 1)), np.zeros(1)

    def forward(self, X):
        self.h1 = np.tanh(X @ self.W1 + self.b1)
        self.h2 = np.tanh(self.h1 @ self.W2 + self.b2)
        return 1 / (1 + np.exp(-(self.h2 @ self.W3 + self.b3).ravel()))

    def fit(self, X, y, epochs: int = 600, lr: float = 0.5):
        n = len(y)
        for _ in range(epochs):
            p = self.forward(X)
            d3 = ((p - y) / n)[:, None]
            gW3, gb3 = self.h2.T @ d3, d3.sum(0)
            d2 = (d3 @ self.W3.T) * (1 - self.h2**2)
            gW2, gb2 = self.h1.T @ d2, d2.sum(0)
            d1 = (d2 @ self.W2.T) * (1 - self.h1**2)
            gW1, gb1 = X.T @ d1, d1.sum(0)
            for w, g in ((self.W1, gW1), (self.b1, gb1), (self.W2, gW2), (self.b2, gb2), (self.W3, gW3), (self.b3, gb3)):
                w -= lr * g
        return self


def run(p: Platform, tenant: str = "finance") -> dict:
    from .ml import Logistic

    with p.job("dl", tenant, model="mlp-anomaly"):
        X, y = synth()
        cut = 1500
        mlp = MLP(4).fit(X[:cut], y[:cut])
        acc = float(((mlp.forward(X[cut:]) >= 0.5) == y[cut:]).mean())
        lin = Logistic().fit(X[:cut], y[:cut])
        lin_acc = float(((lin.proba(X[cut:]) >= 0.5) == y[cut:]).mean())
        return {"mlp_accuracy": round(acc, 4), "linear_accuracy": round(lin_acc, 4), "n_test": len(y) - cut, "data": "synthetic"}
