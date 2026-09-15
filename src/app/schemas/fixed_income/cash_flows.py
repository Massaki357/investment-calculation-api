from pydantic import Field

from app.schemas.fixed_income.common import FixedIncomeRequest


class IrrRequest(FixedIncomeRequest):
    cash_flows: list[float] = Field(
        min_length=2,
        max_length=1000,
        description="Cash flows at t = 0, 1, ..., n (equally spaced periods). Investments are "
        "negative, receipts positive.",
    )
    periods_per_year: int | None = Field(
        default=None,
        ge=1,
        le=365,
        description="Optional; adds the effective annual IRR = (1 + IRR)^periods_per_year − 1.",
    )
