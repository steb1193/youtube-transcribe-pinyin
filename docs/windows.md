# Windows — Docker + NVIDIA

YouTube Transcribe Pinyin: китайский YouTube → 汉字 + pinyin + перевод. Speech-to-text на GPU, шаринг по LAN.

## 1. Driver and Docker

1. Install a current **NVIDIA Game Ready / Studio** driver.
2. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) with the **WSL2** backend.
3. In Docker Desktop: Settings → Resources → WSL integration (your distro on).
4. Confirm GPU passthrough:

```bat
docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi
```

You should see the GPU name. If not, GPU in containers is not enabled yet.

## 2. Run YouTube Transcribe Pinyin

From the repo root:

```bat
start-asr.bat
```

or:

```bat
docker compose up --build
```

- This PC: http://localhost:8080
- LAN: `http://<IPv4-of-this-PC>:8080`

Find the IP: `ipconfig` → Ethernet / Wi‑Fi → IPv4. Allow **TCP 8080** inbound in Windows Firewall if other PCs cannot connect.

First boot pulls the image and Hugging Face weights (ASR ~3–4 GB, translator ~3 GB). Later starts reuse the `transcribe-models` volume.

## 3. Stop / logs

```bat
docker compose logs -f
docker compose down
```

Weights survive `down`. To wipe them: `docker volume ls` and remove `youtube-transcribe-pinyin_transcribe-models`.

## 4. VRAM

| Setup | Rough VRAM |
|---|---|
| ASR 1.7B + Qwen2.5-1.5B | ~8 GB |
| ASR only (translator failed to load) | ~5 GB |

If the translator OOM’s, transcription still works; pinyin does not use the GPU.

## 5. YouTube cookies

If yt-dlp asks to sign in, export cookies (browser extension → Netscape `cookies.txt`) to:

```
downloads\cookies.txt
```

Restart is not required; the next job picks the file up.

## Optional: MeTube downloader

Classic download-only UI (no ASR):

```bat
docker compose -f docker-compose.metube.yml up -d
```

http://localhost:8081 — see [metube.md](metube.md).
