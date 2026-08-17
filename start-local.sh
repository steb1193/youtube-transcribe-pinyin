#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p downloads
python3 -m venv .venv
.venv/bin/pip install -r simple_web/requirements.txt
echo "http://127.0.0.1:8081"
.venv/bin/python simple_web/app.py
