@echo off
cd /d "%~dp0"
echo YouTube Transcribe Pinyin - Chinese YouTube ASR + pinyin
echo UI:  http://localhost:8080
echo LAN: http://THIS-PC-IP:8080
echo.
docker compose up --build
