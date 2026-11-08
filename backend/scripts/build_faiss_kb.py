"""重建实验室制度 FAISS 索引。

用法（在 backend 目录）：
  PYTHONPATH=src python scripts/build_faiss_kb.py

需已配置 .env 中 LLM_API_KEY（百炼兼容 Embedding）。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from utils.faiss_kb import KB_SOURCE_DIR, build_index  # noqa: E402


def main() -> None:
    print(f"语料目录: {KB_SOURCE_DIR}")
    info = build_index(force=True)
    print(f"完成: chunks={info['chunks']} dim={info['dim']} -> {info['dir']}")


if __name__ == "__main__":
    main()
