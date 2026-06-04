from __future__ import annotations

import uuid

from sqlalchemy import func, select, update
from sqlalchemy.orm import aliased
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bank_account import BankAccount
from app.models.transaction import Transaction


async def detect_transfers(user_id: uuid.UUID, session: AsyncSession) -> int:
    """Detect inter-account transfers and mark both legs.

    Matches expense+income pairs across different accounts owned by the same
    user when amount is identical and dates differ by at most 1 calendar day.
    Returns the number of new transfer pairs detected.
    """
    exp = aliased(Transaction, name="exp")
    inc = aliased(Transaction, name="inc")
    ba_exp = aliased(BankAccount, name="ba_exp")
    ba_inc = aliased(BankAccount, name="ba_inc")

    stmt = (
        select(exp.id, inc.id)
        .join(ba_exp, ba_exp.id == exp.bank_account_id)
        .join(ba_inc, ba_inc.id == inc.bank_account_id)
        .where(
            ba_exp.user_id == user_id,
            ba_inc.user_id == user_id,
            exp.type == "expense",
            inc.type == "income",
            exp.amount == inc.amount,
            exp.bank_account_id != inc.bank_account_id,
            func.abs(exp.date - inc.date) <= 1,
            exp.is_transfer.is_(False),
            inc.is_transfer.is_(False),
        )
        .order_by(exp.id, func.abs(exp.date - inc.date), inc.created_at)
    )

    rows = (await session.execute(stmt)).all()

    # Greedy match: each transaction leg can only be used once
    used: set[uuid.UUID] = set()
    pairs: list[tuple[uuid.UUID, uuid.UUID]] = []
    for exp_id, inc_id in rows:
        if exp_id not in used and inc_id not in used:
            pairs.append((exp_id, inc_id))
            used.add(exp_id)
            used.add(inc_id)

    for exp_id, inc_id in pairs:
        pair_id = uuid.uuid4()
        await session.execute(
            update(Transaction)
            .where(Transaction.id.in_([exp_id, inc_id]))
            .values(is_transfer=True, transfer_pair_id=pair_id)
        )

    if pairs:
        await session.commit()

    return len(pairs)


async def unmark_transfer(transaction_id: uuid.UUID, session: AsyncSession) -> None:
    """Clear is_transfer and transfer_pair_id on both legs of a pair."""
    result = await session.execute(
        select(Transaction.transfer_pair_id).where(Transaction.id == transaction_id)
    )
    pair_id = result.scalar_one_or_none()

    if pair_id is None:
        # Not part of a pair — just clear the single row
        await session.execute(
            update(Transaction)
            .where(Transaction.id == transaction_id)
            .values(is_transfer=False, transfer_pair_id=None)
        )
    else:
        await session.execute(
            update(Transaction)
            .where(Transaction.transfer_pair_id == pair_id)
            .values(is_transfer=False, transfer_pair_id=None)
        )

    await session.commit()
