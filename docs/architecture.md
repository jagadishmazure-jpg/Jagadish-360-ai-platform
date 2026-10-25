# Architecture

```mermaid
flowchart LR
    subgraph Apps["Workloads (one platform context)"]
        AG[Agents<br/>tools + approvals]
        RG[GenAI / RAG<br/>BM25 + citations]
        ML[Classic ML<br/>churn model]
        DL[Deep learning<br/>anomaly MLP]
        AN[Analytics<br/>small-cell suppression]
    end
    subgraph Shared["Shared controls"]
        GR[Guardrails<br/>injection screen, PII redaction,<br/>redacting logs + errors]
        AU[(Hash-chained<br/>audit trail)]
        CO[Cost ledger<br/>per tenant / model]
    end
    subgraph GW["Model gateway (OpenAI-compatible API)"]
        RT{Router<br/>1 privacy<br/>2 confidence<br/>3 budget}
        CB[Retries, backoff,<br/>circuit breakers, call caps]
    end
    subgraph Open["Open models (self-hosted)"]
        LC[llama.cpp on CPU<br/>measured here]
        OL[Ollama on CPU]
        VL[vLLM on one NVIDIA GPU<br/>config only]
    end
    subgraph Closed["Closed models"]
        OA[OpenAI gpt-4o-mini<br/>wired, not run]
        AZ[Azure OpenAI<br/>config option]
    end
    subgraph Expert["Expert feedback loop"]
        RU[Expert rules<br/>-> guard + tests]
        RV[Review: approve / fix / reject<br/>with reasons]
        PP[(Preference pairs)]
        RK[Reranker<br/>Bradley-Terry]
    end
    Apps --> GR --> RT
    RT -->|PII, restricted tenant,<br/>high confidence| Open
    RT -->|low confidence, budget left| Closed
    RT --- CB
    GW --> AU
    GW --> CO
    Open --> RV
    RU --> GR
    RV --> PP --> RK --> RT
```

## Deployment view

```mermaid
flowchart TB
    GH[GitHub Actions<br/>lint, tests, doc drift, gitleaks,<br/>terraform validate, bicep build, helm lint] --> IMG[Gateway image<br/>non-root, no weights, no keys]
    IMG --> HELM[Helm chart deploy/helm/p360]
    HELM --> AZ[Azure profile<br/>AKS + GPU pool + secret store]
    HELM --> AWS[AWS profile<br/>EKS + GPU node group + KMS]
    HELM --> GCP[GCP profile<br/>GKE + GPU pool + Workload Identity]
    HELM --> OP[On-prem profiles<br/>one GPU server or CPU box]
```

The same chart deploys everywhere; a profile file only changes the inference engine, node placement and
where secrets come from. Terraform for each cloud and Bicep for Azure are validated in CI and never applied.

## Components and files

| component | file | notes |
|---|---|---|
| Guardrails | `src/p360/guardrails.py` | patterns + Luhn checksum, keyed HMAC pseudonyms, log filter, safe errors |
| Audit trail | `src/p360/audit.py` | SHA-256 chain; `verify()` detects edits |
| Cost ledger | `src/p360/cost.py` | list prices with an as-of date; local cost from the break-even model |
| Backends | `src/p360/backends.py` | OpenAI, Azure OpenAI, Ollama, vLLM (one HTTP client), llama.cpp in-process, offline stub |
| Router | `src/p360/router.py` | privacy rule, then a 6-feature logistic confidence model, then budget |
| Gateway + HTTP | `src/p360/gateway.py`, `server.py` | bearer token, 64 KB body cap, generic errors |
| Workloads | `src/p360/workloads/` | agent, rag, ml, dl, analytics |
| Break-even | `src/p360/breakeven.py` | every assumption has a source note |
| Expert loop | `src/p360/expert/` | rules, tasks, review, tune, loop |
| Deploy | `Dockerfile`, `deploy/` | Helm, 5 profiles, Terraform x3, Bicep |
