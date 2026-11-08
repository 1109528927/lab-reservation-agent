"""实验室制度语料：轻量向量检索（优先 FAISS，否则 numpy 内积，接口一致）。

正文来自 backend/kb_source/*.md；索引落在 backend/data/faiss_lab/。
结构化空闲/预约仍走业务 Tool；本模块只回答规则、安全须知、管理员等说明。
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
KB_SOURCE_DIR = Path(os.getenv("LAB_KB_SOURCE", str(_BACKEND_ROOT / "kb_source")))
INDEX_DIR = Path(os.getenv("LAB_FAISS_DIR", str(_BACKEND_ROOT / "data" / "faiss_lab")))
META_NAME = "meta.jsonl"
INDEX_NAME = "index.faiss"
NUMPY_NAME = "index.npy"
BACKEND_NAME = "backend.json"

CHUNK_SIZE = int(os.getenv("LAB_KB_CHUNK_SIZE", "400"))
CHUNK_OVERLAP = int(os.getenv("LAB_KB_CHUNK_OVERLAP", "60"))
TOP_K = int(os.getenv("LAB_KB_TOP_K", "3"))

_index = None
_metas: list[dict[str, Any]] | None = None
_backend: str | None = None


def _try_import_faiss():
    try:
        import faiss  # noqa: F401

        return True
    except Exception:
        return False


def _env(name: str, default: str = "") -> str:
    # Windows .env 常带 \r，会导致 URL 非法
    return (os.getenv(name, default) or default).strip().strip("\r")


def _embed_model():
    from langchain_openai import OpenAIEmbeddings

    api_key = _env("LLM_API_KEY")
    if not api_key:
        raise RuntimeError("未配置 LLM_API_KEY，无法做 Embedding")
    return OpenAIEmbeddings(
        model=_env("LAB_EMBED_MODEL", "text-embedding-v3"),
        api_key=api_key,
        base_url=_env(
            "LLM_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        ),
        check_embedding_ctx_length=False,
        chunk_size=10,
    )


def _iter_md_files(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(
        p for p in root.rglob("*.md") if p.name.lower() != "readme.md"
    )


def _split_text(text: str) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    parts = re.split(r"\n(?=##\s)", text)
    chunks: list[str] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if len(part) <= CHUNK_SIZE:
            chunks.append(part)
            continue
        start = 0
        while start < len(part):
            end = min(len(part), start + CHUNK_SIZE)
            chunks.append(part[start:end].strip())
            if end >= len(part):
                break
            start = max(end - CHUNK_OVERLAP, start + 1)
    return [c for c in chunks if c]


def _lab_tag_from_path(path: Path) -> str:
    try:
        rel = path.relative_to(KB_SOURCE_DIR)
    except ValueError:
        return ""
    parts = rel.parts
    if parts and parts[0].lower() == "labs":
        return path.stem
    return ""


def load_corpus() -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for path in _iter_md_files(KB_SOURCE_DIR):
        raw = path.read_text(encoding="utf-8")
        source = str(path.relative_to(KB_SOURCE_DIR)).replace("\\", "/")
        lab = _lab_tag_from_path(path)
        for i, chunk in enumerate(_split_text(raw)):
            docs.append(
                {
                    "id": f"{source}#{i}",
                    "text": chunk,
                    "source": source,
                    "lab": lab,
                }
            )
    return docs


def build_index(*, force: bool = True) -> dict[str, Any]:
    """切分 → Embedding → FAISS 或 numpy 内积索引。"""
    import numpy as np

    docs = load_corpus()
    if not docs:
        raise RuntimeError(f"语料为空，请检查目录：{KB_SOURCE_DIR}")

    embed = _embed_model()
    texts = [d["text"] for d in docs]
    vectors = embed.embed_documents(texts)
    arr = np.array(vectors, dtype="float32")
    # 归一化后内积 = 余弦相似度
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-12)
    arr = arr / norms

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    backend = "faiss" if _try_import_faiss() else "numpy"

    if backend == "faiss":
        import faiss

        index = faiss.IndexFlatIP(arr.shape[1])
        index.add(arr)
        faiss.write_index(index, str(INDEX_DIR / INDEX_NAME))
        store: Any = index
    else:
        np.save(str(INDEX_DIR / NUMPY_NAME), arr)
        store = arr
        logger.warning(
            "未安装 faiss-cpu，已用 numpy 内积索引（与 IndexFlatIP 同构）；"
            "建议在 Python 3.10–3.12 环境 pip install faiss-cpu"
        )

    with (INDEX_DIR / META_NAME).open("w", encoding="utf-8") as f:
        for d in docs:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    (INDEX_DIR / BACKEND_NAME).write_text(
        json.dumps({"backend": backend, "dim": int(arr.shape[1])}, ensure_ascii=False),
        encoding="utf-8",
    )

    global _index, _metas, _backend
    _index, _metas, _backend = store, docs, backend
    return {
        "chunks": len(docs),
        "dim": int(arr.shape[1]),
        "dir": str(INDEX_DIR),
        "backend": backend,
    }


def _ensure_loaded() -> tuple[Any, list[dict[str, Any]], str]:
    global _index, _metas, _backend
    if _index is not None and _metas is not None and _backend:
        return _index, _metas, _backend

    meta_path = INDEX_DIR / META_NAME
    backend_path = INDEX_DIR / BACKEND_NAME
    if not meta_path.is_file():
        info = build_index()
        assert _index is not None and _metas is not None and _backend
        return _index, _metas, _backend

    backend = "numpy"
    if backend_path.is_file():
        backend = json.loads(backend_path.read_text(encoding="utf-8")).get(
            "backend", "numpy"
        )

    metas: list[dict[str, Any]] = []
    with meta_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                metas.append(json.loads(line))

    if backend == "faiss" and _try_import_faiss() and (INDEX_DIR / INDEX_NAME).is_file():
        import faiss

        store: Any = faiss.read_index(str(INDEX_DIR / INDEX_NAME))
        backend = "faiss"
    elif (INDEX_DIR / NUMPY_NAME).is_file():
        import numpy as np

        store = np.load(str(INDEX_DIR / NUMPY_NAME))
        backend = "numpy"
    else:
        info = build_index()
        assert _index is not None and _metas is not None and _backend
        return _index, _metas, _backend

    _index, _metas, _backend = store, metas, backend
    return _index, _metas, _backend


def _keyword_fallback(q: str, lab: str | None, limit: int) -> list[dict[str, Any]]:
    docs = load_corpus()
    q_low = (q or "").lower()
    tokens = re.findall(r"[\u4e00-\u9fff]{2,}|\w+", q_low)
    hits: list[dict[str, Any]] = []
    for d in docs:
        if lab and lab.strip():
            tag = (d.get("lab") or "") + " " + (d.get("source") or "")
            if d.get("lab") and lab.strip() not in tag:
                continue
        text = d.get("text") or ""
        score = sum(1 for w in tokens if w in text.lower())
        if score <= 0 and q_low and q_low not in text.lower():
            continue
        hits.append({**d, "score": float(score)})
    hits.sort(key=lambda x: x.get("score") or 0, reverse=True)
    return hits[:limit]


def _search_vectors(
    store: Any,
    backend: str,
    qv,
    metas: list[dict[str, Any]],
    fetch: int,
) -> list[tuple[float, int]]:
    import numpy as np

    if backend == "faiss":
        scores, idxs = store.search(qv, min(fetch, len(metas)))
        return list(zip(scores[0].tolist(), idxs[0].tolist()))

    # numpy: store shape (n, dim), already L2-normalized
    sims = (store @ qv[0]).astype("float32")
    k = min(fetch, len(metas))
    if k <= 0:
        return []
    idxs = np.argpartition(-sims, kth=min(k - 1, len(sims) - 1))[:k]
    idxs = idxs[np.argsort(-sims[idxs])]
    return [(float(sims[i]), int(i)) for i in idxs]


def search_lab_docs(
    q: str,
    *,
    lab: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """返回 [{text, source, lab, score}, ...]。"""
    import numpy as np

    limit = limit or TOP_K
    q = (q or "").strip()
    if not q:
        return []

    try:
        store, metas, backend = _ensure_loaded()
        embed = _embed_model()
        qv = np.array([embed.embed_query(q)], dtype="float32")
        norms = np.linalg.norm(qv, axis=1, keepdims=True)
        qv = qv / np.maximum(norms, 1e-12)

        fetch = max(limit * 4, 12)
        ranked = _search_vectors(store, backend, qv, metas, fetch)
        hits: list[dict[str, Any]] = []
        for score, idx in ranked:
            if idx < 0 or idx >= len(metas):
                continue
            meta = dict(metas[idx])
            if lab and lab.strip():
                tag = (meta.get("lab") or "") + " " + (meta.get("source") or "")
                if meta.get("lab") and lab.strip() not in tag:
                    continue
            meta["score"] = float(score)
            meta["_via"] = backend
            hits.append(meta)
            if len(hits) >= limit:
                break
        if hits:
            return hits
        return _keyword_fallback(q, lab, limit)
    except Exception:
        logger.exception("向量检索失败，降级关键字 q=%s", q)
        return _keyword_fallback(q, lab, limit)


def format_hits(hits: list[dict[str, Any]], *, via: str | None = None) -> str:
    if not hits:
        return (
            "知识库未检索到相关片段。请结合业务工具查实验室列表/预约，"
            "不要编造开放时间或管理员姓名；未命中时明确说明未找到。"
        )
    channel = via or hits[0].get("_via") or "vector"
    lines = [
        f"检索通道={channel}；作答时文末写「依据：[序号] source=…」，禁止无来源编造制度。"
    ]
    for i, h in enumerate(hits, 1):
        text = (h.get("text") or "").strip()
        if len(text) > 450:
            text = text[:450] + "…"
        source = h.get("source") or "unknown"
        lab = h.get("lab") or "通用"
        lines.append(f"[{i}] source={source} lab={lab}\n{text}")
    return "\n\n".join(lines)
