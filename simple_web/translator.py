"""Локальный LLM-перевод на русский. 7B в 4-bit — заметно сильнее 1.5B."""

from __future__ import annotations

import os
import re
import threading

import torch

from runtime import gpu_lock

MODEL_ID = os.environ.get("TRANSLATE_MODEL", "Qwen/Qwen2.5-7B-Instruct")
BATCH = int(os.environ.get("TRANSLATE_BATCH", "2"))

_lock = threading.Lock()
_loaded = threading.Event()
_model = None
_tokenizer = None
_ready = False
_loading = False
_error: str | None = None
_device = "cpu"


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
            raise RuntimeError(_error or "Не удалось загрузить LLM перевода")
        return

    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

        if torch.cuda.is_available():
            compute = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
            quant = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
                bnb_4bit_compute_dtype=compute,
            )
            extra = {
                "quantization_config": quant,
                "device_map": "cuda:0",
            }
            _device = "cuda:0 (4-bit)"
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


def _generate(prompt_user: str, max_new_tokens: int) -> str:
    if not _ready:
        load_model()
    messages = [
        {
            "role": "system",
            "content": (
                "Ты профессиональный переводчик на русский. "
                "Переводи естественно, сохраняй смысл и тон, без транслита. "
                "Отвечай только переводом: без кавычек, пояснений и нумерации."
            ),
        },
        {"role": "user", "content": prompt_user},
    ]
    text = _tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )
    inputs = _tokenizer([text], return_tensors="pt")
    inputs = {k: v.to(_model_device()) for k, v in inputs.items()}
    with gpu_lock, torch.no_grad():
        out = _model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            pad_token_id=_tokenizer.eos_token_id,
        )
    prompt_len = inputs["input_ids"].shape[1]
    decoded = _tokenizer.decode(out[0][prompt_len:], skip_special_tokens=True)
    return decoded.strip().strip("«»\"'")


def translate_one(sentence: str, src_lang: str) -> str:
    src = src_lang or "unknown"
    tokens = min(768, max(96, len(sentence) * 3))
    return _generate(f"Язык оригинала: {src}\n\n{sentence}", tokens)


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
        numbered = "\n".join(f"{i}. {s}" for i, s in enumerate(chunk, start=1))
        raw = _generate(
            (
                f"Язык оригинала: {src_lang or 'unknown'}. "
                f"Переведи каждое предложение на русский. "
                f"Верни ровно {len(chunk)} строк — одна строка на предложение, без номеров.\n\n"
                f"{numbered}"
            ),
            min(1536, 120 * len(chunk) + 96),
        )
        parsed = _parse_lines(raw, len(chunk))
        if parsed is None:
            parsed = [translate_one(s, src_lang) for s in chunk]
        out.extend(parsed)
    return out
