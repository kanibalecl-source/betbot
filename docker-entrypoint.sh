#!/usr/bin/env sh
set -eu

DATA_PATH="${KANIBAL_DATA_DIR:-${PERSISTENT_DATA_DIR:-${RAILWAY_VOLUME_MOUNT_PATH:-/data}}}"
OWNER_MARKER="${DATA_PATH}/.kanibal_owner_uid_10001"

if [ "$(id -u)" = "0" ]; then
  if [ -d "${DATA_PATH}" ]; then
    current_owner="$(stat -c '%u' "${DATA_PATH}" 2>/dev/null || echo unknown)"
    if [ "${current_owner}" != "10001" ] || [ ! -f "${OWNER_MARKER}" ]; then
      echo "Preparing persistent storage ownership for uid 10001"
      chown -R 10001:10001 "${DATA_PATH}"
      gosu 10001:10001 sh -c "printf '%s\n' ready > \"${OWNER_MARKER}\""
    fi
  fi
  exec gosu 10001:10001 "$@"
fi

exec "$@"
