import pytest

from p360.breakeven import ASSUMPTIONS, Inputs, capacity_mtok_month, local_cost_per_mtok, payback_month, report, servers_needed, sweep


def test_never_pays_back_vs_cheap_api():
    assert payback_month(Inputs(monthly_tokens_m=500)) is None


def test_pays_back_vs_premium():
    m = payback_month(Inputs(monthly_tokens_m=500, api_usd_per_mtok=4.375))
    assert m is not None and 1 <= m <= 36


def test_more_volume_pays_back_sooner():
    a = payback_month(Inputs(monthly_tokens_m=200, api_usd_per_mtok=4.375))
    b = payback_month(Inputs(monthly_tokens_m=600, api_usd_per_mtok=4.375))
    assert b < a


def test_servers_scale_with_volume():
    i = Inputs(monthly_tokens_m=capacity_mtok_month(Inputs()) * 2.5)
    assert servers_needed(i) == 3


def test_local_cost_falls_with_volume():
    assert local_cost_per_mtok(Inputs(monthly_tokens_m=100)) > local_cost_per_mtok(Inputs(monthly_tokens_m=400))


def test_report_labelled():
    r = report(Inputs())
    assert "ESTIMATED" in r["label"] and set(ASSUMPTIONS) >= {"server_usd", "tokens_per_s", "api_usd_per_mtok"}


@pytest.mark.parametrize("v", [10, 100, 1000])
def test_sweep_rows(v):
    assert sweep(Inputs(), [v])[0]["monthly_tokens_m"] == v
