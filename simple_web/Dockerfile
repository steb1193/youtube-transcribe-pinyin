FROM pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/models \
    PORT=8080 \
    HOST=0.0.0.0 \
    DATA_DIR=/data \
    ASR_MODEL=Qwen/Qwen3-ASR-1.7B-hf \
    TRANSLATE_MODEL=tencent/Hy-MT2-7B \
    TRANSLATE_BITS=8 \
    NVIDIA_VISIBLE_DEVICES=all \
    NVIDIA_DRIVER_CAPABILITIES=compute,utility

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        libsndfile1 \
        git \
        ca-certificates \
        curl \
        unzip \
    && rm -rf /var/lib/apt/lists/* \
    && ffmpeg -version \
    && ffprobe -version

# YouTube: yt-dlp EJS нужен Deno (https://github.com/yt-dlp/yt-dlp/wiki/EJS)
RUN curl -fsSL https://deno.land/install.sh | DENO_INSTALL=/usr/local sh \
    && deno --version

WORKDIR /app

COPY requirements-asr.txt /app/requirements-asr.txt
RUN pip install --no-cache-dir -U pip \
    && pip install --no-cache-dir -r /app/requirements-asr.txt \
    && pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cu124 torch==2.5.1 \
    && python -m yt_dlp --js-runtimes deno --version

# Веса в слое образа: на Windows не качать Hugging Face при каждом docker run.
RUN python -c "from huggingface_hub import snapshot_download; import os; \
[snapshot_download(repo_id=r) for r in (os.environ['ASR_MODEL'], os.environ['TRANSLATE_MODEL'])]"

ENV HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

COPY engine.py media.py asr_studio.py runtime.py enrich.py translator.py pinyinconv.py /app/

EXPOSE 8080
CMD ["python", "asr_studio.py"]
