#!/bin/sh
set -eu

uv run python manage.py migrate --noinput
uv run python manage.py collectstatic --noinput

exec uv run gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers "${WEB_CONCURRENCY:-2}" \
    --timeout "${GUNICORN_TIMEOUT:-60}" \
    --access-logfile - \
    --error-logfile -
