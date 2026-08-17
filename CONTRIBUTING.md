# Contributing · как помочь

RU-аудитория, EN-ключи в README — так репозиторий ищут по `youtube transcribe`, `speech-to-text`, `расшифровка видео`, `pinyin`, `Qwen ASR`.

## Issues

Баги и идеи — через GitHub Issues (шаблоны на русском с английскими полями).  
Не кидай сюда поломки самого yt-dlp (логин YouTube, сайт не качается) — это [yt-dlp](https://github.com/yt-dlp/yt-dlp/issues).

## PR

1. Форк → ветка `fix/...` или `feat/...`
2. Меняй по возможности только `simple_web/` и compose/доки YouTube Transcribe Pinyin. `app/` + `ui/` — upstream MeTube (AGPL), не раздувай их без нужды.
3. Не коммить веса моделей, `downloads/`, `.venv`, cookies.
4. README.md должен остаться **двуязычным** (RU смысл + EN keywords). Лимит CI: &lt; 25 000 байт (лимит Docker Hub).

## Code

- Python 3.12-ish, Flask, без облачных API.
- Пиньинь только `pypinyin` + CC-CEDICT, не LLM.
- Перевод — локальная instruct-модель, в русский.
- UI на русском.

## License

Патчи к этому дереву — AGPL-3.0, как у MeTube.
