# ADR 0001: one OpenAI-compatible gateway for every workload

**Decision.** All model calls go through one gateway that speaks the chat-completions shape.
**Why.** Every open-model server we target (Ollama, vLLM, llama.cpp server) and both closed options already speak it,
so switching models is a config change, and guardrails, audit and cost live in one place.
**Trade-off.** Provider-specific features (structured outputs, tool-call formats) need adapters behind the gateway.
