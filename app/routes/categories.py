from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
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
    name: str
    type: str
    created_at: datetime

    model_config = {"from_attributes": True}


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
