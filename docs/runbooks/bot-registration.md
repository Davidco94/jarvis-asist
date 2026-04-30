# Telegram Bot Registration (US-0.3)

One-time setup. Re-run only when migrating to a new bot identity.

## 1. Create the bot

1. Open Telegram, message **@BotFather**.
2. `/newbot`. Pick a name (display) and a unique `@username` ending in `bot`.
3. BotFather replies with a **token** like `123456789:AAH...`. Paste it into `.env` as `TELEGRAM_BOT_TOKEN`.

## 2. Set commands list

In BotFather: `/setcommands` → select your bot → paste:

```
start - Welcome message
help - List available commands
ping - Liveness check
```

## 3. Generate the webhook secret

```bash
openssl rand -hex 32
```

Paste into `.env` as `TELEGRAM_WEBHOOK_SECRET`. This value never leaves the server; Telegram echoes it back in the `X-Telegram-Bot-Api-Secret-Token` header on every webhook delivery.

## 4. Find your user ID

Message **@userinfobot** in Telegram. Copy the numeric ID into `.env` as `ALLOWED_TELEGRAM_USER_IDS=<your-id>`. Anyone not in this list gets silently dropped.

## 5. Register the webhook

After bringing the stack up and exposing port 8000 publicly (ngrok in dev, Caddy in prod):

```bash
# .env must have TELEGRAM_WEBHOOK_URL set, e.g. https://yourdomain.dev/webhooks/telegram
make register-webhook
```

The script calls `setWebhook` with `secret_token` and `allowed_updates=["message"]` (Phase 0 ignores everything else).

## 6. Re-registering on a new server

1. SSH to old server: `curl https://api.telegram.org/bot<TOKEN>/deleteWebhook`.
2. Update `TELEGRAM_WEBHOOK_URL` in new server's `.env`.
3. Run `make register-webhook` on the new server.

Telegram only delivers to one URL per bot — last `setWebhook` wins.

## 7. Sanity check

```bash
curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo
```

Should show your URL, `has_custom_certificate: false`, and `pending_update_count: 0`.
