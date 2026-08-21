FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    ULTRALYTICS_CONFIG_DIR=/app/.config/Ultralytics

WORKDIR /app

# OpenCV's headless wheel still needs these runtime libraries on slim images.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libglib2.0-0 libgl1 \
    && rm -rf /var/lib/apt/lists/*

COPY inference/requirements.txt /app/inference/requirements.txt
RUN python -m pip install --upgrade pip \
    && python -m pip install -r /app/inference/requirements.txt

# Source code and the checked-in mock fixture are reproducible. Model weights,
# private data, and generated snapshots are deliberately excluded by the root
# .dockerignore and must be supplied/downloaded at runtime when needed.
COPY inference /app/inference
COPY dataset/mock /app/dataset/mock

RUN useradd --create-home --uid 10001 basir \
    && mkdir -p /app/.config/Ultralytics /app/snapshots \
    && chown -R basir:basir /app

USER basir

CMD ["python", "-m", "inference.main"]
