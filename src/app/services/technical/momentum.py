"""Momentum oscillators."""

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from app.core.exceptions import InvalidInputError
from app.services.technical.common import (
    Series,
    as_ohlc,
    as_series,
    pad,
    ratio_index,
    require_length,
    require_period,
    rolling_mean_optional,
    rolling_reduce,
    seeded_ema,
    windows,
)


def rsi(prices: Sequence[float], period: int = 14) -> Series:
    """Wilder RSI.

    Δ_t = P_t − P_(t−1); first averages = mean of the first N gains / losses (RSI at t = N);
    then avg_t = (avg_(t−1) × (N − 1) + current) / N; RSI = 100 − 100 / (1 + avg_gain / avg_loss).
    """
    require_period(period)
    data = as_series(prices, "prices", positive=True)
    require_length(data.size, period + 1, f"RSI({period})")
    changes = np.diff(data)
    gains, losses = np.maximum(changes, 0.0), np.maximum(-changes, 0.0)
    alpha = 1 / period
    avg_gain = seeded_ema(gains, period, alpha)
    avg_loss = seeded_ema(losses, period, alpha)
    values = [ratio_index(gain, loss) for gain, loss in zip(avg_gain, avg_loss, strict=True)]
    return pad(values, data.size)


@dataclass(frozen=True, slots=True)
class Macd:
    macd: Series
    signal: Series
    histogram: Series


def macd(
    prices: Sequence[float], fast_period: int = 12, slow_period: int = 26, signal_period: int = 9
) -> Macd:
    """MACD = EMA_fast − EMA_slow; signal = EMA_signal(MACD); histogram = MACD − signal."""
    for value, name in (
        (fast_period, "fast_period"),
        (slow_period, "slow_period"),
        (signal_period, "signal_period"),
    ):
        require_period(value, name)
    if fast_period >= slow_period:
        raise InvalidInputError("fast_period must be smaller than slow_period")
    data = as_series(prices, "prices", positive=True)
    require_length(
        data.size,
        slow_period + signal_period - 1,
        f"MACD({fast_period},{slow_period},{signal_period})",
    )

    fast = seeded_ema(data, fast_period, 2 / (fast_period + 1))
    slow = seeded_ema(data, slow_period, 2 / (slow_period + 1))
    macd_line = fast[slow_period - fast_period :] - slow
    signal_line = seeded_ema(macd_line, signal_period, 2 / (signal_period + 1))
    histogram = macd_line[signal_period - 1 :] - signal_line
    return Macd(
        macd=pad(macd_line, data.size),
        signal=pad(signal_line, data.size),
        histogram=pad(histogram, data.size),
    )


def roc(prices: Sequence[float], period: int = 12) -> Series:
    """ROC_t = P_t / P_(t−N) − 1 (decimal)."""
    require_period(period)
    data = as_series(prices, "prices", positive=True)
    require_length(data.size, period + 1, f"ROC({period})")
    return pad(data[period:] / data[:-period] - 1, data.size)


def _range_position(
    high: Sequence[float], low: Sequence[float], close: Sequence[float], period: int, name: str
) -> tuple[int, list[float | None]]:
    """(C_t − lowest low) / (highest high − lowest low) over the window; None for a zero range."""
    require_period(period)
    bar = as_ohlc(high, low, close)
    require_length(bar.close.size, period, f"{name}({period})")
    highest = windows(bar.high, period).max(axis=1)
    lowest = windows(bar.low, period).min(axis=1)
    closes = bar.close[period - 1 :]
    positions = [
        None if hh == ll else float((c - ll) / (hh - ll))
        for c, hh, ll in zip(closes, highest, lowest, strict=True)
    ]
    return bar.close.size, positions


@dataclass(frozen=True, slots=True)
class Stochastic:
    percent_k: Series
    percent_d: Series


def stochastic(
    high: Sequence[float],
    low: Sequence[float],
    close: Sequence[float],
    k_period: int = 14,
    d_period: int = 3,
) -> Stochastic:
    """%K = 100 × (C − LL_N) / (HH_N − LL_N); %D = SMA_d(%K)."""
    require_period(d_period, "d_period")
    total, positions = _range_position(high, low, close, k_period, "Stochastic")
    percent_k = [None if p is None else 100 * p for p in positions]
    require_length(len(percent_k), d_period, f"Stochastic %D({d_period})")
    return Stochastic(
        percent_k=pad(percent_k, total),
        percent_d=pad(rolling_mean_optional(percent_k, d_period), total),
    )


def williams_r(
    high: Sequence[float], low: Sequence[float], close: Sequence[float], period: int = 14
) -> Series:
    """%R = −100 × (HH_N − C) / (HH_N − LL_N), from −100 (at the low) to 0 (at the high)."""
    total, positions = _range_position(high, low, close, period, "Williams %R")
    return pad([None if p is None else -100 * (1 - p) for p in positions], total)


def cci(
    high: Sequence[float], low: Sequence[float], close: Sequence[float], period: int = 20
) -> Series:
    """CCI = (TP − SMA_N(TP)) / (0.015 × mean deviation), TP = (H + L + C) / 3."""
    require_period(period)
    bar = as_ohlc(high, low, close)
    require_length(bar.close.size, period, f"CCI({period})")
    means = windows(bar.typical_price, period).mean(axis=1)
    deviations = rolling_reduce(
        bar.typical_price,
        period,
        lambda rows: np.abs(rows - rows.mean(axis=1, keepdims=True)).mean(axis=1),
    )
    latest = bar.typical_price[period - 1 :]
    values = [
        None if md == 0 else float((tp - m) / (0.015 * md))
        for tp, m, md in zip(latest, means, deviations, strict=True)
    ]
    return pad(values, bar.close.size)
