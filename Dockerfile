# ── Build stage ───────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

COPY pyproject.toml .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application files
COPY src/ ./src/
COPY config.yaml .

# Persistent volume for state.json (override with -e STATE_DIR or fly.toml mount)
ENV STATE_DIR=/data
RUN mkdir -p /data

# Run scanner
CMD ["python", "-m", "src.main"]
