"""Agent: a tool-using refund/claims assistant with least-privilege tools and a human-approval gate.

The planner is rule-based so it is deterministic; the gateway drafts the customer message.
Tools are allow-listed per tenant; anything over the auto-approve limit waits for a person.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..guardrails import injection
from ..platform import Platform

ORDERS = {"A1001": {"amount": 42.0, "status": "delivered"}, "A1002": {"amount": 640.0, "status": "delivered"}, "A1003": {"amount": 18.5, "status": "in_transit"}}
TOOLS = {"lookup_order": "read", "issue_refund": "write", "draft_message": "read"}


@dataclass
class AgentRun:
    steps: list[str] = field(default_factory=list)
    outcome: str = ""
    needs_approval: bool = False
    message: str = ""


def refund_agent(
    p: Platform, order_id: str, reason: str, *, tenant: str = "retail", auto_limit: float = 100.0, allowed: tuple[str, ...] = ("lookup_order", "issue_refund", "draft_message"), approver=None
) -> AgentRun:
    run = AgentRun()
    with p.job("agent", tenant, agent="refund"):
        if injection(reason):
            run.outcome = "blocked: prompt injection in customer text"
            p.audit.append("blocked", workload="agent", rule="prompt_injection")
            return run
        if "lookup_order" not in allowed:
            run.outcome = "denied: tool not allowed"
            return run
        run.steps.append("lookup_order")
        order = ORDERS.get(order_id)
        if order is None:
            run.outcome = "no such order"
            return run
        if order["status"] != "delivered":
            run.outcome = "not eligible: not delivered yet"
            return run
        if "issue_refund" not in allowed:
            run.outcome = "denied: tool not allowed"
            return run
        if order["amount"] > auto_limit:
            run.needs_approval = True
            decision = approver(order_id, order["amount"]) if approver else False
            p.audit.append("approval", workload="agent", order=order_id, amount=order["amount"], approved=bool(decision))
            if not decision:
                run.outcome = "waiting for human approval"
                return run
        run.steps.append("issue_refund")
        p.audit.append("tool_write", workload="agent", tool="issue_refund", order=order_id, amount=order["amount"])
        run.steps.append("draft_message")
        r = p.gateway.chat([{"role": "user", "content": f"Write two sentences confirming a refund of {order['amount']:.2f} for order {order_id}."}], tenant=tenant, workload="agent", max_tokens=80)
        run.message = r.text
        run.outcome = "refunded"
        return run
