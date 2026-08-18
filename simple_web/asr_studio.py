#!/usr/bin/env python3
"""YouTube Transcribe Pinyin — веб-интерфейс: YouTube / файл → ASR + пиньинь + перевод."""

from __future__ import annotations

import os
import shutil
import threading
import uuid
from pathlib import Path

from flask import Flask, jsonify, render_template_string, request, send_file

import engine
import translator
from enrich import (
    Sentence,
    as_payload,
    format_text,
    is_chinese,
    is_russian,
    split_sentences,
)
from media import ALLOWED_EXT, MediaError, download_source, to_wav
from pinyinconv import to_pinyin
from runtime import pipeline_lock

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
COOKIES = Path(os.environ.get("COOKIES_FILE", "/data/cookies.txt"))

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = int(os.environ.get("MAX_UPLOAD_MB", "2048")) * 1024 * 1024

_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()

LANGUAGES = [
    ("auto", "Авто (определить язык)"),
    ("Russian", "Русский"),
    ("English", "English"),
    ("Chinese", "中文"),
    ("German", "Deutsch"),
    ("French", "Français"),
    ("Spanish", "Español"),
    ("Italian", "Italiano"),
    ("Portuguese", "Português"),
    ("Japanese", "日本語"),
    ("Korean", "한국어"),
    ("Arabic", "العربية"),
    ("Turkish", "Türkçe"),
    ("Polish", "Polski"),
    ("Dutch", "Nederlands"),
    ("Hindi", "हिन्दी"),
    ("Thai", "ไทย"),
    ("Vietnamese", "Tiếng Việt"),
    ("Indonesian", "Bahasa Indonesia"),
]

PAGE = r"""
<!doctype html>
<html lang="ru">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>YouTube Transcribe Pinyin — китайский YouTube + пиньинь / ASR + pinyin</title>
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
    --ok: #3dd68c;
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
  .wrap { max-width: 720px; margin: 0 auto; padding: 56px 20px 40px; }
  .card {
    background: color-mix(in srgb, var(--card) 88%, black);
    border: 1px solid var(--line);
    border-radius: 20px;
    padding: 28px;
    box-shadow: 0 24px 60px #0006;
  }
  h1 { margin: 0 0 6px; font-size: 28px; letter-spacing: -0.03em; }
  .sub { color: var(--muted); margin: 0 0 20px; font-size: 15px; }
  .status {
    display: flex; gap: 8px; align-items: center; flex-wrap: wrap;
    margin: 0 0 20px; font-size: 13px; color: var(--muted);
  }
  .dot {
    width: 8px; height: 8px; border-radius: 50%; background: #fbbf24;
    box-shadow: 0 0 0 3px #fbbf2433;
  }
  .dot.ok { background: var(--ok); box-shadow: 0 0 0 3px #3dd68c33; }
  .dot.bad { background: var(--err); box-shadow: 0 0 0 3px #ff6b7a33; }
  .tabs {
    display: grid; grid-template-columns: 1fr 1fr; gap: 8px;
    background: #0c121a; border: 1px solid var(--line);
    border-radius: 12px; padding: 4px; margin-bottom: 16px;
  }
  .tabs button {
    margin: 0; width: auto; padding: 10px 12px; background: transparent;
    color: var(--muted); font-weight: 600; font-size: 14px;
  }
  .tabs button.on { background: var(--accent); color: #fff; }
  .tabs button:hover { background: #1d2a3c; }
  .tabs button.on:hover { background: var(--accent-press); }
  label.field { display: block; font-size: 13px; color: var(--muted); margin: 0 0 8px; }
  input[type=url], input[type=text], select, textarea {
    width: 100%; padding: 12px 14px; border-radius: 12px;
    border: 1px solid var(--line); background: #0c121a; color: var(--text);
    font-size: 16px; outline: none;
  }
  input:focus, select:focus, textarea:focus { border-color: var(--accent); }
  textarea {
    min-height: 160px; font-size: 15px; line-height: 1.45; resize: vertical;
    font-family: ui-sans-serif, system-ui, sans-serif;
  }
  .sents { display: flex; flex-direction: column; gap: 10px; margin: 12px 0 16px; }
  .sent {
    background: #0c121a; border: 1px solid var(--line);
    border-radius: 12px; padding: 12px 14px;
  }
  .sent .orig { font-size: 16px; }
  .sent .py { color: #8cb4ff; font-size: 14px; margin-top: 4px; }
  .sent .tr { color: var(--ok); font-size: 15px; margin-top: 6px; }
  .row { margin-bottom: 16px; }
  .drop {
    border: 1.5px dashed var(--line); border-radius: 12px; padding: 28px 16px;
    text-align: center; color: var(--muted); background: #0c121a; cursor: pointer;
  }
  .drop.over { border-color: var(--accent); color: var(--text); }
  .drop input { display: none; }
  .drop strong { color: var(--text); }
  button {
    width: 100%; margin-top: 8px; padding: 13px 16px; border: 0;
    border-radius: 12px; background: var(--accent); color: white;
    font-size: 16px; font-weight: 650; cursor: pointer;
  }
  button:hover { background: var(--accent-press); }
  button:disabled { opacity: 0.65; cursor: wait; }
  .actions { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 12px; }
  .actions button { margin: 0; background: #243044; }
  .actions button:hover { background: #2d3c54; }
  .err, .note {
    margin: 14px 0 0; padding: 12px 14px; border-radius: 12px; font-size: 13px;
    white-space: pre-wrap; overflow-wrap: anywhere;
  }
  .err { background: #3a1520; color: var(--err); }
  .note { background: #15243a; color: var(--muted); }
  .hint { margin-top: 14px; color: var(--muted); font-size: 13px; }
  .hidden { display: none; }
  .meta { margin: 8px 0 0; color: var(--muted); font-size: 13px; }
</style>
<body>
  <div class="wrap">
    <div class="card">
      <h1>YouTube Transcribe Pinyin</h1>
      <p class="sub">Китайский ролик → иероглифы + пиньинь + перевод по предложениям. YouTube / аудио / видео, из видео только звук. Не китайский — расшифровка и перевод на русский. Всё локально.</p>
      <div class="status">
        <span class="dot" id="dot"></span>
        <span id="modelStatus">Проверяю модель…</span>
      </div>
      <form id="form">
        <div class="tabs">
          <button type="button" class="on" data-tab="url" id="tabUrl">Ссылка</button>
          <button type="button" data-tab="file" id="tabFile">Видео / аудио</button>
        </div>
        <div class="row" id="urlRow">
          <label class="field">Ссылка (YouTube, VK, прямая… — всё, что умеет yt-dlp)</label>
          <input type="url" name="url" id="url"
                 placeholder="https://www.youtube.com/watch?v=...">
        </div>
        <div class="row hidden" id="fileRow">
          <label class="field">Файл</label>
          <label class="drop" id="drop">
            <input type="file" name="file" id="file"
                   accept="video/*,audio/*,.mp4,.mkv,.webm,.mov,.avi,.mp3,.wav,.m4a,.ogg,.flac,.opus">
            <div><strong>Перетащи сюда</strong> или нажми — видео или аудио</div>
            <div class="meta" id="fileName">mp4 / mkv / mp3 / wav / m4a и другие</div>
          </label>
        </div>
        <div class="row">
          <label class="field">Язык</label>
          <select name="language" id="language">
            {% for value, title in languages %}
              <option value="{{ value }}">{{ title }}</option>
            {% endfor %}
          </select>
        </div>
        <button type="submit" id="go">Расшифровать</button>
      </form>
      <p class="note hidden" id="progress"></p>
      <p class="err hidden" id="error"></p>
      <div id="resultBox" class="hidden">
        <p class="meta" id="resultMeta"></p>
        <div class="sents" id="sentences"></div>
        <label class="field">Всё одним текстом</label>
        <textarea id="result" readonly></textarea>
        <div class="actions">
          <button type="button" id="copy">Скопировать</button>
          <button type="button" id="download">Скачать .txt</button>
        </div>
      </div>
      <p class="hint">LAN: <code>http://&lt;IP-этого-ПК&gt;:8080</code>. YouTube Transcribe Pinyin · AGPL-3.0 · первый запуск качает ASR и LLM.</p>
    </div>
  </div>
<script>
const form = document.getElementById("form");
const go = document.getElementById("go");
const progress = document.getElementById("progress");
const errorEl = document.getElementById("error");
const resultBox = document.getElementById("resultBox");
const result = document.getElementById("result");
const resultMeta = document.getElementById("resultMeta");
const sentencesEl = document.getElementById("sentences");
const urlRow = document.getElementById("urlRow");
const fileRow = document.getElementById("fileRow");
const fileInput = document.getElementById("file");
const fileName = document.getElementById("fileName");
const drop = document.getElementById("drop");
let tab = "url";
let pollTimer = null;

function show(el, on) { el.classList.toggle("hidden", !on); }

function renderSentences(items) {
  sentencesEl.innerHTML = "";
  if (!items.length) return;
  for (const item of items) {
    const el = document.createElement("article");
    el.className = "sent";
    const orig = document.createElement("div");
    orig.className = "orig";
    orig.textContent = item.original || "";
    el.appendChild(orig);
    if (item.pinyin) {
      const py = document.createElement("div");
      py.className = "py";
      py.textContent = item.pinyin;
      el.appendChild(py);
    }
    if (item.translation) {
      const tr = document.createElement("div");
      tr.className = "tr";
      tr.textContent = item.translation;
      el.appendChild(tr);
    }
    sentencesEl.appendChild(el);
  }
}

document.getElementById("tabUrl").onclick = () => setTab("url");
document.getElementById("tabFile").onclick = () => setTab("file");

function setTab(name) {
  tab = name;
  document.getElementById("tabUrl").classList.toggle("on", name === "url");
  document.getElementById("tabFile").classList.toggle("on", name === "file");
  show(urlRow, name === "url");
  show(fileRow, name === "file");
}

fileInput.onchange = () => {
  fileName.textContent = fileInput.files[0] ? fileInput.files[0].name : "mp4 / mkv / mp3 / wav / m4a и другие";
};
["dragenter","dragover"].forEach(ev => drop.addEventListener(ev, e => {
  e.preventDefault(); drop.classList.add("over");
}));
["dragleave","drop"].forEach(ev => drop.addEventListener(ev, e => {
  e.preventDefault(); drop.classList.remove("over");
}));
drop.addEventListener("drop", e => {
  const f = e.dataTransfer.files[0];
  if (!f) return;
  const dt = new DataTransfer();
  dt.items.add(f);
  fileInput.files = dt.files;
  fileName.textContent = f.name;
});

async function refreshStatus() {
  try {
    const r = await fetch("/api/status");
    const s = await r.json();
    const dot = document.getElementById("dot");
    const label = document.getElementById("modelStatus");
    if (s.ready) {
      dot.className = "dot ok";
      const bits = [s.model, s.translate_model, s.device].filter(Boolean);
      label.textContent = bits.join(" · ");
    } else if (s.loading) {
      dot.className = "dot";
      label.textContent = s.stage || "Загружаю модели… это может занять несколько минут";
    } else if (s.error) {
      dot.className = "dot bad";
      label.textContent = "Модель не поднялась: " + s.error;
    } else {
      dot.className = "dot";
      label.textContent = "Модель ещё не готова";
    }
  } catch (e) {
    document.getElementById("dot").className = "dot bad";
    document.getElementById("modelStatus").textContent = "Сервер недоступен";
  }
}
refreshStatus();
setInterval(refreshStatus, 4000);

form.onsubmit = async (ev) => {
  ev.preventDefault();
  show(errorEl, false);
  show(resultBox, false);
  show(progress, true);
  progress.textContent = "Отправляю…";
  go.disabled = true;
  go.textContent = "Работаю…";
  const fd = new FormData();
  fd.append("language", document.getElementById("language").value);
  fd.append("source", tab);
  if (tab === "url") {
    fd.append("url", document.getElementById("url").value.trim());
  } else if (fileInput.files[0]) {
    fd.append("file", fileInput.files[0]);
  }
  try {
    const r = await fetch("/api/transcribe", { method: "POST", body: fd });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || "Не удалось запустить задачу");
    poll(data.job_id);
  } catch (e) {
    show(progress, false);
    show(errorEl, true);
    errorEl.textContent = e.message || String(e);
    go.disabled = false;
    go.textContent = "Расшифровать";
  }
};

function poll(id) {
  if (pollTimer) clearInterval(pollTimer);
  const tick = async () => {
    const r = await fetch("/api/jobs/" + id);
    const j = await r.json();
    if (j.stage) progress.textContent = j.stage;
    if (j.status === "done") {
      clearInterval(pollTimer);
      show(progress, false);
      show(resultBox, true);
      result.value = j.text || "";
      resultMeta.textContent = [j.language, j.mode_label, j.source_name].filter(Boolean).join(" · ");
      renderSentences(j.sentences || []);
      go.disabled = false;
      go.textContent = "Расшифровать";
      window.__txtName = (j.source_name || "transcript").replace(/\.[^.]+$/, "") + ".txt";
    } else if (j.status === "error") {
      clearInterval(pollTimer);
      show(progress, false);
      show(errorEl, true);
      errorEl.textContent = j.error || "Ошибка";
      go.disabled = false;
      go.textContent = "Расшифровать";
    }
  };
  tick();
  pollTimer = setInterval(tick, 1200);
}

document.getElementById("copy").onclick = async () => {
  await navigator.clipboard.writeText(result.value);
  document.getElementById("copy").textContent = "Скопировано";
  setTimeout(() => document.getElementById("copy").textContent = "Скопировать", 1200);
};
document.getElementById("download").onclick = () => {
  const blob = new Blob([result.value], { type: "text/plain;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = window.__txtName || "transcript.txt";
  a.click();
  URL.revokeObjectURL(a.href);
};
</script>
</body>
</html>
"""


def _job(job_id: str) -> dict | None:
    with _jobs_lock:
        return _jobs.get(job_id)


def _update(job_id: str, **fields) -> None:
    with _jobs_lock:
        if job_id in _jobs:
            _jobs[job_id].update(fields)


def _run_job(job_id: str, url: str, saved: Path | None, language: str, source_name: str) -> None:
    work = DATA_DIR / "jobs" / job_id
    work.mkdir(parents=True, exist_ok=True)
    try:
        _update(job_id, status="running", stage="Готовлю аудио…")
        if url:
            _update(job_id, stage="Скачиваю источник…")
            cookies = COOKIES if COOKIES.is_file() else None
            saved = download_source(url, work / "dl", cookies)
            source_name = saved.stem
            _update(job_id, source_name=source_name)

        if saved is None:
            raise MediaError("Нет файла и нет ссылки.")

        _update(job_id, stage="Снимаю аудиодорожку…" if saved.suffix.lower() in {
            ".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v", ".wmv", ".mpeg", ".mpg", ".flv", ".3gp", ".ts",
        } else "Нормализую звук…")
        wav = to_wav(saved, work / "audio.wav")

        _update(job_id, stage="Расшифровываю (Qwen3-ASR-1.7B-hf)…")
        engine.set_progress("Расшифровываю…")
        with pipeline_lock:
            result = engine.transcribe_wav(wav, language, work)
            chinese = is_chinese(result.language, result.text)
            russian = is_russian(result.language, result.text)
            pieces = split_sentences(result.text, chinese)
            sentences = [Sentence(original=p) for p in pieces]
            if chinese:
                _update(job_id, stage="Пиньинь (pypinyin + CC-CEDICT)…")
                engine.set_progress("Ставлю пиньинь…")
                for item in sentences:
                    item.pinyin = to_pinyin(item.original) or None

            if not russian and sentences:
                _update(job_id, stage="Перевожу (Hy-MT2-7B)…")
                engine.set_progress("Освобождаю GPU под переводчик…")
                engine.release_gpu()
                try:
                    translations = translator.translate_many(
                        [s.original for s in sentences],
                        result.language,
                        progress=engine.set_progress,
                    )
                    for item, translated in zip(sentences, translations):
                        item.translation = translated
                except Exception as exc:  # noqa: BLE001
                    engine.set_progress(f"Перевод не вышел: {exc}")
                finally:
                    translator.release_gpu()
                    engine.set_progress("Возвращаю ASR на GPU…")
                    try:
                        engine.load_model()
                    except Exception:
                        pass

        if chinese:
            mode_label = "пиньинь + перевод по предложениям"
        elif russian:
            mode_label = "только расшифровка"
        else:
            mode_label = "расшифровка + перевод"

        formatted = format_text(sentences, chinese) if (chinese or not russian) else (result.text or "")
        _update(
            job_id,
            status="done",
            stage="Готово",
            text=formatted,
            language=result.language,
            source_name=source_name,
            sentences=as_payload(sentences),
            mode_label=mode_label,
        )
        txt = DATA_DIR / "transcripts" / f"{job_id}.txt"
        txt.parent.mkdir(parents=True, exist_ok=True)
        txt.write_text(formatted or "", encoding="utf-8")
        _update(job_id, txt_path=str(txt))
    except MediaError as exc:
        _update(job_id, status="error", error=str(exc), stage="")
    except Exception as exc:  # noqa: BLE001
        _update(job_id, status="error", error=str(exc), stage="")
    finally:
        shutil.rmtree(work, ignore_errors=True)
        shutil.rmtree(DATA_DIR / "uploads" / job_id, ignore_errors=True)


@app.get("/")
def index():
    return render_template_string(PAGE, languages=LANGUAGES)


@app.get("/api/status")
def api_status():
    asr = engine.status()
    llm = translator.status()
    loading = asr["loading"] or llm["loading"]
    ready = asr["ready"]
    if asr["loading"]:
        stage = "Загружаю Qwen3-ASR-1.7B-hf…"
    elif llm["loading"]:
        stage = "Загружаю Hy-MT2-7B…"
    else:
        stage = ""
    return jsonify(
        {
            "ready": ready,
            "loading": loading,
            "error": asr["error"],
            "device": asr["device"],
            "model": asr["model"] if asr["ready"] else "",
            "translate_model": llm["model"] if llm["ready"] else "",
            "translate_ready": llm["ready"],
            "translate_error": llm["error"],
            "stage": stage,
        }
    )


@app.post("/api/transcribe")
def api_transcribe():
    language = (request.form.get("language") or "auto").strip()
    source = (request.form.get("source") or "").strip()
    url = (request.form.get("url") or "").strip()
    upload = request.files.get("file")

    use_file = source == "file" or (upload and upload.filename)
    if use_file:
        if not upload or not upload.filename:
            return jsonify(error="Выбери видео или аудио файл."), 400
        suffix = Path(upload.filename).suffix.lower()
        if suffix not in ALLOWED_EXT:
            return jsonify(error=f"Формат {suffix or 'без расширения'} не поддерживается."), 400
        job_id = uuid.uuid4().hex
        incoming = DATA_DIR / "uploads" / job_id
        incoming.mkdir(parents=True, exist_ok=True)
        saved = incoming / Path(upload.filename).name
        upload.save(saved)
        source_name = Path(upload.filename).name
        url = ""
    else:
        if not url:
            return jsonify(error="Вставь ссылку."), 400
        job_id = uuid.uuid4().hex
        saved = None
        source_name = url

    with _jobs_lock:
        _jobs[job_id] = {
            "status": "queued",
            "stage": "В очереди…",
            "text": "",
            "language": "",
            "error": "",
            "source_name": source_name,
            "sentences": [],
            "mode_label": "",
        }

    thread = threading.Thread(
        target=_run_job,
        args=(job_id, url, saved, language, source_name),
        daemon=True,
    )
    thread.start()
    return jsonify(job_id=job_id)


@app.get("/api/jobs/<job_id>")
def api_job(job_id: str):
    job = _job(job_id)
    if not job:
        return jsonify(error="Нет такой задачи"), 404
    payload = {k: v for k, v in job.items() if k != "txt_path"}
    if job.get("status") == "running":
        extra = engine.get_progress()
        if extra:
            payload["stage"] = extra
    return jsonify(payload)


@app.get("/api/jobs/<job_id>/txt")
def api_job_txt(job_id: str):
    job = _job(job_id)
    if not job or not job.get("txt_path"):
        return jsonify(error="Текст ещё не готов"), 404
    path = Path(job["txt_path"])
    name = (job.get("source_name") or "transcript").rsplit(".", 1)[0] + ".txt"
    return send_file(path, as_attachment=True, download_name=name, mimetype="text/plain")


def _boot_model() -> None:
    try:
        engine.load_model()
    except Exception:
        return


if __name__ == "__main__":
    threading.Thread(target=_boot_model, daemon=True).start()
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8080"))
    app.run(host=host, port=port, debug=False, threaded=True)
