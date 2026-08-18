# syntax=docker/dockerfile:1
# Basir AI — Backend API container
# Python 3.11, matching the pinned version in ARCHITECTURE.md.

FROM python:3.11-slim

# --- OS dependencies ---
# libpq-dev is needed by psycopg[binary] on slim images.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# --- Working directory ---
WORKDIR /app

# --- Python dependencies ---
# Copy requirements first so Docker layer-caches the install step.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# --- Application source ---
COPY . .

# --- Port ---
EXPOSE 8000

# --- Entrypoint ---
# 1. Run Alembic migrations (creates / upgrades schema).
# 2. Start Uvicorn.
# alembic must run from the directory that contains alembic.ini (i.e. /app).
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
