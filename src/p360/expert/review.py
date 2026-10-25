"""Expert review: approve, fix or reject an answer with a reason. Records become preference pairs.

The same ReviewRecord is produced by a person at the CLI (`p360 review`) or by a SimulatedExpert in the demo.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from ..guardrails import redact
from .rules import violations

VERDICTS = ("approve", "fix", "reject")


@dataclass
class ReviewRecord:
    task_id: str
    domain: str
    prompt: str
    answer: str
    verdict: str
    reason: str
    fix: str | None = None
    reviewer: str = "simulated"

    def __post_init__(self):
        if self.verdict not in VERDICTS:
            raise ValueError(f"verdict must be one of {VERDICTS}")
        if self.verdict != "approve" and not self.reason.strip():
            raise ValueError("a reason is required for fix and reject")
        if self.verdict == "fix" and not (self.fix or "").strip():
            raise ValueError("a fix needs the corrected answer")
        # reviews are stored, so strip PII before they ever hit disk
        self.prompt, self.answer = redact(self.prompt).text, redact(self.answer).text
        self.fix = redact(self.fix).text if self.fix else None


def decision(answer: str) -> str | None:
    m = re.match(r"\W*(yes|no)\b", answer.strip(), re.I)
    return m.group(1).upper() if m else None


def judge(pack: dict, task: dict, answer: str) -> tuple[bool, str]:
    """The SIMULATED expert's check: right decision first, then every expert rule."""
    d = decision(answer)
    if d is None:
        return False, "does not start with a YES/NO decision"
    if d != task["expected"]:
        return False, f"wrong decision: policy says {task['expected']}"
    v = violations(pack, answer, task["prompt"])
    if v:
        return False, "breaks rule " + ", ".join(v)
    return True, "correct and compliant"


class SimulatedExpert:
    """Stands in for a domain expert. Knows the right decision and writes a compliant fix."""

    def __init__(self, pack: dict, name: str | None = None):
        self.pack, self.name = pack, name or f"sim-{pack['domain']}-expert"

    def write_fix(self, task: dict) -> str:
        parts = [f"{task['expected']}."]
        for r in self.pack["rule_objs"]:
            if r.kind == "must_include" and r.when and r.when.lower() in task["prompt"].lower():
                parts.append(r.append or r.instruction)
        parts.append("This follows the stated policy.")
        return " ".join(parts)

    def review(self, task: dict, answer: str) -> ReviewRecord:
        ok, why = judge(self.pack, task, answer)
        if ok:
            return ReviewRecord(task["id"], task["domain"], task["prompt"], answer, "approve", why, reviewer=self.name)
        if decision(answer) is None:
            return ReviewRecord(task["id"], task["domain"], task["prompt"], answer, "reject", why, reviewer=self.name)
        return ReviewRecord(task["id"], task["domain"], task["prompt"], answer, "fix", why, self.write_fix(task), self.name)


def save(records: list[ReviewRecord], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        for r in records:
            f.write(json.dumps(asdict(r)) + "\n")


def load_reviews(path: Path) -> list[ReviewRecord]:
    return [ReviewRecord(**json.loads(x)) for x in path.read_text().splitlines() if x.strip()] if path.exists() else []
