"""LIVE: quantization quality vs size on CPU for one open model at several GGUF quant levels.

python scripts/bench_quant.py --models ~/models/qwen2.5-0.5b-instruct-{q2_k,q4_k_m,q8_0,fp16}.gguf
Measures file size, short-answer accuracy (40 self-written questions, a regression check, not a benchmark),
agreement with the fp16 answers, perplexity on a self-written paragraph, and decode tokens/s. Writes results/quant.json.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", required=True)
    a = ap.parse_args()
    import numpy as np
    from llama_cpp import Llama

    qa = json.loads((ROOT / "data/bench/qa.json").read_text())
    text = (ROOT / "data/bench/ppl.txt").read_text()
    rows, answers = [], {}
    for path in a.models:
        name = Path(path).name
        t0 = time.time()
        llm = Llama(path, n_ctx=1024, verbose=False, seed=0, logits_all=True)
        load_s = time.time() - t0
        outs, correct = [], 0
        for q, gold in qa:
            r = llm.create_chat_completion(messages=[{"role": "system", "content": "Answer in a few words."}, {"role": "user", "content": q}], max_tokens=16, temperature=0.0, seed=0)
            ans = (r["choices"][0]["message"]["content"] or "").strip()
            outs.append(ans)
            correct += any(g in ans.lower() for g in gold)
        answers[name] = outs
        # perplexity
        toks = llm.tokenize(text.encode())[:900]
        llm.reset()
        llm.eval(toks)
        logits = np.array(llm.scores[: len(toks)])
        nll = 0.0
        for i in range(len(toks) - 1):
            row = logits[i]
            m = row.max()
            lse = m + math.log(np.exp(row - m).sum())
            nll += lse - row[toks[i + 1]]
        ppl = math.exp(nll / (len(toks) - 1))
        # decode speed
        llm.reset()
        t1 = time.time()
        r = llm.create_completion("Write a short paragraph about keeping a shop ledger.", max_tokens=128, temperature=0.0, seed=0)
        dt = time.time() - t1
        rows.append(
            {
                "model": name,
                "size_mb": round(os.path.getsize(path) / 2**20, 1),
                "load_s": round(load_s, 2),
                "qa_accuracy": round(correct / len(qa), 4),
                "perplexity": round(ppl, 3),
                "decode_tok_s": round(r["usage"]["completion_tokens"] / dt, 1),
            }
        )
        print(rows[-1], flush=True)
        del llm
    ref = next((k for k in answers if "fp16" in k), list(answers)[-1])
    for row in rows:
        row["agree_with_fp16"] = round(sum(x.lower() == y.lower() for x, y in zip(answers[row["model"]], answers[ref], strict=True)) / len(qa), 4)
    out = {"label": "MEASURED on this machine's CPU (8 vCPU, no GPU); 40-question self-written regression set", "cpu_threads": os.cpu_count(), "questions": len(qa), "rows": rows}
    (ROOT / "results/quant.json").write_text(json.dumps(out, indent=1) + "\n")


if __name__ == "__main__":
    main()
