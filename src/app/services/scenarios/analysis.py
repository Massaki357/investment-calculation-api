"""Aggregation of scenario outcomes and factor stress tests."""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.core.exceptions import InvalidInputError

PROBABILITY_TOLERANCE = 1e-6


def probability_weighted_value(values: Sequence[float], probabilities: Sequence[float]) -> float:
    """E[X] = Σ p_i × x_i, with probabilities ≥ 0 summing to 1 (tolerance 1e-6)."""
    if len(values) != len(probabilities) or not values:
        raise InvalidInputError("each scenario needs exactly one probability")
    if any(p < 0 for p in probabilities):
        raise InvalidInputError("probabilities cannot be negative")
    total = math.fsum(probabilities)
    if abs(total - 1) > PROBABILITY_TOLERANCE:
        raise InvalidInputError(f"probabilities must sum to 1 (received {total})")
    return math.fsum(p * v for p, v in zip(probabilities, values, strict=True))


@dataclass(frozen=True, slots=True)
class PositionImpact:
    name: str
    exposure: float
    shock_return: float
    pnl: float


@dataclass(frozen=True, slots=True)
class StressResult:
    scenario: str
    total_exposure: float
    total_pnl: float
    value_after: float
    return_on_gross_exposure: float | None
    positions: list[PositionImpact]


@dataclass(frozen=True, slots=True)
class Position:
    name: str
    exposure: float
    sensitivities: Mapping[str, float]


def stress_test(
    positions: Sequence[Position], scenario_name: str, shocks: Mapping[str, float]
) -> StressResult:
    """Linear factor stress test.

    shock_return_i = Σ_f sensitivity_(i,f) × shock_f (factors missing from the scenario are 0)
    P&L_i = exposure_i × shock_return_i; total P&L = Σ P&L_i
    return on gross exposure = total P&L / Σ |exposure_i|
    """
    impacts = []
    for position in positions:
        shock_return = math.fsum(
            beta * shocks.get(factor, 0.0) for factor, beta in position.sensitivities.items()
        )
        impacts.append(
            PositionImpact(
                name=position.name,
                exposure=position.exposure,
                shock_return=shock_return,
                pnl=position.exposure * shock_return,
            )
        )
    total_exposure = math.fsum(position.exposure for position in positions)
    gross = math.fsum(abs(position.exposure) for position in positions)
    total_pnl = math.fsum(impact.pnl for impact in impacts)
    return StressResult(
        scenario=scenario_name,
        total_exposure=total_exposure,
        total_pnl=total_pnl,
        value_after=total_exposure + total_pnl,
        return_on_gross_exposure=None if gross == 0 else total_pnl / gross,
        positions=impacts,
    )
