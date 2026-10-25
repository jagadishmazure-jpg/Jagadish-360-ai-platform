# ADR 0003: learn from experts with a reranker first, weight tuning later

**Decision.** Expert preference pairs first train a small reranker over sampled answers; DPO/LoRA on model weights is planned.
**Why.** It runs on a CPU in seconds, is easy to inspect (six weights), and needs few pairs. Weight tuning needs a GPU
and more data, and its gains are harder to attribute.
**Trade-off.** A reranker can only choose among answers the model already produces. The measured results show exactly
that limit: when every sample has the wrong decision, reranking cannot help, and the expert's decision tool is needed.
