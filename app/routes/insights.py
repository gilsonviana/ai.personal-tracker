from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import date

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
from app.services.fx import get_or_create_prefs, get_rate_for_date, load_rates

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
    main_currency: str
    has_unconverted: bool


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

    prefs = await get_or_create_prefs(user.id, session)
    main_currency = prefs.main_currency

    # Group by (date, currency) to allow per-date FX conversion
    q = (
        select(
            Transaction.date,
            BankAccount.currency,
            func.sum(
                case((Transaction.type == "income", Transaction.amount), else_=0)
            ).label("total_income"),
            func.sum(
                case((Transaction.type == "expense", Transaction.amount), else_=0)
            ).label("total_expenses"),
        )
        .join(BankAccount, Transaction.bank_account_id == BankAccount.id)
        .where(Transaction.bank_account_id.in_(ids))
        .where(Transaction.is_transfer.is_(False))
    )

    today = date.today()
    if year and month:
        q = q.where(func.extract("year", Transaction.date) == year)
        q = q.where(func.extract("month", Transaction.date) == month)
    elif year:
        q = q.where(func.extract("year", Transaction.date) == year)
    else:
        m = today.month - 11
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        q = q.where(Transaction.date >= date(y, m, 1))

    q = q.group_by(Transaction.date, BankAccount.currency).order_by(Transaction.date)

    rows = (await session.execute(q)).all()

    # Load FX rates for any non-main currencies present
    non_main = {r.currency for r in rows if r.currency != main_currency}
    rates_by_currency = await load_rates(session, non_main, main_currency)

    # Aggregate into period buckets (YYYY-MM) in main currency
    period_income: dict[str, int] = defaultdict(int)
    period_expenses: dict[str, int] = defaultdict(int)
    has_unconverted = False

    for row in rows:
        period = row.date.strftime("%Y-%m")

        if row.currency == main_currency:
            period_income[period] += row.total_income or 0
            period_expenses[period] += row.total_expenses or 0
        else:
            rate = get_rate_for_date(rates_by_currency.get(row.currency, []), row.date)
            if rate is None:
                has_unconverted = True
                continue  # exclude rows without a rate rather than distort totals
            period_income[period] += int((row.total_income or 0) * rate)
            period_expenses[period] += int((row.total_expenses or 0) * rate)

    all_periods = sorted(set(period_income) | set(period_expenses))
    summaries = [
        PeriodSummary(
            period=p,
            total_income=period_income[p],
            total_expenses=period_expenses[p],
            net=period_income[p] - period_expenses[p],
        )
        for p in all_periods
    ]

    score = compute_score(summaries)
    narrative = await get_reflection(summaries, score)
    return InsightResponse(
        summaries=summaries,
        score=score,
        narrative=narrative,
        main_currency=main_currency,
        has_unconverted=has_unconverted,
    )
