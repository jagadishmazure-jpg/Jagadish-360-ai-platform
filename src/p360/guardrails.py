"""Shared guardrails used by every workload: PII redaction, prompt-injection screen, safe errors and log filtering.

PII detection uses patterns plus checksum validators (Luhn for cards) so ordinary numbers are not flagged.
Optional keyed pseudonymisation (HMAC-SHA256, key from P360_PSEUDO_KEY) gives stable tokens for joins.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import re
from dataclasses import dataclass, field

EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE = re.compile(r"(?<!\d)(?:\+?1[ .-]?)?\(?\d{3}\)?[ .-]\d{3}[ .-]\d{4}(?!\d)")
SSN = re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)")
CARD = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")
MRN = re.compile(r"\bMRN[-: ]?\d{6,10}\b", re.I)
APIKEY = re.compile(r"\b(?:sk-[A-Za-z0-9_-]{16,}|AKIA[0-9A-Z]{16})\b")

INJECTION = [
    re.compile(p, re.I)
    for p in (
        r"ignore (all |any )?(previous|prior|above) (instructions|rules)",
        r"disregard (the |your )?(system|previous) (prompt|instructions)",
        r"you are now (in )?(developer|dan|jailbreak) mode",
        r"reveal (the |your )?(system prompt|hidden instructions|api key)",
        r"print (the |your )?(system prompt|secrets?|environment)",
        r"act as (an? )?unrestricted",
        r"override (the |all )?(guardrails|safety|policy)",
    )
]


def luhn_ok(digits: str) -> bool:
    d = [int(c) for c in digits if c.isdigit()]
    if not 13 <= len(d) <= 19:
        return False
    total = 0
    for i, n in enumerate(reversed(d)):
        if i % 2:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


@dataclass
class Redaction:
    text: str
    findings: list[str] = field(default_factory=list)

    @property
    def had_pii(self) -> bool:
        return bool(self.findings)


def pseudonym(value: str, kind: str) -> str:
    key = os.environ.get("P360_PSEUDO_KEY")
    if not key:
        return f"[{kind}]"
    tag = hmac.new(key.encode(), value.encode(), hashlib.sha256).hexdigest()[:10]
    return f"[{kind}:{tag}]"


def redact(text: str) -> Redaction:
    findings: list[str] = []

    def sub(rx: re.Pattern[str], kind: str, s: str, check=None) -> str:
        def rep(m: re.Match[str]) -> str:
            if check and not check(m.group(0)):
                return m.group(0)
            findings.append(kind)
            return pseudonym(m.group(0), kind)

        return rx.sub(rep, s)

    out = sub(APIKEY, "SECRET", text)
    out = sub(EMAIL, "EMAIL", out)
    out = sub(SSN, "SSN", out)
    out = sub(CARD, "CARD", out, luhn_ok)
    out = sub(PHONE, "PHONE", out)
    out = sub(MRN, "MRN", out)
    return Redaction(out, findings)


def injection(text: str) -> str | None:
    for rx in INJECTION:
        if rx.search(text):
            return rx.pattern
    return None


def safe_error(exc: BaseException) -> str:
    """Error text that is safe to return or log: type plus a redacted, truncated message."""
    return f"{type(exc).__name__}: {redact(str(exc)).text[:200]}"


class RedactingFilter(logging.Filter):
    """Logging filter that redacts PII and secrets from every record, including exception text."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.getMessage()).text
        record.args = ()
        if record.exc_info and record.exc_info[1] is not None:
            exc = record.exc_info[1]
            record.exc_text = safe_error(exc)
            record.exc_info = None
        return True


def get_logger(name: str = "p360") -> logging.Logger:
    log = logging.getLogger(name)
    if not any(isinstance(f, RedactingFilter) for f in log.filters):
        log.addFilter(RedactingFilter())
    return log
