"""Documented field types shared across domains.

Validation rule of thumb:
- Constraints on a single field that always hold (price > 0, tax rate in [0, 1], magnitudes ≥ 0)
  are schema rules and produce HTTP 422.
- Formula-specific or cross-field conditions (zero denominators, discount rate ≤ growth rate)
  are enforced by services and produce HTTP 400.
"""

from typing import Annotated

from pydantic import Field

SharePrice = Annotated[float, Field(gt=0, description="Price per share (amount, > 0).")]
SharesOutstanding = Annotated[
    float, Field(gt=0, description="Number of (diluted) shares outstanding (> 0).")
]
TaxRate = Annotated[
    float,
    Field(ge=0, le=1, description="Effective tax rate in decimal form (0.34 = 34%), in [0, 1]."),
]
DiscountRate = Annotated[
    float,
    Field(gt=-1, description="Discount rate per period in decimal form (0.10 = 10%), > −1."),
]
GrowthRate = Annotated[
    float,
    Field(gt=-1, description="Growth rate per period in decimal form (0.03 = 3%), > −1."),
]
RateDecimal = Annotated[float, Field(description="Rate in decimal form (0.05 = 5%).")]
Beta = Annotated[float, Field(description="Beta coefficient (dimensionless).")]
CashFlowSeries = Annotated[
    list[float],
    Field(
        min_length=1,
        max_length=1000,
        description="Cash flows for periods 1..n, in chronological order (1 to 1000 items).",
    ),
]
