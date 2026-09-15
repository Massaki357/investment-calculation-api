"""Technical analysis routes: /api/v1/technical/*."""

from typing import cast

from fastapi import APIRouter

from app.api.endpoint_specs import CalculationEndpoint, add_calculation_endpoints
from app.schemas.technical import (
    AtrRequest,
    AverageRequest,
    BollingerRequest,
    BollingerResponse,
    CciRequest,
    HistoricalVolatilityRequest,
    IndicatorResponse,
    MacdRequest,
    MacdResponse,
    MfiRequest,
    ObvRequest,
    RocRequest,
    RsiRequest,
    StochasticRequest,
    StochasticResponse,
    VwapRequest,
    VwmaRequest,
    WilliamsRRequest,
)
from app.services.technical import averages, momentum, volatility, volume
from app.services.technical.common import Series, last

router = APIRouter(prefix="/technical")
averages_router = APIRouter(tags=["Technical · Moving averages"])
momentum_router = APIRouter(tags=["Technical · Momentum"])
volatility_router = APIRouter(tags=["Technical · Volatility"])
volume_router = APIRouter(tags=["Technical · Volume"])

# Sample daily closing prices for the documentation examples, oldest first.
CLOSES = [
    44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42, 45.84, 46.08,
    45.89, 46.03, 45.61, 46.28, 46.28, 46.00, 46.03, 46.41, 46.22, 45.64,
]  # fmt: skip
HIGHS = [round(price + 0.35, 2) for price in CLOSES]
LOWS = [round(price - 0.40, 2) for price in CLOSES]
VOLUMES = [
    1200.0, 1350.0, 980.0, 1600.0, 1420.0, 1510.0, 1280.0, 1330.0, 1700.0, 1450.0,
    1190.0, 1240.0, 1560.0, 1620.0, 1010.0, 1150.0, 1080.0, 1390.0, 1270.0, 1880.0,
]  # fmt: skip

WARMUP_NOTE = (
    "Output series have the same length as the input; values are null during warm-up (and "
    "where the indicator is undefined)."
)
HLC_NOTE = "high, low and close must have the same length, with low ≤ close ≤ high."


def _indicator(metric: str, series: Series, **parameters: int | float) -> IndicatorResponse:
    return IndicatorResponse(
        metric=metric, parameters=parameters, values=series, latest=last(series)
    )


def _sma(r: AverageRequest) -> IndicatorResponse:
    return _indicator("SMA", averages.sma(r.prices, r.period), period=r.period)


def _ema(r: AverageRequest) -> IndicatorResponse:
    return _indicator("EMA", averages.ema(r.prices, r.period), period=r.period)


def _wma(r: AverageRequest) -> IndicatorResponse:
    return _indicator("WMA", averages.wma(r.prices, r.period), period=r.period)


def _vwma(r: VwmaRequest) -> IndicatorResponse:
    return _indicator("VWMA", averages.vwma(r.prices, r.volumes, r.period), period=r.period)


def _rsi(r: RsiRequest) -> IndicatorResponse:
    return _indicator("RSI", momentum.rsi(r.prices, r.period), period=r.period)


def _roc(r: RocRequest) -> IndicatorResponse:
    return _indicator("ROC", momentum.roc(r.prices, r.period), period=r.period)


def _macd(r: MacdRequest) -> MacdResponse:
    result = momentum.macd(r.prices, r.fast_period, r.slow_period, r.signal_period)
    return MacdResponse(
        metric="MACD",
        parameters={
            "fast_period": r.fast_period,
            "slow_period": r.slow_period,
            "signal_period": r.signal_period,
        },
        macd=result.macd,
        signal=result.signal,
        histogram=result.histogram,
        latest={
            "macd": last(result.macd),
            "signal": last(result.signal),
            "histogram": last(result.histogram),
        },
    )


def _stochastic(r: StochasticRequest) -> StochasticResponse:
    result = momentum.stochastic(r.high, r.low, r.close, r.k_period, r.d_period)
    return StochasticResponse(
        metric="Stochastic Oscillator",
        parameters={"k_period": r.k_period, "d_period": r.d_period},
        percent_k=result.percent_k,
        percent_d=result.percent_d,
        latest={"percent_k": last(result.percent_k), "percent_d": last(result.percent_d)},
    )


def _williams_r(r: WilliamsRRequest) -> IndicatorResponse:
    series = momentum.williams_r(r.high, r.low, r.close, r.period)
    return _indicator("Williams %R", series, period=r.period)


def _cci(r: CciRequest) -> IndicatorResponse:
    return _indicator("CCI", momentum.cci(r.high, r.low, r.close, r.period), period=r.period)


def _atr(r: AtrRequest) -> IndicatorResponse:
    return _indicator("ATR", volatility.atr(r.high, r.low, r.close, r.period), period=r.period)


def _bollinger(r: BollingerRequest) -> BollingerResponse:
    result = volatility.bollinger_bands(r.prices, r.period, r.standard_deviations)
    return BollingerResponse(
        metric="Bollinger Bands",
        parameters={"period": r.period, "standard_deviations": r.standard_deviations},
        middle=result.middle,
        upper=result.upper,
        lower=result.lower,
        percent_b=result.percent_b,
        bandwidth=result.bandwidth,
        latest={
            "middle": last(result.middle),
            "upper": last(result.upper),
            "lower": last(result.lower),
            "percent_b": last(result.percent_b),
            "bandwidth": last(result.bandwidth),
        },
    )


def _historical_volatility(r: HistoricalVolatilityRequest) -> IndicatorResponse:
    series = volatility.historical_volatility(r.prices, r.period, r.periods_per_year)
    return _indicator(
        "Historical Volatility", series, period=r.period, periods_per_year=r.periods_per_year
    )


def _obv(r: ObvRequest) -> IndicatorResponse:
    return _indicator("OBV", volume.obv(r.close, r.volumes))


def _vwap(r: VwapRequest) -> IndicatorResponse:
    # The request validator guarantees prices or a complete high/low/close set.
    if r.prices is not None:
        prices = r.prices
    else:
        prices = volume.typical_prices(
            cast(list[float], r.high), cast(list[float], r.low), cast(list[float], r.close)
        )
    return _indicator("VWAP", volume.vwap(prices, r.volumes))


def _mfi(r: MfiRequest) -> IndicatorResponse:
    series = volume.money_flow_index(r.high, r.low, r.close, r.volumes, r.period)
    return _indicator("Money Flow Index", series, period=r.period)


AVERAGES = (
    CalculationEndpoint(
        path="/sma",
        title="SMA",
        summary="Simple moving average",
        formulas=("SMA_t = (P_(t−N+1) + … + P_t) / N",),
        request_model=AverageRequest,
        response_model=IndicatorResponse,
        compute=_sma,
        examples={"period_5": {"prices": CLOSES, "period": 5}},
        notes=("First value at index N − 1.", WARMUP_NOTE),
    ),
    CalculationEndpoint(
        path="/ema",
        title="EMA",
        summary="Exponential moving average",
        formulas=("EMA_(N−1) = SMA_N", "EMA_t = α × P_t + (1 − α) × EMA_(t−1), α = 2 / (N + 1)"),
        request_model=AverageRequest,
        response_model=IndicatorResponse,
        compute=_ema,
        examples={"period_5": {"prices": CLOSES, "period": 5}},
        notes=("Seeded with the SMA of the first N prices (TA-Lib convention).", WARMUP_NOTE),
    ),
    CalculationEndpoint(
        path="/wma",
        title="WMA",
        summary="Linearly weighted moving average",
        formulas=("WMA_t = Σ_(i=1..N) i × P_(t−N+i) / (N (N + 1) / 2)",),
        request_model=AverageRequest,
        response_model=IndicatorResponse,
        compute=_wma,
        examples={"period_5": {"prices": CLOSES, "period": 5}},
        notes=("The most recent price has the largest weight (N).", WARMUP_NOTE),
    ),
    CalculationEndpoint(
        path="/vwma",
        title="VWMA",
        summary="Volume-weighted moving average",
        formulas=("VWMA_t = Σ (P × V) / Σ V over the last N periods",),
        request_model=VwmaRequest,
        response_model=IndicatorResponse,
        compute=_vwma,
        examples={"period_5": {"prices": CLOSES, "volumes": VOLUMES, "period": 5}},
        notes=("null where the window volume is zero.", WARMUP_NOTE),
    ),
)

MOMENTUM = (
    CalculationEndpoint(
        path="/rsi",
        title="RSI",
        summary="Relative Strength Index (Wilder)",
        formulas=(
            "first average gain/loss = mean of the first N gains/losses",
            "avg_t = (avg_(t−1) × (N − 1) + current) / N",
            "RSI = 100 − 100 / (1 + avg_gain / avg_loss)",
        ),
        request_model=RsiRequest,
        response_model=IndicatorResponse,
        compute=_rsi,
        examples={"wilder_14": {"prices": CLOSES, "period": 14}},
        notes=(
            "Scale 0–100 (unit index). First value at index N; requires N + 1 prices.",
            "No losses in the window gives 100; no movement at all gives 50.",
            WARMUP_NOTE,
        ),
    ),
    CalculationEndpoint(
        path="/macd",
        title="MACD",
        summary="Moving Average Convergence Divergence",
        formulas=(
            "MACD = EMA_fast(P) − EMA_slow(P)",
            "signal = EMA_signal(MACD), histogram = MACD − signal",
        ),
        request_model=MacdRequest,
        response_model=MacdResponse,
        compute=_macd,
        examples={
            "short_periods": {
                "prices": CLOSES,
                "fast_period": 5,
                "slow_period": 10,
                "signal_period": 4,
            }
        },
        notes=(
            "Defaults 12/26/9; EMAs are SMA-seeded. Requires slow + signal − 1 prices.",
            "fast_period must be smaller than slow_period.",
            WARMUP_NOTE,
        ),
    ),
    CalculationEndpoint(
        path="/roc",
        title="ROC",
        summary="Rate of change",
        formulas=("ROC_t = P_t / P_(t−N) − 1",),
        request_model=RocRequest,
        response_model=IndicatorResponse,
        compute=_roc,
        examples={"period_10": {"prices": CLOSES, "period": 10}},
        notes=("Decimal form (0.05 = 5%), not percentage points.", WARMUP_NOTE),
    ),
    CalculationEndpoint(
        path="/stochastic",
        title="Stochastic Oscillator",
        summary="Stochastic oscillator (%K and %D)",
        formulas=(
            "%K = 100 × (C_t − lowest low_N) / (highest high_N − lowest low_N)",
            "%D = SMA_d(%K)",
        ),
        request_model=StochasticRequest,
        response_model=StochasticResponse,
        compute=_stochastic,
        examples={
            "k14_d3": {"high": HIGHS, "low": LOWS, "close": CLOSES, "k_period": 14, "d_period": 3}
        },
        notes=(HLC_NOTE, "Fast stochastic; %K is null when the window range is zero.", WARMUP_NOTE),
    ),
    CalculationEndpoint(
        path="/williams-r",
        title="Williams %R",
        summary="Williams %R",
        formulas=("%R = −100 × (highest high_N − C_t) / (highest high_N − lowest low_N)",),
        request_model=WilliamsRRequest,
        response_model=IndicatorResponse,
        compute=_williams_r,
        examples={"period_14": {"high": HIGHS, "low": LOWS, "close": CLOSES, "period": 14}},
        notes=(HLC_NOTE, "Scale −100 (at the low) to 0 (at the high).", WARMUP_NOTE),
    ),
    CalculationEndpoint(
        path="/cci",
        title="CCI",
        summary="Commodity Channel Index",
        formulas=(
            "TP = (H + L + C) / 3",
            "CCI = (TP − SMA_N(TP)) / (0.015 × mean absolute deviation_N(TP))",
        ),
        request_model=CciRequest,
        response_model=IndicatorResponse,
        compute=_cci,
        examples={"period_10": {"high": HIGHS, "low": LOWS, "close": CLOSES, "period": 10}},
        notes=(
            HLC_NOTE,
            "Lambert's constant 0.015; null when the mean deviation is zero.",
            WARMUP_NOTE,
        ),
    ),
)

VOLATILITY = (
    CalculationEndpoint(
        path="/atr",
        title="ATR",
        summary="Average True Range (Wilder)",
        formulas=(
            "TR_t = max(H_t − L_t, |H_t − C_(t−1)|, |L_t − C_(t−1)|), t ≥ 1",
            "ATR_N = mean(TR_1..TR_N); ATR_t = (ATR_(t−1) × (N − 1) + TR_t) / N",
        ),
        request_model=AtrRequest,
        response_model=IndicatorResponse,
        compute=_atr,
        examples={"period_14": {"high": HIGHS, "low": LOWS, "close": CLOSES, "period": 14}},
        notes=(HLC_NOTE, "Price units (amount). First value at index N.", WARMUP_NOTE),
    ),
    CalculationEndpoint(
        path="/bollinger-bands",
        title="Bollinger Bands",
        summary="Bollinger Bands, %B and bandwidth",
        formulas=(
            "middle = SMA_N(P), upper/lower = middle ± k × σ_N (population σ)",
            "%B = (P − lower) / (upper − lower); bandwidth = (upper − lower) / middle",
        ),
        request_model=BollingerRequest,
        response_model=BollingerResponse,
        compute=_bollinger,
        examples={"period_10": {"prices": CLOSES, "period": 10, "standard_deviations": 2}},
        notes=(
            "Population standard deviation, as defined by Bollinger.",
            "%B is null when the bands collapse (zero σ).",
            WARMUP_NOTE,
        ),
    ),
    CalculationEndpoint(
        path="/historical-volatility",
        title="Historical Volatility",
        summary="Rolling historical volatility of log returns",
        formulas=("HV_t = σ(ln(P_i / P_(i−1)), last N returns) × √periods_per_year",),
        request_model=HistoricalVolatilityRequest,
        response_model=IndicatorResponse,
        compute=_historical_volatility,
        examples={"period_10": {"prices": CLOSES, "period": 10}},
        notes=("Sample σ (ddof = 1), annualized decimal. First value at index N.", WARMUP_NOTE),
    ),
)

VOLUME = (
    CalculationEndpoint(
        path="/obv",
        title="OBV",
        summary="On-Balance Volume",
        formulas=("OBV_0 = 0; OBV_t = OBV_(t−1) ± V_t when C_t is above / below C_(t−1)",),
        request_model=ObvRequest,
        response_model=IndicatorResponse,
        compute=_obv,
        examples={"daily": {"close": CLOSES, "volumes": VOLUMES}},
        notes=("Cumulative; unchanged when the close is unchanged.",),
    ),
    CalculationEndpoint(
        path="/vwap",
        title="VWAP",
        summary="Volume-weighted average price (cumulative)",
        formulas=(
            "VWAP_t = Σ_(i≤t) P_i × V_i / Σ_(i≤t) V_i",
            "with high/low/close: P = (H + L + C) / 3",
        ),
        request_model=VwapRequest,
        response_model=IndicatorResponse,
        compute=_vwap,
        examples={
            "typical_price": {"high": HIGHS, "low": LOWS, "close": CLOSES, "volumes": VOLUMES},
            "close_only": {"prices": CLOSES, "volumes": VOLUMES},
        },
        notes=(
            "Accumulated over the whole series (no session reset); send one session to get an "
            "intraday VWAP.",
            "null while cumulative volume is zero.",
        ),
    ),
    CalculationEndpoint(
        path="/money-flow-index",
        title="Money Flow Index",
        summary="Money Flow Index",
        formulas=(
            "TP = (H + L + C) / 3, raw flow = TP × V",
            "MFI = 100 − 100 / (1 + Σ positive flow_N / Σ negative flow_N)",
        ),
        request_model=MfiRequest,
        response_model=IndicatorResponse,
        compute=_mfi,
        examples={
            "period_14": {
                "high": HIGHS,
                "low": LOWS,
                "close": CLOSES,
                "volumes": VOLUMES,
                "period": 14,
            }
        },
        notes=(
            HLC_NOTE,
            "Flow is positive when TP rises and negative when it falls. Scale 0–100.",
            WARMUP_NOTE,
        ),
    ),
)

add_calculation_endpoints(averages_router, AVERAGES)
add_calculation_endpoints(momentum_router, MOMENTUM)
add_calculation_endpoints(volatility_router, VOLATILITY)
add_calculation_endpoints(volume_router, VOLUME)
for _router in (averages_router, momentum_router, volatility_router, volume_router):
    router.include_router(_router)

METRIC_ENDPOINTS = ()
CALCULATION_ENDPOINTS = (*AVERAGES, *MOMENTUM, *VOLATILITY, *VOLUME)
