# FInSight

Privacy-first personal finance analyser. Upload your bank statements and get ML-powered financial health insights — everything runs locally, no data ever leaves your machine.

---

## Features

- **Statement ingestion** — upload CSV or PDF bank statements
- **Auto-categorisation** — TF-IDF + Logistic Regression classifier trained on EN/PT transaction descriptions
- **Anomaly detection** — Isolation Forest flags unusual spending per category
- **Financial health score** — savings-rate-based score across the last 12 months
- **LLM narrative** — Ollama (mistral:7b) generates a plain-English summary of your finances
- **JWT auth** — every resource is scoped to the authenticated user; nothing leaks across accounts
- **Streamlit UI** — browser dashboard for uploads, charts, and transaction review

---

## Stack

| Layer | Tool |
|---|---|
| API | FastAPI + uvicorn |
| Auth | FastAPI-Users + JWT |
| Database | PostgreSQL 15 (asyncpg) |
| ORM / Migrations | SQLAlchemy 2.0 async + Alembic |
| CSV parsing | pandas |
| PDF parsing | pdfplumber |
| ML | scikit-learn (TF-IDF, Logistic Regression, Isolation Forest) |
| LLM | Ollama — mistral:7b |
| Frontend | Streamlit |
| Infrastructure | Docker + docker-compose |

---

## Requirements

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or Docker Engine + Compose)
- [Ollama](https://ollama.com/) running locally with the `mistral:7b` model

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

# 6. Start the Streamlit frontend
cd frontend && pip install -r requirements.txt && streamlit run streamlit_app.py
```

Open [http://localhost:8501](http://localhost:8501) for the UI or [http://localhost:8000/docs](http://localhost:8000/docs) for the interactive API docs.

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
│   ├── main.py               # FastAPI app, lifespan, router registration
│   ├── core/
│   │   ├── config.py         # pydantic-settings (reads .env)
│   │   └── security.py       # FastAPI-Users + JWT setup
│   ├── db/
│   │   └── database.py       # Async engine, session factory, Base
│   ├── models/               # SQLAlchemy ORM models
│   │   ├── user.py
│   │   ├── bank_account.py   # BankAccount + Import
│   │   ├── transaction.py
│   │   └── category.py
│   ├── routes/
│   │   ├── auth.py           # User schemas (UserRead/Create/Update)
│   │   ├── accounts.py       # CRUD for bank accounts
│   │   ├── uploads.py        # CSV/PDF upload → transactions
│   │   ├── transactions.py   # List + patch transactions
│   │   └── insights.py       # Monthly aggregation + score + narrative
│   ├── ml/
│   │   ├── parser.py         # CSV and PDF statement parser
│   │   ├── categoriser.py    # TF-IDF + LR classifier
│   │   ├── anomaly.py        # Isolation Forest per category
│   │   ├── scoring.py        # Savings-rate health score
│   │   └── reflection.py     # Ollama narrative generation
│   └── services/
│       └── seed.py           # Seeds system-default categories on startup
├── alembic/                  # Migration scripts
├── frontend/
│   └── streamlit_app.py      # Streamlit UI
├── training/
│   └── train_categoriser.py  # Trains and saves the categoriser model
├── models/                   # Serialised .joblib model files (git-ignored)
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

---

## Training the Categoriser

The categoriser ships with 20 built-in seed samples (EN + PT). To train on your own labelled data, create `training/labelled_data.json`:

```json
[
  { "description": "SUPERMERCADO EXTRA", "category": "Food & Groceries" },
  { "description": "UBER TRIP", "category": "Transport" }
]
```

Then run:

```bash
docker compose exec api python training/train_categoriser.py
```

The trained model is saved to `models/categoriser.joblib` and loaded automatically at API startup.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://finsight:finsight@localhost:5432/finsight` | Postgres connection string |
| `SECRET_KEY` | `change-me-in-production` | JWT signing key — **change this** |
| `ALGORITHM` | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Token lifetime |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API base URL |

---

## API Overview

All routes except `/auth/register` and `/auth/jwt/login` require a `Bearer` token.

| Method | Path | Description |
|---|---|---|
| `POST` | `/auth/register` | Create account |
| `POST` | `/auth/jwt/login` | Obtain JWT |
| `GET` | `/accounts/` | List bank accounts |
| `POST` | `/accounts/` | Create bank account |
| `DELETE` | `/accounts/{id}` | Delete bank account |
| `POST` | `/uploads/{account_id}` | Upload CSV or PDF statement |
| `GET` | `/transactions/` | List transactions (filterable) |
| `PATCH` | `/transactions/{id}` | Update category / notes |
| `GET` | `/insights/monthly` | Monthly summaries + score + narrative |

Full interactive docs at [http://localhost:8000/docs](http://localhost:8000/docs).

---

## Financial Health Score

The score is a number from **0 to 100** that reflects how well you are saving money across the selected period. It is computed per month and then averaged.

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
| **85 – 100** | Excellent. You consistently save 25–30 %+ of your income. You are building wealth and have a strong financial buffer. |
| **60 – 84** | Good. You save on average 18–25 % of your income. Some months are better than others but the trend is positive. |
| **35 – 59** | Fair. Savings are inconsistent — some months you save well, others you break even or overspend. |
| **10 – 34** | Weak. Most months your expenses consume nearly all your income, leaving little room for savings or emergencies. |
| **0 – 9** | Critical. You are regularly spending more than you earn. Immediate review of recurring expenses is recommended. |

### Examples

**High score — 91.7**

| Month | Income | Expenses | Savings rate | Monthly score |
|---|---|---|---|---|
| 2025-01 | R$ 10,000 | R$ 6,500 | 35 % | 1.00 |
| 2025-02 | R$ 10,000 | R$ 6,800 | 32 % | 1.00 |
| 2025-03 | R$ 10,000 | R$ 7,500 | 25 % | 0.83 |

Average score: `(1.00 + 1.00 + 0.83) / 3 × 100 = 94.4`

A person earning R$ 10,000/month and spending around R$ 7,000 consistently qualifies for a high score. Even one month of higher spending only reduces the score slightly.

---

**Low score — 18.3**

| Month | Income | Expenses | Savings rate | Monthly score |
|---|---|---|---|---|
| 2025-01 | R$ 10,000 | R$ 9,800 | 2 % | 0.07 |
| 2025-02 | R$ 10,000 | R$ 11,200 | −12 % | 0.00 |
| 2025-03 | R$ 10,000 | R$ 9,400 | 6 % | 0.20 |

Average score: `(0.07 + 0.00 + 0.20) / 3 × 100 = 9.0`

A person who consistently spends close to — or beyond — their entire income will score near 0. A single month where expenses exceed income contributes 0 to the average, pulling the score down significantly.

---

## Amount Handling

All amounts are stored as **integers in cents** (always positive). The transaction direction is captured by the `type` field (`income` or `expense`), never by a negative sign.

- Ingestion: `"1.234,56"` → `123456` (handles Brazilian number format)
- Display: `123456` → `"R$ 1,234.56"`

---

## Privacy

No data leaves your machine. Postgres, the API, and the ML models all run locally in Docker. Ollama also runs locally. The only network calls are between your browser and `localhost`.
