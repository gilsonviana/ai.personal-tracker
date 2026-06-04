from __future__ import annotations

import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import current_active_user
from app.db.database import get_async_session
from app.ml.transfer_detector import detect_transfers, unmark_transfer
from app.models.bank_account import BankAccount
from app.models.transaction import Transaction
from app.models.user import User

router = APIRouter(prefix="/transactions", tags=["transactions"])


class TransactionOut(BaseModel):
    id: uuid.UUID
    bank_account_id: uuid.UUID
    date: date
    description: str
    amount: int
    type: str
    category_id: uuid.UUID | None
    is_anomaly: bool
    is_transfer: bool
    transfer_pair_id: uuid.UUID | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TransactionPatch(BaseModel):
    category_id: uuid.UUID | None = None
    notes: str | None = None
    is_transfer: bool | None = None


async def _owned_account_ids(user: User, session: AsyncSession) -> list[uuid.UUID]:
    result = await session.execute(
        select(BankAccount.id).where(BankAccount.user_id == user.id)
    )
    return result.scalars().all()


@router.get("/", response_model=list[TransactionOut])
async def list_transactions(
    account_id: uuid.UUID | None = Query(None),
    start: date | None = Query(None),
    end: date | None = Query(None),
    limit: int = Query(200, le=1000),
    offset: int = Query(0),
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    owned = await _owned_account_ids(user, session)
    q = select(Transaction).where(Transaction.bank_account_id.in_(owned))
    if account_id:
        if account_id not in owned:
            raise HTTPException(status_code=403, detail="Forbidden")
        q = q.where(Transaction.bank_account_id == account_id)
    if start:
        q = q.where(Transaction.date >= start)
    if end:
        q = q.where(Transaction.date <= end)
    q = q.order_by(Transaction.date.desc()).limit(limit).offset(offset)
    result = await session.execute(q)
    return result.scalars().all()


@router.patch("/{transaction_id}", response_model=TransactionOut)
async def patch_transaction(
    transaction_id: uuid.UUID,
    payload: TransactionPatch,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    owned = await _owned_account_ids(user, session)
    result = await session.execute(
        select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.bank_account_id.in_(owned),
        )
    )
    tx = result.scalar_one_or_none()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    patch = payload.model_dump(exclude_unset=True)

    # Unmarking a transfer must clear both legs via transfer_pair_id
    if patch.get("is_transfer") is False:
        await unmark_transfer(transaction_id, session)
        patch.pop("is_transfer")

    for field, value in patch.items():
        setattr(tx, field, value)

    await session.commit()
    await session.refresh(tx)
    return tx


@router.post("/detect-transfers", status_code=status.HTTP_200_OK)
async def run_transfer_detection(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    pairs_found = await detect_transfers(user.id, session)
    return {"pairs_found": pairs_found}


@router.delete("/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_all_transactions(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    owned = await _owned_account_ids(user, session)
    await session.execute(
        delete(Transaction).where(Transaction.bank_account_id.in_(owned))
    )
    await session.commit()
