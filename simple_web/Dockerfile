FROM pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/models \
    HUGGINGFACE_HUB_CACHE=/models \
    TRANSFORMERS_CACHE=/models \
    PORT=8080 \
    HOST=0.0.0.0 \
    DATA_DIR=/data \
    ASR_MODEL=Qwen/Qwen3-ASR-1.7B \
    TRANSLATE_MODEL=Qwen/Qwen2.5-1.5B-Instruct \
    NVIDIA_VISIBLE_DEVICES=all \
    NVIDIA_DRIVER_CAPABILITIES=compute,utility

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        git \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements-asr.txt /app/requirements-asr.txt
RUN pip install --no-cache-dir -U pip \
    && pip install --no-cache-dir -r /app/requirements-asr.txt \
    && pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cu124 torch==2.5.1

COPY engine.py media.py asr_studio.py runtime.py enrich.py translator.py pinyinconv.py /app/

EXPOSE 8080
CMD ["python", "asr_studio.py"]
