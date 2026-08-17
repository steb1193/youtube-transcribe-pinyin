# Security Policy

YouTube Transcribe Pinyin — self-hosted ASR UI **без логина**. Это ожидаемо: ставь на доверенную LAN или за VPN / reverse proxy. «Открывается без пароля» — не уязвимость.

## Reporting

Пиши уязвимости **приватно** (GitHub Security Advisories в этом репо). Не открывай публичный issue с эксплойтом.

## Supported

Только текущий `main` / latest Docker build.

## Scope

- In: path traversal, SSRF через загрузку, утечка cookies.txt, RCE в обработчике файлов.
- Out: «нет auth», «yt-dlp качает чужое», галлюцинации ASR/перевода.
