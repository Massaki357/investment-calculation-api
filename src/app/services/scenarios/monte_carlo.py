"""Monte Carlo simulation of a value following geometric Brownian motion."""

import math
import secrets
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from app.core.exceptions import InvalidInputError, LimitExceededError
from app.core.time_budget import check_time_budget
from app.services.statistics.descriptive import FloatArray

# Simulations are generated in batches so memory stays bounded; the random stream is consumed in
# the same order for any batch size, so a seed always reproduces the same result.
_BATCH_CELLS = 1_000_000


@dataclass(frozen=True, slots=True)
class MonteCarloResult:
    seed_used: int
    horizon_years: float
    final_values: FloatArray
    max_drawdowns: FloatArray
    sample_paths: list[list[float]]
    theoretical_mean_final_value: float
    theoretical_median_final_value: float


def simulate_gbm(
    initial_value: float,
    expected_return: float,
    volatility: float,
    periods: int,
    simulations: int,
    *,
    periods_per_year: int = 252,
    seed: int | None = None,
    max_cells: int,
    sample_paths: int = 0,
) -> MonteCarloResult:
    """Simulate S_t = S_(t−1) × exp((μ − σ²/2) Δt + σ √Δt Z_t), Z_t ~ N(0, 1), Δt = 1 / ppy.

    μ (expected_return) and σ (volatility) are annual. E[S_T] = S_0 e^(μT) and
    median[S_T] = S_0 e^((μ − σ²/2) T), with T = periods / periods_per_year.
    """
    if initial_value <= 0:
        raise InvalidInputError("initial_value must be greater than zero")
    if volatility < 0:
        raise InvalidInputError("volatility cannot be negative")
    if periods < 1 or simulations < 1 or periods_per_year < 1:
        raise InvalidInputError("periods, simulations and periods_per_year must be at least 1")
    if simulations * periods > max_cells:
        raise LimitExceededError(
            f"simulations × periods = {simulations * periods} exceeds the limit of {max_cells}"
        )
    if not 0 <= sample_paths <= simulations:
        raise InvalidInputError("sample_paths must be between 0 and simulations")

    # Generated seeds stay below 2^53 so JSON clients (e.g. JavaScript) read them exactly.
    seed_used = secrets.randbits(53) if seed is None else seed
    generator = np.random.default_rng(seed_used)
    dt = 1 / periods_per_year
    drift = (expected_return - 0.5 * volatility**2) * dt
    diffusion = volatility * math.sqrt(dt)

    final_values = np.empty(simulations)
    max_drawdowns = np.empty(simulations)
    paths: list[list[float]] = []
    batch_size = max(1, _BATCH_CELLS // periods)
    log_initial = math.log(initial_value)

    for start in range(0, simulations, batch_size):
        check_time_budget()
        count = min(batch_size, simulations - start)
        shocks = generator.standard_normal((count, periods))
        log_paths = log_initial + np.cumsum(drift + diffusion * shocks, axis=1)
        with np.errstate(over="ignore"):
            values = np.exp(log_paths)
        if not np.all(np.isfinite(values)):
            raise InvalidInputError("simulated values overflow; reduce volatility or horizon")
        running_peak = np.maximum.accumulate(np.maximum(values, initial_value), axis=1)
        final_values[start : start + count] = values[:, -1]
        max_drawdowns[start : start + count] = np.min(values / running_peak - 1, axis=1)
        if len(paths) < sample_paths:
            needed = min(sample_paths - len(paths), count)
            paths.extend([initial_value, *row.tolist()] for row in values[:needed])

    horizon = periods / periods_per_year
    return MonteCarloResult(
        seed_used=seed_used,
        horizon_years=horizon,
        final_values=final_values,
        max_drawdowns=np.minimum(max_drawdowns, 0.0),
        sample_paths=paths,
        theoretical_mean_final_value=initial_value * math.exp(expected_return * horizon),
        theoretical_median_final_value=initial_value
        * math.exp((expected_return - 0.5 * volatility**2) * horizon),
    )


@dataclass(frozen=True, slots=True)
class DistributionSummary:
    mean: float
    standard_deviation: float
    minimum: float
    maximum: float
    percentiles: list[tuple[float, float]]


def summarize(values: FloatArray, percentile_ranks: Sequence[float]) -> DistributionSummary:
    """Mean, sample standard deviation (0 for a single value), extremes and linear percentiles."""
    ranks = list(percentile_ranks)
    if any(rank < 0 or rank > 100 for rank in ranks):
        raise InvalidInputError("percentiles must be between 0 and 100")
    levels = np.percentile(values, ranks) if ranks else np.array([])
    return DistributionSummary(
        mean=float(values.mean()),
        standard_deviation=float(values.std(ddof=1)) if values.size > 1 else 0.0,
        minimum=float(values.min()),
        maximum=float(values.max()),
        percentiles=[
            (float(rank), float(level)) for rank, level in zip(ranks, levels, strict=True)
        ],
    )


@dataclass(frozen=True, slots=True)
class TailLoss:
    value_at_risk: float
    expected_shortfall: float


def tail_loss(final_values: FloatArray, initial_value: float, confidence: float) -> TailLoss:
    """Losses versus the initial value: VaR = S_0 − q_(1−c)(S_T); ES = S_0 − mean(S_T | S_T ≤ q)."""
    if not 0 < confidence < 1:
        raise InvalidInputError("confidence must be between 0 and 1")
    threshold = float(np.quantile(final_values, 1 - confidence))
    tail = final_values[final_values <= threshold]
    return TailLoss(
        value_at_risk=initial_value - threshold,
        expected_shortfall=initial_value - float(tail.mean()),
    )
