from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def next_copy_name(db: AsyncSession, model, base_name: str) -> str:
    first = f"{base_name} (Copy)"
    result = await db.execute(select(model.name).where(model.name == first))
    if result.scalar_one_or_none() is None:
        return first
    i = 2
    while True:
        candidate = f"{base_name} (Copy {i})"
        result = await db.execute(select(model.name).where(model.name == candidate))
        if result.scalar_one_or_none() is None:
            return candidate
        i += 1
