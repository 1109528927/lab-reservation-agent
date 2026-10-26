"""Redis 客户端（按需启用）。"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
_client = None


def get_redis():
    """懒加载；未安装/未启动 Redis 时调用方自行降级。"""
    global _client
    if _client is None:
        import redis

        _client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    return _client
