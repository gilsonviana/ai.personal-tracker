from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import delete, func, select
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


class TransactionPage(BaseModel):
    items: list[TransactionOut]
    total: int
    offset: int
    limit: int


class TransferLinkRequest(BaseModel):
    expense_ids: list[uuid.UUID]
    income_id: uuid.UUID


async def _owned_account_ids(user: User, session: AsyncSession) -> list[uuid.UUID]:
    result = await session.execute(
        select(BankAccount.id).where(BankAccount.user_id == user.id)
    )
    return result.scalars().all()


@router.get("/", response_model=TransactionPage)
async def list_transactions(
    account_ids: list[uuid.UUID] = Query(default=[]),
    start: date | None = Query(None),
    end: date | None = Query(None),
    tx_type: Literal["income", "expense"] | None = Query(None, alias="type"),
    is_transfer: bool | None = Query(None),
    category_id: uuid.UUID | None = Query(None),
    search: str | None = Query(None),
    is_anomaly: bool | None = Query(None),
    limit: int = Query(100, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    owned = await _owned_account_ids(user, session)

    filters = [Transaction.bank_account_id.in_(owned)]

    if account_ids:
        forbidden = set(account_ids) - set(owned)
        if forbidden:
            raise HTTPException(status_code=403, detail="Forbidden")
        filters.append(Transaction.bank_account_id.in_(account_ids))
    if start:
        filters.append(Transaction.date >= start)
    if end:
        filters.append(Transaction.date <= end)
    if tx_type is not None:
        filters.append(Transaction.type == tx_type)
    if is_transfer is not None:
        filters.append(Transaction.is_transfer == is_transfer)
    if category_id is not None:
        filters.append(Transaction.category_id == category_id)
    if search:
        filters.append(Transaction.description.ilike(f"%{search}%"))
    if is_anomaly is not None:
        filters.append(Transaction.is_anomaly == is_anomaly)

    total: int = (
        await session.execute(select(func.count(Transaction.id)).where(*filters))
    ).scalar_one()

    q = (
        select(Transaction)
        .where(*filters)
        .order_by(Transaction.date.desc())
        .limit(limit)
        .offset(offset)
    )
    primary_txs = (await session.execute(q)).scalars().all()

    # Fetch partner legs for any transfer pairs on the current page
    partner_txs: list[Transaction] = []
    pair_ids = [tx.transfer_pair_id for tx in primary_txs if tx.transfer_pair_id]
    if pair_ids:
        primary_ids = [tx.id for tx in primary_txs]
        partner_result = await session.execute(
            select(Transaction).where(
                Transaction.transfer_pair_id.in_(pair_ids),
                Transaction.bank_account_id.in_(owned),
                Transaction.id.not_in(primary_ids),
            )
        )
        partner_txs = partner_result.scalars().all()

    return TransactionPage(
        items=list(primary_txs) + list(partner_txs),
        total=total,
        offset=offset,
        limit=limit,
    )


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
    if not payload.expense_ids:
        raise HTTPException(status_code=422, detail="At least one expense_id is required")

    owned = await _owned_account_ids(user, session)
    all_ids = list(payload.expense_ids) + [payload.income_id]

    result = await session.execute(
        select(Transaction).where(
            Transaction.id.in_(all_ids),
            Transaction.bank_account_id.in_(owned),
        )
    )
    txs = result.scalars().all()

    if len(txs) != len(all_ids):
        raise HTTPException(status_code=404, detail="One or more transactions not found")

    tx_map = {tx.id: tx for tx in txs}
    exp_txs = [tx_map[eid] for eid in payload.expense_ids]
    inc_tx  = tx_map[payload.income_id]

    if any(t.type != "expense" for t in exp_txs):
        raise HTTPException(status_code=422, detail="All expense_ids must be expense transactions")
    if inc_tx.type != "income":
        raise HTTPException(status_code=422, detail="income_id must be an income transaction")

    all_accounts = {t.bank_account_id for t in exp_txs} | {inc_tx.bank_account_id}
    if len(all_accounts) < 2:
        raise HTTPException(status_code=422, detail="Transactions must span at least two different accounts")

    if any(t.is_transfer for t in exp_txs) or inc_tx.is_transfer:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="One or more transactions are already part of a transfer pair — unlink them first",
        )

    pair_id = uuid.uuid4()
    for t in exp_txs + [inc_tx]:
        t.is_transfer = True
        t.transfer_pair_id = pair_id
    await session.commit()
    for t in exp_txs + [inc_tx]:
        await session.refresh(t)
    return exp_txs + [inc_tx]


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
