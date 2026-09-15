"""Valuation formulas: time value of money, DCF, dividend discount models and cost of capital.

Conventions:
- Rates are decimals per period (0.10 = 10%) and must be greater than −1.
- Cash flow i (1-based) occurs at the end of period i unless the mid-year convention is used,
  in which case it is discounted at i − 0.5.
- Terminal values are always discounted from the end of the last explicit period.
"""
