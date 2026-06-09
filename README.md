# FInSight

Privacy-first personal finance analyser. Upload your bank statements and get ML-powered financial health insights — everything runs locally, no data ever leaves your machine.

---

## Features

- **Statement ingestion** — upload CSV or PDF bank statements
- **Auto-categorisation** — TF-IDF + Logistic Regression classifier trained on EN/PT transaction descriptions
- **Inline category editing** — click any category cell in the transactions table to reassign it; bulk-assign to a selection
- **Category management** — create and delete custom categories; toggle any category's inclusion in insights and graphs
- **Transfer detection** — automatically pairs internal transfers across accounts to avoid double-counting; supports multi-expense transfers (e.g. multiple ATM withdrawals funding one deposit)
- **Anomaly detection** — Isolation Forest flags unusual spending per category
- **Financial health score** — savings-rate-based score across the last 12 months; excluded categories are omitted from the calculation
- **LLM narrative** — Ollama (mistral:7b) generates a plain-English summary of your finances
- **Multi-currency** — FX rates are fetched and stored locally; all amounts are normalised to a configurable main currency for insights
- **JWT auth** — short-lived access tokens + long-lived refresh tokens; every resource is scoped to the authenticated user
- **React frontend** — full SPA with server-side pagination, filter bar, transfer linking, insights chart
- **Streamlit frontend** — legacy browser dashboard (still functional; kept for reference)
- **Automated backups** — daily `pg_dump` via shell script with configurable retention and a guided restore script

---

## Stack

| Layer | Tool |
|---|---|
| API | FastAPI + uvicorn |
| Auth | FastAPI-Users + JWT (access + refresh tokens) |
| Database | PostgreSQL 15 (asyncpg) |
| ORM / Migrations | SQLAlchemy 2.0 async + Alembic |
| CSV parsing | pandas |
| PDF parsing | pdfplumber |
| ML | scikit-learn (TF-IDF, Logistic Regression, Isolation Forest) |
| LLM | Ollama — mistral:7b |
| React frontend | Vite + React 18 + TypeScript, Tailwind CSS, shadcn/ui, TanStack Query & Table, Recharts, Zod |
| Streamlit frontend (legacy) | Streamlit |
| Infrastructure | Docker + docker-compose |

---

## Requirements

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or Docker Engine + Compose)
- [Ollama](https://ollama.com/) running locally with the `mistral:7b` model
- Node.js 20+ (for the React frontend)

Pull the model before starting:

```bash
ollama pull mistral:7b
```

---

## Quick Start

```bash
# 1. Clone and enter the project
git clone <repo-url>
cd finsight

# 2. Create your .env from the example
cp .env.example .env

# 3. Build and start Postgres + API
docker compose up --build -d

# 4. Apply database migrations
docker compose exec api alembic upgrade head

# 5. Train the transaction categoriser (uses built-in seed data)
docker compose exec api python training/train_categoriser.py

# 6. Start the React frontend
cd frontend-react && npm install && npm run dev
```

Open [http://localhost:5173](http://localhost:5173) for the React UI or [http://localhost:8000/docs](http://localhost:8000/docs) for the interactive API docs.

To use the legacy Streamlit UI instead:

```bash
cd frontend && pip install -r requirements.txt && streamlit run streamlit_app.py
# → http://localhost:8501
```

---

## Docker Commands

| Command | Description |
|---|---|
| `docker compose up --build -d` | Build images and start all services |
| `docker compose down` | Stop and remove containers |
| `docker compose build --no-cache api` | Force-rebuild the API image |
| `docker compose restart api` | Restart only the API container |
| `docker compose logs -f` | Tail logs for all services |
| `docker compose exec api bash` | Open a shell inside the API container |
| `docker compose exec db psql -U finsight finsight` | Open `psql` inside the Postgres container |
| `docker compose exec api alembic upgrade head` | Run pending Alembic migrations |
| `docker compose exec api alembic revision --autogenerate -m "..."` | Auto-generate a new Alembic revision |
| `docker compose exec api python training/train_categoriser.py` | Train the transaction categoriser |
| `docker compose exec api ruff check app/` | Run `ruff` linter over `app/` |

---

## Project Structure

```
finsight/
├── app/
│   ├── main.py               # FastAPI app, lifespan, CORS, router registration
│   ├── core/
│   │   ├── config.py         # pydantic-settings (reads .env); CORS_ORIGINS, token lifetimes
│   │   └── security.py       # FastAPI-Users + JWT; access + refresh strategies
│   ├── db/
│   │   └── database.py       # Async engine, session factory, Base
│   ├── models/               # SQLAlchemy ORM models
│   │   ├── user.py
│   │   ├── bank_account.py   # BankAccount + Import
│   │   ├── transaction.py    # is_transfer, transfer_pair_id fields
│   │   ├── category.py       # user_id (null = system), exclude_from_insights
│   │   ├── preferences.py    # Per-user main_currency setting
│   │   └── fx_rate.py        # Cached FX rates by date pair
│   ├── routes/
│   │   ├── auth.py           # Custom /auth/jwt/token + /auth/jwt/refresh endpoints
│   │   ├── accounts.py       # CRUD for bank accounts + import history
│   │   ├── uploads.py        # CSV/PDF upload → transactions
│   │   ├── transactions.py   # List (paginated, full filters), patch, bulk-patch, transfer ops
│   │   ├── categories.py     # CRUD + retrain + insight exclusion toggle
│   │   ├── insights.py       # Monthly aggregation + score + narrative
│   │   ├── preferences.py    # Get/update user preferences
│   │   └── fx.py             # FX rate sync
│   ├── ml/
│   │   ├── parser.py         # CSV and PDF statement parser
│   │   ├── categoriser.py    # TF-IDF + LR classifier (shared + per-user)
│   │   ├── anomaly.py        # Isolation Forest per category
│   │   ├── scoring.py        # Savings-rate health score
│   │   ├── transfer_detector.py  # Auto-pairs internal transfers
│   │   └── reflection.py    # Ollama narrative generation
│   └── services/
│       ├── seed.py           # Seeds system-default categories on startup
│       └── fx.py             # FX fetch + caching logic
├── alembic/                  # Migration scripts
├── frontend-react/           # React SPA (Vite + TypeScript)
│   └── src/
│       ├── api/              # Typed Axios wrappers for every endpoint
│       ├── types/            # TypeScript interfaces mirroring backend schemas
│       ├── lib/              # AuthContext, QueryClient, utils
│       ├── hooks/            # TanStack Query hooks
│       ├── components/       # Layout, Transactions sub-components, shadcn/ui
│       └── pages/            # One file per page
├── frontend/
│   └── streamlit_app.py      # Legacy Streamlit UI (all pages in one file)
├── training/
│   └── train_categoriser.py  # Trains and saves the categoriser model
├── scripts/
│   ├── backup.sh             # pg_dump + gzip + rotation
│   └── restore.sh            # Guided restore from a .sql.gz backup
├── models/                   # Serialised .joblib model files (git-ignored)
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

---

## UI Pages

| Page | Description |
|---|---|
| **Transactions** | Filterable, paginated table (date range, account, type, category, text search); server-side filters; inline category edit; row selection for link/unlink/bulk-assign actions |
| **Categories** | System + custom categories; toggle inclusion in insights; create and delete custom categories; retrain ML model |
| **Accounts** | Bank account CRUD; expandable import history per account |
| **Upload** | Drag-and-drop CSV / PDF statement upload with FX sync prompt for non-BRL accounts |
| **Insights** | Health score (0–100, colour-coded), LLM narrative (analysis + next steps), income vs expenses bar chart |
| **Preferences** | Set main display currency |

---

## Authentication

The API issues two tokens on login:

| Token | Lifetime | Storage |
|---|---|---|
| `access_token` | 60 minutes (configurable) | React Context (memory only) |
| `refresh_token` | 7 days (configurable) | `localStorage` |

The React client automatically refreshes the access token on 401 responses without requiring the user to log in again. The legacy `/auth/jwt/login` endpoint is still available for backward compatibility with the Streamlit client.

---

## Training the Categoriser

The categoriser ships with 160 built-in seed samples covering 14 categories in English and Portuguese. To retrain on your own labelled history, assign categories to your transactions and use the **Retrain model** button on the Categories page, or call the API directly:

```bash
curl -X POST http://localhost:8000/categories/retrain \
  -H "Authorization: Bearer <token>"
```

The personal model is saved to `models/categoriser_<user_id>.joblib` and used in preference to the shared model on future uploads. Retraining never modifies existing transaction records — it only reads the current category labels as training data.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://finsight:finsight@localhost:5432/finsight` | Postgres connection string |
| `SECRET_KEY` | `change-me-in-production` | JWT signing key — **change this** |
| `ALGORITHM` | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Access token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token lifetime |
| `CORS_ORIGINS` | `["http://localhost:3000","http://localhost:5173"]` | Allowed browser origins for CORS |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API base URL |
| `FINSIGHT_BACKUP_KEEP_DAYS` | `30` | Days of backup files to retain |

---

## API Overview

All routes except `/auth/register`, `/auth/jwt/login`, `/auth/jwt/token`, and `/auth/jwt/refresh` require a `Bearer` token.

| Method | Path | Description |
|---|---|---|
| `POST` | `/auth/register` | Create account |
| `POST` | `/auth/jwt/login` | Obtain access token (legacy, Streamlit) |
| `POST` | `/auth/jwt/token` | Obtain access + refresh token pair (React) |
| `POST` | `/auth/jwt/refresh` | Exchange refresh token for new access token |
| `GET` | `/accounts/` | List bank accounts |
| `POST` | `/accounts/` | Create bank account |
| `GET` | `/accounts/{id}/imports` | List import history for an account |
| `DELETE` | `/accounts/{id}` | Delete bank account |
| `POST` | `/uploads/{account_id}` | Upload CSV or PDF statement |
| `DELETE` | `/uploads/{import_id}` | Delete an import and its transactions |
| `GET` | `/transactions/` | List transactions — filters: `start`, `end`, `account_ids`, `type`, `is_transfer`, `category_id`, `search`, `is_anomaly`; pagination: `limit`, `offset` |
| `PATCH` | `/transactions/{id}` | Update category / notes / transfer flag |
| `PATCH` | `/transactions/bulk-category` | Assign one category to multiple transactions |
| `POST` | `/transactions/detect-transfers` | Auto-detect internal transfers |
| `POST` | `/transactions/link-transfer` | Manually link expense(s) + income as a transfer |
| `GET` | `/categories/` | List system + user categories |
| `POST` | `/categories/` | Create a custom category |
| `PATCH` | `/categories/{id}` | Toggle `exclude_from_insights` |
| `DELETE` | `/categories/{id}` | Delete a custom category |
| `POST` | `/categories/retrain` | Retrain personal categoriser from labelled transactions |
| `GET` | `/insights/monthly` | Monthly summaries + score + narrative |
| `GET` | `/preferences/` | Get user preferences |
| `PATCH` | `/preferences/` | Update main currency |
| `POST` | `/fx/sync` | Fetch and cache FX rates for non-BRL transactions |

Full interactive docs at [http://localhost:8000/docs](http://localhost:8000/docs).

---

## Financial Health Score

The score is a number from **0 to 100** that reflects how well you are saving money across the selected period. It is computed per month and then averaged. Transactions belonging to categories marked as **excluded from insights** are not counted.

### How it is calculated

For each month:

1. **Savings rate** is computed as `net ÷ total_income`, where `net = income − expenses`.
2. The savings rate is normalised against a **30 % target** — saving 30 % or more of your income in a month yields a perfect monthly score of 1.0.
3. The result is clamped to `[0.0, 1.0]`, so negative months (expenses exceed income) count as 0 and months above 30 % do not exceed 1.
4. All monthly scores are averaged and multiplied by 100 to produce the final score.

```
monthly_score = clamp(savings_rate / 0.30, 0.0, 1.0)
final_score   = average(monthly_scores) × 100
```

### Score reference

| Score | What it means |
|---|---|
| **85 – 100** | Excellent. You consistently save 25–30 %+ of your income. |
| **60 – 84** | Good. You save on average 18–25 % of your income. |
| **35 – 59** | Fair. Savings are inconsistent — some months you break even or overspend. |
| **10 – 34** | Weak. Most months your expenses consume nearly all your income. |
| **0 – 9** | Critical. You are regularly spending more than you earn. |

---

## Amount Handling

All amounts are stored as **integers in cents** (always positive). The transaction direction is captured by the `type` field (`income` or `expense`), never by a negative sign.

- Ingestion: `"1.234,56"` → `123456` (handles Brazilian number format)
- Display: `123456` → `"R$ 1,234.56"`

---

## Backups

Data is stored in the `pgdata` Docker named volume. The backup scripts use `pg_dump` inside the running container — no Postgres client tools required on the host.

**Manual backup:**

```bash
bash scripts/backup.sh
# → backups/finsight_YYYYMMDD_HHMMSS.sql.gz
```

**Restore from a backup:**

```bash
bash scripts/restore.sh backups/finsight_20260606_020000.sql.gz
```

The restore script drops and recreates the database, then streams the dump in. It prompts for confirmation before making any changes.

**Schedule daily backups (cron):**

```bash
crontab -e
```

Add:

```
0 2 * * * /path/to/finsight/scripts/backup.sh >> /path/to/finsight/backups/backup.log 2>&1
```

Backups older than `FINSIGHT_BACKUP_KEEP_DAYS` (default 30) are removed automatically after each run. The `backups/` directory is git-ignored.

> **macOS note:** `cron` requires Full Disk Access for the terminal app. If jobs run silently without output, grant access in **System Settings → Privacy & Security → Full Disk Access**.

---

## Privacy

No data leaves your machine. Postgres, the API, and the ML models all run locally in Docker. Ollama also runs locally. The only outbound network calls are FX rate fetches if multi-currency support is enabled.
