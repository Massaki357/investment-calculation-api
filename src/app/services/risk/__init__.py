"""Risk and risk-adjusted performance formulas on periodic return series.

Conventions:
- Returns are simple by default (P_t / P_{t−1} − 1); log returns (ln(P_t / P_{t−1})) are supported.
- Annual rates (risk-free, MAR) are converted to the return period: (1 + r)^(1/ppy) − 1 for simple
  returns, ln(1 + r) / ppy for log returns.
- Annualization: geometric for returns, × √ppy for dispersion (periods_per_year defaults to 252).
- Dispersion uses sample statistics (ddof = 1) unless stated otherwise.
- VaR and expected shortfall are reported as positive losses.
"""
