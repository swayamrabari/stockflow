FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
COPY ai-service/pyproject.toml ./ai-service/pyproject.toml
RUN uv sync --frozen --no-dev --no-install-workspace

COPY manage.py .
COPY config ./config
COPY core ./core
COPY assets ./assets
COPY tailwind ./tailwind
COPY docker ./docker

RUN chmod +x docker/django-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/docker/django-entrypoint.sh"]
