# YouTube Transcribe Pinyin — YouTube ASR + пиньинь / speech-to-text + pinyin

Локальная расшифровка **китайского** YouTube (и любого аудио/видео): не просто текст, а **иероглифы + pinyin (пиньинь) + перевод на русский по предложениям**. Self-hosted ASR, без облака.

Most Whisper boxes dump a wall of hanzi. This one annotates **Chinese speech → 汉字 + pinyin + Russian**, sentence by sentence — for watching, not for a subtitle file you’ll never open.

**Self-hosted speech-to-text:** ссылка на YouTube / файл → из видео только звук → Qwen3-ASR.

- **Chinese / китайский:** 汉字 + **pinyin** + перевод RU по предложениям  
- **Not Russian / не русский:** transcript + offline translation → русский  
- **Russian / русский:** только расшифровка

Docker + NVIDIA GPU. LAN: `http://<IP>:8080`. Не Whisper API, не Google Speech.

> **GitHub About:**  
> `Китайский YouTube → иероглифы + пиньинь + перевод. Local speech-to-text (ASR) with pinyin for Chinese, offline Russian translation. Qwen3, Docker GPU, без облака.`
>
> **Repo:** `youtube-transcribe-pinyin`  
> **Topics:** `asr` `speech-to-text` `pinyin` `chinese` `hanzi` `youtube` `transcription` `language-learning` `qwen` `docker` `self-hosted` `gpu` `yt-dlp` `russian` `offline` `subtitles` `ffmpeg` `whisper-alternative`

[Windows / Docker](docs/windows.md) · [Модели / Models](docs/models.md) · [API](docs/api.md) · [MeTube](docs/metube.md)

```
YouTube / VK / любая ссылка yt-dlp ┐
Audio: mp3 wav m4a flac opus       ├─ ffmpeg ─ Qwen3-ASR-1.7B ─ text
Video: mp4 mkv webm mov            ┘              │
                                    Chinese  → pypinyin + CC-CEDICT (pinyin)
                                    not RU   → local LLM → русский перевод
                                    Russian  → transcript only
```

## Зачем пиньинь / Why pinyin

Обычный local ASR (Whisper и клоны) для китайского отдаёт простыню иероглифов. Учить или просто смотреть ролик с этим неудобно: нет озвучки слогов, перевод если и есть — одним абзацем.

Здесь после распознавания каждое предложение отдельно:

```
你好世界。
nǐ hǎo shì jiè。
Привет, мир.
```

Пиньинь — словарь **pypinyin + CC-CEDICT** (не LLM, не GPU). Перевод на русский — маленькая локальная модель, по тем же предложениям. Для китайского YouTube / лекций / влогов это ближе к «карточкам», чем к сырому transcript.

Typical self-hosted transcribers stop at hanzi. This pipeline is **ASR → pinyin → per-sentence Russian**, so a Chinese video is readable if you don’t know the characters yet.

## Зачем локально / Why local

Ролик с китайским часто не хочется гнать в облачный speech-to-text. Тут GPU дома, UI по LAN, телеметрии нет.

Cloud ASR is fine until the clip is private. Local models, LAN UI, no telemetry.

## Возможности / Features

| | RU | EN |
|---|---|---|
| Источник | YouTube, VK, прямые ссылки, загрузка файла | YouTube & [yt-dlp sites](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md), file upload |
| Видео | только аудиодорожка (ffmpeg demux) | extract audio track, drop the picture |
| ASR | [Qwen3-ASR-1.7B](https://huggingface.co/Qwen/Qwen3-ASR-1.7B), ~52 языка | multilingual speech recognition |
| Пиньинь | словарь `pypinyin` + CC-CEDICT, без GPU | hanzi → pinyin, dictionary not an LLM |
| Перевод | Qwen2.5-1.5B-Instruct → русский, оффлайн | local translation, imperfect on purpose |
| Сеть | `0.0.0.0:8080`, шаринг по LAN | share on the local network |

Опционально качалка без ASR: [MeTube](docs/metube.md) на порту 8081.

## Требования / Requirements

- Windows 10/11 (Docker Desktop + WSL2) или Linux  
- NVIDIA GPU, **~8 GB VRAM** (ASR 1.7B + small LLM)  
- Актуальный NVIDIA driver + [Docker](https://www.docker.com/products/docker-desktop/) с GPU

Первый запуск качает веса с Hugging Face (несколько ГБ) в volume `transcribe-models`.

## Запуск / Quick start

```bat
git clone https://github.com/<you>/youtube-transcribe-pinyin.git
cd youtube-transcribe-pinyin
start-asr.bat
```

```bash
docker compose up --build
```

UI: [http://localhost:8080](http://localhost:8080)  
LAN: `http://<IPv4-этого-ПК>:8080`

Подробно: [docs/windows.md](docs/windows.md). YouTube «Sign in to confirm» → `downloads/cookies.txt` (Netscape).

## Конфиг / Config

`docker-compose.yml`:

| Variable | Default | |
|---|---|---|
| `ASR_MODEL` | `Qwen/Qwen3-ASR-1.7B` | speech-to-text checkpoint |
| `TRANSLATE_MODEL` | `Qwen/Qwen2.5-1.5B-Instruct` | local translator |
| `ASR_CHUNK_SEC` | `480` | нарезка длинных роликов / long-audio chunks |
| `ASR_MAX_NEW_TOKENS` | `4096` | лимит генерации на кусок |

## Структура / Layout

```
simple_web/          Flask UI + ASR + pinyin + translate
  asr_studio.py
  engine.py          Qwen3-ASR (speech recognition)
  pinyinconv.py      pypinyin + CC-CEDICT
  translator.py      local LLM
  media.py           yt-dlp + ffmpeg
docker-compose.yml   GPU service
```

## Лицензия / License

Код — **AGPL-3.0** (в дереве есть [MeTube](https://github.com/alexta69/metube)). Веса моделей и CC-CEDICT — свои условия: [NOTICE](NOTICE.md).

Free software: fork, run, share. If you serve a modified copy on a network, AGPL requires offering source to users.

## Disclaimer

Качайте через yt-dlp только то, на что есть право. Перевод маленькой LLM местами кривой. Пиньинь словарный: многозначные иероглифы и sandhi `一/不` могут быть неточными.

Use yt-dlp only where you may download. Translation is a small local model. Pinyin is dictionary-based, not neural G2P.

## Credits

[Qwen3-ASR](https://github.com/QwenLM/Qwen3-ASR) · [pypinyin](https://github.com/mozillazg/python-pinyin) · [CC-CEDICT](https://cc-cedict.org/) · [yt-dlp](https://github.com/yt-dlp/yt-dlp) · [MeTube](https://github.com/alexta69/metube)
