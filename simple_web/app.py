#!/usr/bin/env python3
"""Минимальный веб-интерфейс для скачивания YouTube через yt-dlp."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

from flask import Flask, after_this_request, render_template_string, request, send_file

ROOT = Path(__file__).resolve().parent.parent
DOWNLOADS = ROOT / "downloads"
DOWNLOADS.mkdir(exist_ok=True)

app = Flask(__name__)

FORMATS = {
    "mp4": (
        "MP4, лучшее качество",
        "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b",
        "mp4",
    ),
    "mp4_1080": (
        "MP4 1080p",
        "bv*[ext=mp4][height<=1080]+ba[ext=m4a]/b[ext=mp4][height<=1080]/bv*[height<=1080]+ba/b",
        "mp4",
    ),
    "mp4_720": (
        "MP4 720p",
        "bv*[ext=mp4][height<=720]+ba[ext=m4a]/b[ext=mp4][height<=720]/bv*[height<=720]+ba/b",
        "mp4",
    ),
    "mp4_480": (
        "MP4 480p",
        "bv*[ext=mp4][height<=480]+ba[ext=m4a]/b[ext=mp4][height<=480]/bv*[height<=480]+ba/b",
        "mp4",
    ),
    "mp3": (
        "MP3, только звук",
        "bestaudio/best",
        "mp3",
    ),
}

PAGE = r"""
<!doctype html>
<html lang="ru">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>YouTube downloader</title>
<style>
  :root {
    --bg: #0f1419;
    --card: #1a2332;
    --line: #2c3a4f;
    --text: #e8eef7;
    --muted: #8b9bb4;
    --accent: #3d8bfd;
    --accent-press: #2f73d8;
    --err: #ff6b7a;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    min-height: 100vh;
    font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif;
    background:
      radial-gradient(900px 400px at 10% -10%, #1d4ed844, transparent 55%),
      radial-gradient(700px 360px at 110% 10%, #db277744, transparent 50%),
      var(--bg);
    color: var(--text);
  }
  .wrap {
    max-width: 560px;
    margin: 0 auto;
    padding: 72px 20px 40px;
  }
  .card {
    background: color-mix(in srgb, var(--card) 88%, black);
    border: 1px solid var(--line);
    border-radius: 20px;
    padding: 28px;
    box-shadow: 0 24px 60px #0006;
  }
  h1 {
    margin: 0 0 6px;
    font-size: 28px;
    letter-spacing: -0.03em;
  }
  .sub { color: var(--muted); margin: 0 0 24px; font-size: 15px; }
  label.field {
    display: block;
    font-size: 13px;
    color: var(--muted);
    margin: 0 0 8px;
  }
  input[type=url], select {
    width: 100%;
    padding: 12px 14px;
    border-radius: 12px;
    border: 1px solid var(--line);
    background: #0c121a;
    color: var(--text);
    font-size: 16px;
    outline: none;
  }
  input[type=url]:focus, select:focus { border-color: var(--accent); }
  .row { margin-bottom: 16px; }
  button {
    width: 100%;
    margin-top: 8px;
    padding: 13px 16px;
    border: 0;
    border-radius: 12px;
    background: var(--accent);
    color: white;
    font-size: 16px;
    font-weight: 650;
    cursor: pointer;
  }
  button:hover { background: var(--accent-press); }
  button:disabled { opacity: 0.65; cursor: wait; }
  .err {
    margin: 14px 0 0;
    padding: 12px 14px;
    border-radius: 12px;
    background: #3a1520;
    color: var(--err);
    font-size: 13px;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }
  .hint { margin-top: 14px; color: var(--muted); font-size: 13px; }
</style>
<body>
  <div class="wrap">
    <div class="card">
      <h1>Скачать с YouTube</h1>
      <p class="sub">Вставь ссылку — файл сразу уйдёт в загрузки браузера.</p>
      <form method="post" onsubmit="this.querySelector('button').disabled=true; this.querySelector('button').textContent='Скачиваю…';">
        <div class="row">
          <label class="field">Ссылка</label>
          <input type="url" name="url" required
                 placeholder="https://www.youtube.com/watch?v=..."
                 value="{{ url }}">
        </div>
        <div class="row">
          <label class="field">Формат</label>
          <select name="fmt">
            {% for key, title in formats %}
              <option value="{{ key }}" {% if key == fmt %}selected{% endif %}>{{ title }}</option>
            {% endfor %}
          </select>
        </div>
        <button type="submit">Скачать</button>
      </form>
      {% if message %}<p class="err">{{ message }}</p>{% endif %}
      <p class="hint">Видео собирается в MP4. Это может занять минуту.</p>
    </div>
  </div>
</body>
</html>
"""


def newest_file(folder: Path) -> Path | None:
    files = [p for p in folder.iterdir() if p.is_file() and not p.name.startswith(".")]
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


@app.get("/")
def index():
    return render_template_string(
        PAGE,
        url="https://www.youtube.com/watch?v=4SwjYGG6WDI",
        fmt="mp4",
        formats=[(k, v[0]) for k, v in FORMATS.items()],
        message="",
    )


@app.post("/")
def download():
    url = (request.form.get("url") or "").strip()
    fmt = request.form.get("fmt") or "mp4"
    if fmt not in FORMATS:
        fmt = "mp4"
    title, format_spec, container = FORMATS[fmt]

    job = DOWNLOADS / uuid.uuid4().hex
    job.mkdir()
    outtmpl = str(job / "%(title)s.%(ext)s")
    cmd = [
        sys.executable,
        "-m",
        "yt_dlp",
        "-f",
        format_spec,
        "-o",
        outtmpl,
        "--no-playlist",
        "--no-mtime",
        url,
    ]
    if container == "mp4":
        cmd[3:3] = ["--merge-output-format", "mp4"]
    elif container == "mp3":
        cmd[3:3] = ["-x", "--audio-format", "mp3"]

    def fail(msg: str):
        shutil.rmtree(job, ignore_errors=True)
        return render_template_string(
            PAGE,
            url=url,
            fmt=fmt,
            formats=[(k, v[0]) for k, v in FORMATS.items()],
            message=msg,
        )

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return fail("Таймаут 10 минут.")

    if proc.returncode != 0:
        return fail((proc.stderr or proc.stdout or "Не удалось скачать.")[-2000:])

    path = newest_file(job)
    if path is None:
        return fail("Файл не появился после скачивания.")

    @after_this_request
    def _cleanup(response):
        shutil.rmtree(job, ignore_errors=True)
        return response

    return send_file(
        path,
        as_attachment=True,
        download_name=path.name,
        mimetype="video/mp4" if container == "mp4" else "audio/mpeg",
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8081"))
    app.run(host="127.0.0.1", port=port, debug=False)
