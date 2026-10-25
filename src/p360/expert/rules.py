"""Expert rule packs -> output guardrails and generated tests."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

DOMAINS_DIR = Path(__file__).resolve().parents[3] / "data" / "domains"
DOMAINS = ("retail", "healthcare", "finance")


@dataclass(frozen=True)
class Rule:
    id: str
    kind: str  # must_not | must_include
    pattern: str
    reason: str
    instruction: str
    when: str | None = None
    append: str | None = None  # expert's standard wording, added by the output guard when a must_include is missing

    def violated(self, answer: str, prompt: str = "") -> bool:
        hit = re.search(self.pattern, answer, re.I) is not None
        if self.kind == "must_not":
            return hit
        if self.when and self.when.lower() not in prompt.lower():
            return False
        return not hit


def load(domain: str, root: Path = DOMAINS_DIR) -> dict:
    pack = json.loads((root / domain / "rules.json").read_text())
    pack["rule_objs"] = [Rule(r["id"], r["kind"], r["pattern"], r["reason"], r["instruction"], r.get("when"), r.get("append")) for r in pack["rules"]]
    return pack


def violations(pack: dict, answer: str, prompt: str = "") -> list[str]:
    return [r.id for r in pack["rule_objs"] if r.violated(answer, prompt)]


def guidance(pack: dict) -> str:
    return "Expert rules:\n" + "\n".join(f"- {r.instruction}" for r in pack["rule_objs"])


HANDOFF = "I can't answer that safely. A specialist will follow up."


def guard(pack: dict, answer: str, prompt: str = "") -> str:
    """Expert rules as an output guard: hand off on a must_not hit, append the expert's wording for a missing must_include."""
    v = violations(pack, answer, prompt)
    by_id = {r.id: r for r in pack["rule_objs"]}
    if any(by_id[i].kind == "must_not" for i in v):
        return HANDOFF
    extra = [by_id[i].append for i in v if by_id[i].append]
    return " ".join([answer.strip(), *extra]) if extra else answer
