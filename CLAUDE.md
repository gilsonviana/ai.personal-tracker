# ai.personal-finance

Privacy-first personal finance manager. Upload bank statements, declare assets, set budgets, and get ML-powered insights with actionable next steps — everything runs locally, no data leaves the machine.

---

## Stack

| Layer | Tool |
|---|---|
| API | FastAPI + uvicorn |
| Validation | Pydantic v2 |
| Auth | FastAPI-Users + JWT (access + refresh tokens) |
| Database | PostgreSQL 15 (asyncpg) |
| ORM | SQLAlchemy 2.0 (async) |
| Migrations | Alembic |
| CSV parsing | pandas |
| PDF parsing | pdfplumber |
| Categorisation | scikit-learn |
| Anomaly detection | scikit-learn |
| LLM reflection | Ollama (mistral:7b) |
| React frontend | Vite + React 18 + TypeScript, Tailwind CSS v4, shadcn/ui, TanStack Query v5, Recharts, Zod |
| Streamlit frontend (legacy) | Streamlit |
| Infrastructure | Docker + docker-compose |

---

## Project Structure

```
finsight/
├── app/
│   ├── main.py               # FastAPI app, lifespan, CORS, router registration
│   ├── routes/
│   │   ├── auth.py           # Custom /auth/jwt/token + /auth/jwt/refresh
│   │   ├── accounts.py
│   │   ├── uploads.py
│   │   ├── transactions.py   # paginated list + all filters
│   │   ├── categories.py
│   │   ├── insights.py
│   │   ├── preferences.py
│   │   ├── fx.py
│   │   ├── assets.py         # planned — asset CRUD + net-worth
│   │   └── budgets.py        # planned — budget CRUD + actual_spent
│   ├── models/
│   │   ├── user.py
│   │   ├── bank_account.py
│   │   ├── transaction.py    # is_transfer, transfer_pair_id
│   │   ├── category.py       # user_id (null = system), exclude_from_insights
│   │   ├── preferences.py
│   │   ├── fx_rate.py
│   │   ├── asset.py          # planned — Asset + AssetSnapshot
│   │   └── budget.py         # planned — Budget
│   ├── ml/
│   │   ├── parser.py
│   │   ├── categoriser.py
│   │   ├── anomaly.py
│   │   ├── scoring.py
│   │   ├── transfer_detector.py
│   │   └── reflection.py
│   ├── services/
│   │   ├── seed.py
│   │   └── fx.py
│   ├── db/
│   │   └── database.py
│   └── core/
│       ├── config.py         # pydantic-settings; CORS_ORIGINS, token lifetimes
│       └── security.py       # access + refresh JWT strategies
├── alembic/
├── training/
│   └── train_categoriser.py
├── frontend-react/           # React SPA (Vite + TypeScript)
│   └── src/
│       ├── api/              # Typed Axios wrappers — client.ts + one file per domain
│       ├── types/            # TypeScript interfaces mirroring backend schemas
│       ├── lib/              # AuthContext, QueryClient, utils (cn, formatCurrency)
│       ├── hooks/            # TanStack Query hooks (use-transactions, use-accounts, …)
│       ├── components/
│       │   ├── layout/       # AppLayout, Sidebar
│       │   ├── transactions/ # FilterBar, ActionPanel, CategoryCell
│       │   └── ui/           # shadcn/ui components (Button, Input, Badge, …)
│       └── pages/            # LoginPage, AccountsPage, TransactionsPage, …
├── frontend/
│   └── streamlit_app.py      # Legacy Streamlit UI
├── scripts/
│   ├── backup.sh
│   └── restore.sh
├── docker-compose.yml
└── requirements.txt
```

---

## Authentication

### Token pair

Login issues two tokens:

| Token | Secret | Lifetime | Storage (React) |
|---|---|---|---|
| `access_token` | `SECRET_KEY` | 60 min | React Context (memory) |
| `refresh_token` | `SECRET_KEY + "-refresh"` | 7 days | `localStorage` |

Using a derived secret for the refresh strategy means a refresh token cannot be used as an access token and vice versa (different signing secrets → validation fails).

### Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/auth/jwt/token` | Login → returns `{ access_token, refresh_token, token_type }` |
| `POST` | `/auth/jwt/refresh` | Body: `{ "refresh_token": "..." }` → returns `{ access_token, token_type }` |
| `POST` | `/auth/jwt/login` | FastAPI-Users legacy endpoint (Streamlit; access token only) |

### React client behaviour

1. On login: store `access_token` in `AuthContext`, store `refresh_token` in `localStorage`.
2. On app load: if `refresh_token` in localStorage → call `/auth/jwt/refresh` → set access token → proceed; if refresh fails → clear localStorage → redirect `/login`.
3. Axios interceptor: attach `Authorization: Bearer <token>` on every request. On 401 → deduplicate concurrent refreshes (shared `refreshing: Promise<string> | null`) → retry the original request once with the new token → on second 401, clear tokens and redirect.

### CORS

`allow_origins=["*"]` with `allow_credentials=True` is rejected by browsers (CORS spec). Origins must be an explicit list:

```python
# app/core/config.py
CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]
```

Set `CORS_ORIGINS` in `.env` to add production domains. Never use `["*"]` with credentials.

---

## Transactions Endpoint

### `GET /transactions/` — filtered, paginated list

**Response shape (`TransactionPage`):**

```python
class TransactionPage(BaseModel):
    items: list[TransactionOut]
    total: int    # count of primary rows only (partner legs not counted)
    offset: int
    limit: int
```

**Query params:**

| Param | Type | Description |
|---|---|---|
| `account_ids` | `list[UUID]` | Repeatable. Omit to include all user accounts. |
| `start` | `date` | Lower date bound (inclusive). |
| `end` | `date` | Upper date bound (inclusive). |
| `type` | `"income" \| "expense"` | Filter by transaction type. |
| `is_transfer` | `bool` | `true` = transfers only; `false` = exclude transfers. |
| `category_id` | `UUID` | Filter by exact category. |
| `search` | `str` | Case-insensitive substring match on `description`. |
| `is_anomaly` | `bool` | `true` = anomalies only. |
| `limit` | `int` | Page size. Default 100, max 2000. |
| `offset` | `int` | Row offset. Default 0. |

**Partner legs:** Transfer partner legs are fetched per-page and appended to `items`, but are not included in `total`. This is intentional — `total` is used for pagination math; showing both legs per page is a display concern.

**Streamlit uses `limit=2000`** to fetch all transactions at once (no UI-side pagination).

---

## Database Conventions

- All primary keys are `UUID`.
- All tables have `created_at` (`DateTime`, server default `now()`).
- Monetary amounts are stored as `Integer` (cents, always positive). Never use `FLOAT` or `NUMERIC` for amounts internally.
- Transaction direction is captured by an explicit `type` field (`income` | `expense`), not by the sign of the amount.
- Presentation layer is the only place that converts cents to a display string.

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
  category_id (FK, nullable), is_anomaly, is_transfer, transfer_pair_id (UUID, nullable),
  notes, created_at

categories
  id, user_id (FK, nullable — null means system default), name,
  type (income|expense), exclude_from_insights (bool), created_at

preferences
  id, user_id (FK), main_currency, created_at

fx_rates
  id, from_currency, to_currency, date, rate, created_at

-- planned --

assets
  id, user_id (FK), name,
  type (savings|estate|investment|vehicle|other),
  value (integer, cents), currency, notes (nullable),
  created_at, updated_at

asset_snapshots
  id, asset_id (FK), value (integer, cents), recorded_at (DateTime)

budgets
  id, user_id (FK), category_id (FK, nullable), period_type (monthly|yearly),
  amount (integer, cents), created_at
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

**React display — cents to string:**

```ts
// src/lib/utils.ts
function formatCurrency(cents: number, currency: string): string {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency", currency, minimumFractionDigits: 2,
  }).format(cents / 100)
}
```

---

## Key Conventions

- All database access is async (SQLAlchemy 2.0 async session + asyncpg).
- Every route is protected by JWT auth unless explicitly marked public (`/auth/register`, `/auth/jwt/login`, `/auth/jwt/token`, `/auth/jwt/refresh`).
- Every resource is scoped to the authenticated user — always filter by `user_id`.
- The `amount` field is `int` throughout the entire app boundary. It only becomes `Decimal` at ingestion and presentation.
- Ollama prompts are always in English regardless of the language of the transaction data.
- Categories have system defaults (seeded at startup) and can be customised per user.
- Categories may be excluded from insights via `exclude_from_insights = True` — all aggregation queries must apply this filter.

---

## Transfer Detection

When the same user owns multiple bank accounts, a transfer between them appears as an expense in the source account and an income in the destination account. Both legs are stored in the `transactions` table but must be excluded from income/expense totals to avoid double-counting.

### Detection rules

A pair of transactions is auto-detected as an internal transfer when **all** of the following are true:
- Both belong to the same user (via `bank_accounts.user_id`).
- They have **opposite types** (one `income`, one `expense`).
- They belong to **different** `bank_account_id`s.
- Their `amount` values are **exactly equal** (cents).
- Their `date`s differ by **at most 1 calendar day**.

### Schema fields

- `is_transfer` — `Boolean`, default `False`. Set to `True` on both legs when matched.
- `transfer_pair_id` — `UUID`, nullable. Shared UUID linking both legs; used to clear both at once on unmark.

### Detection trigger

`detect_transfers(user_id, session)` in `app/ml/transfer_detector.py` is called:
1. Automatically after every file upload.
2. On demand via `POST /transactions/detect-transfers`.

The function is idempotent — already-matched pairs are never re-matched.

### Insights exclusion

All aggregation queries apply `.where(Transaction.is_transfer.is_(False))`. Transfers are invisible to the health score and the LLM narrative.

### Manual override

`PATCH /transactions/{id}` accepts `is_transfer: bool`. Setting it to `False` on either leg calls `unmark_transfer()` which clears both legs of the pair atomically.

---

## Language Handling

Transaction descriptions may be in English, Portuguese, or a mix of both.

- The ML categorisation model is trained on labelled data in both EN and PT. The TF-IDF vectoriser is language-agnostic.
- All LLM reflection output (Ollama) is always in English. Prompts must include: _"Respond in English regardless of the language of the transaction data provided."_

---

## Insight Periods

`GET /insights/monthly` accepts `year` + `month` as optional query params:
- Both omitted → last 12 months (rolling, one row per month)
- `year` only → full year (12 monthly rows)
- `year` + `month` → single month

The LLM reflection layer receives the aggregated summary and returns a structured English narrative (see LLM Output Contract).

---

## Multi-Account Insights

`GET /insights/monthly` accepts `account_ids` (repeatable query param):
- Omitted or empty → aggregate all accounts owned by the user.
- One or more IDs → aggregate only those accounts.
- Any ID not owned by the authenticated user is silently dropped.

---

## Financial Health Score

```
monthly_score = clamp(savings_rate / 0.30, 0.0, 1.0)
final_score   = average(monthly_scores) × 100
```

- `savings_rate = net / total_income` per period.
- Periods where `total_income = 0` contribute `0.0`.
- Transactions in categories with `exclude_from_insights = True` are excluded.

---

## LLM Output Contract

The Ollama prompt in `app/ml/reflection.py` must always produce a response in two clearly labelled parts:

```
Respond in English. Structure your response in exactly two parts:

1. Analysis — 2 to 3 sentences covering trends, strengths, and concerns
   based on the period summaries below.

2. Next steps — exactly 2 to 3 numbered, specific, actionable recommendations.
```

The React `InsightsPage` parses the narrative by finding the line that matches `/next.?step/i` and splitting there. Lines before the separator become the analysis paragraph; lines after matching `/^\d+\./` become the numbered next-steps list.

---

## ML Notes

- Categorisation uses TF-IDF + scikit-learn classifier trained on labelled transaction descriptions in EN and PT.
- Serialised model lives in `models/` as `.joblib`. Loaded once at app startup.
- Per-user model at `models/categoriser_{user_id}.joblib` takes priority over the shared model.
- Anomaly detection uses Isolation Forest per spending category, fitted on the user's own history after sufficient data (≥ 3 months).

### Retrain behaviour

`POST /categories/retrain`:
1. Reads all non-transfer transactions with a `category_id` assigned.
2. Fits a new TF-IDF + LogisticRegression pipeline; saves to `models/categoriser_{user_id}.joblib`.
3. **Never writes to `transactions`** — existing `category_id` values are untouched.
4. Applied only to future uploads — does not re-categorise existing rows.

---

## React Frontend (`frontend-react/`)

### Tech choices

| Concern | Choice |
|---|---|
| Build | Vite + React 18 + TypeScript |
| Routing | React Router v6 |
| Server state | TanStack Query v5 |
| UI / styling | shadcn/ui + Tailwind CSS v4 |
| Charts | Recharts |
| Forms | React Hook Form + Zod |
| HTTP | Axios |

### Tailwind v4 notes

Tailwind v4 is a complete rewrite — no `tailwind.config.ts`, no `npx tailwindcss init -p`. Configuration is CSS-first:

```css
/* src/index.css */
@import "tailwindcss";
@theme {
  --color-primary: hsl(221.2 83.2% 53.3%);
  /* ... all design tokens ... */
}
```

Vite plugin: `@tailwindcss/vite` (not `@tailwindcss/postcss`).

### Path aliases

`@/*` → `./src/*`. Configured in both `vite.config.ts` (Vite resolve) and `tsconfig.app.json` (TypeScript). `ignoreDeprecations: "6.0"` is required because TS 7 deprecated `baseUrl`.

### TanStack Query key conventions

```ts
['accounts']
['accounts', accountId, 'imports']
['transactions', filtersObject]   // refetches when any filter key changes
['categories']
['insights', paramsObject]
['preferences']
```

### Pages

| Page | Route | Description |
|---|---|---|
| Login | `/login` | `POST /auth/jwt/token` → stores token pair |
| Register | `/register` | `POST /auth/register` → auto-login |
| Accounts | `/accounts` | CRUD; expandable import history per account |
| Upload | `/upload` | Drag-and-drop CSV/PDF; FX sync banner for non-BRL accounts |
| Transactions | `/transactions` | Server-side paginated table; full filter bar; inline category edit; link/unlink/bulk actions |
| Categories | `/categories` | Toggle exclude_from_insights; create/delete custom; retrain button |
| Insights | `/insights` | Health score card; ComposedChart (income/expense bars + net line); LLM narrative |
| Preferences | `/preferences` | Currency selector |

### TransactionsPage specifics

- PAGE_SIZE = 25; server-side pagination via `limit`/`offset`.
- `pairMap` built client-side from `transfer_pair_id` on the current page's items — used to show `"Account A → Account B"` in the Transfer column.
- `CategoryCell`: Radix Popover opens a filtered category list (by `tx.type`). On select → `PATCH /transactions/{id}` → invalidate `['transactions', ...]`.
- `ActionPanel` contextual rules:
  - Link: ≥1 expense + exactly 1 income selected, none already transfers → `POST /transactions/link-transfer`
  - Unlink: exactly 1 transfer selected → `PATCH /transactions/{id}` `{ is_transfer: false }`
  - Bulk-category: ≥1 non-transfer selected → `PATCH /transactions/bulk-category`
  - Auto-detect: always available → `POST /transactions/detect-transfers`

---

## Streamlit Frontend (legacy, `frontend/`)

Single-file app (`streamlit_app.py`). Connects to FastAPI at `http://localhost:8000`. Uses `limit=2000` on the transactions endpoint to fetch everything at once. Still functional but not maintained going forward.

---

## Infrastructure

- Postgres and FastAPI run via `docker-compose`.
- Ollama runs separately — expected at `http://localhost:11434`.
- Environment variables managed via `.env` + `pydantic-settings` in `app/core/config.py`.
- Key env vars: `SECRET_KEY`, `DATABASE_URL`, `CORS_ORIGINS`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`, `OLLAMA_BASE_URL`.
