import math

import pytest

from ivsurface.black76 import Reason, implied_vol, price, vega


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
    result = implied_vol(p, f, k, t, option_type)
    assert result.reason == Reason.OK
    assert result.iv == pytest.approx(sigma, abs=1e-8)


@pytest.mark.parametrize(
    ("premium", "strike", "option_type"),
    [
        (9_999.0, 40_000.0, "call"),  # intrinsic is F - K = 10,000
        (4_999.0, 55_000.0, "put"),  # intrinsic is K - F = 5,000
        (0.0, 60_000.0, "call"),  # no time value at all
    ],
)
def test_price_at_or_below_intrinsic_is_rejected(premium, strike, option_type):
    result = implied_vol(premium, 50_000.0, strike, 0.1, option_type)
    assert math.isnan(result.iv)
    assert result.reason == Reason.BELOW_INTRINSIC


@pytest.mark.parametrize(
    ("premium", "strike", "option_type"),
    [
        (50_000.0, 60_000.0, "call"),  # a call is worth at most F
        (55_000.0, 55_000.0, "put"),  # a put is worth at most K
    ],
)
def test_price_at_or_above_upper_bound_is_rejected(premium, strike, option_type):
    result = implied_vol(premium, 50_000.0, strike, 0.1, option_type)
    assert math.isnan(result.iv)
    assert result.reason == Reason.ABOVE_UPPER_BOUND


@pytest.mark.parametrize(
    ("log_moneyness", "t", "sigma"),
    [
        (0.2, 1 / 365, 0.2),  # one day to expiry, ~20 sd out of the money
        (-0.5, 0.02, 0.2),  # a week to expiry, deep OTM put
        (-1.0, 0.1, 0.2),  # a month to expiry, very deep OTM put
    ],
)
def test_tiny_vega_quotes_still_recover_sigma(log_moneyness, t, sigma):
    # Vega underflows to ~0 at the Newton start here, so plain Newton cannot take a step.
    f = 50_000.0
    k = f * math.exp(log_moneyness)
    option_type = "call" if log_moneyness > 0 else "put"
    result = implied_vol(price(f, k, t, sigma, option_type), f, k, t, option_type)
    assert result.reason == Reason.OK
    assert result.iv == pytest.approx(sigma, rel=1e-6)


def test_sigma_beyond_the_search_range_reports_no_convergence():
    # A legal price (inside the bounds) that needs sigma = 30, well past any real vol.
    # ATM with sigma*sqrt(T) = 3: premium = F * (2*N(1.5) - 1) = 0.8663855974622838 * F
    f = 50_000.0
    result = implied_vol(0.8663855974622838 * f, f, f, 0.01, "call")
    assert math.isnan(result.iv)
    assert result.reason == Reason.NO_CONVERGENCE
