# ── EduMind AI — Application Dockerfile ────────────────────────────────────────
# Multi-stage: deps layer (cacheable) + app layer
# Base: python:3.11-slim (no GPU needed — Ollama runs separately)

FROM python:3.11-slim AS deps

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System packages required by python-docx, sentence-transformers, chromadb
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (Docker layer caching)
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# ── App layer ────────────────────────────────────────────────────────────────
FROM deps AS app

WORKDIR /app

# Copy application source
COPY . .

# Create persistent directories (volumes will mount here)
RUN mkdir -p data/staging vector_store/chroma_db

# Expose FastAPI port
EXPOSE 8000

# Health-check: ping the API
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/api/admin/stats', headers={'Authorization':'Bearer dummy'}, timeout=5)"

# Startup: seed the DB if needed, then launch uvicorn
CMD ["sh", "-c", "python seed_users.py 2>/dev/null; uvicorn backend.app:app --host 0.0.0.0 --port 8000 --workers 1"]
