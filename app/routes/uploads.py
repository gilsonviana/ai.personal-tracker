from __future__ import annotations

import uuid
from io import BytesIO

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import current_active_user
from app.db.database import get_async_session
from app.ml.categoriser import get_categoriser
from app.ml.parser import parse_file
from app.ml.transfer_detector import detect_transfers
from app.models.bank_account import BankAccount, Import
from app.models.category import Category
from app.models.transaction import Transaction
from app.models.user import User

router = APIRouter(prefix="/uploads", tags=["uploads"])


class UploadResult(BaseModel):
    import_id: uuid.UUID
    rows_imported: int
    transfers_detected: int
    account_currency: str


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

    duplicate = await session.execute(
        select(Import).where(
            Import.bank_account_id == account_id,
            Import.filename == filename,
        )
    )
    if duplicate.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail=f'"{filename}" has already been imported into this account.',
        )

    rows = parse_file(BytesIO(content), filename)
    if not rows:
        raise HTTPException(status_code=422, detail="No transactions found in file")

    imp = Import(bank_account_id=account_id, filename=filename, row_count=len(rows))
    session.add(imp)
    await session.flush()

    # Build name → UUID map for system + user categories so predictions can be
    # stored as foreign keys rather than being discarded.
    cat_rows = (await session.execute(
        select(Category.id, Category.name).where(
            Category.user_id.is_(None) | (Category.user_id == user.id)
        )
    )).all()
    category_map: dict[str, uuid.UUID] = {r.name: r.id for r in cat_rows}

    categoriser = get_categoriser(user_id=str(user.id))
    descriptions = [r["description"] for r in rows]
    predicted = categoriser.predict(descriptions) if categoriser else [None] * len(rows)

    for row, cat_name in zip(rows, predicted):
        tx = Transaction(
            bank_account_id=account_id,
            import_id=imp.id,
            date=row["date"],
            description=row["description"],
            amount=row["amount"],
            type=row["type"],
            category_id=category_map.get(cat_name) if cat_name else None,
        )
        session.add(tx)

    await session.commit()
    transfers = await detect_transfers(user.id, session)
    return UploadResult(
        import_id=imp.id,
        rows_imported=len(rows),
        transfers_detected=transfers,
        account_currency=account.currency,
    )


@router.delete("/{import_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_import(
    import_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    result = await session.execute(
        select(Import)
        .join(BankAccount, Import.bank_account_id == BankAccount.id)
        .where(Import.id == import_id, BankAccount.user_id == user.id)
    )
    imp = result.scalar_one_or_none()
    if not imp:
        raise HTTPException(status_code=404, detail="Import not found")

    # Transaction.import_id has ondelete=SET NULL, so we delete them explicitly.
    await session.execute(
        delete(Transaction).where(Transaction.import_id == import_id)
    )
    await session.delete(imp)
    await session.commit()
