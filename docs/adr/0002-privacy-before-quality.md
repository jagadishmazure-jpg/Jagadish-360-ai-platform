# ADR 0002: privacy is checked before quality when routing

**Decision.** PII or a restricted tenant forces a self-hosted model even when the router would escalate.
**Why.** A regulated customer's first question is where data goes. Quality loss is measurable and fixable (expert loop,
larger open model); a leak is not reversible.
**Trade-off.** Restricted tenants get open-model quality only, so they need a bigger self-hosted model.
