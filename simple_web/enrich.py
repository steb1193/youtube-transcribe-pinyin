"""Нарезка на предложения и сборка текста. Пиньинь — в pinyinconv."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_CYR_RE = re.compile(r"[А-Яа-яЁё]")
_ZH_SPLIT = re.compile(r"(?<=[。！？!?；;])\s*|\n+")
_LAT_SPLIT = re.compile(r"(?<=[.!?…])\s+|\n+")


@dataclass
class Sentence:
    original: str
    pinyin: str | None = None
    translation: str | None = None


def _ratio(pattern: re.Pattern[str], text: str) -> float:
    if not text:
        return 0.0
    return len(pattern.findall(text)) / max(len(text), 1)


def is_chinese(language: str, text: str) -> bool:
    lang = (language or "").lower()
    if any(key in lang for key in ("chinese", "mandarin", "cantonese", "yue", "zh")):
        return True
    return _ratio(_CJK_RE, text) >= 0.25 and len(_CJK_RE.findall(text)) >= 4


def is_russian(language: str, text: str) -> bool:
    lang = (language or "").lower()
    if "russian" in lang or lang in ("ru", "rus"):
        return True
    if is_chinese(language, text):
        return False
    return _ratio(_CYR_RE, text) >= 0.25 and len(_CYR_RE.findall(text)) >= 8


def split_sentences(text: str, chinese: bool) -> list[str]:
    blob = (text or "").strip()
    if not blob:
        return []
    parts = _ZH_SPLIT.split(blob) if chinese else _LAT_SPLIT.split(blob)
    out = [p.strip() for p in parts if p and p.strip()]
    if len(out) <= 1 and chinese and len(blob) > 80:
        # ASR иногда без пунктуации — режем по ~40 иероглифов на границе.
        out = _split_cjk_chunks(blob, 40)
    return out or [blob]


def _split_cjk_chunks(text: str, size: int) -> list[str]:
    chars = list(text)
    chunks: list[str] = []
    buf: list[str] = []
    cjk = 0
    for ch in chars:
        buf.append(ch)
        if _CJK_RE.match(ch):
            cjk += 1
        if cjk >= size and ch in "，,、 ":
            chunks.append("".join(buf).strip())
            buf, cjk = [], 0
    if buf:
        chunks.append("".join(buf).strip())
    return [c for c in chunks if c]


def format_text(sentences: list[Sentence], chinese: bool) -> str:
    blocks: list[str] = []
    for item in sentences:
        lines = [item.original]
        if chinese and item.pinyin:
            lines.append(item.pinyin)
        if item.translation:
            lines.append(item.translation)
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks).strip()


def as_payload(sentences: list[Sentence]) -> list[dict]:
    return [asdict(s) for s in sentences]
