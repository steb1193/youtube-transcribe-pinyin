"""Qwen3-ASR-1.7B: загрузка модели и расшифровка (с нарезкой длинных дорожек)."""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from pathlib import Path

import torch

from media import duration_sec, split_wav
from runtime import gpu_lock

MODEL_ID = os.environ.get("ASR_MODEL", "Qwen/Qwen3-ASR-1.7B")
CHUNK_SEC = int(os.environ.get("ASR_CHUNK_SEC", "480"))
MAX_NEW_TOKENS = int(os.environ.get("ASR_MAX_NEW_TOKENS", "4096"))

_lock = threading.Lock()
_loaded = threading.Event()
_model = None
_ready = False
_loading = False
_error: str | None = None


@dataclass
class Transcript:
    language: str
    text: str


def status() -> dict:
    if torch.cuda.is_available():
        device = f"cuda:{torch.cuda.current_device()} ({torch.cuda.get_device_name(0)})"
    else:
        device = "cpu"
    return {
        "ready": _ready,
        "loading": _loading,
        "error": _error,
        "device": device,
        "model": MODEL_ID,
    }


def load_model() -> None:
    global _model, _ready, _loading, _error
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
            raise RuntimeError(_error or "Не удалось загрузить ASR")
        return

    try:
        from qwen_asr import Qwen3ASRModel

        if torch.cuda.is_available():
            dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
            device_map = "cuda:0"
        else:
            dtype = torch.float32
            device_map = "cpu"

        with gpu_lock:
            model = Qwen3ASRModel.from_pretrained(
                MODEL_ID,
                dtype=dtype,
                device_map=device_map,
                max_inference_batch_size=1,
                max_new_tokens=MAX_NEW_TOKENS,
            )
        with _lock:
            _model = model
            _ready = True
            _error = None
    except Exception as exc:  # noqa: BLE001 — показываем причину в UI
        with _lock:
            _error = str(exc)
            _ready = False
        raise
    finally:
        with _lock:
            _loading = False
        _loaded.set()


def _transcribe_one(audio_path: Path, language: str | None) -> Transcript:
    if not _ready:
        load_model()
    lang = None if language in (None, "", "auto") else language
    with _lock, gpu_lock:
        results = _model.transcribe(audio=str(audio_path), language=lang)
    result = results[0]
    text = (getattr(result, "text", None) or "").strip()
    detected = str(getattr(result, "language", None) or "")
    return Transcript(language=detected, text=text)


def transcribe_wav(wav_path: Path, language: str | None, work_dir: Path) -> Transcript:
    """Расшифровать wav. Длинные файлы режем на куски, чтобы не упереться в лимит токенов."""
    duration = duration_sec(wav_path)
    set_progress("Расшифровываю…")
    if duration <= CHUNK_SEC + 20:
        return _transcribe_one(wav_path, language)

    chunks_dir = work_dir / "chunks"
    parts = split_wav(wav_path, CHUNK_SEC, chunks_dir)
    texts: list[str] = []
    detected = ""
    total = len(parts)
    for index, chunk in enumerate(parts, start=1):
        piece = _transcribe_one(chunk, language)
        if piece.language and not detected:
            detected = piece.language
        if piece.text:
            texts.append(piece.text)
        _set_progress(f"Расшифровываю кусок {index}/{total}…")
    return Transcript(language=detected, text="\n\n".join(texts).strip())


_progress = ""
_progress_lock = threading.Lock()


def set_progress(message: str) -> None:
    global _progress
    with _progress_lock:
        _progress = message


def get_progress() -> str:
    with _progress_lock:
        return _progress


def _set_progress(message: str) -> None:
    set_progress(message)
