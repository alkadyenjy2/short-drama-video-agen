#!/bin/sh
set -eu

# Railway volumes are mounted at runtime and may be root-owned.
# Prepare persistent application state, then run the app as appuser.
mkdir -p /app/data
chown -R appuser:appuser /app/data

exec su -s /bin/sh appuser -c 'exec python main.py'
