"""Regenerate results/offline.json, results/expert_loop.json, the README results block and catalog/agents.json.

python scripts/render_docs.py          write
python scripts/render_docs.py --check  fail if anything differs from a fresh run (CI)
Live files (results/quant.json, results/router.json) come from scripts/bench_*.py on a machine with the models;
they are read here, not regenerated.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from count_tests import count  # noqa: E402

from p360 import breakeven  # noqa: E402
from p360.cli import demo  # noqa: E402
from p360.expert import loop  # noqa: E402

START, END = "<!-- RESULTS:START -->", "<!-- RESULTS:END -->"


def offline() -> dict:
    d = demo()
    return {
        "label": "deterministic offline run (stub models, SYNTHETIC data)",
        "ml": d["ml"],
        "dl": d["dl"],
        "agent": {"low_value": d["agent"], "high_value": d["agent_high_value"]},
        "injection_blocked": d["injection_blocked"],
        "audit_chain_ok": d["audit_chain_ok"],
        "breakeven_sweep": breakeven.sweep(breakeven.Inputs(), [50, 100, 200, 500, 1000, 2000]),
    }


def block(tests: int, off: dict, ex: dict, q: dict, r: dict) -> str:
    L = [START, "", f"**Tests:** {tests} (counted by `scripts/count_tests.py`).", ""]
    L += [
        "### Expert feedback loop (SIMULATED experts, SYNTHETIC tasks, real local model answers)",
        "",
        f"Generator: `{ex['generator']['model']}` via {ex['generator']['runtime']}, {ex['generator']['samples']} samples per task. Share of held-out answers the simulated expert accepts (right decision and every rule kept):",
        "",
        "| domain | test tasks | pairs | baseline | taught prompt | reranked | reranked + guard | decision tool + guard |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for d, v in ex["domains"].items():
        a = v["accepted_by_expert"]
        L.append(f"| {d} | {v['test_tasks']} | {v['preference_pairs']} | {a['baseline']:.0%} | {a['taught_prompt']:.0%} | {a['reranked']:.0%} | {a['reranked+guard']:.0%} | {a['decision_tool']:.0%} |")
    L += ["", "Rule violations on held-out answers:", "", "| domain | baseline | taught prompt | reranked | reranked + guard | decision tool + guard |", "|---|---|---|---|---|---|"]
    for d, v in ex["domains"].items():
        b = v["rule_violations"]
        L.append(f"| {d} | {b['baseline']} | {b['taught_prompt']} | {b['reranked']} | {b['reranked+guard']} | {b['decision_tool']} |")
    L += [
        "",
        "### Quantization on CPU (MEASURED, 40-question self-written regression set)",
        "",
        "| file | size MB | QA accuracy | agrees with fp16 | perplexity | decode tok/s |",
        "|---|---|---|---|---|---|",
    ]
    for row in q["rows"]:
        L.append(f"| {row['model']} | {row['size_mb']} | {row['qa_accuracy']:.0%} | {row['agree_with_fp16']:.0%} | {row['perplexity']} | {row['decode_tok_s']} |")
    L += [
        "",
        f"### Routing between two open models on CPU (MEASURED, {r['test_tasks']} held-out tasks; closed provider wired, not run)",
        "",
        f"All small (`{r['small']}`): {r['all_small']['accuracy']:.0%} in {r['all_small']['cpu_seconds']} s. All large (`{r['large']}`): {r['all_large']['accuracy']:.0%} in {r['all_large']['cpu_seconds']} s. Best possible per-task pick: {r['oracle']['accuracy']:.0%}.",
        "",
        "| threshold | share to small | accuracy | CPU seconds |",
        "|---|---|---|---|",
    ]
    for s in r["sweep"]:
        L.append(f"| {s['threshold']} | {s['share_small']:.0%} | {s['accuracy']:.0%} | {s['cpu_seconds']} |")
    L += [
        "",
        "### Break-even (ESTIMATED from editable assumptions in `src/p360/breakeven.py`)",
        "",
        "| tokens / month (M) | servers | local $/1M tok | small API $/month | payback vs small API | large API $/month | payback vs large API |",
        "|---|---|---|---|---|---|---|",
    ]
    for s in off["breakeven_sweep"]:
        pb = lambda m: f"month {m}" if m else "never (36 mo)"  # noqa: E731
        L.append(
            f"| {s['monthly_tokens_m']:g} | {s['servers']} | {s['local_usd_per_mtok']} | {s['small_api_usd_month']} | {pb(s['payback_vs_small_api'])} | {s['premium_api_usd_month']} | {pb(s['payback_vs_premium_api'])} |"
        )
    L += [
        "",
        "### Classic ML and DL (SYNTHETIC data, offline)",
        "",
        f"Churn logistic regression AUC {off['ml']['auc']} (accuracy {off['ml']['accuracy']} vs majority baseline {off['ml']['majority_baseline']}, n={off['ml']['n_test']}). "
        f"Anomaly MLP accuracy {off['dl']['mlp_accuracy']} vs linear {off['dl']['linear_accuracy']} (n={off['dl']['n_test']}).",
        "",
        END,
    ]
    return "\n".join(L)


def catalog(ex: dict, tests: int) -> dict:
    base = "https://github.com/jagadishmazure-jpg/Jagadish-360-ai-platform"
    cards = [
        (
            "model-gateway",
            "Model gateway (closed + open)",
            "Advanced",
            "Python stdlib, OpenAI-compatible API",
            "Cross-industry",
            ["routing", "privacy", "cost"],
            "One API that routes between self-hosted open models and closed models by privacy, confidence and budget.",
            ["PII redaction in and out", "injection screen", "per-tenant budgets", "circuit breaker", "hash-chained audit"],
        ),
        (
            "expert-loop",
            "Domain expert feedback loop",
            "Advanced",
            "Preference pairs + reranker on a local open model",
            "Retail, Healthcare, Finance",
            ["rlhf-lite", "guardrails", "domain-experts"],
            "Experts write rules and review answers; their corrections become preference pairs that train a reranker.",
            ["expert rules as output guard", "reasons required on fix/reject", "reviews redacted before storage"],
        ),
        (
            "breakeven",
            "Self-hosting break-even calculator",
            "Beginner",
            "Python",
            "Small business",
            ["finops", "on-prem", "gpu"],
            "Compares a one-time inference server with monthly per-token spend and finds the payback month.",
            ["every assumption sourced and labelled estimated"],
        ),
    ]
    return {
        "repo": base,
        "schema": "agent-card/v1",
        "agents": [
            {
                "name": n,
                "title": t,
                "level": lv,
                "tech": tech,
                "industry": ind,
                "tags": tags,
                "summary": s,
                "guardrails": g,
                "run": "p360 demo" if n == "model-gateway" else f"p360 {n}",
                "page": f"{base}#readme",
                "data": "synthetic",
                "tests": tests,
            }
            for n, t, lv, tech, ind, tags, s, g in cards
        ],
    }


def main(check: bool) -> int:
    tests = count()
    off = offline()
    ex = loop.run()
    q = json.loads((ROOT / "results/quant.json").read_text())
    r = json.loads((ROOT / "results/router.json").read_text())
    files = {
        ROOT / "results/offline.json": json.dumps(off, indent=1) + "\n",
        ROOT / "results/expert_loop.json": json.dumps(ex, indent=1) + "\n",
        ROOT / "catalog/agents.json": json.dumps(catalog(ex, tests), indent=1) + "\n",
    }
    readme = (ROOT / "README.md").read_text()
    files[ROOT / "README.md"] = re.sub(re.escape(START) + ".*?" + re.escape(END), lambda _: block(tests, off, ex, q, r), readme, flags=re.S)
    bad = []
    for p, txt in files.items():
        if check:
            if not p.exists() or p.read_text() != txt:
                bad.append(str(p.relative_to(ROOT)))
        else:
            p.write_text(txt)
    if bad:
        print("out of date (run python scripts/render_docs.py):", ", ".join(bad))
        return 1
    print(f"docs {'match' if check else 'written'}; tests: {tests}")
    return 0


if __name__ == "__main__":
    sys.exit(main("--check" in sys.argv))
