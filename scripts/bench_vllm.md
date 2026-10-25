# Benchmarking a GPU server (not run in this repo)

The build machine has no GPU, so the break-even default `tokens_per_s` is an estimate. Before quoting a customer:

1. Deploy `deploy/profiles/onprem-gpu.yaml` (vLLM, one GPU).
2. Run vLLM's own serving benchmark against the endpoint with a prompt mix that looks like the customer's traffic,
   at several concurrency levels.
3. Take the aggregate output tokens per second at the latency target you promise, and put it in `Inputs.tokens_per_s`.
4. Measure wall power under that load and put it in `Inputs.server_watts`.
