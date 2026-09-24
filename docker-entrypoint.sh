#!/bin/sh
set -eu

# Railway volumes are mounted at runtime and may be root-owned.
# Prepare the persistent application data directory before dropping privileges.
mkdir -p /app/data
chown -R appuser:appuser /app/data

# Pass the original Docker CMD to a non-root shell. The explicit $0 keeps
# the first CMD argument (python) from being consumed as the shell name.
exec su appuser -s /bin/sh -c 'exec "$@"' sh "$@"
