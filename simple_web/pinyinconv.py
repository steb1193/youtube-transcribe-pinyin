"""Иероглифы → пиньинь. Только pypinyin + CC-CEDICT, без LLM и без GPU."""

from __future__ import annotations

import re

from pypinyin import Style, lazy_pinyin

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_dicts_loaded = False


def _load_dicts() -> None:
    global _dicts_loaded
    if _dicts_loaded:
        return
    try:
        from pypinyin_dict.pinyin_data import cc_cedict as char_cedict

        char_cedict.load()
    except Exception:
        pass
    try:
        from pypinyin_dict.phrase_pinyin_data import cc_cedict as phrase_cedict

        phrase_cedict.load()
    except Exception:
        pass
    _dicts_loaded = True


def has_hanzi(text: str) -> bool:
    return bool(_CJK_RE.search(text or ""))


def _is_pinyin_token(part: str) -> bool:
    if not part or _CJK_RE.search(part):
        return False
    return bool(re.search(r"[A-Za-züÜāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜńň]", part))


def to_pinyin(text: str) -> str:
    """你好世界 → nǐ hǎo shì jiè. Пунктуацию оставляем как есть."""
    blob = (text or "").strip()
    if not blob or not has_hanzi(blob):
        return ""
    _load_dicts()
    syllables = lazy_pinyin(
        blob,
        style=Style.TONE,
        errors=lambda chunk: list(chunk),
        v_to_u=True,
    )
    pieces: list[str] = []
    for part in syllables:
        if not part:
            continue
        if _is_pinyin_token(part):
            if pieces and not pieces[-1].endswith((" ", "\n")):
                pieces.append(" ")
            pieces.append(part)
        else:
            pieces.append(part)
    return "".join(pieces).strip()
