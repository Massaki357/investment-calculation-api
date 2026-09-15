"""Volume indicators."""

from collections.abc import Sequence

import numpy as np

from app.services.technical.common import (
    Series,
    as_ohlc,
    as_series,
    as_volumes,
    pad,
    ratio_index,
    require_length,
    require_period,
)


def obv(close: Sequence[float], volumes: Sequence[float]) -> Series:
    """On-Balance Volume.

    OBV_0 = 0; OBV_t = OBV_(t−1) + V_t if C_t > C_(t−1), − V_t if C_t < C_(t−1), else unchanged.
    """
    closes = as_series(close, "close", positive=True)
    volume = as_volumes(volumes, closes.size)
    direction = np.sign(np.diff(closes))
    return [0.0, *(float(v) for v in np.cumsum(direction * volume[1:]))]


def vwap(prices: Sequence[float], volumes: Sequence[float]) -> Series:
    """Cumulative VWAP_t = Σ_(i≤t) P_i V_i / Σ_(i≤t) V_i; None while cumulative volume is zero."""
    data = as_series(prices, "prices", positive=True)
    volume = as_volumes(volumes, data.size)
    traded_value = np.cumsum(data * volume)
    cumulative_volume = np.cumsum(volume)
    return [
        None if v == 0 else float(tv / v)
        for tv, v in zip(traded_value, cumulative_volume, strict=True)
    ]


def typical_prices(
    high: Sequence[float], low: Sequence[float], close: Sequence[float]
) -> list[float]:
    return [float(value) for value in as_ohlc(high, low, close).typical_price]


def money_flow_index(
    high: Sequence[float],
    low: Sequence[float],
    close: Sequence[float],
    volumes: Sequence[float],
    period: int = 14,
) -> Series:
    """MFI = 100 − 100 / (1 + positive flow / negative flow) over the last N periods.

    TP = (H + L + C) / 3, raw flow = TP × V; a period's flow is positive when TP_t > TP_(t−1) and
    negative when TP_t < TP_(t−1). First value at t = N.
    """
    require_period(period)
    bar = as_ohlc(high, low, close)
    volume = as_volumes(volumes, bar.close.size)
    require_length(bar.close.size, period + 1, f"MFI({period})")
    tp = bar.typical_price
    flow = tp[1:] * volume[1:]
    change = np.diff(tp)
    positive = np.where(change > 0, flow, 0.0)
    negative = np.where(change < 0, flow, 0.0)
    values = [
        ratio_index(
            float(positive[end - period : end].sum()), float(negative[end - period : end].sum())
        )
        for end in range(period, flow.size + 1)
    ]
    return pad(values, bar.close.size)
