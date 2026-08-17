"""Специализированный перевод на русский: Tencent Hy-MT2-7B."""

from __future__ import annotations

import os
import re
import threading

import torch

from runtime import gpu_lock

MODEL_ID = os.environ.get("TRANSLATE_MODEL", "tencent/Hy-MT2-7B")
BATCH = int(os.environ.get("TRANSLATE_BATCH", "1"))
BITS = int(os.environ.get("TRANSLATE_BITS", "8"))

_lock = threading.Lock()
_loaded = threading.Event()
_model = None
_tokenizer = None
_ready = False
_loading = False
_error: str | None = None
_device = "cpu"

# Полные английские имена, как требует Hy-MT2.
_LANG = {
    "chinese": "Chinese",
    "mandarin": "Chinese",
    "cantonese": "Cantonese",
    "yue": "Cantonese",
    "english": "English",
    "russian": "Russian",
    "japanese": "Japanese",
    "korean": "Korean",
    "german": "German",
    "french": "French",
    "spanish": "Spanish",
    "italian": "Italian",
    "portuguese": "Portuguese",
    "arabic": "Arabic",
    "turkish": "Turkish",
    "thai": "Thai",
    "vietnamese": "Vietnamese",
    "indonesian": "Indonesian",
    "hindi": "Hindi",
    "polish": "Polish",
    "dutch": "Dutch",
    "ukrainian": "Ukrainian",
    "czech": "Czech",
    "persian": "Persian",
    "hebrew": "Hebrew",
    "zh": "Chinese",
    "en": "English",
    "ja": "Japanese",
    "ko": "Korean",
    "ru": "Russian",
}


def status() -> dict:
    return {
        "ready": _ready,
        "loading": _loading,
        "error": _error,
        "model": MODEL_ID,
        "device": _device,
    }


def load_model() -> None:
    global _model, _tokenizer, _ready, _loading, _error, _device
    wait = False
    with _lock:
        if _ready:
            return
        if _loading:
            wait = True
        else:
            _loading = True
            _loaded.clear()
    if wait:
        _loaded.wait()
        if not _ready:
            raise RuntimeError(_error or "Не удалось загрузить Hy-MT2")
        return

    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

        if torch.cuda.is_available():
            if BITS <= 4:
                compute = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
                extra = {
                    "quantization_config": BitsAndBytesConfig(
                        load_in_4bit=True,
                        bnb_4bit_quant_type="nf4",
                        bnb_4bit_use_double_quant=True,
                        bnb_4bit_compute_dtype=compute,
                    ),
                    "device_map": "cuda:0",
                }
                _device = "cuda:0 (4-bit)"
            elif BITS <= 8:
                extra = {
                    "quantization_config": BitsAndBytesConfig(load_in_8bit=True),
                    "device_map": "cuda:0",
                }
                _device = "cuda:0 (8-bit)"
            else:
                dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
                extra = {"dtype": dtype, "device_map": "cuda:0"}
                _device = "cuda:0"
        else:
            extra = {
                "torch_dtype": torch.float32,
                "device_map": "cpu",
            }
            _device = "cpu"

        with gpu_lock:
            tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
            model = AutoModelForCausalLM.from_pretrained(
                MODEL_ID,
                trust_remote_code=True,
                **extra,
            )
            model.eval()

        with _lock:
            _tokenizer = tokenizer
            _model = model
            _ready = True
            _error = None
    except Exception as exc:  # noqa: BLE001
        with _lock:
            _error = str(exc)
            _ready = False
        raise
    finally:
        with _lock:
            _loading = False
        _loaded.set()


def release_gpu() -> None:
    global _model, _tokenizer, _ready
    with _lock, gpu_lock:
        if _model is None:
            return
        try:
            del _model
        except Exception:
            pass
        _model = None
        _tokenizer = None
        _ready = False
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


def _model_device():
    return next(_model.parameters()).device


def _src_name(src_lang: str) -> str:
    key = (src_lang or "").strip().lower()
    if key in _LANG:
        return _LANG[key]
    for token, name in _LANG.items():
        if token in key:
            return name
    return src_lang.strip() or "the source language"


def _is_cjk_src(src_lang: str) -> bool:
    name = _src_name(src_lang).lower()
    return name in ("chinese", "cantonese") or bool(re.search(r"[\u4e00-\u9fff]", src_lang or ""))


def _prompt(text: str, src_lang: str) -> str:
    # Hy-MT2: без system prompt, полные имена языков, только перевод.
    if _is_cjk_src(src_lang):
        return (
            "将以下文本翻译为俄语，注意**只需要输出翻译后的结果，不要额外解释**：\n\n"
            f"{text}"
        )
    return (
        "Translate the following text into Russian. "
        "Note that you should **only output the translated result without any additional explanation**:\n\n"
        f"{text}"
    )


def _generate(prompt_user: str, max_new_tokens: int) -> str:
    if not _ready:
        load_model()
    messages = [{"role": "user", "content": prompt_user}]
    try:
        encoded = _tokenizer.apply_chat_template(
            messages,
            add_generation_prompt=True,
            tokenize=True,
            return_tensors="pt",
            return_dict=True,
        )
    except TypeError:
        ids = _tokenizer.apply_chat_template(
            messages,
            add_generation_prompt=True,
            tokenize=True,
            return_tensors="pt",
        )
        encoded = {"input_ids": ids}
    if hasattr(encoded, "items"):
        inputs = {k: v.to(_model_device()) for k, v in encoded.items()}
    else:
        inputs = {"input_ids": encoded.to(_model_device())}
    pad = _tokenizer.eos_token_id
    with gpu_lock, torch.no_grad():
        out = _model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            repetition_penalty=1.05,
            pad_token_id=pad,
        )
    prompt_len = inputs["input_ids"].shape[-1]
    decoded = _tokenizer.decode(out[0][prompt_len:], skip_special_tokens=True)
    return decoded.strip().strip("«»\"'")


def translate_one(sentence: str, src_lang: str) -> str:
    tokens = min(768, max(96, len(sentence) * 3))
    return _generate(_prompt(sentence, src_lang), tokens)


def _parse_lines(raw: str, expected: int) -> list[str] | None:
    lines = []
    for line in raw.splitlines():
        cleaned = re.sub(r"^\s*(\d+[\).\:]|[-*])\s*", "", line).strip()
        if cleaned:
            lines.append(cleaned)
    if len(lines) == expected:
        return lines
    return None


def translate_many(sentences: list[str], src_lang: str, progress=None) -> list[str]:
    if not sentences:
        return []
    if not _ready:
        load_model()
    out: list[str] = []
    total = len(sentences)
    for start in range(0, total, BATCH):
        chunk = sentences[start : start + BATCH]
        if progress:
            progress(f"Перевожу {start + 1}–{start + len(chunk)}/{total}…")
        if len(chunk) == 1:
            out.append(translate_one(chunk[0], src_lang))
            continue
        numbered = "\n".join(chunk)
        raw = _generate(
            _prompt(numbered, src_lang)
            + "\n\nKeep the same number of lines as the source.",
            min(1536, 120 * len(chunk) + 96),
        )
        parsed = _parse_lines(raw, len(chunk))
        if parsed is None:
            parsed = [translate_one(s, src_lang) for s in chunk]
        out.extend(parsed)
    return out
