from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from model.lab import Lab


async def list_labs(db: AsyncSession, *, only_open: bool = False) -> list[Lab]:
    stmt = select(Lab).order_by(Lab.id.desc())
    if only_open:
        stmt = stmt.where(Lab.status == "open")
    return list((await db.execute(stmt)).scalars().all())


async def get_lab(db: AsyncSession, lab_id: int) -> Lab | None:
    return await db.get(Lab, lab_id)


async def get_lab_by_name(db: AsyncSession, name: str) -> Lab | None:
    stmt = select(Lab).where(Lab.name == name)
    return (await db.execute(stmt)).scalar_one_or_none()


async def create_lab(db: AsyncSession, **kwargs) -> Lab:
    lab = Lab(**kwargs)
    db.add(lab)
    await db.flush()
    await db.commit()
    await db.refresh(lab)
    return lab


async def update_lab(db: AsyncSession, lab: Lab, **kwargs) -> Lab:
    for k, v in kwargs.items():
        if v is not None:
            setattr(lab, k, v)
    await db.flush()
    await db.commit()
    await db.refresh(lab)
    return lab
