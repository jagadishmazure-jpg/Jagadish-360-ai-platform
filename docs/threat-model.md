# Threat model (STRIDE + OWASP LLM Top 10)

| threat | example | control | residual risk |
|---|---|---|---|
| Spoofing | caller pretends to be another tenant | bearer token at the gateway; in a cluster, put the gateway behind the org's identity-aware proxy | tenant is a request field today; bind it to the token in production (planned) |
| Tampering | someone edits the audit file | SHA-256 chain, `verify()` | an attacker who rewrites the whole chain; ship entries to write-once storage (planned) |
| Repudiation | "the model said it, not us" | every completion audited with route, reason and model | none beyond the above |
| Information disclosure | PII sent to a closed model; secrets in logs | redaction before routing, privacy routing, redacting log filter, safe errors | regex PII detection misses free-text identifiers such as names |
| Denial of service | huge bodies, retry storms | 64 KB cap, circuit breaker, call cap, budgets | no rate limiter per tenant yet (planned) |
| Elevation of privilege | agent issues a large refund | tool allow-list, approval over the limit | approver identity is a callback in the demo |
| LLM01 prompt injection | "ignore previous instructions" | pattern screen in gateway and agent | paraphrased attacks can pass a pattern screen; tests list the covered forms |
| LLM02 sensitive output | model repeats an account number | output redaction + expert must-not rules | as above |
| LLM03 supply chain | poisoned model weights | pin model files by name and checksum, pull from a mirror; image pinned by digest | checksums are not enforced in code yet (planned) |
| LLM04 data poisoning | bad expert reviews | reasons required, reviewer recorded, pairs reviewable before training | a single bad reviewer is not detected automatically |
| LLM06 excessive agency | agent writes without checks | least-privilege tools, approval gate | |
| LLM10 unbounded consumption | runaway spend | budgets, caps, cost ledger | |
