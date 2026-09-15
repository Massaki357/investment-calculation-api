"""Descriptive statistics and bivariate relationships.

Single source of truth for variance, covariance, correlation and regression: the risk and portfolio
domains import these functions instead of re-implementing them.

Conventions: sample statistics (ddof = 1) by default; percentiles use linear interpolation;
skewness and excess kurtosis are bias-corrected (adjusted Fisher-Pearson) by default.
"""
