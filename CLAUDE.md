# ai.personal-finance

Privacy-first personal finance analyser. Users upload bank statements and get ML-powered financial health insights. Everything runs locally — no data leaves the machine.

---

## Stack

| Layer             | Tool                    |
| ----------------- | ----------------------- |
| API               | FastAPI + uvicorn       |
| Validation        | Pydantic v2             |
| Auth              | FastAPI-Users + JWT     |
| Database          | PostgreSQL (asyncpg)    |
| ORM               | SQLAlchemy 2.0 (async)  |
| Migrations        | Alembic                 |
| CSV parsing       | pandas                  |
| PDF parsing       | pdfplumber              |
| Categorisation    | scikit-learn            |
| Anomaly detection | scikit-learn            |
| LLM reflection    | Ollama (mistral:7b)     |
| Frontend          | Streamlit               |
| Infrastructure    | Docker + docker-compose |

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
│   │   └── insights.py
│   ├── models/
│   │   ├── user.py
│   │   ├── bank_account.py
│   │   ├── transaction.py
│   │   └── category.py
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
```

---

## Amount Handling

**Ingestion — raw string to cents:**

```python
from decimal import Decimal, ROUND_HALF_UP

def to_cents(raw_value: str) -> int:
    cleaned = raw_value.strip().replace(" ", "").lstrip("-")
    cleaned = cleaned.replace(".", "").replace(",", ".")  # BR format → standard
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
- Every resource (`bank_accounts`, `transactions`, `imports`) is scoped to the authenticated user — always filter by `user_id`.
- The `amount` field is `int` throughout the entire app boundary. It only becomes `Decimal` at ingestion and presentation.
- Ollama prompts are always in English regardless of the language of the transaction data.
- Categories have system defaults (seeded at startup) and can be customised per user.

---

## Language Handling

Transaction descriptions may be in English, Portuguese, or a mix of both — this is expected from Brazilian bank statements. No translation layer is applied.

- The ML categorisation model is trained on labelled transaction data in both EN and PT. The TF-IDF vectoriser is language-agnostic.
- All LLM reflection output (Ollama) is always in English. Prompts must include the instruction: _"Respond in English regardless of the language of the transaction data provided."_
- Amount formatting uses plain Python — no i18n library required.

---

## Insight Periods

Insights are computed at three granularities via SQL aggregation — no ML required:

- **Monthly** — last 12 months, one row per month
- **Quarterly** — last 4 quarters
- **Yearly** — all available years

The LLM reflection layer receives the aggregated summary as context and returns a narrative in English.

---

## ML Notes

- Categorisation uses a TF-IDF + scikit-learn classifier trained on labelled transaction descriptions in both EN and PT.
- Serialised model lives in `models/` as `.joblib`. Loaded once at app startup.
- Anomaly detection uses Isolation Forest per spending category, fitted on the user's own history after sufficient data (≥ 3 months).
- User category corrections are stored and used to retrain on demand (stretch goal).

---

## Infrastructure

- Postgres and the FastAPI app run via `docker-compose`.
- Ollama runs separately — expected at `http://localhost:11434`.
- Streamlit connects to FastAPI via `http://localhost:8000`.
- Environment variables managed via `.env` + `pydantic-settings` in `app/core/config.py`.
