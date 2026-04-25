#!/bin/sh
# Celery worker + Beat scheduler combined.
# Concurrency is set in celery_app.py (worker_concurrency=2) to stay within
# Railway's 512 MB memory limit. Beat runs in the same process to avoid a
# second dyno.
exec celery -A app.tasks.celery_app worker \
    --beat \
    --loglevel=info \
    --concurrency=2 \
    --max-tasks-per-child=50 \
    -Q celery,marketing
