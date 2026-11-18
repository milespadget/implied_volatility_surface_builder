"""The pipeline on a real Deribit BTC snapshot (committed fixture, taken 2026-11-18 20:00 UTC)."""

import numpy as np
import pytest

from conftest import REAL_SNAPSHOT as FIXTURE
from ivsurface.arbitrage import ViolationKind
from ivsurface.data import load_snapshot
from ivsurface.pipeline import build


@pytest.fixture(scope="module")
def snapshot():
    return load_snapshot(FIXTURE)


@pytest.fixture(scope="module")
def result(snapshot):
    return build(snapshot)


def test_our_mid_ivs_agree_with_deribits_mark_iv(result):
    # We invert mid prices; Deribit inverts its own mark prices, so expect small gaps, not zero.
    ok = result.points.query("reason == 'ok'")
    gap = np.abs(ok["iv"].to_numpy() - ok["mark_iv"].to_numpy())
    assert len(ok) > 300  # most OTM quotes survive the default filters
    assert np.median(gap) < 0.002
    assert gap.max() < 0.02


def test_each_expiry_is_one_slice_of_the_surface(result):
    # Deribit's per-instrument timestamps must not split an expiry into many slightly different T.
    expiries_kept = set(result.points.query("reason == 'ok'")["expiry"])
    assert result.interpolated is not None
    assert len(result.interpolated.expiries) == len(expiries_kept) == 9


def test_the_real_surface_has_no_calendar_arbitrage(result):
    assert result.interpolated_arbitrage is not None
    assert result.interpolated_arbitrage.count(ViolationKind.CALENDAR) == 0


def test_quotes_with_an_empty_bid_side_are_rejected_as_zero_bid(snapshot, result):
    # Deribit sends a null bid when nobody is bidding; it must not reach the solver.
    no_bid = np.isnan(snapshot["bid"].to_numpy(dtype=float))
    assert no_bid.sum() > 0
    reasons = set(result.points["reason"].to_numpy()[no_bid])
    assert reasons <= {"zero_bid", "short_expiry", "itm", "atm_duplicate"}  # earlier checks may win
    assert "zero_bid" in reasons


def test_svi_fits_every_expiry_with_a_valid_smile(result):
    params = result.svi_params
    assert result.interpolated is not None
    np.testing.assert_allclose(params["T"], result.interpolated.expiries)  # every expiry is fitted
    assert np.all(params["b"].to_numpy() >= 0)
    assert np.all(np.abs(params["rho"].to_numpy()) < 1)
    assert np.all(params["sigma"].to_numpy() > 0)
    assert np.all(params["min_variance"].to_numpy() >= 0)


def test_svi_fits_the_real_quotes_closely(result):
    ok = result.points.query("reason == 'ok'")
    assert result.svi is not None
    misfit = np.abs(ok["iv"].to_numpy() - result.svi.iv(ok["k"].to_numpy(), ok["T"].to_numpy()))
    assert np.median(misfit) < 0.002
    assert misfit.max() < 0.03


def test_svi_has_no_more_arbitrage_than_the_interpolated_surface(result):
    interpolated, svi = result.interpolated_arbitrage, result.svi_arbitrage
    assert interpolated is not None and svi is not None
    for kind in ViolationKind:
        assert svi.count(kind) <= interpolated.count(kind)
    assert interpolated.count(ViolationKind.BUTTERFLY) > 0  # so the comparison means something
