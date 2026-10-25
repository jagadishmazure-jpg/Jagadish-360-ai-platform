# ADR 0004: measure on CPU, estimate GPU

**Decision.** Every quality and speed number in the README comes from CPU runs on the build machine. GPU throughput,
power and price are estimates with sources, used only in the break-even calculator.
**Why.** The build machine has no GPU and nothing billable is created. Mixing measured and estimated numbers without
labels would mislead.
