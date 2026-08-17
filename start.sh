#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p downloads
docker compose up --build -d
echo "YouTube Transcribe Pinyin (YouTube ASR + pinyin): http://127.0.0.1:8080"
echo "LAN: http://<IP>:8080"
echo "MeTube downloader only: docker compose -f docker-compose.metube.yml up -d"
