"""Draw results/evidence_board.png from the results JSON files (needs matplotlib)."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
R = {k: json.loads((ROOT / f"results/{k}.json").read_text()) for k in ("expert_loop", "quant", "router", "offline")}

fig, ax = plt.subplots(2, 2, figsize=(15, 10))
fig.suptitle("360 AI platform - evidence board (measured on CPU; experts SIMULATED; data SYNTHETIC; break-even ESTIMATED)", fontsize=13, weight="bold")

a = ax[0][0]
arms = ["baseline", "taught_prompt", "reranked", "reranked+guard", "decision_tool"]
doms = list(R["expert_loop"]["domains"])
w = 0.16
for i, arm in enumerate(arms):
    vals = [R["expert_loop"]["domains"][d]["accepted_by_expert"][arm] * 100 for d in doms]
    bars = a.bar([j + i * w for j in range(len(doms))], vals, w, label=arm)
    a.bar_label(bars, fmt="%.0f", fontsize=7)
a.set_xticks([j + 2 * w for j in range(len(doms))], doms)
a.set_ylabel("% held-out answers accepted by expert")
a.set_title("Expert feedback loop (simulated experts, real 0.5B model answers)")
a.legend(fontsize=8)
a.set_ylim(0, 110)

a = ax[0][1]
rows = R["quant"]["rows"]
for row in rows:
    a.scatter(row["size_mb"], row["qa_accuracy"] * 100, s=80)
    a.annotate(
        f"{row['model'].split('-')[-1].replace('.gguf', '')}\nppl {row['perplexity']}, {row['decode_tok_s']} tok/s",
        (row["size_mb"], row["qa_accuracy"] * 100),
        fontsize=8,
        xytext=(5, -18),
        textcoords="offset points",
    )
a.set_xlabel("file size (MB)")
a.set_ylabel("QA accuracy % (40 questions)")
a.set_title("Quantization: size vs quality, Qwen2.5-0.5B on CPU")

a = ax[1][0]
sw = R["router"]["sweep"]
a.plot([s["share_small"] * 100 for s in sw], [s["accuracy"] * 100 for s in sw], "o-", label="router sweep")
a.axhline(R["router"]["all_large"]["accuracy"] * 100, ls="--", c="g", label="all large (1.5B)")
a.axhline(R["router"]["all_small"]["accuracy"] * 100, ls="--", c="r", label="all small (0.5B)")
a.set_xlabel("% of requests kept on small model")
a.set_ylabel("accuracy %")
a.set_title(f"Routing between two open models ({R['router']['test_tasks']} held-out tasks)")
a.legend(fontsize=8)

a = ax[1][1]
be = R["offline"]["breakeven_sweep"]
xs = [b["monthly_tokens_m"] for b in be]
a.plot(xs, [b["small_api_usd_month"] for b in be], "o-", label="small closed model $/month")
a.plot(xs, [b["premium_api_usd_month"] for b in be], "o-", label="large closed model $/month")
a.plot(xs, [b["local_usd_per_mtok"] * b["monthly_tokens_m"] for b in be], "s--", label="own server(s), amortised $/month")
for b in be:
    if b["payback_vs_premium_api"]:
        a.annotate(f"pays back m{b['payback_vs_premium_api']}", (b["monthly_tokens_m"], b["premium_api_usd_month"]), fontsize=7)
a.set_xscale("log")
a.set_yscale("log")
a.set_xlabel("million tokens / month")
a.set_ylabel("USD / month")
a.set_title("Break-even (ESTIMATED assumptions)")
a.legend(fontsize=8)

fig.tight_layout()
fig.savefig(ROOT / "results/evidence_board.png", dpi=110)
print("wrote results/evidence_board.png")
