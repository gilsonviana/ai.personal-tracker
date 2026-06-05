from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import current_active_user
from app.db.database import get_async_session
from app.models.bank_account import BankAccount, Import
from app.models.user import User

router = APIRouter(prefix="/accounts", tags=["accounts"])


class AccountCreate(BaseModel):
    name: str
    bank_name: str | None = None
    currency: str = "BRL"


class AccountOut(BaseModel):
    id: uuid.UUID
    name: str
    bank_name: str | None
    currency: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ImportOut(BaseModel):
    id: uuid.UUID
    filename: str
    row_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("/", response_model=list[AccountOut])
async def list_accounts(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    result = await session.execute(
        select(BankAccount).where(BankAccount.user_id == user.id)
    )
    return result.scalars().all()


@router.post("/", response_model=AccountOut, status_code=status.HTTP_201_CREATED)
async def create_account(
    payload: AccountCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    account = BankAccount(user_id=user.id, **payload.model_dump())
    session.add(account)
    await session.commit()
    await session.refresh(account)
    return account


@router.get("/{account_id}/imports", response_model=list[ImportOut])
async def list_imports(
    account_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    result = await session.execute(
        select(BankAccount).where(
            BankAccount.id == account_id, BankAccount.user_id == user.id
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Account not found")

    result = await session.execute(
        select(Import)
        .where(Import.bank_account_id == account_id)
        .order_by(Import.created_at.desc())
    )
    return result.scalars().all()


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    account_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    result = await session.execute(
        select(BankAccount).where(
            BankAccount.id == account_id, BankAccount.user_id == user.id
        )
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    await session.delete(account)
    await session.commit()
