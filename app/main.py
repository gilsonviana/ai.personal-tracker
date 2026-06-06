from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.security import auth_backend, fastapi_users
from app.db.database import Base, engine
from app.models import bank_account, category, fx_rate, preferences, transaction, user  # noqa: F401
from app.routes import accounts, fx, insights, preferences as pref_route, transactions, uploads
from app.routes.auth import UserCreate, UserRead, UserUpdate
from app.services.seed import seed_categories


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await seed_categories()
    yield


app = FastAPI(title="FInSight API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    fastapi_users.get_auth_router(auth_backend), prefix="/auth/jwt", tags=["auth"]
)
app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/auth",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate), prefix="/users", tags=["users"]
)
app.include_router(accounts.router)
app.include_router(uploads.router)
app.include_router(transactions.router)
app.include_router(insights.router)
app.include_router(pref_route.router)
app.include_router(fx.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
