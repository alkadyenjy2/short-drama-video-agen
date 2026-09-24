#!/bin/sh
set -eu

# Railway volumes are mounted at runtime and may be root-owned.
# Prepare the persistent application data directory before dropping privileges.
mkdir -p /app/data
chown -R appuser:appuser /app/data

exec su -s /bin/sh appuser -c 'exec "$@"' -- "$@"
