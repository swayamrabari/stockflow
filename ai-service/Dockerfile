FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
COPY ai-service/pyproject.toml ./ai-service/pyproject.toml
COPY ai-service/README.md ./ai-service/README.md
COPY ai-service/src ./ai-service/src
RUN uv sync --frozen --no-dev --package ai-service

WORKDIR /app/ai-service

EXPOSE 8001

CMD ["uv", "run", "uvicorn", "ai_service.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]
