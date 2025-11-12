#!/bin/sh
set -e

# Copy .env from env_file if not exists
if [ ! -f "/var/www/html/.env" ]; then
  echo "Creating .env from environment variables..."
  printenv | grep -E '^(APP_|DB_|PASSPORT_|REDIS_)' > /var/www/html/.env
fi

# Run original command
exec "$@"