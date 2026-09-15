"""Market sensitivity and risk-adjusted performance."""

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from app.services.risk.drawdown import maximum_drawdown
from app.services.risk.returns import (
    ReturnType,
    annualize_dispersion,
    annualized_return,
    periodic_rate,
    validate_returns,
    wealth_index,
)
from app.services.statistics.descriptive import standard_deviation
from app.services.statistics.relationships import covariance, linear_regression, paired_arrays
from app.utils.math import safe_divide


def _pair(asset: Sequence[float], benchmark: Sequence[float], return_type: ReturnType) -> None:
    paired_arrays(asset, benchmark, x_name="asset_returns", y_name="benchmark_returns")
    validate_returns(asset, return_type, "asset_returns")
    validate_returns(benchmark, return_type, "benchmark_returns")


def beta(asset: Sequence[float], benchmark: Sequence[float]) -> float:
    """β = cov(asset, benchmark) / var(benchmark) (same ddof, so it cancels)."""
    cov = covariance(asset, benchmark, x_name="asset_returns", y_name="benchmark_returns")
    var = covariance(benchmark, benchmark, x_name="benchmark_returns", y_name="benchmark_returns")
    return safe_divide(cov, var, denominator_name="variance of benchmark_returns")


@dataclass(frozen=True, slots=True)
class RegressionAlpha:
    annualized_alpha: float
    periodic_alpha: float
    beta: float


def regression_alpha(
    asset: Sequence[float],
    benchmark: Sequence[float],
    risk_free_rate: float,
    periods_per_year: float,
    return_type: ReturnType,
) -> RegressionAlpha:
    """OLS on excess returns: (r_a − rf_p) = α + β (r_b − rf_p); annualized α = α × ppy."""
    _pair(asset, benchmark, return_type)
    rf = periodic_rate(risk_free_rate, periods_per_year, return_type)
    fit = linear_regression(
        [b - rf for b in benchmark],
        [a - rf for a in asset],
        x_name="benchmark_returns",
        y_name="asset_returns",
    )
    return RegressionAlpha(
        annualized_alpha=fit.intercept * periods_per_year,
        periodic_alpha=fit.intercept,
        beta=fit.slope,
    )


def downside_deviation(
    returns: Sequence[float],
    minimum_acceptable_return: float,
    periods_per_year: float,
    return_type: ReturnType,
) -> float:
    """Periodic downside deviation = √(Σ min(r − MAR_p, 0)² / N), N = all observations."""
    data = validate_returns(returns, return_type, "returns")
    mar = periodic_rate(minimum_acceptable_return, periods_per_year, return_type)
    shortfall = np.minimum(data - mar, 0.0)
    return math.sqrt(float(np.mean(shortfall**2)))


def sharpe_ratio(
    returns: Sequence[float],
    risk_free_rate: float,
    periods_per_year: float,
    return_type: ReturnType,
) -> float:
    """Sharpe = mean(r − rf_p) / σ(r − rf_p) × √ppy (sample σ)."""
    data = validate_returns(returns, return_type, "returns")
    excess = (data - periodic_rate(risk_free_rate, periods_per_year, return_type)).tolist()
    ratio = safe_divide(
        math.fsum(excess) / len(excess),
        standard_deviation(excess),
        denominator_name="standard deviation of excess returns",
    )
    return ratio * math.sqrt(periods_per_year)


def sortino_ratio(
    returns: Sequence[float],
    minimum_acceptable_return: float,
    periods_per_year: float,
    return_type: ReturnType,
) -> float:
    """Sortino = mean(r − MAR_p) / downside deviation × √ppy."""
    data = validate_returns(returns, return_type, "returns")
    mar = periodic_rate(minimum_acceptable_return, periods_per_year, return_type)
    deviation = downside_deviation(
        returns, minimum_acceptable_return, periods_per_year, return_type
    )
    ratio = safe_divide(
        float(np.mean(data - mar)), deviation, denominator_name="downside deviation"
    )
    return ratio * math.sqrt(periods_per_year)


def treynor_ratio(
    asset: Sequence[float],
    benchmark: Sequence[float],
    risk_free_rate: float,
    periods_per_year: float,
    return_type: ReturnType,
) -> float:
    """Treynor = (annualized asset return − rf) / β."""
    _pair(asset, benchmark, return_type)
    excess = annualized_return(asset, return_type, periods_per_year) - risk_free_rate
    return safe_divide(excess, beta(asset, benchmark), denominator_name="beta")


def calmar_ratio(
    returns: Sequence[float], periods_per_year: float, return_type: ReturnType
) -> float:
    """Calmar = annualized return / |maximum drawdown| over the full series."""
    drawdown = maximum_drawdown(wealth_index(returns, return_type)).max_drawdown
    return safe_divide(
        annualized_return(returns, return_type, periods_per_year),
        abs(drawdown),
        denominator_name="maximum drawdown",
    )


@dataclass(frozen=True, slots=True)
class InformationRatio:
    information_ratio: float
    annualized_active_return: float
    tracking_error: float


def information_ratio(
    asset: Sequence[float],
    benchmark: Sequence[float],
    periods_per_year: float,
    return_type: ReturnType,
) -> InformationRatio:
    """IR = mean(active) × ppy / (σ(active) × √ppy), active = asset − benchmark (arithmetic)."""
    _pair(asset, benchmark, return_type)
    active = [a - b for a, b in zip(asset, benchmark, strict=True)]
    annual_active = math.fsum(active) / len(active) * periods_per_year
    tracking = annualize_dispersion(standard_deviation(active), periods_per_year)
    return InformationRatio(
        information_ratio=safe_divide(annual_active, tracking, denominator_name="tracking error"),
        annualized_active_return=annual_active,
        tracking_error=tracking,
    )


@dataclass(frozen=True, slots=True)
class JensensAlpha:
    alpha: float
    beta: float
    asset_return: float
    benchmark_return: float


def jensens_alpha(
    asset: Sequence[float],
    benchmark: Sequence[float],
    risk_free_rate: float,
    periods_per_year: float,
    return_type: ReturnType,
) -> JensensAlpha:
    """Jensen's α = R_p − [rf + β (R_m − rf)] with annualized geometric returns."""
    _pair(asset, benchmark, return_type)
    asset_return = annualized_return(asset, return_type, periods_per_year)
    benchmark_return = annualized_return(benchmark, return_type, periods_per_year)
    sensitivity = beta(asset, benchmark)
    return JensensAlpha(
        alpha=asset_return - (risk_free_rate + sensitivity * (benchmark_return - risk_free_rate)),
        beta=sensitivity,
        asset_return=asset_return,
        benchmark_return=benchmark_return,
    )


@dataclass(frozen=True, slots=True)
class ModiglianiM2:
    m2: float
    sharpe_ratio: float
    benchmark_volatility: float


def modigliani_m2(
    asset: Sequence[float],
    benchmark: Sequence[float],
    risk_free_rate: float,
    periods_per_year: float,
    return_type: ReturnType,
) -> ModiglianiM2:
    """M² = Sharpe_p × σ_m + rf (annualized Sharpe and benchmark volatility)."""
    _pair(asset, benchmark, return_type)
    sharpe = sharpe_ratio(asset, risk_free_rate, periods_per_year, return_type)
    benchmark_volatility = annualize_dispersion(standard_deviation(benchmark), periods_per_year)
    return ModiglianiM2(
        m2=sharpe * benchmark_volatility + risk_free_rate,
        sharpe_ratio=sharpe,
        benchmark_volatility=benchmark_volatility,
    )
