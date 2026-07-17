# ── 🦉 Hypatia Sims4ModGuard API ─────────────────────────────────────────────
# Production-ready FastAPI service image
# Build:  docker build -t hypatia-sims4-service .
# Run:    docker run -p 8765:8765 --env-file .env hypatia-sims4-service

FROM python:3.11-slim

# Security: run as non-root
RUN groupadd --gid 1001 hypatia && \
    useradd --uid 1001 --gid hypatia --no-create-home --shell /bin/false hypatia

WORKDIR /app

# Install dependencies first (layer cached unless requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy service source
COPY main.py analyzer.py conflict_db.py models.py ./

# Ensure the container runs as non-root
USER hypatia

EXPOSE 8765

# Use uvicorn with multiple workers for production throughput.
# Adjust --workers based on available CPU cores (2 * cores + 1 is typical).
CMD ["uvicorn", "main:app", \
     "--host", "0.0.0.0", \
     "--port", "8765", \
     "--workers", "2", \
     "--log-level", "info", \
     "--access-log"]
