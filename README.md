# Investment Calculation API

Stateless, deterministic HTTP microservice for investment calculations.

**Receives data → calculates → returns results.**

It is consumed by JARVIS (the main AI system) over HTTP/REST. This service:

- does **not** fetch prices, news or any market data;
- does **not** use LLMs, agents or prompts;
- does **not** issue buy/sell/hold recommendations or opinions;
- does **not** access JARVIS's code, database or API.

> **Status:** Phase 3 complete — API foundation, Fundamental Analysis (59 endpoints) and
> Valuation (21 endpoints).
> See [Roadmap](#roadmap).

---

## Architecture

```text
JARVIS ──HTTP/REST──▶ Investment Calculation API (FastAPI)

HTTP request
  → RequestContextMiddleware (request id, access log, timing)
  → CORS (only when CORS_ORIGINS is set)
  → Router /api/v1/...          (thin: no math)
  → Pydantic request schema     (validation)
  → Service                     (pure functions: numbers in, numbers out)
  → Pydantic response model
  → HTTP response
       ↘ domain exceptions → error handlers → {"error": {...}}
```

### Project layout

```text
investment-calculation-api/
├── pyproject.toml / uv.lock
├── Dockerfile / docker-compose.yml
├── .env.example
├── src/app/
│   ├── main.py              # create_app() factory + ASGI `app`
│   ├── __main__.py          # `python -m app` (host/port from env)
│   ├── core/                # config, exceptions, error handlers, logging, middleware, security
│   ├── api/
│   │   ├── health.py        # GET /health
│   │   ├── endpoint_specs.py   # declarative MetricEndpoint / CalculationEndpoint registration
│   │   └── v1/
│   │       ├── router.py    # aggregates domain routers under /api/v1
│   │       └── routes/<domain>/      # one module per group (multiples, dcf, ddm, ...)
│   ├── schemas/             # common.py + one package per domain (request/response models)
│   ├── services/            # pure calculation functions per domain
│   └── utils/               # safe_divide, ensure_finite, length guards
└── tests/
    ├── unit/                # formula / pure-function tests
    └── api/                 # request → endpoint → response tests
```

Design rules:

- **Services never import FastAPI.** They are pure functions that raise domain exceptions.
- **Routers contain no math.** They map schema → service → response model.
- **Versioned by package.** `/api/v2` will be a sibling package; v1 stays untouched.
- **Sync endpoints (`def`).** Calculations are CPU-bound; FastAPI runs them in a threadpool.

### Adding a calculation

1. Write a pure function in `services/<domain>/` (raise `CalculationError` subclasses on invalid math).
2. Add its request model in `schemas/<domain>/` (reuse the documented field types).
3. Declare a `MetricEndpoint` (single value) or a `CalculationEndpoint` (structured response
   model) in `api/v1/routes/<domain>/`. Docs, request/response examples and error responses
   are generated, and every example is executed at import time so documentation cannot drift
   from the code.
4. Add unit tests for the formula and a normal/edge/invalid case to the API test table — a guard
   test fails if an endpoint has no cases.

Shared, documented field types live in `schemas/fields.py`.

---

## Requirements

- Python 3.12+ (developed on 3.13)
- [uv](https://docs.astral.sh/uv/)
- Docker + Docker Compose (optional)

## Installation

```bash
cd investment-calculation-api
uv sync                  # creates .venv and installs runtime + dev dependencies
cp .env.example .env     # optional: adjust settings
```

## Running locally

```bash
uv run uvicorn app.main:app --reload
# or, honouring APP_HOST / APP_PORT from the environment:
uv run python -m app
```

- Swagger UI: <http://localhost:8000/docs>
- ReDoc: <http://localhost:8000/redoc>
- OpenAPI JSON: <http://localhost:8000/openapi.json>

## Running with Docker

```bash
docker compose up --build
```

The API is served on `http://localhost:${HOST_PORT:-8000}`. The container runs as a non-root
user with a read-only filesystem and a `HEALTHCHECK` on `/health`
(`docker compose ps` shows `healthy`).

---

## Configuration

All configuration comes from environment variables (or a local `.env`, which is git-ignored).

| Variable | Default | Description |
|---|---|---|
| `APP_NAME` | `Investment Calculation API` | Title shown in the docs |
| `APP_ENV` | `development` | `development`, `staging`, `production` or `test` |
| `APP_HOST` | `0.0.0.0` | Bind host for `python -m app` / Docker |
| `APP_PORT` | `8000` | Bind port for `python -m app` / Docker |
| `CORS_ORIGINS` | *(empty)* | Comma-separated origins. Empty disables CORS. `*` is rejected when `APP_ENV=production` |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `API_KEY` | *(empty)* | When set, `/api/*` requests must send `X-API-Key`. Empty keeps auth disabled |
| `HOST_PORT` | `8000` | Docker Compose only: host port mapped to the container |
| `MAX_SERIES_LENGTH` | `100000` | Max observations accepted in a series |
| `MAX_MONTE_CARLO_CELLS` | `10000000` | Max `simulations × periods` for Monte Carlo |

---

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness probe → `{"status": "healthy"}` |
| GET | `/docs` | Swagger UI |
| GET | `/redoc` | ReDoc |
| GET | `/openapi.json` | OpenAPI schema |

Calculation endpoints follow `POST /api/v1/{domain}/{metric}` (kebab-case). Every one documents
its formula, unit, assumptions, a request example, a response example and its error responses in
`/docs`. Response examples in `/docs` omit `null` fields (FastAPI strips them from the OpenAPI
document); live responses always include every field of the response model.

### Examples

```bash
curl http://localhost:8000/health
```

```json
{"status": "healthy"}
```

```bash
curl -X POST http://localhost:8000/api/v1/fundamentals/pe-ratio \
  -H "Content-Type: application/json" \
  -d '{"share_price": 35.50, "earnings_per_share": 4.20}'
```

```json
{"metric": "P/E", "value": 8.452380952380953, "unit": "multiple", "currency": null}
```

Average balances (ROE, ROA, ROIC, asset turnover, DuPont):

```bash
curl -X POST http://localhost:8000/api/v1/fundamentals/roe \
  -H "Content-Type: application/json" \
  -d '{"net_income": 180, "shareholders_equity": {"beginning": 900, "ending": 1100}}'
```

```json
{"metric": "ROE", "value": 0.18, "unit": "decimal", "currency": null}
```

Monetary result with informational currency:

```bash
curl -X POST http://localhost:8000/api/v1/fundamentals/net-debt \
  -H "Content-Type: application/json" \
  -d '{"gross_debt": 1100, "cash_and_equivalents": 300, "currency": "BRL"}'
```

```json
{"metric": "Net Debt", "value": 800.0, "unit": "amount", "currency": "BRL"}
```

Structured result (DuPont, five factors):

```bash
curl -X POST http://localhost:8000/api/v1/fundamentals/dupont \
  -H "Content-Type: application/json" \
  -d '{"method": "five_factor", "net_income": 120, "pretax_income": 160, "ebit": 200,
       "revenue": 1000, "total_assets": 2000, "shareholders_equity": 800}'
```

```json
{
  "metric": "DuPont Analysis",
  "method": "five_factor",
  "return_on_equity": 0.15000000000000002,
  "components": [
    {"metric": "Tax Burden", "value": 0.75, "unit": "decimal"},
    {"metric": "Interest Burden", "value": 0.8, "unit": "decimal"},
    {"metric": "Operating Margin", "value": 0.2, "unit": "decimal"},
    {"metric": "Asset Turnover", "value": 0.5, "unit": "multiple"},
    {"metric": "Equity Multiplier", "value": 2.5, "unit": "multiple"}
  ]
}
```

Calculation error:

```bash
curl -X POST http://localhost:8000/api/v1/fundamentals/pe-ratio \
  -H "Content-Type: application/json" \
  -d '{"share_price": 35.50, "earnings_per_share": 0}'
```

```json
{"error": {"code": "DIVISION_BY_ZERO", "message": "earnings_per_share cannot be zero", "details": null}}
```

With authentication enabled (`API_KEY` set), add `-H "X-API-Key: $API_KEY"`.

### Fundamental Analysis

Input conventions specific to this domain:

- **Balance fields** (`shareholders_equity`, `total_assets`, `invested_capital`) accept a number or
  `{"beginning": x, "ending": y}`, in which case the simple average is used.
- **Positive magnitudes**: `capital_expenditures`, `depreciation_amortization`,
  `interest_expense`, dividends and balance-sheet items are sent as values ≥ 0, even when the
  financial statements show them as negative.
- `change_in_working_capital > 0` means cash invested in working capital.
- `tax_rate` is a decimal in `[0, 1]`.
- Growth rates use `|previous_value|` as the base, so going from −100 to −50 is `+0.50`.
- CAGR requires beginning and ending values > 0.
- PEG receives growth in decimal (`0.10`) and uses percentage points (`10`) in the formula.

##### Valuation multiples

| Endpoint | Metric | Formula | Unit |
|---|---|---|---|
| `POST /api/v1/fundamentals/pe-ratio` | P/E | `P/E = share_price / earnings_per_share` | `multiple` |
| `POST /api/v1/fundamentals/pb-ratio` | P/B | `P/B = share_price / book_value_per_share` | `multiple` |
| `POST /api/v1/fundamentals/ps-ratio` | P/S | `P/S = market_capitalization / revenue` | `multiple` |
| `POST /api/v1/fundamentals/ev-to-ebitda` | EV/EBITDA | `EV/EBITDA = enterprise_value / ebitda` | `multiple` |
| `POST /api/v1/fundamentals/ev-to-ebit` | EV/EBIT | `EV/EBIT = enterprise_value / ebit` | `multiple` |
| `POST /api/v1/fundamentals/ev-to-revenue` | EV/Revenue | `EV/Revenue = enterprise_value / revenue` | `multiple` |
| `POST /api/v1/fundamentals/ev-to-fcf` | EV/FCF | `EV/FCF = enterprise_value / free_cash_flow` | `multiple` |
| `POST /api/v1/fundamentals/earnings-yield` | Earnings Yield | `earnings_to_price: EPS / share_price · ebit_to_enterprise_value: EBIT / EV` | `decimal` |
| `POST /api/v1/fundamentals/fcf-yield` | FCF Yield | `FCF Yield = free_cash_flow / market_capitalization` | `decimal` |
| `POST /api/v1/fundamentals/ebitda-yield` | EBITDA Yield | `EBITDA Yield = ebitda / enterprise_value` | `decimal` |
| `POST /api/v1/fundamentals/peg-ratio` | PEG | `PEG = pe_ratio / (earnings_growth_rate × 100)` | `multiple` |

##### Profitability

| Endpoint | Metric | Formula | Unit |
|---|---|---|---|
| `POST /api/v1/fundamentals/roe` | ROE | `ROE = net_income / shareholders_equity` | `decimal` |
| `POST /api/v1/fundamentals/roa` | ROA | `ROA = net_income / total_assets` | `decimal` |
| `POST /api/v1/fundamentals/roic` | ROIC | `ROIC = ebit × (1 − tax_rate) / invested_capital` | `decimal` |
| `POST /api/v1/fundamentals/roce` | ROCE | `ROCE = ebit / (total_assets − current_liabilities)` | `decimal` |
| `POST /api/v1/fundamentals/gross-margin` | Gross Margin | `Gross Margin = gross_profit / revenue` | `decimal` |
| `POST /api/v1/fundamentals/ebitda-margin` | EBITDA Margin | `EBITDA Margin = ebitda / revenue` | `decimal` |
| `POST /api/v1/fundamentals/ebit-margin` | EBIT Margin | `EBIT Margin = ebit / revenue` | `decimal` |
| `POST /api/v1/fundamentals/net-margin` | Net Margin | `Net Margin = net_income / revenue` | `decimal` |
| `POST /api/v1/fundamentals/fcf-margin` | FCF Margin | `FCF Margin = free_cash_flow / revenue` | `decimal` |
| `POST /api/v1/fundamentals/asset-turnover` | Asset Turnover | `Asset Turnover = revenue / total_assets` | `multiple` |
| `POST /api/v1/fundamentals/dupont` | DuPont Analysis | 3 or 5 factors whose product is ROE | structured |

##### Growth

| Endpoint | Metric | Formula | Unit |
|---|---|---|---|
| `POST /api/v1/fundamentals/revenue-growth` | Revenue Growth | `growth = (current_value − previous_value) / |previous_value|` | `decimal` |
| `POST /api/v1/fundamentals/ebitda-growth` | EBITDA Growth | `growth = (current_value − previous_value) / |previous_value|` | `decimal` |
| `POST /api/v1/fundamentals/ebit-growth` | EBIT Growth | `growth = (current_value − previous_value) / |previous_value|` | `decimal` |
| `POST /api/v1/fundamentals/net-income-growth` | Net Income Growth | `growth = (current_value − previous_value) / |previous_value|` | `decimal` |
| `POST /api/v1/fundamentals/eps-growth` | EPS Growth | `growth = (current_value − previous_value) / |previous_value|` | `decimal` |
| `POST /api/v1/fundamentals/fcf-growth` | FCF Growth | `growth = (current_value − previous_value) / |previous_value|` | `decimal` |
| `POST /api/v1/fundamentals/cagr` | CAGR | `CAGR = (ending_value / beginning_value) ^ (1 / years) − 1` | `decimal` |
| `POST /api/v1/fundamentals/sustainable-growth-rate` | Sustainable Growth Rate | `SGR = return_on_equity × retention_ratio` | `decimal` |
| `POST /api/v1/fundamentals/retention-ratio` | Retention Ratio | `Retention = (net_income − dividends_paid) / net_income` | `decimal` |
| `POST /api/v1/fundamentals/reinvestment-rate` | Reinvestment Rate | `Reinvestment Rate = (capex − D&A + ΔNWC) / (ebit × (1 − tax_rate))` | `decimal` |

##### Debt

| Endpoint | Metric | Formula | Unit |
|---|---|---|---|
| `POST /api/v1/fundamentals/gross-debt` | Gross Debt | `Gross Debt = short_term_debt + long_term_debt + lease_liabilities` | `amount` |
| `POST /api/v1/fundamentals/net-debt` | Net Debt | `Net Debt = gross_debt − cash_and_equivalents − short_term_investments` | `amount` |
| `POST /api/v1/fundamentals/net-debt-to-ebitda` | Net Debt/EBITDA | `Net Debt/EBITDA = net_debt / ebitda` | `multiple` |
| `POST /api/v1/fundamentals/debt-to-equity` | Debt/Equity | `Debt/Equity = gross_debt / shareholders_equity` | `multiple` |
| `POST /api/v1/fundamentals/debt-to-capital` | Debt/Total Capital | `Debt/Capital = gross_debt / (gross_debt + shareholders_equity)` | `decimal` |
| `POST /api/v1/fundamentals/interest-coverage` | Interest Coverage | `Interest Coverage = ebit / interest_expense` | `multiple` |
| `POST /api/v1/fundamentals/debt-to-fcf` | Debt/FCF | `Debt/FCF = gross_debt / free_cash_flow` | `multiple` |

##### Liquidity

| Endpoint | Metric | Formula | Unit |
|---|---|---|---|
| `POST /api/v1/fundamentals/current-ratio` | Current Ratio | `Current Ratio = current_assets / current_liabilities` | `multiple` |
| `POST /api/v1/fundamentals/quick-ratio` | Quick Ratio | `Quick Ratio = (current_assets − inventories) / current_liabilities` | `multiple` |
| `POST /api/v1/fundamentals/cash-ratio` | Cash Ratio | `Cash Ratio = (cash_and_equivalents + short_term_investments) / current_liabilities` | `multiple` |
| `POST /api/v1/fundamentals/general-liquidity-ratio` | General Liquidity Ratio | `(current_assets + long_term_receivables) / (current_liabilities + non_current_liabilities)` | `multiple` |

##### Cash flow

| Endpoint | Metric | Formula | Unit |
|---|---|---|---|
| `POST /api/v1/fundamentals/free-cash-flow` | Free Cash Flow | `FCF = operating_cash_flow − capital_expenditures` | `amount` |
| `POST /api/v1/fundamentals/fcff` | FCFF | `FCFF = ebit × (1 − tax_rate) + D&A − capex − ΔNWC` | `amount` |
| `POST /api/v1/fundamentals/fcfe` | FCFE | `FCFE = FCFF − interest_expense × (1 − tax_rate) + net_borrowing` | `amount` |
| `POST /api/v1/fundamentals/fcf-conversion` | FCF Conversion | `FCF Conversion = free_cash_flow / net_income` | `decimal` |
| `POST /api/v1/fundamentals/cash-conversion-ratio` | Cash Conversion Ratio | `Cash Conversion = operating_cash_flow / net_income` | `decimal` |
| `POST /api/v1/fundamentals/cfo-margin` | CFO Margin | `CFO Margin = operating_cash_flow / revenue` | `decimal` |
| `POST /api/v1/fundamentals/capex-to-revenue` | Capex/Revenue | `Capex/Revenue = capital_expenditures / revenue` | `decimal` |
| `POST /api/v1/fundamentals/capex-to-depreciation` | Capex/Depreciation | `Capex/Depreciation = capital_expenditures / depreciation_amortization` | `multiple` |
| `POST /api/v1/fundamentals/cash-flow-per-share` | Cash Flow per Share | `Cash Flow per Share = operating_cash_flow / shares_outstanding` | `amount` |
| `POST /api/v1/fundamentals/owner-earnings` | Owner Earnings | `Owner Earnings = net_income + D&A − maintenance_capex − ΔNWC` | `amount` |

##### Dividends

| Endpoint | Metric | Formula | Unit |
|---|---|---|---|
| `POST /api/v1/fundamentals/dividend-yield` | Dividend Yield | `Dividend Yield = dividend_per_share / share_price` | `decimal` |
| `POST /api/v1/fundamentals/dividend-payout` | Dividend Payout | `Payout = dividends_paid / net_income` | `decimal` |
| `POST /api/v1/fundamentals/dividend-coverage` | Dividend Coverage | `Coverage = earnings_per_share / dividend_per_share` | `multiple` |
| `POST /api/v1/fundamentals/dividend-cagr` | Dividend CAGR | `Dividend CAGR = (ending_dividend / beginning_dividend) ^ (1 / years) − 1` | `decimal` |
| `POST /api/v1/fundamentals/dividend-per-share` | Dividend per Share | `DPS = total_dividends / shares_outstanding` | `amount` |
| `POST /api/v1/fundamentals/yield-on-cost` | Yield on Cost | `Yield on Cost = dividend_per_share / average_cost_per_share` | `decimal` |

### Valuation

Input conventions specific to this domain:

- Rates are decimals **per period** and must be greater than −1.
- Cash flow *i* occurs at the **end of period i**; `mid_year_convention: true` discounts it at
  *i − 0.5*. The **terminal value is always discounted from the end of the last period**.
- Perpetuity growth requires `discount_rate > growth_rate` (otherwise `INVALID_INPUT`).
- Full DCF endpoints accept `terminal` as a tagged object:
  `{"method": "perpetuity_growth", "growth_rate": 0.02}` or
  `{"method": "exit_multiple", "terminal_metric": 250, "multiple": 8}`.
- `terminal_value_percentage = PV(terminal value) / total value`; `value_per_share` needs
  `shares_outstanding`; `margin_of_safety` also needs `share_price` and is `null` when the value
  per share is ≤ 0. Standalone `/margin-of-safety` requires `intrinsic_value > 0`.
- Equity bridge: `equity = EV − net_debt − minority_interest + non_operating_assets`.
- Beta relevering uses Hamada (debt beta = 0). WACC weights must be market values.
- Three-stage DDM: growth declines linearly during the transition and reaches the stable rate
  in its last year (Damodaran). `stable_cost_of_equity` only affects the terminal price.

FCFF DCF example:

```bash
curl -X POST http://localhost:8000/api/v1/valuation/dcf/fcff \
  -H "Content-Type: application/json" \
  -d '{"cash_flows": [100, 110, 121], "discount_rate": 0.10,
       "terminal": {"method": "perpetuity_growth", "growth_rate": 0.02},
       "net_debt": 300, "shares_outstanding": 100, "share_price": 9}'
```

```json
{
  "metric": "DCF (FCFF)",
  "enterprise_value": 1431.8181818181815,
  "equity_value": 1131.8181818181815,
  "terminal_value": 1542.75,
  "terminal_value_percentage": 0.8095238095238094,
  "value_per_share": 11.318181818181815,
  "margin_of_safety": 0.2048192771084335,
  "present_value_of_cash_flows": 272.7272727272727,
  "present_value_of_terminal_value": 1159.0909090909088,
  "discounted_cash_flows": [
    {"period": 1.0, "cash_flow": 100.0, "discount_factor": 0.9090909090909091, "present_value": 90.9090909090909},
    "..."
  ],
  "currency": null
}
```

WACC example:

```bash
curl -X POST http://localhost:8000/api/v1/valuation/wacc \
  -H "Content-Type: application/json" \
  -d '{"equity_value": 600, "debt_value": 400, "cost_of_equity": 0.12,
       "pre_tax_cost_of_debt": 0.08, "tax_rate": 0.34}'
```

```json
{
  "metric": "WACC", "value": 0.09312, "unit": "decimal", "currency": null,
  "components": [
    {"metric": "Equity Weight", "value": 0.6, "unit": "decimal"},
    {"metric": "Debt Weight", "value": 0.4, "unit": "decimal"},
    {"metric": "Cost of Equity", "value": 0.12, "unit": "decimal"},
    {"metric": "After-tax Cost of Debt", "value": 0.05279999999999999, "unit": "decimal"}
  ]
}
```

##### DCF and time value

| Endpoint | Result | Formula | Unit |
|---|---|---|---|
| `POST /api/v1/valuation/future-value` | Future Value | `FV = present_value × (1 + rate) ^ periods` | `amount` |
| `POST /api/v1/valuation/terminal-value/perpetuity-growth` | Terminal Value (Perpetuity Growth) | `TV = final_cash_flow × (1 + growth_rate) / (discount_rate − growth_rate)` | `amount` |
| `POST /api/v1/valuation/terminal-value/exit-multiple` | Terminal Value (Exit Multiple) | `TV = terminal_metric × multiple` | `amount` |
| `POST /api/v1/valuation/enterprise-value` | Enterprise Value | `EV = present_value_of_cash_flows + present_value_of_terminal_value` | `amount` |
| `POST /api/v1/valuation/equity-value` | Equity Value | `Equity = enterprise_value − net_debt − minority_interest + non_operating_assets` | `amount` |
| `POST /api/v1/valuation/value-per-share` | Intrinsic Value per Share | `Value per Share = equity_value / shares_outstanding` | `amount` |
| `POST /api/v1/valuation/margin-of-safety` | Margin of Safety | `MoS = (intrinsic_value − market_price) / intrinsic_value` | `decimal` |
| `POST /api/v1/valuation/present-value` | Present Value | `PV = Σ CF_i / (1 + discount_rate) ^ t_i` | structured |
| `POST /api/v1/valuation/dcf/fcff` | DCF (FCFF) | `EV = Σ FCFF_t / (1 + WACC)^t + TV / (1 + WACC)^n` | structured |
| `POST /api/v1/valuation/dcf/fcfe` | DCF (FCFE) | `Equity = Σ FCFE_t / (1 + Ke)^t + TV / (1 + Ke)^n` | structured |

##### Dividend discount models

| Endpoint | Result | Formula | Unit |
|---|---|---|---|
| `POST /api/v1/valuation/ddm` | Dividend Discount Model | `Value = Σ D_t / (1 + cost_of_equity)^t + terminal_price / (1 + cost_of_equity)^n` | `amount` |
| `POST /api/v1/valuation/gordon-growth` | Gordon Growth Model | `P0 = D1 / (cost_of_equity − growth_rate), with D1 = D0 × (1 + growth_rate)` | `amount` |
| `POST /api/v1/valuation/ddm/two-stage` | Two-Stage DDM | `D_t = D0 × (1 + high_growth_rate)^t, t = 1..n` | structured |
| `POST /api/v1/valuation/ddm/three-stage` | Three-Stage DDM | `High growth: D_t = D_{t−1} × (1 + g1), t = 1..n` | structured |

##### Cost of capital

| Endpoint | Result | Formula | Unit |
|---|---|---|---|
| `POST /api/v1/valuation/capm` | CAPM Expected Return | `E(R) = risk_free_rate + beta × market_risk_premium` | `decimal` |
| `POST /api/v1/valuation/levered-beta` | Levered Beta | `βL = βU × [1 + (1 − tax_rate) × debt_to_equity]` | `number` |
| `POST /api/v1/valuation/unlevered-beta` | Unlevered Beta | `βU = βL / [1 + (1 − tax_rate) × debt_to_equity]` | `number` |
| `POST /api/v1/valuation/cost-of-equity` | Cost of Equity | `Ke = risk_free_rate + beta × market_risk_premium + country_risk_premium + size_premium + specific_risk_premium` | `decimal` |
| `POST /api/v1/valuation/cost-of-debt` | Cost of Debt | `risk_free_plus_spread: Kd = risk_free_rate + credit_spread · interest_over_debt: Kd = interest_expense / total_debt` | `decimal` |
| `POST /api/v1/valuation/after-tax-cost-of-debt` | After-tax Cost of Debt | `Kd after tax = pre_tax_cost_of_debt × (1 − tax_rate)` | `decimal` |
| `POST /api/v1/valuation/wacc` | WACC | `WACC = E / (D + E) × cost_of_equity + D / (D + E) × pre_tax_cost_of_debt × (1 − tax_rate)` | structured |

---

## Conventions

### Rates

Rates and percentages are **always decimals**:

| Meaning | Send |
|---|---|
| 10% | `0.10` |
| 5% | `0.05` |
| 2.5% | `0.025` |

Never send `10` meaning 10%. Technical oscillators (RSI, Stochastic, Williams %R, MFI, CCI)
keep their conventional scale and are returned with `unit: "index"`.

### Numbers

- **Currency agnostic**: amounts are plain numbers. `currency` (ISO 4217, optional) is echoed
  back and never changes the math.
- **No rounding**: results are returned in full float64 precision (≈15–17 significant digits).
  Formatting (e.g. `8.45x`) is the consumer's responsibility.
- **NaN / Infinity are rejected** on input; a non-finite result becomes a `NON_FINITE_RESULT` error.
- **Negative denominators** return the signed result without interpretation; a **zero**
  denominator returns `DIVISION_BY_ZERO`.
- **Unknown fields are rejected** (`422`), so typos never silently fall back to defaults.
- **Where validation happens**: constraints that always hold for a single field (price > 0,
  tax rate in [0, 1], magnitudes ≥ 0) are schema rules → `422 VALIDATION_ERROR`. Formula-specific
  or cross-field conditions (zero denominator, CAGR with non-positive values) are calculation
  rules → `400` with a specific code.
- `currency` is echoed only when the result `unit` is `amount`.

### Units

| `unit` | Meaning | Example |
|---|---|---|
| `multiple` | Ratio read as "x" | P/E 8.45 |
| `decimal` | Rate / percentage in decimal | ROE 0.18 |
| `amount` | Monetary value in the input currency | FCF 1200000 |
| `index` | Indicator on its own scale | RSI 63.2 |
| `years` | Time in years | Duration 4.2 |
| `number` | Dimensionless number | Beta 1.1 |

---

## Errors

Every error uses one envelope, and stack traces are never exposed:

```json
{
  "error": {
    "code": "DIVISION_BY_ZERO",
    "message": "earnings_per_share cannot be zero",
    "details": null
  }
}
```

| HTTP | `code` | When |
|---|---|---|
| 400 | `DIVISION_BY_ZERO`, `INVALID_INPUT`, `INSUFFICIENT_DATA`, `CONVERGENCE_ERROR`, `NON_FINITE_RESULT`, `LIMIT_EXCEEDED`, `MALFORMED_REQUEST` | Data invalid for the calculation, or body is not valid JSON |
| 401 | `UNAUTHORIZED` | Missing/invalid `X-API-Key` (only when `API_KEY` is set) |
| 404 | `NOT_FOUND` | Unknown endpoint |
| 405 | `METHOD_NOT_ALLOWED` | Wrong HTTP method |
| 422 | `VALIDATION_ERROR` | Schema validation failed; `details` lists `{field, message, type}` |
| 500 | `INTERNAL_ERROR` | Unexpected error; details go only to the server log |

Every response carries an `X-Request-ID` header (a valid incoming one is propagated), which
matches the `request_id` in the server logs.

## Logging

One JSON line per request with `request_id`, `method`, `path`, `status`, `duration_ms`.
Request bodies, query strings and headers (including `X-API-Key`) are never logged.
Unhandled exceptions are logged with their traceback, server-side only.

---

## Tests

```bash
uv run pytest            # full suite
uv run ruff check .      # lint
uv run ruff format .     # format
pyright                  # type check (npm install -g pyright)
```

Warnings are treated as errors in the test suite. `TestClient` uses `httpx2`, the drop-in
successor of `httpx` required by Starlette 1.x.

- `tests/unit/` — pure functions and formulas (normal, edge and invalid cases).
- `tests/api/` — `request → endpoint → response` through FastAPI's `TestClient`.

---

## Roadmap

| Phase | Scope | Status |
|---|---|---|
| 1 | API foundation: config, health, errors, logging, schemas, Docker, tests | ✅ |
| 2 | Fundamental Analysis (59 endpoints) | ✅ |
| 3 | Valuation (21 endpoints) | ✅ |
| 4 | Fixed Income | pending |
| 5 | Risk + Statistics | pending |
| 6 | Portfolio | pending |
| 7 | Technical Analysis | pending |
| 8 | Scenarios + Monte Carlo | pending |

## Limitations

- float64 arithmetic (no `Decimal`): suitable for analytics, not for accounting ledgers.
- No market data, no persistence, no recommendations — by design.
- Authentication is a single optional shared API key; no users, roles or rate limiting yet.
