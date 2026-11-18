import math
from datetime import UTC, datetime

import numpy as np
import pytest

from ivsurface.pipeline import build
from ivsurface.synthetic import flat_vol_chain

SNAPSHOT_TIME = datetime(2026, 1, 1, 8, 0, tzinfo=UTC)
EXPIRY = datetime(2026, 1, 31, 8, 0, tzinfo=UTC)  # exactly 30 calendar days later
FORWARD = 50_000.0
STRIKES = [40_000.0, 45_000.0, 50_000.0, 55_000.0, 60_000.0]


@pytest.fixture
def result():
    chain = flat_vol_chain(
        forward=FORWARD,
        vol=0.55,
        strikes=STRIKES,
        expiry=EXPIRY,
        snapshot_time=SNAPSHOT_TIME,
    )
    return build(chain)


def test_points_recover_the_known_vol(result):
    assert len(result.points) == 2 * len(STRIKES)  # a call and a put per strike
    np.testing.assert_allclose(result.points["iv"], 0.55, atol=1e-8)


def test_time_to_expiry_is_calendar_time_in_years(result):
    np.testing.assert_allclose(result.points["T"], 30 / 365, rtol=1e-12)


def test_log_moneyness_is_relative_to_the_forward(result):
    atm = result.points[result.points["strike"] == 50_000.0]
    np.testing.assert_allclose(atm["k"], 0.0, atol=1e-15)
    upper = result.points[result.points["strike"] == 60_000.0]
    np.testing.assert_allclose(upper["k"], math.log(1.2), rtol=1e-12)


def test_total_variance_is_sigma_squared_t(result):
    np.testing.assert_allclose(result.points["w"], 0.55**2 * 30 / 365, rtol=1e-8)
