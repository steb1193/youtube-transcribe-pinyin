"""Скачивание по ссылке (yt-dlp) и снятие аудиодорожки (ffmpeg)."""

from __future__ import annotations

import subprocess
from pathlib import Path

VIDEO_EXT = {
    ".mp4",
    ".mkv",
    ".webm",
    ".mov",
    ".avi",
    ".m4v",
    ".wmv",
    ".mpeg",
    ".mpg",
    ".flv",
    ".3gp",
    ".ts",
}
AUDIO_EXT = {
    ".mp3",
    ".wav",
    ".m4a",
    ".aac",
    ".ogg",
    ".oga",
    ".opus",
    ".flac",
    ".wma",
    ".aiff",
    ".aif",
    ".amr",
}
ALLOWED_EXT = VIDEO_EXT | AUDIO_EXT


class MediaError(RuntimeError):
    pass


def _run(cmd: list[str], timeout: int = 600) -> subprocess.CompletedProcess[str]:
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise MediaError(f"Таймаут {timeout} с: {' '.join(cmd[:3])}") from exc
    except FileNotFoundError as exc:
        raise MediaError(f"Не найдена программа: {cmd[0]}") from exc
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "ошибка").strip()
        raise MediaError(err[-2500:])
    return proc


def duration_sec(path: Path) -> float:
    proc = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        timeout=60,
    )
    try:
        return float((proc.stdout or "0").strip() or 0)
    except ValueError:
        return 0.0


def to_wav(src: Path, dst: Path) -> Path:
    """Видео → только звук; аудио → 16 kHz mono WAV для ASR."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    _run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(src),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(dst),
        ],
        timeout=900,
    )
    if not dst.is_file() or dst.stat().st_size == 0:
        raise MediaError("Не удалось снять аудиодорожку.")
    return dst


def split_wav(src: Path, chunk_sec: int, dest: Path) -> list[Path]:
    dest.mkdir(parents=True, exist_ok=True)
    pattern = dest / "chunk_%03d.wav"
    _run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(src),
            "-f",
            "segment",
            "-segment_time",
            str(chunk_sec),
            "-c",
            "copy",
            str(pattern),
        ],
        timeout=300,
    )
    parts = sorted(dest.glob("chunk_*.wav"))
    if not parts:
        raise MediaError("Не получилось нарезать аудио на куски.")
    return parts


def newest_file(folder: Path) -> Path | None:
    files = [p for p in folder.iterdir() if p.is_file() and not p.name.startswith(".")]
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def download_source(url: str, dest: Path, cookies: Path | None = None) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    outtmpl = str(dest / "source.%(ext)s")
    cmd = [
        "yt-dlp",
        "-f",
        "bestaudio/best",
        "-x",
        "--audio-format",
        "wav",
        "--audio-quality",
        "0",
        "-o",
        outtmpl,
        "--no-playlist",
        "--no-mtime",
        "--newline",
        url,
    ]
    if cookies and cookies.is_file():
        cmd[1:1] = ["--cookies", str(cookies)]
    _run(cmd, timeout=1200)
    path = newest_file(dest)
    if path is None:
        raise MediaError("После скачивания файл не появился.")
    return path
