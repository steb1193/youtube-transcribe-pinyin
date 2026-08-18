# Models

YouTube Transcribe Pinyin does **not** train anything. It downloads public checkpoints on first start and keeps them in the Docker volume `transcribe-models` (`HF_HOME=/models`).

## Speech · Qwen3-ASR-1.7B

- Card: [Qwen/Qwen3-ASR-1.7B-hf](https://huggingface.co/Qwen/Qwen3-ASR-1.7B-hf)
- Runtime: Hugging Face `transformers>=5.13` (native Qwen3-ASR)
- Role: language id + transcription (including long audio, chunked every `ASR_CHUNK_SEC` seconds)
- Override: `ASR_MODEL` in `docker-compose.yml`

## Translation · Qwen2.5-1.5B-Instruct

- Card: [Qwen/Qwen2.5-1.5B-Instruct](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct)
- Role: sentence-level translation **into Russian** when the transcript is not Russian
- Override: `TRANSLATE_MODEL`
- Quality: small on purpose (fits next to ASR). Awkward wording is expected.

A dedicated MT checkpoint (e.g. Tencent Hy-MT2-1.8B) can be swapped in via `TRANSLATE_MODEL` if you change `translator.py` to match that model’s chat template.

## Pinyin · not a neural net

Hanzi → pinyin is **[pypinyin](https://github.com/mozillazg/python-pinyin)** plus **[CC-CEDICT](https://cc-cedict.org/)** (`pypinyin-dict`). No GPU, no LLM.

- Good at known compounds (`银行`, `行走`)
- Weak at isolated polyphones (`得` / `地` / `了`) and tone sandhi (`一`, `不`)

That is an explicit tradeoff: dictionary-only, fast, offline.

## What is downloaded vs what is in git

| In git | Downloaded at runtime |
|---|---|
| Flask app, Dockerfiles, compose | Qwen3-ASR weights |
| `pypinyin` / `pypinyin-dict` wheels | Qwen2.5-1.5B weights |
| | CUDA PyTorch (image) |
