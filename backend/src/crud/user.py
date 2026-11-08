import re
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


async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
    return await db.get(User, user_id)


async def list_students(
    db: AsyncSession, *, q: str | None = None, limit: int = 200
) -> list[User]:
    stmt = select(User).where(User.role == "student").order_by(User.id.desc())
    keyword = (q or "").strip()
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            (User.username.like(like)) | (User.employee_no.like(like))
        )
    stmt = stmt.limit(max(1, min(limit, 500)))
    return list((await db.execute(stmt)).scalars().all())


async def update_student(
    db: AsyncSession,
    user: User,
    *,
    employee_no: str | None = None,
    password: str | None = None,
) -> User:
    if employee_no is not None:
        no = employee_no.strip()
        if not no:
            raise ValueError("学号不能为空")
        if no != user.employee_no:
            existed = await get_user_by_employee_no(db, no)
            if existed and existed.id != user.id:
                raise ValueError("学号已被占用")
            user.employee_no = no
    if password is not None:
        pwd = password.strip()
        if len(pwd) < 6:
            raise ValueError("密码至少 6 位")
        user.password = hash_password(pwd)
    await db.commit()
    await db.refresh(user)
    return user


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


def parse_employee_no_list(raw: str) -> list[str]:
    """换行 / 逗号 / 分号 / 空白分隔；去重保序。"""
    parts = re.split(r"[\s,;，；]+", (raw or "").strip())
    seen: set[str] = set()
    out: list[str] = []
    for p in parts:
        no = p.strip()
        if not no or no in seen:
            continue
        seen.add(no)
        out.append(no)
    return out


async def bulk_create_students(
    db: AsyncSession,
    *,
    employee_nos: list[str],
    default_password: str,
) -> list[dict]:
    """
    学号即登录账号（username = employee_no），角色固定 student。
    已存在学号或用户名则跳过，不覆盖密码。
    """
    hashed = hash_password(default_password)
    results: list[dict] = []
    for no in employee_nos:
        if len(no) > 50:
            results.append(
                {
                    "employee_no": no[:50],
                    "username": None,
                    "status": "failed",
                    "reason": "学号过长（最多50）",
                }
            )
            continue
        if await get_user_by_employee_no(db, no):
            results.append(
                {
                    "employee_no": no,
                    "username": no,
                    "status": "skipped",
                    "reason": "学号已存在",
                }
            )
            continue
        if await get_user_by_username(db, no):
            results.append(
                {
                    "employee_no": no,
                    "username": no,
                    "status": "skipped",
                    "reason": "用户名已被占用",
                }
            )
            continue
        db.add(
            User(
                username=no,
                password=hashed,
                employee_no=no,
                role="student",
            )
        )
        results.append(
            {
                "employee_no": no,
                "username": no,
                "status": "created",
                "reason": None,
            }
        )
    await db.commit()
    return results


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
