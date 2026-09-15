"""Portfolio analytics and optimization.

Conventions:
- Weights are decimals that sum to 1 (tolerance 1e-6). Negative weights (shorts) are allowed in
  analytics; concentration and risk parity require long-only weights.
- Returns matrices have one row per period and one column per asset; they are simple returns
  (log returns do not aggregate across assets).
- Estimates from a returns matrix are annualized: expected return = mean × ppy (arithmetic) and
  covariance = sample covariance × ppy. A covariance matrix sent directly is used as-is, so results
  are expressed in its period.
"""
