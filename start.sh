#!/usr/bin/env sh
set -eu

unset STREAMLIT_SERVER_PORT || true

if [ -z "${PORT:-}" ]; then
  APP_PORT=8501
else
  APP_PORT="$PORT"
fi

case "$APP_PORT" in
  ''|*[!0-9]*)
    APP_PORT=8501
    ;;
esac

echo "Starting Streamlit on port ${APP_PORT}"
exec streamlit run dashboard_streamlit.py --server.address=0.0.0.0 --server.port="${APP_PORT}" --server.headless=true
