# Investment Calculation API

Stateless, deterministic HTTP microservice for investment calculations.

**Receives data → calculates → returns results.**

It is consumed by JARVIS (the main AI system) over HTTP/REST. This service:

- does **not** fetch prices, news or any market data;
- does **not** use LLMs, agents or prompts;
- does **not** issue buy/sell/hold recommendations or opinions;
- does **not** access JARVIS's code, database or API.

> **Status:** Phase 2 complete — API foundation + Fundamental Analysis (59 endpoints).
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
│   │   ├── metric_endpoint.py  # declarative registration of single-value metric endpoints
│   │   └── v1/
│   │       ├── router.py    # aggregates domain routers under /api/v1
│   │       └── routes/fundamentals/  # one module per group (multiples, profitability, ...)
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

### Adding a single-value calculation

1. Write a pure function in `services/<domain>/` (raise `CalculationError` subclasses on invalid math).
2. Add its request model in `schemas/<domain>/` (reuse the documented field types).
3. Declare a `MetricEndpoint` (path, metric, unit, formula, notes, example, compute) in
   `api/v1/routes/<domain>/`. Docs, request/response examples and error responses are generated,
   and the example is executed at import time so documentation cannot drift from the code.
4. Add unit tests for the formula and a normal/edge/invalid case to the API test table — a guard
   test fails if an endpoint has no cases.

Structured results (e.g. DuPont) use an explicit route with their own response model.

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
`/docs`.

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
| 3 | Valuation | pending |
| 4 | Fixed Income | pending |
| 5 | Risk + Statistics | pending |
| 6 | Portfolio | pending |
| 7 | Technical Analysis | pending |
| 8 | Scenarios + Monte Carlo | pending |

## Limitations

- float64 arithmetic (no `Decimal`): suitable for analytics, not for accounting ledgers.
- No market data, no persistence, no recommendations — by design.
- Authentication is a single optional shared API key; no users, roles or rate limiting yet.
