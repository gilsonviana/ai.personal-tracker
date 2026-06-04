from sqlalchemy import select

from app.db.database import async_session_maker
from app.models.category import Category

SYSTEM_CATEGORIES = [
    ("Salary", "income"),
    ("Freelance", "income"),
    ("Investment", "income"),
    ("Other Income", "income"),
    ("Housing", "expense"),
    ("Food & Groceries", "expense"),
    ("Transport", "expense"),
    ("Health", "expense"),
    ("Education", "expense"),
    ("Entertainment", "expense"),
    ("Utilities", "expense"),
    ("Clothing", "expense"),
    ("Travel", "expense"),
    ("Other Expense", "expense"),
]


async def seed_categories() -> None:
    async with async_session_maker() as session:
        existing = (
            await session.execute(select(Category).where(Category.user_id.is_(None)))
        ).scalars().all()
        existing_names = {c.name for c in existing}
        for name, ctype in SYSTEM_CATEGORIES:
            if name not in existing_names:
                session.add(Category(name=name, type=ctype))
        await session.commit()
