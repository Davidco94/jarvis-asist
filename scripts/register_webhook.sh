#!/usr/bin/env bash
# Register the Telegram webhook with the secret token.
# Reads TELEGRAM_BOT_TOKEN, TELEGRAM_WEBHOOK_URL, TELEGRAM_WEBHOOK_SECRET from .env.

set -euo pipefail

if [ ! -f .env ]; then
    echo "error: .env not found. copy .env.example -> .env first." >&2
    exit 1
fi

# shellcheck disable=SC1091
set -a; . ./.env; set +a

: "${TELEGRAM_BOT_TOKEN:?TELEGRAM_BOT_TOKEN must be set}"
: "${TELEGRAM_WEBHOOK_URL:?TELEGRAM_WEBHOOK_URL must be set}"
: "${TELEGRAM_WEBHOOK_SECRET:?TELEGRAM_WEBHOOK_SECRET must be set}"

echo "Registering webhook: ${TELEGRAM_WEBHOOK_URL}"

curl --fail --silent --show-error \
    "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook" \
    -d "url=${TELEGRAM_WEBHOOK_URL}" \
    -d "secret_token=${TELEGRAM_WEBHOOK_SECRET}" \
    -d "allowed_updates=[\"message\"]" \
    -d "drop_pending_updates=true" \
    | python3 -m json.tool
