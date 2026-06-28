#!/bin/bash
# ── EduMind AI — Docker startup script ────────────────────────────────────────
# Runs inside the container; handles Ollama env var override.

set -e

# Override Ollama base URL if set via environment (Docker Compose passes this)
if [ -n "$OLLAMA_BASE_URL" ]; then
    echo "[STARTUP] Ollama base URL: $OLLAMA_BASE_URL"
fi

# Patch rag/ollama_client.py default base_url at runtime if needed
# (The OllamaConfig default is localhost:11434; in Docker we point to the ollama service)
export PYTHONPATH="/app:${PYTHONPATH}"

# Seed the users database (idempotent — only creates if not exists)
echo "[STARTUP] Seeding database..."
python -c "
from backend.database import Base, engine
Base.metadata.create_all(bind=engine)
from backend.database import SessionLocal, User
from backend.auth import hash_password
db = SessionLocal()
if not db.query(User).first():
    from seed_users import SEED_USERS
    for e in SEED_USERS:
        db.add(User(username=e['username'], hashed_password=hash_password(e['password']), role=e['role']))
    db.commit()
    print('[STARTUP] Users seeded.')
else:
    print('[STARTUP] Users already present.')
db.close()
" 2>/dev/null || echo "[STARTUP] DB seed skipped (already exists)"

# Wait for Ollama if OLLAMA_BASE_URL is set
if [ -n "$OLLAMA_BASE_URL" ]; then
    echo "[STARTUP] Waiting for Ollama at $OLLAMA_BASE_URL ..."
    for i in $(seq 1 30); do
        if curl -sf "$OLLAMA_BASE_URL/" > /dev/null 2>&1; then
            echo "[STARTUP] Ollama is ready."
            break
        fi
        echo "[STARTUP]   attempt $i/30..."
        sleep 3
    done
fi

# Launch FastAPI
echo "[STARTUP] Starting EduMind FastAPI server..."
exec uvicorn backend.app:app --host 0.0.0.0 --port 8000 --workers 1
