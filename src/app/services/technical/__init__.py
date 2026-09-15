"""Technical analysis indicators.

Conventions:
- Every output series has the same length as the input; positions without enough history
  (warm-up) are None. A value can also be None where the indicator is undefined (e.g. zero range).
- EMA is seeded with the SMA of the first `period` values, α = 2 / (period + 1).
- RSI and ATR use Wilder smoothing (α = 1 / period), seeded with a simple average.
- Oscillators (RSI, Stochastic, Williams %R, MFI, CCI) keep their conventional scale; ROC and
  historical volatility are decimals.
- Each window is computed independently (no running sums), so precision does not degrade on long
  series.
"""
