from fastapi import Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession

from config.request import get_db
from crud.user import get_user_by_token
from model.user import User


async def get_current_user(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not authorization:
        raise HTTPException(status_code=401, detail="未登录或缺少 token")

    token = authorization
    if authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()

    if not token:
        raise HTTPException(status_code=401, detail="token 无效")

    user = await get_user_by_token(db, token)
    if not user:
        raise HTTPException(status_code=401, detail="登录已失效，请重新登录")

    return user
