# How it works, step by step

## 1. A request comes in
Any workload (or any OpenAI-compatible client pointed at `p360 serve`) sends chat messages plus a tenant name.

## 2. Input guard
`guardrails.injection()` screens the user text for common override phrasing. A hit is refused with a fixed
message and an audit entry; the model never sees it. `guardrails.redact()` then replaces emails, phone numbers,
SSNs, card numbers (only when the Luhn checksum passes), record numbers and API keys. With `P360_PSEUDO_KEY` set,
each value becomes a stable keyed token such as `[EMAIL:3f9a0c1d2e]`, so joins still work without the raw value.

## 3. Routing
`router.decide()` applies three checks in order:
1. **Privacy.** PII found, or a tenant marked `restricted` (the healthcare tenant in the example config), keeps the
   request on a self-hosted open model.
2. **Confidence.** A tiny logistic model scores how likely the cheap open model gets it right, from six features
   (length, reasoning verbs, arithmetic, code, number of questions). At or above the threshold the open model takes it.
3. **Budget.** Below the threshold the request escalates to a closed model, unless the tenant's closed-model budget
   is spent, in which case it stays on open and the reason says so.

`scripts/bench_router.py` fits the confidence model on real outcomes from two local models.

## 4. Calling the model
Backends share one shape. Remote calls retry 429/5xx with exponential backoff, a circuit breaker opens after three
straight failures, and a hard call cap protects spend. A closed-route request falls back to the open model if the
closed one is down. Plain-HTTP endpoints are refused unless they are local or in-cluster service names.

## 5. Output guard, cost, audit
The answer is redacted again, the cost ledger records tokens and dollars per tenant and model, and the audit trail
appends a hash-chained entry (route, reason, confidence, tokens, cost, how many PII items were removed in and out).

## 6. The expert feedback loop
1. **Experts write rules** in `data/domains/<domain>/rules.json`: things that must never appear, things that must
   appear when a trigger is present, the reason, plain instructions, and standard wording. Edge cases in the same
   file become pytest cases automatically (`tests/test_expert.py`).
2. **The open model answers** each task twice: plain, and "taught" (expert instructions plus the facts their policy
   checker computes, never the final answer). It also draws several samples of the taught answer.
3. **Experts review** each answer: approve, fix (with the corrected answer) or reject, always with a reason.
   `p360 review` is the human CLI; `SimulatedExpert` produces the same records for the demo.
4. **Corrections become preference pairs** (approved or fixed answer preferred over each rejected one).
5. **A reranker learns** from the pairs with a Bradley-Terry objective, the same loss shape as DPO but over six
   answer features instead of model weights. It picks the best sample for new tasks.
6. **The rules also run as an output guard**: a forbidden phrase means a safe hand-off, a missing required phrase gets
   the expert's standard wording appended.
7. **Measured per domain** on held-out tasks (see README results).

## 7. Break-even
`breakeven.report()` compares one server's price plus power and support against monthly per-token spend, adds
servers when volume exceeds one server's capacity, and returns the payback month or "never" within 36 months.
