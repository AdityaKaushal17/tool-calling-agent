#!/bin/sh
# Container entrypoint. On hosts without free background workers (e.g. Render free),
# set RUN_WORKER_IN_PROCESS=true to run the Celery worker alongside the API.
set -e

python -m app.db.bootstrap

if [ "${RUN_WORKER_IN_PROCESS:-false}" = "true" ]; then
  celery -A app.workers.celery_app.celery_app worker --loglevel=INFO --pool=solo --concurrency=1 &
fi

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips="*"
