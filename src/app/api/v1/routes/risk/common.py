from typing import cast

from app.schemas.risk import _PairedSeries, _SingleSeries
from app.services.risk.returns import ReturnType, returns_from_prices, validate_returns

RETURNS_EXAMPLE = [0.012, -0.008, 0.015, -0.021, 0.009, 0.004, -0.013, 0.018, 0.007, -0.005]
BENCHMARK_EXAMPLE = [0.010, -0.006, 0.011, -0.018, 0.007, 0.005, -0.010, 0.014, 0.006, -0.004]
PRICES_EXAMPLE = [100.0, 101.2, 100.4, 101.9, 99.8, 100.7, 101.1, 99.8, 101.6, 102.3, 101.8]

SERIES_NOTE = "Send returns or prices (not both); prices are converted with return_type."
PAIRED_NOTE = (
    "Send asset_returns or asset_prices and benchmark_returns or benchmark_prices; both series "
    "must cover the same periods (same length after conversion)."
)
ANNUAL_RATE_NOTE = (
    "Annual rates are converted to the return period: (1 + r)^(1/ppy) − 1 for simple returns, "
    "ln(1 + r) / ppy for log returns."
)


def _resolve(
    returns: list[float] | None, prices: list[float] | None, return_type: ReturnType, name: str
) -> list[float]:
    # The request validators guarantee exactly one of returns / prices per series.
    series = (
        returns
        if returns is not None
        else returns_from_prices(cast(list[float], prices), return_type)
    )
    validate_returns(series, return_type, name)
    return series


def single_returns(request: _SingleSeries) -> list[float]:
    return _resolve(request.returns, request.prices, request.return_type, "returns")


def paired_returns(request: _PairedSeries) -> tuple[list[float], list[float]]:
    asset = _resolve(
        request.asset_returns, request.asset_prices, request.return_type, "asset_returns"
    )
    benchmark = _resolve(
        request.benchmark_returns,
        request.benchmark_prices,
        request.return_type,
        "benchmark_returns",
    )
    return asset, benchmark
