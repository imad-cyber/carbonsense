# Multi-stage build — production image has no build tools
FROM python:3.12-slim AS base

WORKDIR /app

# Install system dependencies for psycopg2 and other native libs
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

FROM base AS builder
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM base AS production
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

COPY . .

# Create directories the app needs at runtime
RUN mkdir -p models vector_store logs

# Non-root user — security requirement in every enterprise deployment
RUN adduser --disabled-password --gecos "" appuser
RUN chown -R appuser:appuser /app /root/.local
USER appuser

EXPOSE 8000

# Healthcheck — Kubernetes uses this to determine pod health
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
