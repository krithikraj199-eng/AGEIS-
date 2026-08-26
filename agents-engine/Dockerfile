# =============================================================================
# AEGIS Ω Intelligence Engine — Production Dockerfile for Google Cloud Run
# =============================================================================

FROM python:3.12-slim AS base

# Prevent Python from buffering stdout/stderr and writing .pyc files
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080 \
    HOST=0.0.0.0

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Create non-root system user for security
RUN addgroup --system aegis && \
    adduser --system --group aegis && \
    chown -R aegis:aegis /app

USER aegis

# Cloud Run injects PORT environment variable dynamically
EXPOSE 8080

# Run FastAPI server with Uvicorn
CMD ["sh", "-c", "exec uvicorn runtime.server:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1"]
