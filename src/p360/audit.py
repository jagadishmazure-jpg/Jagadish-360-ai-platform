"""Append-only, hash-chained audit trail. Each entry stores the hash of the previous one, so edits are detectable."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from .guardrails import redact

GENESIS = "0" * 64


class AuditLog:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else None
        self.entries: list[dict] = []
        if self.path and self.path.exists():
            self.entries = [json.loads(line) for line in self.path.read_text().splitlines() if line.strip()]

    def append(self, event: str, **data) -> dict:
        prev = self.entries[-1]["hash"] if self.entries else GENESIS
        clean = {k: (redact(v).text if isinstance(v, str) else v) for k, v in data.items()}
        body = {"seq": len(self.entries), "ts": round(time.time(), 3), "event": event, "data": clean, "prev": prev}
        body["hash"] = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
        self.entries.append(body)
        if self.path:
            with self.path.open("a") as f:
                f.write(json.dumps(body, sort_keys=True) + "\n")
        return body

    def verify(self) -> bool:
        prev = GENESIS
        for e in self.entries:
            body = {k: v for k, v in e.items() if k != "hash"}
            if e["prev"] != prev or hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest() != e["hash"]:
                return False
            prev = e["hash"]
        return True
