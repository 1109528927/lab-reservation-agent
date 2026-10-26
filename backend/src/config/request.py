import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

# 加载 backend/.env
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

# 本地默认 localhost；Docker Compose 里用环境变量指向服务名 mysql
db_url = os.getenv(
    "DATABASE_URL",
    "mysql+aiomysql://root:123456@localhost:3306/lab_access?charset=utf8mb4",
)

# ② 创建异步引擎（连库的总管道）
async_engine = create_async_engine(
    db_url,
    echo=True,
    pool_size=10,
    max_overflow=20,
)

# ③ 创建异步会话工厂（按配置生产 session）
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# ④ 依赖项：获取数据库会话，注入到路由
# 注意：yield 之后的 commit 发生在「响应发后」，连续写读请求会竞态。
# 写操作请在业务里显式 await db.commit()（见 crud 层），此处仅作兜底提交。
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# Agent 工具是同步函数，不能 await get_db()，用同步 Session
_sync_url = db_url.replace("mysql+aiomysql://", "mysql+pymysql://", 1)
sync_engine = create_engine(_sync_url, echo=True, pool_pre_ping=True)
SyncSessionLocal = sessionmaker(bind=sync_engine)