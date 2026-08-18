"""Qwen3-ASR-1.7B-hf: нативный transformers, нарезка длинных дорожек."""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from pathlib import Path

import torch

from media import duration_sec, split_wav
from runtime import gpu_lock

MODEL_ID = os.environ.get("ASR_MODEL", "Qwen/Qwen3-ASR-1.7B-hf")
CHUNK_SEC = int(os.environ.get("ASR_CHUNK_SEC", "480"))
MAX_NEW_TOKENS = int(os.environ.get("ASR_MAX_NEW_TOKENS", "4096"))

_lock = threading.Lock()
_loaded = threading.Event()
_model = None
_processor = None
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
    global _model, _processor, _ready, _loading, _error
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
        from transformers import AutoModelForMultimodalLM, AutoProcessor

        if torch.cuda.is_available():
            dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
            device_map = "cuda:0"
        else:
            dtype = torch.float32
            device_map = "cpu"

        with gpu_lock:
            processor = AutoProcessor.from_pretrained(MODEL_ID)
            model = AutoModelForMultimodalLM.from_pretrained(
                MODEL_ID,
                dtype=dtype,
                device_map=device_map,
            )
            model.eval()
        with _lock:
            _processor = processor
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


def release_gpu() -> None:
    """Снять ASR с видеопамяти, чтобы влез переводчик побольше."""
    global _model, _processor, _ready
    with _lock, gpu_lock:
        if _model is None and _processor is None:
            return
        try:
            del _model
        except Exception:
            pass
        try:
            del _processor
        except Exception:
            pass
        _model = None
        _processor = None
        _ready = False
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


def _parse_generated(generated_ids) -> Transcript:
    parsed = _processor.decode(generated_ids, return_format="parsed")
    if isinstance(parsed, list):
        parsed = parsed[0] if parsed else {}
    if isinstance(parsed, dict):
        text = str(parsed.get("transcription") or "").strip()
        detected = str(parsed.get("language") or "").strip()
        return Transcript(language=detected, text=text)
    text = _processor.decode(generated_ids, return_format="transcription_only")
    if isinstance(text, list):
        text = text[0] if text else ""
    return Transcript(language="", text=str(text or "").strip())


def _transcribe_one(audio_path: Path, language: str | None) -> Transcript:
    if not _ready:
        load_model()
    lang = None if language in (None, "", "auto") else language
    kwargs = {"audio": str(audio_path)}
    if lang:
        kwargs["language"] = lang
    with _lock, gpu_lock, torch.inference_mode():
        inputs = _processor.apply_transcription_request(**kwargs)
        inputs = inputs.to(_model.device, _model.dtype)
        output_ids = _model.generate(
            **inputs,
            max_new_tokens=MAX_NEW_TOKENS,
            do_sample=False,
        )
        prompt_len = inputs["input_ids"].shape[1]
        generated_ids = output_ids[:, prompt_len:]
        return _parse_generated(generated_ids)


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
