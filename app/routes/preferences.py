from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import current_active_user
from app.db.database import get_async_session
from app.models.user import User
from app.services.fx import get_or_create_prefs

router = APIRouter(prefix="/preferences", tags=["preferences"])

_SUPPORTED = {"BRL", "USD", "EUR", "GBP", "ARS"}


class PreferencesOut(BaseModel):
    main_currency: str


class PreferencesUpdate(BaseModel):
    main_currency: str


@router.get("/", response_model=PreferencesOut)
async def get_preferences(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    prefs = await get_or_create_prefs(user.id, session)
    await session.commit()
    return PreferencesOut(main_currency=prefs.main_currency)


@router.patch("/", response_model=PreferencesOut)
async def update_preferences(
    body: PreferencesUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    prefs = await get_or_create_prefs(user.id, session)
    prefs.main_currency = body.main_currency.upper()
    await session.commit()
    return PreferencesOut(main_currency=prefs.main_currency)
