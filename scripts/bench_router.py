"""LIVE: routing between a small and a larger open model, both on CPU via llama.cpp.

The closed provider (OpenAI / Azure OpenAI) is wired in the gateway but NOT RUN here: the available key had no
quota. A larger open model (1.5B) stands in as the escalation tier, so every number below is a real measurement.

python scripts/bench_router.py --small <0.5b.gguf> --large <1.5b.gguf>   -> results/router.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from p360.expert.review import decision  # noqa: E402
from p360.expert.rules import DOMAINS  # noqa: E402
from p360.expert.tasks import BASE_SYSTEM, as_dicts, make  # noqa: E402
from p360.router import ConfidenceModel  # noqa: E402


def tasks() -> list[dict]:
    qa = json.loads((ROOT / "data/bench/qa.json").read_text())
    out = [{"prompt": q, "gold": g, "kind": "qa"} for q, g in qa]
    for d in DOMAINS:
        out += [{"prompt": t["prompt"], "expected": t["expected"], "kind": d} for t in as_dicts(make(d, 20, seed=777))]
    return out


def correct(t: dict, ans: str) -> bool:
    if t["kind"] == "qa":
        return any(g in ans.lower() for g in t["gold"])
    return decision(ans) == t["expected"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--small", required=True)
    ap.add_argument("--large", required=True)
    a = ap.parse_args()
    from llama_cpp import Llama

    ts = tasks()
    res = {}
    for tag, path in (("small", a.small), ("large", a.large)):
        llm = Llama(path, n_ctx=1024, verbose=False, seed=0)
        for t in ts:
            sys_p = "Answer in a few words." if t["kind"] == "qa" else BASE_SYSTEM
            t0 = time.time()
            r = llm.create_chat_completion(messages=[{"role": "system", "content": sys_p}, {"role": "user", "content": t["prompt"]}], max_tokens=40, temperature=0.0, seed=0)
            t[f"{tag}_ok"] = correct(t, r["choices"][0]["message"]["content"] or "")
            t[f"{tag}_s"] = time.time() - t0
        res[tag] = Path(path).name
        del llm
    # alternate split so both halves mix task kinds
    tr, te = ts[0::2], ts[1::2]
    model = ConfidenceModel.fit([t["prompt"] for t in tr], [int(t["small_ok"]) for t in tr])
    sweep = []
    for th in (0.3, 0.4, 0.5, 0.6, 0.7, 0.8):
        small = [model.score(t["prompt"]) >= th for t in te]
        acc = sum((t["small_ok"] if s else t["large_ok"]) for t, s in zip(te, small, strict=True)) / len(te)
        sec = sum((t["small_s"] if s else t["small_s"] * 0 + t["large_s"]) for t, s in zip(te, small, strict=True))
        sweep.append({"threshold": th, "share_small": round(sum(small) / len(te), 4), "accuracy": round(acc, 4), "cpu_seconds": round(sec, 2)})
    out = {
        "label": "MEASURED on CPU: two real open models; closed provider wired but not run (no API quota)",
        "small": res["small"],
        "large": res["large"],
        "test_tasks": len(te),
        "train_tasks": len(tr),
        "all_small": {"accuracy": round(sum(t["small_ok"] for t in te) / len(te), 4), "cpu_seconds": round(sum(t["small_s"] for t in te), 2)},
        "all_large": {"accuracy": round(sum(t["large_ok"] for t in te) / len(te), 4), "cpu_seconds": round(sum(t["large_s"] for t in te), 2)},
        "oracle": {"accuracy": round(sum(t["small_ok"] or t["large_ok"] for t in te) / len(te), 4)},
        "router_weights": [round(w, 3) for w in model.weights],
        "sweep": sweep,
    }
    (ROOT / "results/router.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
