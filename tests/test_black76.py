import math

import pytest

from ivsurface.black76 import implied_vol, price, vega


def test_atm_call_matches_known_value():
    # ATM Black-76 with r=0: C = F * (2*N(sigma*sqrt(T)/2) - 1).
    # F=100, sigma=0.2, T=1 -> 100 * (2*N(0.1) - 1) = 7.965567455405804
    assert price(100.0, 100.0, 1.0, 0.2, "call") == pytest.approx(7.965567455405804, rel=1e-12)


def test_put_call_parity_on_forward():
    # With r=0: C - P = F - K
    f, k, t, sigma = 100.0, 120.0, 0.5, 0.6
    assert price(f, k, t, sigma, "call") - price(f, k, t, sigma, "put") == pytest.approx(f - k, abs=1e-10)


def test_atm_vega_matches_known_value():
    # ATM vega with r=0: F * sqrt(T) * n(d1), d1 = sigma*sqrt(T)/2 = 0.1
    # 100 * 1 * n(0.1) = 39.69525474770118
    assert vega(100.0, 100.0, 1.0, 0.2) == pytest.approx(39.69525474770118, rel=1e-12)


@pytest.mark.parametrize("option_type", ["call", "put"])
@pytest.mark.parametrize("log_moneyness", [-0.5, -0.2, 0.0, 0.2, 0.5])
@pytest.mark.parametrize("t", [0.05, 0.25, 1.0])
@pytest.mark.parametrize("sigma", [0.3, 0.6, 1.2])
def test_round_trip_recovers_sigma(option_type, log_moneyness, t, sigma):
    in_the_money = (option_type == "call") == (log_moneyness < 0)
    if in_the_money and abs(log_moneyness) / (sigma * math.sqrt(t)) > 3.0:
        # Deep ITM, the time value is a ~1e-6 sliver of the premium and is lost to rounding
        # against intrinsic. The pipeline only inverts OTM quotes (ticket 03).
        pytest.skip("deep ITM: time value lost to cancellation; pipeline uses OTM quotes")
    f = 50_000.0
    k = f * math.exp(log_moneyness)
    p = price(f, k, t, sigma, option_type)
    assert implied_vol(p, f, k, t, option_type) == pytest.approx(sigma, abs=1e-8)
