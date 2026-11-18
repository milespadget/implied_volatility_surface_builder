"""The pipeline's interpolated surface, checked against a known synthetic surface."""

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from ivsurface.pipeline import build
from ivsurface.synthetic import option_chain

SNAPSHOT_TIME = datetime(2026, 1, 1, 8, 0, tzinfo=UTC)
FORWARD = 50_000.0
EXPIRY_DAYS = [7, 30, 90, 180]
STRIKES = list(FORWARD * np.exp(np.linspace(-0.6, 0.6, 49)))


def smile(k, t):
    """A true vol that depends on k only, so w = smile(k)^2 * T is exactly linear in T."""
    return 0.5 - 0.1 * k + 0.3 * k**2


@pytest.fixture(scope="module")
def surface():
    snapshot = option_chain(
        forward=FORWARD,
        vol=smile,
        strikes=STRIKES,
        expiries=[SNAPSHOT_TIME + timedelta(days=d) for d in EXPIRY_DAYS],
        snapshot_time=SNAPSHOT_TIME,
    )
    result = build(snapshot)
    assert result.interpolated is not None
    return result.interpolated, result.points.query("reason == 'ok'")


def test_surface_reproduces_the_quoted_points(surface):
    interpolated, points = surface
    np.testing.assert_allclose(interpolated.iv(points["k"], points["T"]), points["iv"], rtol=1e-10)


def test_surface_recovers_the_true_vol_between_strikes_and_expiries(surface):
    interpolated, _ = surface
    k = np.array([-0.43, -0.11, 0.0, 0.07, 0.29, 0.51])
    t = np.array([15, 45, 60, 100, 150, 170]) / 365
    np.testing.assert_allclose(interpolated.iv(k, t), smile(k, t), atol=1e-4)


def test_total_variance_is_iv_squared_t(surface):
    interpolated, _ = surface
    k, t = np.array([0.1, -0.2]), np.array([0.1, 0.3])
    np.testing.assert_allclose(interpolated.total_variance(k, t), interpolated.iv(k, t) ** 2 * t, rtol=1e-12)


def test_vol_is_flat_beyond_the_quoted_expiries(surface):
    interpolated, _ = surface
    k = np.array([0.0, 0.2])
    first, last = EXPIRY_DAYS[0] / 365, EXPIRY_DAYS[-1] / 365
    np.testing.assert_allclose(interpolated.iv(k, np.full(2, 1 / 365)), interpolated.iv(k, np.full(2, first)), rtol=1e-12)
    np.testing.assert_allclose(interpolated.iv(k, np.full(2, 2.0)), interpolated.iv(k, np.full(2, last)), rtol=1e-12)
