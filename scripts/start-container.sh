#!/bin/sh
set -e

python manage.py migrate --noinput
# Idempotent: prints "already exists" and returns 0 on every deploy after the first.
python manage.py createcachetable

exec gunicorn config.wsgi:application \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers "${WEB_CONCURRENCY:-2}" \
  --timeout "${GUNICORN_TIMEOUT:-120}"
