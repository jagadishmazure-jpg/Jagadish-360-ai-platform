"""The model gateway: one entry point for every workload.

Pipeline per request: injection screen -> PII redaction (input) -> route -> call with fallback -> PII redaction
(output) -> cost ledger -> audit entry. The closed model only ever sees redacted text.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from .audit import AuditLog
from .backends import Backend, BackendError, Completion
from .cost import Budget, CostLedger
from .guardrails import get_logger, injection, redact, safe_error
from .router import DEFAULT, ConfidenceModel, decide

log = get_logger("p360.gateway")


@dataclass
class Tenant:
    name: str
    restricted: bool = False  # e.g. a healthcare tenant: never leave self-hosted
    closed_budget_usd: float = 1.0


@dataclass
class Result:
    ok: bool
    text: str
    model: str = ""
    route: str = ""
    reason: str = ""
    cost_usd: float = 0.0
    pii_in: list[str] = field(default_factory=list)
    blocked: str | None = None
    latency_s: float = 0.0


class Gateway:
    def __init__(
        self,
        open_backend: Backend,
        closed_backend: Backend | None = None,
        *,
        audit: AuditLog | None = None,
        ledger: CostLedger | None = None,
        router: ConfidenceModel = DEFAULT,
        threshold: float = 0.6,
    ):
        self.open, self.closed = open_backend, closed_backend
        self.audit = audit or AuditLog()
        self.ledger = ledger or CostLedger()
        self.router, self.threshold = router, threshold
        self.tenants: dict[str, Tenant] = {}
        self.budgets: dict[str, Budget] = {}

    def tenant(self, name: str) -> Tenant:
        if name not in self.tenants:
            self.tenants[name] = Tenant(name)
        t = self.tenants[name]
        self.budgets.setdefault(name, Budget(t.closed_budget_usd))
        return t

    def add_tenant(self, t: Tenant) -> None:
        self.tenants[t.name] = t
        self.budgets[t.name] = Budget(t.closed_budget_usd)

    def chat(self, messages: list[dict], *, tenant: str = "default", workload: str = "chat", max_tokens: int = 256, force: str | None = None) -> Result:
        t0 = time.perf_counter()
        t = self.tenant(tenant)
        user_text = "\n".join(m["content"] for m in messages if m["role"] == "user")
        hit = injection(user_text)
        if hit:
            self.audit.append("blocked", tenant=tenant, workload=workload, rule="prompt_injection")
            return Result(False, "Request blocked by the input guard.", blocked="prompt_injection")
        red_msgs, pii = [], []
        for m in messages:
            r = redact(m["content"])
            pii += r.findings
            red_msgs.append({"role": m["role"], "content": r.text})
        budget = self.budgets[tenant]
        d = decide(user_text, pii=bool(pii), restricted=t.restricted, model=self.router, threshold=self.threshold, closed_budget_ok=budget.allow(0.001) and self.closed is not None)
        route = force or d.target
        order = [self.closed, self.open] if route == "closed" else [self.open]
        comp: Completion | None = None
        used = None
        for b in order:
            if b is None or b.breaker.open:
                continue
            try:
                comp = b.complete(red_msgs, max_tokens=max_tokens)
                b.breaker.success()
                used = b
                break
            except BackendError as e:
                b.breaker.failure()
                log.warning("backend %s failed: %s", b.name, safe_error(e))
        if comp is None:
            self.audit.append("error", tenant=tenant, workload=workload, route=route)
            return Result(False, "No model available right now.", route=route, reason=d.reason, pii_in=pii)
        out = redact(comp.text)
        model_key = comp.model if used.kind == "closed" else "local"
        usd = self.ledger.record(tenant, model_key, comp.tokens_in, comp.tokens_out)
        if used.kind == "closed":
            budget.spent_usd += usd
        self.audit.append(
            "completion",
            tenant=tenant,
            workload=workload,
            model=used.name,
            route=route,
            reason=d.reason,
            confidence=round(d.confidence, 3),
            tokens_in=comp.tokens_in,
            tokens_out=comp.tokens_out,
            cost_usd=round(usd, 8),
            pii_in=len(pii),
            pii_out=len(out.findings),
        )
        return Result(True, out.text, used.name, "closed" if used.kind == "closed" else "open", d.reason, usd, pii, None, time.perf_counter() - t0)
