import math
from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd
import pytest

from ivsurface.chain import FilterConfig
from ivsurface.pipeline import build
from ivsurface.synthetic import flat_vol_chain

SNAPSHOT_TIME = datetime(2026, 1, 1, 8, 0, tzinfo=UTC)
EXPIRY = datetime(2026, 1, 31, 8, 0, tzinfo=UTC)  # exactly 30 calendar days later
FORWARD = 50_000.0
STRIKES = [40_000.0, 45_000.0, 50_000.0, 55_000.0, 60_000.0]


def chain(**overrides: Any) -> pd.DataFrame:
    kwargs: dict[str, Any] = dict(
        forward=FORWARD, vol=0.55, strikes=STRIKES, expiry=EXPIRY, snapshot_time=SNAPSHOT_TIME
    )
    return flat_vol_chain(**(kwargs | overrides))


def ok(points: pd.DataFrame) -> pd.DataFrame:
    return points.query("reason == 'ok'")


def quote(points: pd.DataFrame, strike: float, option_type: str) -> dict[str, Any]:
    """The points-table row for one instrument, as a plain dict."""
    rows = points.query("strike == @strike and option_type == @option_type")
    assert len(rows) == 1
    return rows.iloc[0].to_dict()


@pytest.fixture
def result():
    return build(chain())


def test_every_input_quote_gets_a_row(result):
    assert len(result.points) == 2 * len(STRIKES)  # a call and a put per strike


def test_only_otm_quotes_are_inverted(result):
    # Puts below the forward, calls at or above it: one quote per strike.
    used = ok(result.points)
    assert sorted(zip(used["strike"], used["option_type"], strict=True)) == [
        (40_000.0, "put"),
        (45_000.0, "put"),
        (50_000.0, "call"),
        (55_000.0, "call"),
        (60_000.0, "call"),
    ]
    itm = result.points.query("reason != 'ok'")
    assert set(itm["reason"]) == {"itm"}
    assert np.isnan(np.asarray(itm["iv"], dtype=float)).all()


def test_points_recover_the_known_vol(result):
    np.testing.assert_allclose(ok(result.points)["iv"], 0.55, atol=1e-8)


def test_time_to_expiry_is_calendar_time_in_years(result):
    np.testing.assert_allclose(result.points["T"], 30 / 365, rtol=1e-12)


def test_log_moneyness_is_relative_to_the_forward(result):
    assert quote(result.points, 50_000.0, "call")["k"] == pytest.approx(0.0, abs=1e-15)
    assert quote(result.points, 60_000.0, "call")["k"] == pytest.approx(math.log(1.2), rel=1e-12)


def test_total_variance_is_sigma_squared_t(result):
    np.testing.assert_allclose(ok(result.points)["w"], 0.55**2 * 30 / 365, rtol=1e-8)


def test_unsolvable_quotes_are_kept_with_a_reason():
    snapshot = chain()
    # An OTM call is worth at most F, i.e. 1 BTC. Quote the 60k call above that.
    bad = (snapshot["strike"] == 60_000.0) & (snapshot["option_type"] == "call")
    snapshot.loc[bad, ["bid", "ask", "mark"]] = 1.01

    points = build(snapshot).points

    assert quote(points, 60_000.0, "call")["reason"] == "above_upper_bound"
    assert math.isnan(quote(points, 60_000.0, "call")["iv"])
    assert len(ok(points)) == 4


def test_quotes_are_inverted_at_mid():
    # A 20% bid/ask spread centred on the true price: the mid is the true price.
    points = build(chain(relative_spread=0.2)).points
    np.testing.assert_allclose(ok(points)["iv"], 0.55, atol=1e-8)


def test_each_quote_reports_its_relative_spread():
    points = build(chain(relative_spread=0.2)).points
    np.testing.assert_allclose(ok(points)["relative_spread"], 0.2, rtol=1e-12)


def test_noisy_quotes_give_ivs_near_the_true_vol():
    points = build(chain(relative_spread=0.05, noise=0.01, seed=7)).points
    ivs = ok(points)["iv"]
    assert not np.allclose(ivs, 0.55, atol=1e-6)  # the noise really moved them
    np.testing.assert_allclose(ivs, 0.55, atol=0.02)


def test_zero_bid_quotes_are_rejected():
    snapshot = chain()
    no_bid = (snapshot["strike"] == 55_000.0) & (snapshot["option_type"] == "call")
    snapshot.loc[no_bid, "bid"] = 0.0
    points = build(snapshot).points
    assert quote(points, 55_000.0, "call")["reason"] == "zero_bid"
    assert math.isnan(quote(points, 55_000.0, "call")["iv"])


def test_min_bid_is_configurable():
    snapshot = chain()
    thin = (snapshot["strike"] == 55_000.0) & (snapshot["option_type"] == "call")
    snapshot.loc[thin, ["bid", "ask"]] = [0.0001, 0.00012]  # bid of one Deribit tick, tight spread
    assert quote(build(snapshot).points, 55_000.0, "call")["reason"] == "ok"
    strict = FilterConfig(min_bid=0.0001)
    assert quote(build(snapshot, strict).points, 55_000.0, "call")["reason"] == "zero_bid"


def test_wide_spread_quotes_are_rejected_at_the_configured_threshold():
    snapshot = chain(relative_spread=0.2)
    assert set(ok(build(snapshot, FilterConfig(max_relative_spread=0.25)).points)["strike"]) == set(STRIKES)
    tight = build(snapshot, FilterConfig(max_relative_spread=0.15)).points
    otm = tight.query("reason != 'itm'")
    assert set(otm["reason"]) == {"wide_spread"}


def test_short_expiries_are_rejected_at_the_configured_threshold():
    one_day = datetime(2026, 1, 2, 8, 0, tzinfo=UTC)
    snapshot = chain(expiry=one_day)
    assert set(build(snapshot).points["reason"]) == {"short_expiry"}  # default minimum is 2 days
    relaxed = build(snapshot, FilterConfig(min_days_to_expiry=0.5)).points
    assert len(ok(relaxed)) == len(STRIKES)
