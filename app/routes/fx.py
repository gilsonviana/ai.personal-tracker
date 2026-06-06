from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import date

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import current_active_user
from app.db.database import get_async_session
from app.models.bank_account import BankAccount
from app.models.fx_rate import FxRate
from app.models.transaction import Transaction
from app.models.user import User
from app.services.fx import fetch_and_cache_rates, get_or_create_prefs

router = APIRouter(prefix="/fx", tags=["fx"])


class SyncResult(BaseModel):
    rates_fetched: int


@router.post("/sync", response_model=SyncResult)
async def sync_fx_rates(
    import_id: uuid.UUID | None = Query(None),
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    prefs = await get_or_create_prefs(user.id, session)
    main_currency = prefs.main_currency

    q = (
        select(Transaction.date, BankAccount.currency)
        .join(BankAccount, Transaction.bank_account_id == BankAccount.id)
        .where(BankAccount.user_id == user.id)
        .where(BankAccount.currency != main_currency)
        .where(Transaction.is_transfer.is_(False))
        .distinct()
    )
    if import_id:
        q = q.where(Transaction.import_id == import_id)

    rows = (await session.execute(q)).all()

    dates_by_currency: dict[str, set[date]] = defaultdict(set)
    for row in rows:
        dates_by_currency[row.currency].add(row.date)

    total_fetched = 0
    for from_currency, all_dates in dates_by_currency.items():
        # Only fetch dates not already cached
        existing = {
            r.rate_date
            for r in (
                await session.execute(
                    select(FxRate.rate_date).where(
                        FxRate.from_currency == from_currency,
                        FxRate.to_currency == main_currency,
                        FxRate.rate_date.in_(all_dates),
                    )
                )
            ).all()
        }
        missing = list(all_dates - existing)
        if missing:
            fetched = await fetch_and_cache_rates(session, missing, from_currency, main_currency)
            total_fetched += fetched

    await session.commit()
    return SyncResult(rates_fetched=total_fetched)
