# ── Stage 1: build ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Install deps into an isolated prefix so we can copy only them
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: runtime ────────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Backend package
COPY backend/ backend/

# Root-level Python modules imported by the backend
COPY data_ingestion.py           .
COPY winner_feature_engineering.py .
COPY winner_model.py             .
COPY winner_labels.py            .
COPY chaos_matrix.py             .
COPY practice_data_ingestion.py  .
COPY practice_feature_engineering.py .

# Pre-trained model (committed to git, required on Render free tier)
COPY models/ models/

# Create writable dirs for FastF1 cache and practice cache at runtime
RUN mkdir -p cache fastf1_cache

ENV FASTF1_CACHE_DIR=/app/fastf1_cache
ENV PORT=8011

EXPOSE 8011

# Use shell form so $PORT is expanded at container start
CMD uvicorn backend.main:app --host 0.0.0.0 --port ${PORT}
