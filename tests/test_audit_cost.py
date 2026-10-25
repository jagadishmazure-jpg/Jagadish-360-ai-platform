from p360.audit import AuditLog
from p360.cost import PRICES_AS_OF, Budget, CostLedger


def test_chain_verifies_and_detects_tamper(tmp_path):
    a = AuditLog(tmp_path / "a.jsonl")
    for i in range(5):
        a.append("e", n=i)
    assert a.verify()
    a.entries[2]["data"]["n"] = 99
    assert not a.verify()


def test_audit_reload(tmp_path):
    p = tmp_path / "a.jsonl"
    AuditLog(p).append("x", v=1)
    b = AuditLog(p)
    b.append("y", v=2)
    assert len(b.entries) == 2 and b.verify()


def test_audit_redacts_strings():
    a = AuditLog()
    e = a.append("e", note="mail jo@example.com")
    assert "jo@example.com" not in e["data"]["note"]


def test_prices():
    led = CostLedger(local_per_mtok=1.0)
    assert abs(led.price("gpt-4o-mini", 1_000_000, 0) - 0.15) < 1e-9
    assert abs(led.price("gpt-4o-mini", 0, 1_000_000) - 0.60) < 1e-9
    assert abs(led.price("local", 500_000, 500_000) - 1.0) < 1e-9
    assert "2026" in PRICES_AS_OF


def test_ledger_report():
    led = CostLedger()
    led.record("t", "gpt-4o-mini", 1000, 1000)
    assert led.total() > 0 and "t/gpt-4o-mini" in led.report()


def test_budget():
    b = Budget(1.0)
    assert b.allow(0.5)
    b.spent_usd = 0.9
    assert not b.allow(0.2)
