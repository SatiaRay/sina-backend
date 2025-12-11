#!/bin/sh
set -e

SECRET_FILE="/secrets/${SERVICE_NAME}.env"

# Wait up to 30s for the file to exist
TIMEOUT=30
COUNTER=0
while [ ! -f "$SECRET_FILE" ]; do
    echo "Waiting for secret file '$SECRET_FILE'..."
    sleep 1
    COUNTER=$((COUNTER+1))
    if [ $COUNTER -ge $TIMEOUT ]; then
        echo "ERROR: Secret file '$SECRET_FILE' not found after $TIMEOUT seconds. Exiting."
        exit 1
    fi
done

set -a
. "$SECRET_FILE"
set +a

# Copy .env from env_file if not exists
if [ ! -f "/var/www/html/.env" ]; then
  echo "Creating .env from environment variables..."
  printenv | grep -E '^(APP_|DB_|PASSPORT_|REDIS_)' > /var/www/html/.env
fi

# Run original command
exec "$@"