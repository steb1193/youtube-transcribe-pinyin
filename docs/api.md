# HTTP API

The UI is a static page that talks to these endpoints. Bind address is `0.0.0.0` (LAN). There is **no auth** — put it behind a VPN or reverse proxy if the network is not trusted.

## `GET /`

HTML UI (Russian).

## `GET /api/status`

Model load state.

```json
{
  "ready": true,
  "loading": false,
  "error": null,
  "device": "cuda:0 (NVIDIA GeForce RTX 3060)",
  "model": "Qwen/Qwen3-ASR-1.7B",
  "translate_model": "Qwen/Qwen2.5-1.5B-Instruct",
  "translate_ready": true,
  "translate_error": null,
  "stage": ""
}
```

`ready` is true when ASR is up. Translation can still be loading; jobs will wait or skip translate on failure.

## `POST /api/transcribe`

`multipart/form-data`:

| Field | |
|---|---|
| `source` | `url` or `file` |
| `url` | http(s) link (yt-dlp) |
| `file` | video or audio upload |
| `language` | `auto` or an ASR language name (`Chinese`, `English`, `Russian`, …) |

Response: `{ "job_id": "<hex>" }`.

Max upload: `MAX_UPLOAD_MB` (default 2048).

## `GET /api/jobs/<job_id>`

```json
{
  "status": "queued | running | done | error",
  "stage": "Пиньинь (pypinyin + CC-CEDICT)…",
  "text": "formatted transcript",
  "language": "Chinese",
  "mode_label": "пиньинь + перевод по предложениям",
  "source_name": "video title",
  "sentences": [
    {
      "original": "你好。",
      "pinyin": "nǐ hǎo。",
      "translation": "Привет."
    }
  ],
  "error": ""
}
```

Poll every ~1 s until `done` or `error`.

## `GET /api/jobs/<job_id>/txt`

Download the formatted `.txt` (original / pinyin / translation blocks).
