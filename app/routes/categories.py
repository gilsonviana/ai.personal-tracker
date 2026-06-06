from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import current_active_user
from app.db.database import get_async_session
from app.ml.categoriser import MIN_TRAIN_SAMPLES, train as train_model
from app.models.bank_account import BankAccount
from app.models.category import Category
from app.models.transaction import Transaction
from app.models.user import User

router = APIRouter(prefix="/categories", tags=["categories"])


class CategoryOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None
    name: str
    type: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CategoryCreate(BaseModel):
    name: str
    type: Literal["income", "expense"]


class RetrainResult(BaseModel):
    samples_used: int
    classes: list[str]


@router.get("/", response_model=list[CategoryOut])
async def list_categories(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    result = await session.execute(
        select(Category)
        .where(Category.user_id.is_(None) | (Category.user_id == user.id))
        .order_by(Category.type, Category.name)
    )
    return result.scalars().all()


@router.post("/", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
async def create_category(
    payload: CategoryCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    existing = await session.execute(
        select(Category).where(
            Category.name == payload.name,
            Category.user_id.is_(None) | (Category.user_id == user.id),
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="A category with this name already exists.")
    cat = Category(user_id=user.id, name=payload.name, type=payload.type)
    session.add(cat)
    await session.commit()
    await session.refresh(cat)
    return cat


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    result = await session.execute(
        select(Category).where(Category.id == category_id)
    )
    cat = result.scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found.")
    if cat.user_id is None:
        raise HTTPException(status_code=403, detail="System categories cannot be deleted.")
    if cat.user_id != user.id:
        raise HTTPException(status_code=403, detail="Category not found.")
    await session.delete(cat)
    await session.commit()


@router.post("/retrain", response_model=RetrainResult)
async def retrain_categoriser(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """Train a personal categorisation model from the user's own labeled transactions."""
    rows = (await session.execute(
        select(Transaction.description, Category.name.label("cat_name"))
        .join(Category, Transaction.category_id == Category.id)
        .join(BankAccount, Transaction.bank_account_id == BankAccount.id)
        .where(
            BankAccount.user_id == user.id,
            Transaction.category_id.is_not(None),
            Transaction.is_transfer.is_(False),
        )
    )).all()

    if len(rows) < MIN_TRAIN_SAMPLES:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Need at least {MIN_TRAIN_SAMPLES} categorized transactions to train. "
                f"Found {len(rows)}. Assign more categories and try again."
            ),
        )

    descriptions = [r.description for r in rows]
    labels = [r.cat_name for r in rows]

    train_model(descriptions, labels, user_id=str(user.id))
    return RetrainResult(samples_used=len(rows), classes=sorted(set(labels)))
