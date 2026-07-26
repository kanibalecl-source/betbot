#!/usr/bin/env sh
set -eu

APP_PORT="${PORT:-8000}"
API_WORKER_COUNT="${API_WORKERS:-1}"

case "$APP_PORT" in
  ''|*[!0-9]*)
    echo "ERROR: PORT must be a positive integer" >&2
    exit 2
    ;;
esac

case "$API_WORKER_COUNT" in
  ''|*[!0-9]*)
    echo "ERROR: API_WORKERS must be a positive integer" >&2
    exit 2
    ;;
esac

if [ "$APP_PORT" -lt 1 ] || [ "$APP_PORT" -gt 65535 ]; then
  echo "ERROR: PORT must be between 1 and 65535" >&2
  exit 2
fi

if [ "$API_WORKER_COUNT" -lt 1 ]; then
  echo "ERROR: API_WORKERS must be at least 1" >&2
  exit 2
fi

# The API is analytical by default. Explicit Railway variables may override
# these values later, but a missing variable must never enable capital actions
# or the state-publishing worker.
: "${BETTING_ENABLED:=false}"
: "${REALTIME_ENABLED:=false}"
export BETTING_ENABLED REALTIME_ENABLED

echo "Starting BetBot FastAPI on port ${APP_PORT} with ${API_WORKER_COUNT} worker(s)"
exec python -m uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "$APP_PORT" \
  --workers "$API_WORKER_COUNT" \
  --proxy-headers \
  --forwarded-allow-ips="*"
