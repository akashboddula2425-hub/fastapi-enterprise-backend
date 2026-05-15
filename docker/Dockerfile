# ── Stage 1: Build dependencies ──────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

COPY requirements.txt .

# Install dependencies into /install
RUN pip install --upgrade pip \
    && pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: Runtime image ────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# curl is needed for the docker-compose healthcheck
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 1. Copy the installed libraries from the builder stage
COPY --from=builder /install /usr/local

# 2. Copy application source
COPY app/ ./app/

# 3. Copy Alembic configuration and migration folder
COPY alembic.ini .
COPY alembic/ ./alembic/

# 4. Copy Testing configuration and test folder
COPY tests/ ./tests/
COPY pytest.ini .

# Entrypoint runs migrations before launching uvicorn
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

CMD ["/entrypoint.sh"]