#!/bin/bash
set -euo pipefail

DONE_MARKER="/secrets/done"

if [ -f "$DONE_MARKER" ]; then
  echo "Passport clients already generated – skipping."
  exit 0
fi

echo "Waiting for MySQL to be ready..."
/usr/local/bin/wait-for-it.sh idp-mysql:3307 --timeout=60 --strict -- \
    echo "MySQL is up!"

echo "Running migrations..."
php artisan migrate

# Read the list from environment variable (comma or newline separated)
IFS=',' read -ra CLIENTS <<< "$(echo "$PASSPORT_CLIENTS" | tr '\n' ',' | tr -s ' ')"
CLIENTS=($(echo "$PASSPORT_CLIENTS" | tr ',' '\n' | awk NF))  # clean whitespace

if [ ${#CLIENTS[@]} -eq 0 ]; then
  echo "No clients defined in PASSPORT_CLIENTS – nothing to do."
  touch "$DONE_MARKER"
  exit 0
fi

for NAME in "${CLIENTS[@]}"; do
    NAME=$(echo "$NAME" | xargs)
    echo -n "Creating client for '$NAME' ... "

    # ← ADD --no-interaction (or -n) HERE
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
PASSPORT_CLIENT_ID=$CLIENT_ID
PASSPORT_CLIENT_SECRET=$CLIENT_SECRET
EOF

    echo "OK (ID: $CLIENT_ID)"
done

touch "$DONE_MARKER"
echo "All Passport clients generated successfully!"