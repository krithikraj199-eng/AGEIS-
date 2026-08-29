FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AEGIS_HOST=0.0.0.0 \
    AEGIS_PORT=8000 \
    AEGIS_MEMORY_DB=/data/aegis_memory.db

WORKDIR /app
COPY backend/requirements-core.txt /app/backend/requirements-core.txt
RUN pip install --no-cache-dir -r /app/backend/requirements-core.txt
COPY backend /app/backend
RUN mkdir -p /data

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]

