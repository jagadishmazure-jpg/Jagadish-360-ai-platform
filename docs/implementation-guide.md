# Implementation guide (for adopters)

## 0. Decide the hosting mix with the break-even calculator
```bash
p360 breakeven --tokens-m 300 --server-usd 9000                  # vs a small closed model
p360 breakeven --tokens-m 300 --api-usd-per-mtok 4.375           # vs a larger closed model
```
Replace every default in `src/p360/breakeven.py` (`ASSUMPTIONS` lists the source of each) with the customer's quote,
tariff and your own throughput benchmark. The measured CPU numbers in this repo are not GPU numbers.

## 1. Run offline
```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest -q && p360 demo
```

## 2. Run a real open model on CPU
```bash
pip install -e ".[local]"
# download a GGUF file, e.g. Qwen2.5-0.5B-Instruct q4_k_m (about 470 MB)
cp config/gateway.example.json config/gateway.json   # set open.model_path
p360 serve --config config/gateway.json
curl -s localhost:8360/v1/chat/completions -d '{"model":"auto","messages":[{"role":"user","content":"Capital of France?"}]}'
```
Or use Ollama: switch `open` to the `ollama-local` entry.

## 3. Add a closed model (optional, billable)
Put the key in the environment only: `export AZURE_OPENAI_API_KEY=...` (the variable name is shared by the
OpenAI and Azure OpenAI entries). Keep `max_calls` and the tenant budgets set. For Azure OpenAI, use the
`azure-openai` entry with your resource URL, deployment name and API version.

## 4. Deploy
```bash
docker build -t p360-gateway:0.1.0 .
helm upgrade --install p360 deploy/helm/p360 -f deploy/profiles/onprem-cpu.yaml   # or azure / aws / gcp / onprem-gpu
```
Create the `p360-gateway-token` Secret first (from the cloud key store via the CSI driver or External Secrets).
The Terraform in `deploy/terraform/<cloud>` and `deploy/bicep` is a starting point that is validated, not applied:
review networking, node sizes and quotas, and price it before `apply`.

## 5. Onboard domains
Follow `docs/domain-onboarding-playbook.md`.

## 6. Operate
- Watch the audit trail (`verify()` daily) and the cost ledger per tenant.
- Re-run `scripts/bench_router.py` when you change models; refit the router threshold.
- Rotate `P360_PSEUDO_KEY` and the gateway token on a schedule.
