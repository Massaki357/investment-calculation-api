"""Fundamental analysis formulas.

Conventions shared by every module in this package:
- Rates are decimals (0.10 = 10%).
- A zero denominator raises DivisionByZeroError; a negative denominator returns the signed
  result without interpretation.
- Balance-sheet values are received already chosen by the caller (end-of-period or average).
- Capital expenditures, depreciation, interest expense and dividends are positive magnitudes.
"""
