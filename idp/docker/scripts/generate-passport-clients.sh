#!/bin/bash
set -euo pipefail

DONE_MARKER="/secrets/done"

DONE_LARAVEL_PERSONAL="/secrets/done-laravel-personal"

php artisan vendor:publish --tag=passport-config

# ------------------------------------------------------------------
# Wait for MySQL
# ------------------------------------------------------------------
echo "Waiting for MySQL to be ready..."
/usr/local/bin/wait-for-it.sh idp-mysql:3307 --timeout=60 --strict -- \
    echo "MySQL is up!"

# ------------------------------------------------------------------
# Run Laravel migrations (
# ------------------------------------------------------------------
echo "Running migrations..."
php artisan migrate --force

# ------------------------------------------------------------------
# Create the official "Laravel" Personal Access Client – only once
# ------------------------------------------------------------------
if [ ! -f "$DONE_LARAVEL_PERSONAL" ]; then
    echo "Creating static Personal Access Client 'Laravel' (one-time setup)..."

    # This command is silent when the client already exists → that's fine
    php artisan passport:client --personal --name="Laravel"  --provider="users" --no-interaction > /dev/null 2>&1 || true

    echo "Static Personal Access Client 'Laravel' created (or already exists)"
    touch "$DONE_LARAVEL_PERSONAL"
else
    echo "Static Personal Access Client 'Laravel' already created – skipping."
fi

# ------------------------------------------------------------------
# Skip if already done (idempotent)
# ------------------------------------------------------------------
if [ -f "$DONE_MARKER" ]; then
  echo "Passport clients already generated – skipping."
  exit 0
fi

# ------------------------------------------------------------------
# Read client names from SERVICE_CLIENTS env var
# Supports comma-separated, newline-separated, or both
# ------------------------------------------------------------------
IFS=',' read -ra CLIENTS <<< "$(echo "$SERVICE_CLIENTS" | tr '\n' ',' | tr -s ' ')"
CLIENTS=($(echo "$SERVICE_CLIENTS" | tr ',' '\n' | awk NF))  # clean whitespace

if [ ${#CLIENTS[@]} -eq 0 ]; then
  echo "No clients defined in SERVICE_CLIENTS – nothing to do."
  touch "$DONE_MARKER"
  exit 0
fi

# ------------------------------------------------------------------
# Create Personal Access Clients (one per name)
# ------------------------------------------------------------------
for NAME in "${CLIENTS[@]}"; do
    NAME=$(echo "$NAME" | xargs)
    echo -n "Creating client for '$NAME' ... "

    OUTPUT=$(php artisan passport:client --client --name="$NAME" --no-interaction 2>&1)

    CLIENT_ID=$(echo "$OUTPUT" \
      | grep -E "Client ID" \
      | sed 's/.*Client ID[^0-9a-zA-Z-]*//' )

    CLIENT_SECRET=$(echo "$OUTPUT" \
      | grep -E "Client Secret" \
      | sed 's/.*Client Secret[^0-9a-zA-Z]*//' )

    if [[ -z "$CLIENT_ID" || -z "$CLIENT_SECRET" ]]; then
        echo "FAILED"
        echo "$OUTPUT"
        exit 1
    fi

    cat > "/secrets/${NAME}.env" <<EOF
OAUTH_CLIENT_ID=$CLIENT_ID
OAUTH_CLIENT_SECRET=$CLIENT_SECRET
EOF

    echo "OK (ID: $CLIENT_ID)"
done

touch "$DONE_MARKER"
echo "All Passport clients generated successfully!"