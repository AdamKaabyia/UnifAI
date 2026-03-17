#!/bin/sh

set -e

echo ""
echo "------------------------------------------"
echo "  Starting container with ROLE=\"$ROLE\""
echo "------------------------------------------"

case "$ROLE" in
  serve)
    echo "Starting production API server (Gunicorn)..."
    exec mas api serve \
      --port "${PORT:-8002}" \
      --workers "${GUNICORN_WORKERS:-4}" \
      --threads "${GUNICORN_THREADS:-1}" \
      --timeout "${GUNICORN_TIMEOUT:-120}"
    ;;

  serve-dev)
    echo "Starting development API server (Flask)..."
    exec mas api dev --port "${PORT:-8002}"
    ;;

  temporal-worker)
    echo "Starting Temporal worker..."
    exec mas temporal-worker --threads "${WORKER_THREADS:-10}"
    ;;

  debug)
    echo "Debug mode — container will stay alive."
    tail -f /dev/null
    ;;

  *)
    echo "ERROR: Unknown ROLE \"$ROLE\""
    echo "Valid roles: serve, serve-dev, temporal-worker, debug"
    exit 1
    ;;
esac
