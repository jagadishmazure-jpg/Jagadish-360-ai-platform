"""LIVE: generate answers with a real local open model (CPU, llama.cpp) for the expert loop.

python scripts/gen_candidates.py --model ~/models/qwen2.5-0.5b-instruct-q4_k_m.gguf
Writes data/candidates.json (committed, so CI can replay the loop without the model).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from p360.expert.rules import DOMAINS, guidance, load  # noqa: E402
from p360.expert.tasks import BASE_SYSTEM, as_dicts, make  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--samples", type=int, default=4)
    a = ap.parse_args()
    from llama_cpp import Llama

    llm = Llama(a.model, n_ctx=1024, verbose=False, seed=0)

    def gen(system: str, prompt: str, temp: float, seed: int) -> str:
        r = llm.create_chat_completion(messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}], max_tokens=80, temperature=temp, seed=seed)
        return (r["choices"][0]["message"]["content"] or "").strip()

    items, t0 = [], time.time()
    for dom in DOMAINS:
        rules_sys = BASE_SYSTEM + "\n" + guidance(load(dom))
        for t in as_dicts(make(dom, a.n)):
            t["baseline"] = gen(BASE_SYSTEM, t["prompt"], 0.0, 0)
            taught = f"{t['prompt']}\nExpert policy checker: {t['facts']}"
            t["rules_greedy"] = gen(rules_sys, taught, 0.0, 0)
            t["rules_samples"] = [gen(rules_sys, taught, 0.9, s + 1) for s in range(a.samples)]
            items.append(t)
        print(dom, "done", round(time.time() - t0, 1), "s", flush=True)
    out = {"generator": {"model": Path(a.model).name, "runtime": "llama.cpp on CPU", "samples": a.samples, "max_tokens": 80, "seconds": round(time.time() - t0, 1)}, "items": items}
    (ROOT / "data" / "candidates.json").write_text(json.dumps(out, indent=1) + "\n")


if __name__ == "__main__":
    main()
