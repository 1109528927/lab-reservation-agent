"""对外展示文案清洗：去掉 Markdown 星号等装饰。"""

from __future__ import annotations

import re


_BOLD = re.compile(r"\*\*([^*]+)\*\*")
_ITALIC = re.compile(r"(?<!\*)\*([^*]+)\*(?!\*)")
_MD_HEAD = re.compile(r"^#{1,6}\s*", re.M)
_BULLET = re.compile(r"^\s*[-*]\s+", re.M)


def scrub_assistant_text(text: str) -> str:
    if not text:
        return text
    s = str(text)
    s = _BOLD.sub(r"\1", s)
    s = _ITALIC.sub(r"\1", s)
    s = s.replace("**", "").replace("__", "")
    s = _MD_HEAD.sub("", s)
    s = _BULLET.sub("· ", s)
    return s.strip()
