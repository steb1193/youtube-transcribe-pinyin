"""Общий GPU-лок: ASR и LLM не должны работать параллельно."""

from __future__ import annotations

import threading

gpu_lock = threading.Lock()
pipeline_lock = threading.Lock()
