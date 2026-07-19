# ── EduMind AI — Application Dockerfile ────────────────────────────────────────
FROM python:3.11-slim AS deps

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# ── Application ───────────────────────────────────────────────────────────────
FROM deps AS app

WORKDIR /app

COPY . .

RUN mkdir -p data/staging vector_store/chroma_db

# Cloud Run listens on port 8080
EXPOSE 8080

CMD ["sh", "-c", "uvicorn backend.app:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1"]