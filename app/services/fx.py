from __future__ import annotations

import bisect
import logging
from collections import defaultdict
from datetime import date
from decimal import Decimal

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fx_rate import FxRate
from app.models.preferences import UserPreferences

_log = logging.getLogger(__name__)

_AWESOME_URL = "https://economia.awesomeapi.com.br/json/daily/{pair}/{n}?start_date={start}&end_date={end}"


async def get_or_create_prefs(user_id, session: AsyncSession) -> UserPreferences:
    result = await session.execute(
        select(UserPreferences).where(UserPreferences.user_id == user_id)
    )
    prefs = result.scalar_one_or_none()
    if prefs is None:
        prefs = UserPreferences(user_id=user_id, main_currency="BRL")
        session.add(prefs)
        await session.flush()
    return prefs


async def fetch_and_cache_rates(
    session: AsyncSession,
    dates: list[date],
    from_currency: str,
    to_currency: str,
) -> int:
    if not dates or from_currency == to_currency:
        return 0

    min_date = min(dates)
    max_date = max(dates)
    start = min_date.strftime("%Y%m%d")
    end = max_date.strftime("%Y%m%d")
    pair = f"{from_currency}-{to_currency}"
    # n large enough to cover the full range (366 days max + buffer)
    n = min((max_date - min_date).days + 60, 3650)

    url = _AWESOME_URL.format(pair=pair, n=n, start=start, end=end)
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        raise RuntimeError(f"Exchange rate API unavailable for {pair}: {exc}") from exc

    # Parse API response into {date: rate}
    available: dict[date, Decimal] = {}
    for record in data:
        try:
            d = date.fromisoformat(record["create_date"][:10])
            available[d] = Decimal(record["bid"])
        except (KeyError, ValueError):
            continue

    if not available:
        return 0

    sorted_avail = sorted(available.keys())

    # For each requested date, use most recent rate on or before that date.
    # If the transaction date is before the earliest API record (e.g. a weekend
    # right at the boundary of the query window), fall back to the earliest
    # available rate rather than skipping the date permanently.
    to_insert: list[dict] = []
    for d in dates:
        idx = bisect.bisect_right(sorted_avail, d) - 1
        if idx < 0:
            if sorted_avail:
                rate_day = sorted_avail[0]
            else:
                continue
        else:
            rate_day = sorted_avail[idx]
        to_insert.append({
            "id": __import__("uuid").uuid4(),
            "rate_date": d,
            "from_currency": from_currency,
            "to_currency": to_currency,
            "rate": available[rate_day],
        })

    if not to_insert:
        return 0

    stmt = pg_insert(FxRate).values(to_insert).on_conflict_do_nothing(
        constraint="uq_fx_rate_date_pair"
    )
    result = await session.execute(stmt)
    return result.rowcount if result.rowcount >= 0 else len(to_insert)


async def load_rates(
    session: AsyncSession,
    from_currencies: set[str],
    to_currency: str,
) -> dict[str, list[tuple[date, Decimal]]]:
    """Return {from_currency: [(date, rate), ...]} sorted by date asc."""
    if not from_currencies:
        return {}
    rows = await session.execute(
        select(FxRate.from_currency, FxRate.rate_date, FxRate.rate)
        .where(FxRate.to_currency == to_currency)
        .where(FxRate.from_currency.in_(from_currencies))
        .order_by(FxRate.rate_date.asc())
    )
    result: dict[str, list[tuple[date, Decimal]]] = defaultdict(list)
    for row in rows:
        result[row.from_currency].append((row.rate_date, Decimal(str(row.rate))))
    return dict(result)


def get_rate_for_date(
    rates: list[tuple[date, Decimal]],
    d: date,
) -> Decimal | None:
    """Return the most recent rate on or before `d`, or None if unavailable."""
    if not rates:
        return None
    dates_only = [r[0] for r in rates]
    idx = bisect.bisect_right(dates_only, d) - 1
    if idx < 0:
        return None
    return rates[idx][1]
