# Third-party notices

YouTube Transcribe Pinyin’s **application code** is licensed under AGPL-3.0 (see `LICENSE`). This file lists other people’s work that the project uses or downloads. Their terms still apply.

## In the repository / image

| Project | Use | License (typical) |
|---|---|---|
| [MeTube](https://github.com/alexta69/metube) | Optional downloader UI (`docker-compose.metube.yml`, `app/`, `ui/`) | AGPL-3.0 |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | Download from URLs | Unlicense |
| [Flask](https://flask.palletsprojects.com/) | HTTP UI | BSD-3-Clause |
| [pypinyin](https://github.com/mozillazg/python-pinyin) | Hanzi → pinyin | MIT |
| [pypinyin-dict](https://github.com/mozillazg/pypinyin-dict) / [CC-CEDICT](https://cc-cedict.org/) | Phrase readings | CC-CEDICT: **CC-BY-SA-4.0** |
| [FFmpeg](https://ffmpeg.org/) | Demux audio from video | LGPL/GPL (distro package) |
| [PyTorch](https://pytorch.org/) | Inference | BSD-style |

## Downloaded at runtime (not in git)

| Checkpoint | Use | License (see the model card) |
|---|---|---|
| [Qwen/Qwen3-ASR-1.7B-hf](https://huggingface.co/Qwen/Qwen3-ASR-1.7B-hf) | Speech recognition | Apache-2.0 (card) |
| [Qwen/Qwen2.5-1.5B-Instruct](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct) | Translation | Apache-2.0 (card) |

Always re-check the Hugging Face model card before commercial use.

## Attribution

CC-CEDICT is a Creative Commons Attribution-Share Alike 4.0 dictionary. YouTube Transcribe Pinyin uses it only to look up pinyin; modified dictionary dumps, if you publish them, need to follow ShareAlike.
