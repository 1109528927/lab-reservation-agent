from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from model.user import User, UserToken
from utils.security import hash_password


async def get_user_by_token(db: AsyncSession, token: str) -> User | None:
    stmt = select(UserToken).where(UserToken.token == token)
    row = (await db.execute(stmt)).scalar_one_or_none()
    if not row:
        return None
    if row.expires_at < datetime.now():
        return None
    stmt_user = select(User).where(User.id == row.user_id)
    return (await db.execute(stmt_user)).scalar_one_or_none()


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    stmt = select(User).where(User.username == username)
    return (await db.execute(stmt)).scalar_one_or_none()


async def get_user_by_employee_no(db: AsyncSession, employee_no: str) -> User | None:
    stmt = select(User).where(User.employee_no == employee_no)
    return (await db.execute(stmt)).scalar_one_or_none()


async def add_user(
    db: AsyncSession,
    *,
    username: str,
    password: str,
    employee_no: str,
    role: str = "student",
) -> User:
    user = User(
        username=username,
        password=hash_password(password),
        employee_no=employee_no,
        role=role,
    )
    db.add(user)
    await db.flush()
    await db.commit()
    await db.refresh(user)
    return user


async def create_token(db: AsyncSession, user_id: int, days: int = 7) -> UserToken:
    token_row = UserToken(
        user_id=user_id,
        token=uuid4().hex,
        expires_at=datetime.now() + timedelta(days=days),
    )
    db.add(token_row)
    await db.flush()
    await db.commit()
    await db.refresh(token_row)
    return token_row
