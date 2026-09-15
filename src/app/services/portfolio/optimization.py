"""Portfolio construction: minimum variance, maximum Sharpe, efficient frontier, risk parity and
inverse volatility."""

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy.optimize import minimize

from app.core.exceptions import ConvergenceError, DivisionByZeroError, InvalidInputError
from app.core.time_budget import check_time_budget
from app.services.portfolio.analytics import risk_contributions, variance
from app.services.portfolio.inputs import MarketInputs, require_expected_returns
from app.services.statistics.descriptive import FloatArray

_FEASIBILITY_TOLERANCE = 1e-9
_WEIGHT_SUM_TOLERANCE = 1e-8
_RISK_PARITY_TOLERANCE = 1e-6


@dataclass(frozen=True, slots=True)
class PortfolioPoint:
    weights: FloatArray
    expected_return: float | None
    volatility: float
    variance: float
    sharpe_ratio: float | None


def describe(
    weights: FloatArray, market: MarketInputs, risk_free_rate: float | None = None
) -> PortfolioPoint:
    portfolio_variance = variance(weights, market.covariance)
    sigma = math.sqrt(portfolio_variance)
    mu = None if market.expected_returns is None else float(weights @ market.expected_returns)
    sharpe = None
    if mu is not None and risk_free_rate is not None and sigma > 0:
        sharpe = (mu - risk_free_rate) / sigma
    return PortfolioPoint(
        weights=weights,
        expected_return=mu,
        volatility=sigma,
        variance=portfolio_variance,
        sharpe_ratio=sharpe,
    )


def _check_bounds(n: int, min_weight: float, max_weight: float) -> None:
    if min_weight > max_weight:
        raise InvalidInputError("min_weight cannot exceed max_weight")
    if n * min_weight > 1 + _FEASIBILITY_TOLERANCE or n * max_weight < 1 - _FEASIBILITY_TOLERANCE:
        raise InvalidInputError(
            f"weights between {min_weight} and {max_weight} cannot sum to 1 with {n} assets"
        )


def _scale(covariance: FloatArray) -> float:
    mean_variance = float(np.mean(np.diag(covariance)))
    if mean_variance <= 0:
        raise DivisionByZeroError("the covariance matrix has zero variances")
    return 1 / mean_variance


def _solve_slsqp(
    objective: Callable[[FloatArray], float],
    gradient: Callable[[FloatArray], FloatArray],
    x0: FloatArray,
    min_weight: float,
    max_weight: float,
    extra_constraints: tuple[dict[str, Any], ...] = (),
) -> FloatArray:
    n = x0.size
    budget = {"type": "eq", "fun": lambda w: np.sum(w) - 1.0, "jac": lambda w: np.ones_like(w)}

    def timed_objective(w: FloatArray) -> float:
        check_time_budget()
        return objective(w)

    result = minimize(
        timed_objective,
        x0,
        jac=gradient,
        method="SLSQP",
        bounds=[(min_weight, max_weight)] * n,
        constraints=[budget, *extra_constraints],
        # 1e-12 is near the attainable float precision here; tighter tolerances make SLSQP stall
        # at the iteration limit on larger problems (100+ assets) without improving the weights.
        options={"ftol": 1e-12, "maxiter": 2000},
    )
    if not result.success:
        raise ConvergenceError(f"the optimizer did not converge: {result.message}")
    weights = np.clip(np.asarray(result.x, dtype=np.float64), min_weight, max_weight)
    if abs(float(weights.sum()) - 1) > _WEIGHT_SUM_TOLERANCE:
        raise ConvergenceError("the optimizer did not satisfy the budget constraint")
    return weights


def minimum_variance(
    market: MarketInputs, min_weight: float = 0.0, max_weight: float = 1.0
) -> FloatArray:
    """min wᵀΣw  s.t.  Σw = 1, min_weight ≤ w_i ≤ max_weight."""
    n = market.n_assets
    _check_bounds(n, min_weight, max_weight)
    scaled = market.covariance * _scale(market.covariance)
    return _solve_slsqp(
        lambda w: float(w @ scaled @ w),
        lambda w: 2 * scaled @ w,
        np.full(n, 1 / n),
        min_weight,
        max_weight,
    )


def maximum_sharpe(
    market: MarketInputs,
    risk_free_rate: float,
    min_weight: float = 0.0,
    max_weight: float = 1.0,
) -> FloatArray:
    """max (wᵀμ − rf) / √(wᵀΣw)  s.t.  Σw = 1, min_weight ≤ w_i ≤ max_weight."""
    mu = require_expected_returns(market)
    n = market.n_assets
    _check_bounds(n, min_weight, max_weight)
    covariance = market.covariance

    def negative_sharpe(w: FloatArray) -> float:
        sigma = math.sqrt(max(float(w @ covariance @ w), 1e-300))
        return -(float(w @ mu) - risk_free_rate) / sigma

    def gradient(w: FloatArray) -> FloatArray:
        sigma2 = max(float(w @ covariance @ w), 1e-300)
        sigma = math.sqrt(sigma2)
        excess = float(w @ mu) - risk_free_rate
        return -(mu / sigma - excess * (covariance @ w) / (sigma2 * sigma))

    return _solve_slsqp(negative_sharpe, gradient, np.full(n, 1 / n), min_weight, max_weight)


def _maximum_return_weights(mu: FloatArray, min_weight: float, max_weight: float) -> FloatArray:
    """Exact solution of max wᵀμ with box bounds and Σw = 1: fill the best assets first."""
    weights = np.full(mu.size, min_weight)
    remaining = 1 - min_weight * mu.size
    for index in np.argsort(-mu, kind="stable"):
        step = min(max_weight - min_weight, remaining)
        weights[index] += step
        remaining -= step
        if remaining <= 0:
            break
    return weights


def efficient_frontier(
    market: MarketInputs,
    points: int,
    min_weight: float = 0.0,
    max_weight: float = 1.0,
    risk_free_rate: float | None = None,
) -> list[PortfolioPoint]:
    """Minimum-variance portfolios for target returns evenly spaced between the minimum-variance
    portfolio's return and the maximum attainable return."""
    mu = require_expected_returns(market)
    if points < 2:
        raise InvalidInputError("points must be at least 2")
    start = minimum_variance(market, min_weight, max_weight)
    end = _maximum_return_weights(mu, min_weight, max_weight)
    low, high = float(start @ mu), float(end @ mu)
    if high - low <= 1e-12 * max(1.0, abs(high)):
        return [describe(start, market, risk_free_rate)]

    scaled = market.covariance * _scale(market.covariance)
    frontier = [describe(start, market, risk_free_rate)]
    previous = start
    for target in np.linspace(low, high, points)[1:-1]:
        target_return = float(target)
        constraint = {
            "type": "eq",
            "fun": lambda w, t=target_return: float(w @ mu) - t,
            "jac": lambda w: mu,
        }
        previous = _solve_slsqp(
            lambda w: float(w @ scaled @ w),
            lambda w: 2 * scaled @ w,
            previous,
            min_weight,
            max_weight,
            (constraint,),
        )
        frontier.append(describe(previous, market, risk_free_rate))
    frontier.append(describe(end, market, risk_free_rate))
    return frontier


def risk_parity(market: MarketInputs) -> FloatArray:
    """Equal risk contribution (long-only).

    Solves the convex problem min ½ yᵀΣy − (1/N) Σ ln y_i (y > 0) and normalizes w = y / Σy;
    at the optimum every asset contributes σ_p / N (Spinu, 2013).
    """
    covariance = market.covariance
    n = market.n_assets
    if np.any(np.diag(covariance) <= 0):
        raise InvalidInputError("risk parity requires every asset to have positive variance")
    scaled = covariance * _scale(covariance)
    budget = 1 / n

    def objective(y: FloatArray) -> float:
        check_time_budget()
        return 0.5 * float(y @ scaled @ y) - budget * float(np.sum(np.log(y)))

    result = minimize(
        objective,
        1 / np.sqrt(np.diag(scaled)),
        jac=lambda y: scaled @ y - budget / y,
        method="L-BFGS-B",
        bounds=[(1e-12, None)] * n,
        options={"ftol": 1e-15, "gtol": 1e-12, "maxiter": 10_000},
    )
    weights = np.asarray(result.x, dtype=np.float64)
    weights = weights / weights.sum()

    _, contributions = risk_contributions(weights, covariance)
    shares = np.array([item.percent_contribution for item in contributions])
    if not result.success and float(np.max(np.abs(shares - budget))) > _RISK_PARITY_TOLERANCE:
        raise ConvergenceError(f"risk parity did not converge: {result.message}")
    if float(np.max(np.abs(shares - budget))) > _RISK_PARITY_TOLERANCE:
        raise ConvergenceError("risk parity did not reach equal risk contributions")
    return weights


def inverse_volatility(market: MarketInputs) -> FloatArray:
    """w_i = (1 / σ_i) / Σ_j (1 / σ_j), σ_i = √Σ_ii (correlations are ignored)."""
    sigmas = np.sqrt(np.diag(market.covariance))
    if np.any(sigmas == 0):
        raise DivisionByZeroError("inverse volatility is undefined for a zero-volatility asset")
    inverse = 1 / sigmas
    return inverse / inverse.sum()
