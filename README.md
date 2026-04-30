# Jarvis

Personal AI assistant. Telegram-first, single-agent + tool registry, deployed on a single Hetzner box.

See `PRODUCT_SPEC.md` and `ARCHITECTURE.md` (in `docs/`) for the full design.

## Status

**Phase 0 — Foundation Infrastructure.** No AI yet. The bot echoes messages, with idempotency, allowlist, structured logs, and slash-command handling.

## Quick start (local dev)

Requires Docker, `uv` (https://docs.astral.sh/uv/), and a Telegram bot token.

```bash
# 1. Clone and install
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
pre-commit install

# 2. Configure
cp .env.example .env
# edit .env: set TELEGRAM_BOT_TOKEN, TELEGRAM_WEBHOOK_SECRET, ALLOWED_TELEGRAM_USER_IDS

# 3. Bring up the stack
make up
make logs        # tail logs

# 4. Expose webhook (dev: ngrok)
ngrok http 8000
# copy the https URL into TELEGRAM_WEBHOOK_URL in .env, then:
make register-webhook

# 5. Send a Telegram message; you should get an echo within 5s.
```

## Project layout

```
src/jarvis/
├── api/           # FastAPI app (HTTP layer — thin)
├── workers/       # Celery tasks (orchestration)
├── agents/        # LangGraph (Phase 1)
├── tools/         # Tool registry + handlers
├── memory/        # Memory layer (Phase 2)
├── integrations/  # External clients (Telegram, Anthropic, Google)
├── core/          # Settings, logging, exceptions, security
└── db/            # SQLAlchemy + Alembic
tests/             # unit + integration
docker/            # Dockerfile + Caddyfile
docs/              # PRODUCT_SPEC, ARCHITECTURE, runbooks, decisions
scripts/           # one-shot ops scripts
```

## Make targets

| Target | What |
|--------|------|
| `make up` | Dev stack (api + worker + redis + postgres) |
| `make down` | Stop all |
| `make logs` | Tail all services |
| `make prod-up` | Dev + Caddy overlay |
| `make test` | Run pytest |
| `make lint` | ruff + mypy |
| `make register-webhook` | Set Telegram webhook URL |

## Architectural rules

These are load-bearing — see `docs/ARCHITECTURE.md` §1, §8.

- One agent, many tools. No supervisor pattern.
- Stateless API, stateful workers.
- Tools and slash-commands are plugins — register on import, never edit the dispatcher.
- Async on the hot path. No sync I/O in webhook handlers or agent nodes.
- Dependency direction: `api → workers → agents → tools → integrations → core`. No reverse arrows.
