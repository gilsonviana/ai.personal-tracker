import uuid

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from fastapi_users import schemas
from pydantic import BaseModel

from app.core.security import (
    UserManager,
    get_jwt_strategy,
    get_refresh_jwt_strategy,
    get_user_manager,
)


class UserRead(schemas.BaseUser[uuid.UUID]):
    full_name: str | None = None


class UserCreate(schemas.BaseUserCreate):
    full_name: str | None = None


class UserUpdate(schemas.BaseUserUpdate):
    full_name: str | None = None


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AccessToken(BaseModel):
    access_token: str
    token_type: str = "bearer"


router = APIRouter(prefix="/auth/jwt", tags=["auth"])


@router.post("/token", response_model=TokenPair)
async def login_for_token_pair(
    credentials: OAuth2PasswordRequestForm = Depends(),
    user_manager: UserManager = Depends(get_user_manager),
):
    """Login and receive both a short-lived access token and a long-lived refresh token."""
    user = await user_manager.authenticate(credentials)
    if user is None or not user.is_active:
        raise HTTPException(status_code=400, detail="LOGIN_BAD_CREDENTIALS")

    access_token = await get_jwt_strategy().write_token(user)
    refresh_token = await get_refresh_jwt_strategy().write_token(user)
    return TokenPair(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=AccessToken)
async def refresh_access_token(
    refresh_token: str = Body(..., embed=True),
    user_manager: UserManager = Depends(get_user_manager),
):
    """Exchange a valid refresh token for a new access token."""
    user = await get_refresh_jwt_strategy().read_token(refresh_token, user_manager)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="REFRESH_TOKEN_INVALID")

    access_token = await get_jwt_strategy().write_token(user)
    return AccessToken(access_token=access_token)
