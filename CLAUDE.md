# CLAUDE.md

Repo-specific instructions for Claude Code. Read before making changes.

## What this is

Jarvis — a personal AI assistant exposed over Telegram. Owner-operated single-user system. Currently in **Phase 0** (foundation infrastructure, no AI yet).

Authoritative design docs:
- `docs/PRODUCT_SPEC.md` — phases, user stories, acceptance criteria
- `docs/ARCHITECTURE.md` — stack, ADRs, module boundaries, failure modes

## Load-bearing rules

These are not suggestions. Violations should be caught in review.

1. **Single agent, many tools.** Do NOT introduce a supervisor / multi-agent pattern. New capabilities are new tools in `src/jarvis/tools/`, not new graphs.
2. **Plugin pattern, not switch statements.** Both slash-commands (`tools/commands.py`) and (Phase 1+) tools auto-register via decorators on import. Do not edit a central dispatcher to add a command/tool.
3. **Dependency direction is one-way:** `api → workers → agents → tools → integrations → core`. `core/` imports nothing from the project. `integrations/` imports only `core/`. No reverse arrows; no cross-layer reach-arounds.
4. **Webhook stays thin.** `POST /webhooks/telegram` must return 200 in <50 ms. Allowed work: secret check, payload validate, allowlist, idempotency SETNX, Celery `.delay()`. Anything heavier goes in the worker.
5. **Async everywhere on the hot path.** No `requests`, no sync DB drivers, no blocking sleeps. Use `httpx`, `asyncpg`/SQLAlchemy async, `redis.asyncio`.
6. **Tools that mutate external state require confirmation** (Phase 1+) **and tool-call-level idempotency** (`US-X.7`). Both are mandatory because Celery `acks_late=True` can re-deliver a partially-applied task.
7. **Slash-commands bypass the LLM.** They never call Anthropic, never trace to LangSmith, never count against token budgets. Phase 0 commands: `/start`, `/help`, `/ping`. Operational commands (`/audit`, `/cost`, `/forget`, `/memory dump`) all live here too.
8. **No PII in logs by default.** `LOG_PII=true` is the only opt-in. The `_redact_pii` processor in `core/logging.py` redacts `message_text`, `user_first_name`, etc.
9. **Settings come from `core/settings.py`.** Never read `os.environ` directly in app code. Use `get_settings()`.
10. **Cost is a constraint.** Every change touching the LLM path is reviewed against the 50 NIS/month ceiling. New providers/models must compare against ARCH §7.3.

## Project layout

```
src/jarvis/
├── api/           # FastAPI (HTTP layer, thin)
├── workers/       # Celery tasks (orchestration)
├── agents/        # LangGraph nodes (Phase 1)
├── tools/         # Tool + slash-command registry
├── memory/        # Memory layer (Phase 2)
├── integrations/  # Telegram, Anthropic, Google clients
├── core/          # settings, logging, security, idempotency, exceptions
└── db/            # SQLAlchemy + Alembic
tests/{unit,integration}
docker/             # Dockerfile, Caddyfile
docs/{runbooks,decisions}
scripts/            # one-shot ops
prompts/            # versioned LLM prompts (Phase 1+)
```

## Workflow

- `make up` / `make down` — dev stack (api + worker + redis + postgres, no Caddy)
- `make prod-up` — overlays Caddy + drops exposed ports + uses image source-of-truth
- `make test` — pytest (`tests/unit` runs without external services; `tests/integration` is gated by `-m integration`)
- `make lint` — ruff check + format check
- `make typecheck` — mypy `--strict` over `src/`
- Pre-commit hooks run ruff, mypy, gitleaks, basic file hygiene. **Do not bypass with `--no-verify`** unless explicitly told to.

## When adding a new slash-command

1. New file in `src/jarvis/tools/` (or extend an existing one).
2. Decorate with `@commands.register("name", "description")`.
3. Import-side-effect path: ensure the new module is imported by `src/jarvis/tools/__init__.py` so registration fires before the worker dispatches.
4. Add a unit test in `tests/unit/test_commands.py`.

## When adding a new Phase 1+ tool

(Not yet relevant — tracked here so it's captured.)

1. New module under `src/jarvis/tools/<domain>/<verb>.py`.
2. Subclass `BaseTool` (defined in Phase 1, US-1.4) and register via decorator.
3. If the tool mutates external state: set `requires_confirmation=True` AND wire idempotency per US-X.7.
4. Add an eval case in `evals/suites/<domain>.yaml` before merging.

## Things to NOT do

- Do not introduce sync HTTP clients (`requests`, `urllib3`).
- Do not introduce a "supervisor" agent or agent-to-agent messaging.
- Do not log message text without `LOG_PII=true`.
- Do not commit `.env`. `.env.example` is the only env file in git.
- Do not add a tool that mutates state without confirmation + idempotency.
- Do not return a non-2xx from the webhook unless the secret is wrong (silent drops keep Telegram from retrying forever).
- Do not disable `acks_late` to "fix" duplicates — fix idempotency instead.

## When in doubt

`docs/PRODUCT_SPEC.md` answers "what should this feature do?". `docs/ARCHITECTURE.md` answers "where does it live and why?". If those don't answer the question, ask the operator.
