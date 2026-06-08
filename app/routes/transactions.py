from __future__ import annotations

import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import current_active_user
from app.db.database import get_async_session
from app.ml.transfer_detector import detect_transfers, mark_transfer, unmark_transfer
from app.models.bank_account import BankAccount, Import
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


class BulkCategoryPatch(BaseModel):
    transaction_ids: list[uuid.UUID]
    category_id: uuid.UUID | None = None


class TransferLinkRequest(BaseModel):
    expense_id: uuid.UUID
    income_id: uuid.UUID


async def _owned_account_ids(user: User, session: AsyncSession) -> list[uuid.UUID]:
    result = await session.execute(
        select(BankAccount.id).where(BankAccount.user_id == user.id)
    )
    return result.scalars().all()


@router.get("/", response_model=list[TransactionOut])
async def list_transactions(
    account_ids: list[uuid.UUID] = Query(default=[]),
    start: date | None = Query(None),
    end: date | None = Query(None),
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    owned = await _owned_account_ids(user, session)
    q = select(Transaction).where(Transaction.bank_account_id.in_(owned))
    if account_ids:
        forbidden = set(account_ids) - set(owned)
        if forbidden:
            raise HTTPException(status_code=403, detail="Forbidden")
        q = q.where(Transaction.bank_account_id.in_(account_ids))
    if start:
        q = q.where(Transaction.date >= start)
    if end:
        q = q.where(Transaction.date <= end)
    q = q.order_by(Transaction.date.desc())
    result = await session.execute(q)
    primary_txs = result.scalars().all()

    pair_ids = [tx.transfer_pair_id for tx in primary_txs if tx.transfer_pair_id]
    if pair_ids:
        primary_ids = [tx.id for tx in primary_txs]
        partner_q = select(Transaction).where(
            Transaction.transfer_pair_id.in_(pair_ids),
            Transaction.bank_account_id.in_(owned),
            Transaction.id.not_in(primary_ids),
        )
        partner_result = await session.execute(partner_q)
        return primary_txs + partner_result.scalars().all()

    return primary_txs


@router.patch("/bulk-category", response_model=list[TransactionOut])
async def bulk_patch_category(
    payload: BulkCategoryPatch,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    if not payload.transaction_ids:
        raise HTTPException(status_code=400, detail="No transaction IDs provided")
    owned = await _owned_account_ids(user, session)
    result = await session.execute(
        select(Transaction).where(
            Transaction.id.in_(payload.transaction_ids),
            Transaction.bank_account_id.in_(owned),
        )
    )
    txs = result.scalars().all()

    found_ids = {tx.id for tx in txs}
    missing = [str(tid) for tid in payload.transaction_ids if tid not in found_ids]
    if missing:
        raise HTTPException(status_code=404, detail=f"Transactions not found: {', '.join(missing)}")

    for tx in txs:
        tx.category_id = payload.category_id

    await session.commit()
    for tx in txs:
        await session.refresh(tx)
    return txs


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


@router.post("/link-transfer", response_model=list[TransactionOut])
async def link_transfer_pair(
    payload: TransferLinkRequest,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    owned = await _owned_account_ids(user, session)
    result = await session.execute(
        select(Transaction).where(
            Transaction.id.in_([payload.expense_id, payload.income_id]),
            Transaction.bank_account_id.in_(owned),
        )
    )
    txs = result.scalars().all()

    if len(txs) != 2:
        raise HTTPException(status_code=404, detail="One or both transactions not found")

    tx_map = {tx.id: tx for tx in txs}
    exp_tx = tx_map.get(payload.expense_id)
    inc_tx = tx_map.get(payload.income_id)

    if exp_tx.type != "expense" or inc_tx.type != "income":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="expense_id must be an expense transaction and income_id must be an income transaction",
        )

    if exp_tx.bank_account_id == inc_tx.bank_account_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Both transactions belong to the same account — a transfer requires two different accounts",
        )

    if exp_tx.is_transfer or inc_tx.is_transfer:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="One or both transactions are already part of a transfer pair — unlink them first",
        )

    await mark_transfer(payload.expense_id, payload.income_id, session)
    await session.refresh(exp_tx)
    await session.refresh(inc_tx)
    return [exp_tx, inc_tx]


@router.delete("/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_all_transactions(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    owned = await _owned_account_ids(user, session)
    await session.execute(
        delete(Transaction).where(Transaction.bank_account_id.in_(owned))
    )
    await session.execute(
        delete(Import).where(Import.bank_account_id.in_(owned))
    )
    await session.commit()
