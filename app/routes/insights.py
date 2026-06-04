from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import current_active_user
from app.db.database import get_async_session
from app.ml.reflection import get_reflection
from app.ml.scoring import compute_score
from app.models.bank_account import BankAccount
from app.models.transaction import Transaction
from app.models.user import User

router = APIRouter(prefix="/insights", tags=["insights"])


class PeriodSummary(BaseModel):
    period: str
    total_income: int
    total_expenses: int
    net: int


class InsightResponse(BaseModel):
    summaries: list[PeriodSummary]
    score: float
    narrative: str


async def _owned_account_ids(user: User, session: AsyncSession) -> list[uuid.UUID]:
    result = await session.execute(
        select(BankAccount.id).where(BankAccount.user_id == user.id)
    )
    return result.scalars().all()


@router.get("/monthly", response_model=InsightResponse)
async def monthly_insights(
    account_id: uuid.UUID | None = Query(None),
    year: int | None = Query(None, description="Filter to a specific year"),
    month: int | None = Query(None, ge=1, le=12, description="Filter to a specific month (requires year)"),
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    owned = await _owned_account_ids(user, session)
    if account_id:
        ids = [account_id] if account_id in owned else []
    else:
        ids = owned

    period_label = func.to_char(Transaction.date, "YYYY-MM")
    q = (
        select(
            period_label.label("period"),
            func.sum(
                case((Transaction.type == "income", Transaction.amount), else_=0)
            ).label("total_income"),
            func.sum(
                case((Transaction.type == "expense", Transaction.amount), else_=0)
            ).label("total_expenses"),
        )
        .where(Transaction.bank_account_id.in_(ids))
        .where(Transaction.is_transfer.is_(False))
    )

    if year and month:
        q = q.where(func.extract("year", Transaction.date) == year)
        q = q.where(func.extract("month", Transaction.date) == month)
    elif year:
        q = q.where(func.extract("year", Transaction.date) == year)
    else:
        q = q.limit(12)

    q = q.group_by(period_label).order_by(period_label.asc())

    rows = (await session.execute(q)).all()
    summaries = [
        PeriodSummary(
            period=r.period,
            total_income=r.total_income or 0,
            total_expenses=r.total_expenses or 0,
            net=(r.total_income or 0) - (r.total_expenses or 0),
        )
        for r in rows
    ]
    score = compute_score(summaries)
    narrative = await get_reflection(summaries)
    return InsightResponse(summaries=summaries, score=score, narrative=narrative)
