#!/bin/sh
# YouTube ломает extractor чаще, чем мы пересобираем образ с весами.
# Как MeTube: nightly yt-dlp при старте, без этого снова 403 / «no JS runtime».
if [ "${YTDLP_UPDATE:-1}" != "0" ]; then
    echo "Updating yt-dlp (nightly)…"
    python -m pip install --no-cache-dir -U --pre "yt-dlp[default]" \
        || echo "yt-dlp nightly update skipped; using the image copy"
fi
exec "$@"
