"""Shared platform context handed to every workload."""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field

from .audit import AuditLog
from .backends import StubBackend
from .cost import CostLedger
from .gateway import Gateway

# Compute cost for non-LLM workloads: ESTIMATED CPU price per vCPU-second (a mid-range cloud vCPU-hour / 3600).
CPU_USD_PER_SECOND = 0.04 / 3600


@dataclass
class Platform:
    gateway: Gateway
    compute_usd: dict[str, float] = field(default_factory=dict)

    @property
    def audit(self) -> AuditLog:
        return self.gateway.audit

    @property
    def ledger(self) -> CostLedger:
        return self.gateway.ledger

    @contextmanager
    def job(self, workload: str, tenant: str, **meta):
        t0 = time.perf_counter()
        self.audit.append("job_start", workload=workload, tenant=tenant, **meta)
        try:
            yield
        finally:
            dt = time.perf_counter() - t0
            usd = dt * CPU_USD_PER_SECOND
            self.compute_usd[workload] = self.compute_usd.get(workload, 0.0) + usd
            self.audit.append("job_end", workload=workload, tenant=tenant, seconds=round(dt, 4), cost_usd=round(usd, 9))


def offline_platform(answers: dict[str, str] | None = None) -> Platform:
    open_b = StubBackend("open-stub", "open", 0.6, answers=answers or {})
    closed_b = StubBackend("closed-stub", "closed", 0.9, answers=answers or {})
    return Platform(Gateway(open_b, closed_b))
