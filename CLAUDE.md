# ai.personal-finance

Privacy-first personal finance manager. Upload bank statements, declare assets, set budgets, and get ML-powered insights with actionable next steps — everything runs locally, no data leaves the machine.

---

## Stack

| Layer              | Tool                    |
| ------------------ | ----------------------- |
| API                | FastAPI + uvicorn       |
| Validation         | Pydantic v2             |
| Auth               | FastAPI-Users + JWT     |
| Database           | PostgreSQL (asyncpg)    |
| ORM                | SQLAlchemy 2.0 (async)  |
| Migrations         | Alembic                 |
| CSV parsing        | pandas                  |
| PDF parsing        | pdfplumber              |
| Categorisation     | scikit-learn            |
| Anomaly detection  | scikit-learn            |
| LLM reflection     | Ollama (mistral:7b)     |
| Frontend           | Streamlit               |
| Net-worth charts   | plotly (via `st.plotly_chart`) |
| Infrastructure     | Docker + docker-compose |

---

## Project Structure

```
finsight/
├── app/
│   ├── main.py
│   ├── routes/
│   │   ├── auth.py
│   │   ├── accounts.py
│   │   ├── uploads.py
│   │   ├── transactions.py
│   │   ├── insights.py
│   │   ├── assets.py          # v2 — asset CRUD + net-worth
│   │   └── budgets.py         # v2 — budget CRUD + actual_spent
│   ├── models/
│   │   ├── user.py
│   │   ├── bank_account.py
│   │   ├── transaction.py
│   │   ├── category.py
│   │   ├── asset.py           # v2 — Asset + AssetSnapshot
│   │   └── budget.py          # v2 — Budget
│   ├── ml/
│   │   ├── parser.py
│   │   ├── categoriser.py
│   │   ├── anomaly.py
│   │   ├── scoring.py
│   │   └── reflection.py
│   ├── db/
│   │   └── database.py
│   └── core/
│       ├── config.py
│       └── security.py
├── alembic/
├── training/
├── frontend/
│   └── streamlit_app.py
├── docker-compose.yml
└── requirements.txt
```

---

## Database Conventions

- All primary keys are `UUID`.
- All tables have `created_at` (`DateTime`, server default `now()`).
- Monetary amounts are stored as `Integer` (cents, always positive). Never use `FLOAT` or `NUMERIC` for amounts internally.
- Transaction direction is captured by an explicit `type` field (`income` | `expense`), not by the sign of the amount.
- Presentation layer is the only place that converts cents to a display string, using Babel's `format_currency`.

### Core Schema (abbreviated)

```
users
  id, email, hashed_password, full_name, created_at

bank_accounts
  id, user_id (FK), name, bank_name, currency, created_at

imports
  id, bank_account_id (FK), filename, row_count, created_at

transactions
  id, bank_account_id (FK), import_id (FK), date, description,
  amount (integer, cents, positive), type (income|expense),
  category_id (FK, nullable), is_anomaly, notes, created_at

categories
  id, user_id (FK, nullable — null means system default), name,
  type (income|expense), created_at

-- v2 --

assets
  id, user_id (FK), name,
  type (savings|estate|investment|vehicle|other),
  value (integer, cents), currency, notes (nullable),
  created_at, updated_at

asset_snapshots
  id, asset_id (FK), value (integer, cents), recorded_at (DateTime)
  — one row appended every time an asset value is updated via PATCH

budgets
  id, user_id (FK), category_id (FK, nullable — null = global spending cap),
  period_type (monthly|yearly), amount (integer, cents), created_at
```

---

## Amount Handling

**Ingestion — raw string to cents:**

```python
from decimal import Decimal, ROUND_HALF_UP

def to_cents(raw_value: str) -> int:
    cleaned = str(raw_value).strip().replace(" ", "").lstrip("-")
    has_comma, has_dot = "," in cleaned, "." in cleaned
    if has_comma and has_dot:
        # Whichever separator appears last is the decimal separator
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")  # BR: "1.234,56"
        else:
            cleaned = cleaned.replace(",", "")                    # US: "1,234.56"
    elif has_comma and not has_dot:
        cleaned = cleaned.replace(",", ".")                       # "26,27" → "26.27"
    elif has_dot and not has_comma:
        parts = cleaned.split(".")
        if len(parts) > 2 or (len(parts) == 2 and len(parts[-1]) == 3):
            cleaned = cleaned.replace(".", "")  # "2.500" → 2500 (thousands sep)
    decimal = Decimal(cleaned).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return int(decimal * 100)
```

**Presentation — cents to display string:**

```python
from decimal import Decimal

def format_amount(cents: int) -> str:
    return f"R$ {Decimal(cents) / 100:,.2f}"
```

---

## Key Conventions

- All database access is async (SQLAlchemy 2.0 async session + asyncpg).
- Every route is protected by JWT auth unless explicitly marked public (`/auth/register`, `/auth/login`).
- Every resource (`bank_accounts`, `transactions`, `imports`, `assets`, `budgets`) is scoped to the authenticated user — always filter by `user_id`.
- The `amount` field is `int` throughout the entire app boundary. It only becomes `Decimal` at ingestion and presentation.
- Ollama prompts are always in English regardless of the language of the transaction data.
- Categories have system defaults (seeded at startup) and can be customised per user.

---

## Transfer Detection

When the same user owns multiple bank accounts, a transfer between them appears as an expense in the source account and an income in the destination account. Both legs are stored in the `transactions` table but must be excluded from income/expense totals to avoid double-counting in insights and the health score.

### Detection rules
A pair of transactions is auto-detected as an internal transfer when **all** of the following are true:
- Both belong to the same user (via `bank_accounts.user_id`).
- They have **opposite types** (one `income`, one `expense`).
- They belong to **different** `bank_account_id`s.
- Their `amount` values are **exactly equal** (cents).
- Their `date`s differ by **at most 1 calendar day** (handles overnight settlement).

### Schema fields (on `transactions`)
- `is_transfer` — `Boolean`, default `False`. Set to `True` on both legs when matched.
- `transfer_pair_id` — `UUID`, nullable. Shared UUID linking both legs; used to clear both at once on unmark.

### Detection trigger
`detect_transfers(user_id, session)` in `app/ml/transfer_detector.py` is called:
1. Automatically after every file upload (`app/routes/uploads.py`).
2. On demand via `POST /transactions/detect-transfers`.

The function is idempotent — already-matched pairs are never re-matched.

### Insights exclusion
All aggregation queries in `app/routes/insights.py` apply `.where(Transaction.is_transfer.is_(False))`. Transfers are invisible to the health score and the LLM narrative.

### Manual override
`PATCH /transactions/{id}` accepts `is_transfer: bool`. Setting it to `False` on either leg calls `unmark_transfer()` which clears both legs of the pair atomically.

---

## Language Handling

Transaction descriptions may be in English, Portuguese, or a mix of both — this is expected from Brazilian bank statements. No translation layer is applied.

- The ML categorisation model is trained on labelled transaction data in both EN and PT. The TF-IDF vectoriser is language-agnostic.
- All LLM reflection output (Ollama) is always in English. Prompts must include the instruction: _"Respond in English regardless of the language of the transaction data provided."_
- Amount formatting uses plain Python — no i18n library required.

---

## Insight Periods

Insights are computed at three granularities via SQL aggregation — no ML required:

- **Monthly** — accepts optional `year` + `month` filters; defaults to last 12 months
- **Quarterly** — last 4 quarters, grouped by `YYYY-Q{n}` label
- **Yearly** — all available years, grouped by `YYYY`

Controlled by a `period_type: monthly | quarterly | yearly` query param on `GET /insights/`.

The LLM reflection layer receives the aggregated summary as context and returns a structured English narrative (see LLM Output Contract below).

---

## Multi-Account Insights

`GET /insights/` accepts an `account_ids` query param (repeatable: `?account_ids=X&account_ids=Y`).

- Omitted or empty → aggregate all accounts owned by the user.
- One or more IDs → aggregate only those accounts.
- Any ID not owned by the authenticated user is silently dropped.

This replaces the v1 single `account_id` param.

---

## Assets

Assets represent the user's declared wealth outside of transaction history (savings accounts, real estate, investments, vehicles, etc.).

### Routes

- `GET /assets/` — list all assets; response includes a top-level `net_worth` (sum of all asset values in BRL).
- `POST /assets/` — create an asset; automatically records the first `AssetSnapshot`.
- `GET /assets/{id}` — single asset with full snapshot history.
- `PATCH /assets/{id}` — update `value` (and/or other fields); automatically appends a new `AssetSnapshot` so history is preserved.
- `DELETE /assets/{id}` — remove asset and all its snapshots.

### Asset types

| Type | Examples |
|---|---|
| `savings` | Emergency fund, fixed-income account |
| `estate` | Property, land |
| `investment` | Stocks, crypto, funds |
| `vehicle` | Car, motorcycle |
| `other` | Any asset that doesn't fit above |

---

## Budgets

Budgets set a spending limit per category (or globally) for a given period.

### Routes

- `GET /budgets/` — list all budgets; each entry is enriched with `actual_spent` for the current period (SQL aggregation over transactions, same pattern as insights).
- `POST /budgets/` — create a budget.
- `PATCH /budgets/{id}` — update amount or period_type.
- `DELETE /budgets/{id}` — remove budget.

### Budget rules

- `category_id = null` → global cap: total expenses across all categories must not exceed `amount` in the period.
- `period_type = monthly` → resets each calendar month.
- `period_type = yearly` → resets each calendar year.
- `actual_spent` in `GET /budgets/` always reflects the current period only.

---

## Financial Health Score (v2)

The score is a number from **0 to 100** averaged across periods. v2 adds a budget-compliance component.

```
savings_component  = clamp(savings_rate / 0.30, 0.0, 1.0)
                     — savings_rate = net / total_income per period

budget_component   = clamp(1 − overspend_ratio, 0.0, 1.0)
                     — overspend_ratio = avg over budgets of max(0, actual − budget) / budget

final_score = (0.7 × savings_component + 0.3 × budget_component) × 100
```

- If no budgets are defined, `budget_component = 1.0` (no penalty).
- Periods where `total_income = 0` contribute `savings_component = 0.0`.

---

## LLM Output Contract

The Ollama prompt in `app/ml/reflection.py` must always produce a response in two clearly labelled parts:

```
Respond in English. Structure your response in exactly two parts:

1. Analysis — 2 to 3 sentences covering trends, strengths, and concerns
   based on the period summaries below.

2. Next steps — exactly 2 to 3 numbered, specific, actionable recommendations
   (e.g. "Reduce Food & Groceries spending by 12 % to stay within your monthly budget").
```

The prompt context passed to the model includes:
- Monthly period summaries (income, expenses, net).
- Budget compliance per category (over/under and by how much).
- Net-worth trend if ≥ 2 asset snapshots exist (latest vs. previous value).

---

## ML Notes

- Categorisation uses a TF-IDF + scikit-learn classifier trained on labelled transaction descriptions in both EN and PT.
- Serialised model lives in `models/` as `.joblib`. Loaded once at app startup.
- Anomaly detection uses Isolation Forest per spending category, fitted on the user's own history after sufficient data (≥ 3 months).
- User category corrections are stored and used to retrain on demand via `POST /categories/retrain`.

### Retrain behaviour

`POST /categories/retrain` (frontend: "Retrain now" button in the Transactions page) trains a **per-user** model from the current state of the database:

1. Reads all non-transfer transactions that have a `category_id` assigned, joining to `Category` to get the label name. This reflects any manual corrections the user has made.
2. Fits a new TF-IDF + LogisticRegression pipeline and saves it to `models/categoriser_{user_id}.joblib`.
3. **Never writes to the `transactions` table** — existing `category_id` values are untouched.

The retrained model is applied only to **future uploads**: `app/routes/uploads.py` calls `get_categoriser(user_id=...)` and runs `predict()` on descriptions coming in from a new file, not on rows already in the DB.

---

## Frontend Pages (v2)

| Page | Description |
|---|---|
| Dashboard | Health score + net-worth metric card; narrative + numbered next-steps list; income vs expenses bar chart |
| Accounts | Bank account CRUD |
| Upload | CSV / PDF statement upload |
| Transactions | Filterable transaction list |
| Assets | Asset list with current value; total net-worth; plotly sparkline of value history per asset |
| Budgets | Budget list; actual vs budget bar per category (green ≤ 100 %, amber 100–120 %, red > 120 %) |

**Sidebar — Generate Insight:**
- Multi-select of the user's bank accounts (replaces single account picker from v1).
- Period type radio: Monthly / Quarterly / Yearly.
- Year + optional month inputs (same as v1, hidden when period_type ≠ Monthly).

---

## Infrastructure

- Postgres and the FastAPI app run via `docker-compose`.
- Ollama runs separately — expected at `http://localhost:11434`.
- Streamlit connects to FastAPI via `http://localhost:8000`.
- Environment variables managed via `.env` + `pydantic-settings` in `app/core/config.py`.
