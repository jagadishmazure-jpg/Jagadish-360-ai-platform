# Guardrails and security controls

| control | where | tested in |
|---|---|---|
| Prompt-injection screen (7 patterns) before any model call | `guardrails.injection`, gateway, agent | `test_guardrails.py`, `test_gateway.py`, `test_workloads.py` |
| PII redaction in and out (email, phone, SSN, Luhn-valid card, record number, API key) | `guardrails.redact`, gateway | `test_guardrails.py`, `test_gateway.py` |
| Keyed HMAC pseudonyms, key from `P360_PSEUDO_KEY`; rotate by changing the key (old tokens stop matching) | `guardrails.pseudonym` | `test_guardrails.py` |
| Redacting log filter, also rewrites exception text | `RedactingFilter` | `test_log_filter_redacts_message_and_exception` |
| Safe error strings (type + redacted, truncated message) | `safe_error`, server | `test_safe_error_redacts`, `test_http_bad_body` |
| Privacy routing: PII or restricted tenant never leaves self-hosted | `router.decide` | `test_pii_forces_open_and_is_redacted`, `test_restricted_tenant_stays_open` |
| Per-tenant closed-model budget, global call cap | `cost.Budget`, `OpenAICompatBackend.max_calls` | `test_budget_exhausted_degrades_to_open`, `test_call_cap` |
| Circuit breaker, retries with backoff, fallback | `backends`, gateway | `test_breaker_opens_and_half_opens`, `test_fallback_when_closed_fails` |
| Hash-chained audit trail, strings redacted before writing | `audit.AuditLog` | `test_audit_cost.py` |
| Least-privilege agent tools, human approval above a limit | `workloads/agent.py` | `test_workloads.py` |
| RAG abstains when retrieval is weak | `workloads/rag.py` | `test_rag_cites_and_abstains` |
| Small-cell suppression in analytics (k=10) | `workloads/analytics.py` | `test_analytics_suppression` |
| Expert rules as tests and output guard; reviews redacted before storage | `expert/` | `test_expert.py` |
| HTTP: bearer token (constant-time compare), 64 KB body cap, generic 4xx/5xx bodies | `server.py` | `test_http_*` |
| No keys in config or image; keys only from env / Kubernetes Secrets synced from the cloud key store | `config/`, Helm | `test_example_config_parses`, gitleaks in CI |
| Pods: non-root, read-only root FS, all capabilities dropped, no service-account token; model server reachable only from the gateway | `deploy/helm` | `helm lint` + render in CI |
| Brand check (hashed blocklist), gitleaks over full history, CodeQL, Dependabot | `.github/` | CI |
