"""Static-arbitrage diagnostics on the pipeline's surfaces, checked with synthetic surfaces built
to be clean or to contain a known violation."""

import math
from datetime import UTC, datetime, timedelta

import numpy as np

from ivsurface.arbitrage import ViolationKind
from ivsurface.pipeline import build
from ivsurface.synthetic import VolFunction, option_chain

SNAPSHOT_TIME = datetime(2026, 1, 1, 8, 0, tzinfo=UTC)
FORWARD = 50_000.0
STRIKES = list(FORWARD * np.exp(np.linspace(-0.5, 0.5, 41)))


def report_for(vol: VolFunction, expiry_days: list[int]):
    snapshot = option_chain(
        forward=FORWARD,
        vol=vol,
        strikes=STRIKES,
        expiries=[SNAPSHOT_TIME + timedelta(days=d) for d in expiry_days],
        snapshot_time=SNAPSHOT_TIME,
    )
    report = build(snapshot).interpolated_arbitrage
    assert report is not None
    return report


def test_a_clean_surface_has_no_violations():
    def smile(k: float, t: float) -> float:
        return 0.5 - 0.1 * k + 0.3 * k**2

    report = report_for(smile, [14, 30, 90])
    assert report.is_free
    assert report.share(ViolationKind.BUTTERFLY) == 0.0
    assert report.share(ViolationKind.CALENDAR) == 0.0


def test_the_reported_g_curves_are_the_ones_checked_and_are_clean_on_a_clean_surface():
    # The curves span each slice's quoted range (minus the stencil inset) and must not show the
    # spurious end spikes you get by differencing across the flat extrapolation.
    def smile(k: float, t: float) -> float:
        return 0.5 - 0.1 * k + 0.3 * k**2

    report = report_for(smile, [14, 30, 90])
    assert [round(c.t * 365) for c in report.butterfly_curves] == [14, 30, 90]
    for curve in report.butterfly_curves:
        assert curve.k.min() > -0.5 and curve.k.max() < 0.5
        assert curve.k.min() < -0.49 and curve.k.max() > 0.49
        assert np.all(curve.g > 0)


def test_a_concave_vol_hump_is_flagged_as_butterfly_arbitrage():
    # At k = 0, sigma'' = -2 * 0.4 / 0.1^2 = -80, so w''/2 = sigma * sigma'' * T is about
    # -2.8 at 14 days, which swamps the first term (1) of Durrleman's g: g(0) < 0.
    def hump(k: float, t: float) -> float:
        return 0.5 + 0.4 * math.exp(-((k / 0.1) ** 2))

    report = report_for(hump, [14, 30, 90])
    butterflies = report.violations.query("kind == 'butterfly'")
    k = butterflies["k"].to_numpy(dtype=float)
    t_days = np.round(butterflies["T"].to_numpy(dtype=float) * 365)
    assert not report.is_free
    assert len(report.violations.query("kind == 'calendar'")) == 0
    assert set(t_days) == {14, 30, 90}  # every slice has the hump
    assert np.all(np.abs(k) < 0.2)  # and only around the hump
    assert np.all(butterflies["magnitude"].to_numpy(dtype=float) > 0)
    for days in (14, 30, 90):  # every slice is flagged at the money itself
        assert np.abs(k[t_days == days]).min() < 0.02
    assert 0.0 < report.share(ViolationKind.BUTTERFLY) < 0.5  # a local hump, not the whole smile
    assert report.count(ViolationKind.BUTTERFLY) == len(butterflies)


def test_falling_total_variance_is_flagged_as_calendar_arbitrage():
    # 80% vol at 30 days, 30% at 60 days: w falls from 0.64*30/365 to 0.09*60/365 at every k,
    # a drop of 13.8/365.
    def collapsing(k: float, t: float) -> float:
        return 0.8 if t < 45 / 365 else 0.3

    report = report_for(collapsing, [30, 60])
    calendar = report.violations.query("kind == 'calendar'")
    assert len(report.violations.query("kind == 'butterfly'")) == 0  # each smile is flat
    assert len(calendar) > 0
    np.testing.assert_allclose(calendar["T"], 60 / 365)  # reported against the later expiry
    np.testing.assert_allclose(calendar["magnitude"], 13.8 / 365, rtol=1e-6)
    k = calendar["k"].to_numpy(dtype=float)
    assert k.min() < -0.45 and k.max() > 0.45  # across the whole shared k range
    assert report.share(ViolationKind.CALENDAR) == 1.0


def test_rising_total_variance_is_not_calendar_arbitrage_even_when_vol_falls():
    # Vol falls from 60% to 50%, but w = sigma^2 T still rises (0.36*30 < 0.25*60): no arbitrage.
    def falling_vol(k: float, t: float) -> float:
        return 0.6 if t < 45 / 365 else 0.5

    assert report_for(falling_vol, [30, 60]).is_free
