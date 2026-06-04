from __future__ import annotations

import uuid
from io import BytesIO

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import current_active_user
from app.db.database import get_async_session
from app.ml.categoriser import get_categoriser
from app.ml.parser import parse_file
from app.models.bank_account import BankAccount, Import
from app.models.transaction import Transaction
from app.models.user import User

router = APIRouter(prefix="/uploads", tags=["uploads"])


class UploadResult(BaseModel):
    import_id: uuid.UUID
    rows_imported: int


@router.post("/{account_id}", response_model=UploadResult)
async def upload_statement(
    account_id: uuid.UUID,
    file: UploadFile = File(...),
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

    content = await file.read()
    filename = file.filename or "upload"
    rows = parse_file(BytesIO(content), filename)
    if not rows:
        raise HTTPException(status_code=422, detail="No transactions found in file")

    imp = Import(bank_account_id=account_id, filename=filename, row_count=len(rows))
    session.add(imp)
    await session.flush()

    categoriser = get_categoriser()
    descriptions = [r["description"] for r in rows]
    categories = categoriser.predict(descriptions) if categoriser else [None] * len(rows)

    for row, cat in zip(rows, categories):
        tx = Transaction(
            bank_account_id=account_id,
            import_id=imp.id,
            date=row["date"],
            description=row["description"],
            amount=row["amount"],
            type=row["type"],
        )
        session.add(tx)

    await session.commit()
    return UploadResult(import_id=imp.id, rows_imported=len(rows))
