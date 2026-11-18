"""The pipeline's SVI surface, checked against synthetic chains generated from known SVI slices."""

import math
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from ivsurface.pipeline import build
from ivsurface.synthetic import option_chain

SNAPSHOT_TIME = datetime(2026, 1, 1, 8, 0, tzinfo=UTC)
FORWARD = 50_000.0
STRIKES = list(FORWARD * np.exp(np.linspace(-0.6, 0.6, 49)))

# Raw SVI (a, b, rho, m, sigma) per expiry in days: ATM vols of roughly 40%, 44% and 43%.
TRUE = {
    14: (0.002, 0.04, -0.2, 0.02, 0.10),
    30: (0.005, 0.07, -0.25, 0.03, 0.15),
    90: (0.020, 0.12, -0.3, 0.05, 0.20),
}


def raw_svi(k, a, b, rho, m, sigma):
    """Written out here, independently of the code under test."""
    return a + b * (rho * (k - m) + np.sqrt((k - m) ** 2 + sigma**2))


def true_vol(k: float, t: float) -> float:
    days = round(t * 365)
    return math.sqrt(raw_svi(k, *TRUE[days]) / t)


def svi_chain(**quoting):
    return option_chain(
        forward=FORWARD,
        vol=true_vol,
        strikes=STRIKES,
        expiries=[SNAPSHOT_TIME + timedelta(days=d) for d in TRUE],
        snapshot_time=SNAPSHOT_TIME,
        **quoting,
    )


@pytest.fixture(scope="module")
def clean():
    return build(svi_chain(relative_spread=0.05))


def test_noise_free_quotes_give_back_the_true_svi_parameters(clean):
    params = clean.svi_params
    assert sorted(np.round(params["T"] * 365)) == sorted(TRUE)
    for fitted in params.to_dict("records"):
        a, b, rho, m, sigma = TRUE[round(fitted["T"] * 365)]
        assert fitted["a"] == pytest.approx(a, abs=1e-4)
        assert fitted["b"] == pytest.approx(b, rel=1e-3)
        assert fitted["rho"] == pytest.approx(rho, abs=1e-3)
        assert fitted["m"] == pytest.approx(m, abs=1e-3)
        assert fitted["sigma"] == pytest.approx(sigma, rel=1e-3)


@pytest.mark.parametrize("seed", range(5))
def test_noisy_quotes_give_svi_parameters_near_the_truth(seed):
    # With 1% price noise a and sigma trade off against each other (a classic SVI identifiability
    # effect), so they get looser tolerances than b, rho and m.
    params = build(svi_chain(relative_spread=0.05, noise=0.01, seed=seed)).svi_params
    assert len(params) == len(TRUE)
    for fitted in params.to_dict("records"):
        a, b, rho, m, sigma = TRUE[round(fitted["T"] * 365)]
        assert fitted["a"] == pytest.approx(a, abs=3e-3)
        assert fitted["b"] == pytest.approx(b, rel=0.05)
        assert fitted["rho"] == pytest.approx(rho, abs=0.02)
        assert fitted["m"] == pytest.approx(m, abs=0.01)
        assert fitted["sigma"] == pytest.approx(sigma, rel=0.1)


def test_every_fitted_slice_is_a_valid_svi_smile():
    params = build(svi_chain(relative_spread=0.05, noise=0.02, seed=11)).svi_params
    assert np.all(params["b"].to_numpy() >= 0)
    assert np.all(np.abs(params["rho"].to_numpy()) < 1)
    assert np.all(params["sigma"].to_numpy() > 0)
    assert np.all(params["min_variance"].to_numpy() >= 0)


K_CHECK = np.array([-0.5, -0.2, -0.05, 0.0, 0.1, 0.3, 0.55])


def test_the_svi_surface_matches_the_true_vols_on_each_expiry_despite_noise():
    surface = build(svi_chain(relative_spread=0.05, noise=0.01, seed=5)).svi
    assert surface is not None
    for days in TRUE:
        t = np.full_like(K_CHECK, days / 365)
        np.testing.assert_allclose(surface.iv(K_CHECK, t), [true_vol(k, days / 365) for k in K_CHECK], atol=0.005)


def test_the_svi_surface_is_linear_in_total_variance_between_expiries(clean):
    surface = clean.svi
    assert surface is not None
    t30, t90 = 30 / 365, 90 / 365
    t = 50 / 365  # a third of the way from 30 to 90 days
    expected = raw_svi(K_CHECK, *TRUE[30]) + (raw_svi(K_CHECK, *TRUE[90]) - raw_svi(K_CHECK, *TRUE[30])) * (t - t30) / (t90 - t30)
    np.testing.assert_allclose(surface.total_variance(K_CHECK, np.full_like(K_CHECK, t)), expected, rtol=1e-4)


def test_the_svi_surface_holds_vol_flat_beyond_the_quoted_expiries(clean):
    surface = clean.svi
    assert surface is not None
    one_year, one_day = np.full_like(K_CHECK, 1.0), np.full_like(K_CHECK, 1 / 365)
    np.testing.assert_allclose(surface.iv(K_CHECK, one_year), [true_vol(k, 90 / 365) for k in K_CHECK], rtol=1e-4)
    np.testing.assert_allclose(surface.iv(K_CHECK, one_day), [true_vol(k, 14 / 365) for k in K_CHECK], rtol=1e-4)
    np.testing.assert_allclose(surface.expiries * 365, sorted(TRUE))
