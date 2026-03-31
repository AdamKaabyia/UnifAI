#!/bin/sh

set -e

echo ""
echo "------------------------------------------"
echo "Starting container with ROLE=\"$ROLE\""
echo "------------------------------------------"

case "$ROLE" in
  flask)
    echo "Starting Flask API (Server)..."
    . ~/backend/venv/bin/activate
    exec gunicorn -w $GUNICORN_WORKERS --threads $GUNICORN_THREADS -b 0.0.0.0:$PORT --timeout $GUNICORN_TIMEOUT --access-logfile - --error-logfile - run.wsgi:application
    ;;

  debug)
    echo "Debug mode activated - container will stay alive."
    tail -f /dev/null
    ;;

  *)
    echo "ERROR: Unknown ROLE \"$ROLE\""
    echo "Valid roles are: flask, debug"
    exit 1
    ;;
esac
