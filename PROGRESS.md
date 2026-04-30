# Jarvis — Progress Log

> **Authoritative spec:** [docs/PRODUCT_SPEC.md](docs/PRODUCT_SPEC.md) and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
> This file tracks what's actually shipped, what's pending, and what's blocked.
> Update as work lands. Keep it terse.

## Status snapshot

| Phase | State | Started | Closed |
|-------|-------|---------|--------|
| **Phase 0** — Foundation Infrastructure | 🟢 Built locally; deploy pending | 2026-04-29 | — |
| Phase 1 — Calendar Agent | ⚪ Not started | — | — |
| Phase 2 — Memory Layer | ⚪ Not started | — | — |
| Phase 3 — Email Agent | ⚪ Not started | — | — |
| Phase 4+ | ⚪ Not started | — | — |

Legend: 🟢 done · 🟡 in progress · 🟠 blocked · ⚪ not started · 🔵 partially done

---

## Spec revisions (pre-build, 2026-04-29)

Before scaffolding, we revised both spec docs to address 10 gaps. Each is reflected in the latest `docs/PRODUCT_SPEC.md` / `docs/ARCHITECTURE.md`.

| # | Concern | Where it landed |
|---|---------|-----------------|
| 1 | Slash-command short-circuit (bypass LLM for `/audit`, `/cost`, `/ping`, …) | ARCH §3 step 4a; SPEC new **US-0.12** |
| 2 | Per-tool-call idempotency (Celery `acks_late` retry safety) | ARCH §3 step 4f, §10; SPEC US-0.7, new **US-X.7** |
| 3 | Pick `gitleaks` (not `detect-secrets`) | ARCH §4.3; SPEC US-X.4 |
| 4 | Embedding dim from model, not hardcoded `1536` | ARCH §6 Phase 2; SPEC US-2.1 |
| 5 | Dev/prod compose split | ARCH §7.4; SPEC US-0.2 |
| 6 | `age` key location documented | ARCH ADR-007; SPEC US-X.4 |
| 7 | OAuth 7-day refresh-token caveat (Testing mode) | ARCH §10; SPEC US-1.2 |
| 8 | Hebrew dates: LLM resolution, not `dateparser` | SPEC US-1.11 |
| 9 | Cost cap clarified (LLM line vs total) | SPEC US-1.1 |
| 10 | Data retention / archival schema decided in Phase 0 | ARCH §10; SPEC new **US-X.8** |

---

## Phase 0 — Foundation Infrastructure

> **Definition of Done:** Send Telegram message → bot echoes within 5s, deployed on Hetzner, allowlisted, deduplicated, fully logged, no AI. `/start`, `/help`, `/ping` work without invoking the (future) agent.

**Current state:** All code shipped and tested locally. Deploy step (US-0.10) deferred — requires operator-owned VM + DNS.

### Stories

| ID | Story | State | Files / notes |
|----|-------|-------|---------------|
| US-0.1 | Project skeleton | 🟢 | [`pyproject.toml`](pyproject.toml), [`.gitignore`](.gitignore), [`.pre-commit-config.yaml`](.pre-commit-config.yaml), [`README.md`](README.md), full `src/jarvis/` tree |
| US-0.2 | Local dev environment | 🟢 | [`docker-compose.yml`](docker-compose.yml) + [`docker-compose.prod.yml`](docker-compose.prod.yml) + [`Dockerfile`](docker/Dockerfile) + [`Caddyfile`](docker/Caddyfile) + [`Makefile`](Makefile) + [`.env.example`](.env.example) |
| US-0.3 | Telegram bot registration | 🔵 | Runbook done at [`docs/runbooks/bot-registration.md`](docs/runbooks/bot-registration.md); operator must run BotFather steps |
| US-0.4 | FastAPI webhook + `/health` | 🟢 | [`src/jarvis/api/webhooks.py`](src/jarvis/api/webhooks.py), [`src/jarvis/api/health.py`](src/jarvis/api/health.py), [`src/jarvis/api/main.py`](src/jarvis/api/main.py) |
| US-0.5 | Idempotency layer | 🟢 | [`src/jarvis/core/idempotency.py`](src/jarvis/core/idempotency.py) — Redis `SET NX EX 86400` |
| US-0.6 | Allowlist middleware | 🟢 | [`src/jarvis/core/security.py`](src/jarvis/core/security.py) — silent drop, no info leak |
| US-0.7 | Async task queue | 🟢 | [`src/jarvis/workers/celery_app.py`](src/jarvis/workers/celery_app.py) — `acks_late=True`, `reject_on_worker_lost=True`, time limits, retry backoff |
| US-0.8 | Structured logging | 🟢 | [`src/jarvis/core/logging.py`](src/jarvis/core/logging.py) — JSON in prod / pretty in dev, PII redaction by default, `correlation_id` propagation |
| US-0.9 | Echo worker (no AI) | 🟢 | [`src/jarvis/workers/tasks.py`](src/jarvis/workers/tasks.py) — 2s sleep + echo, retries on send failure |
| US-0.10 | Hetzner deployment | 🟠 | Runbook ready at [`docs/runbooks/deploy-hetzner.md`](docs/runbooks/deploy-hetzner.md); blocked on operator VM + DNS |
| US-0.11 | Configuration management | 🟢 | [`src/jarvis/core/settings.py`](src/jarvis/core/settings.py) — pydantic-settings, `SecretStr`, `@lru_cache`, fail-fast on missing required |
| US-0.12 | Slash-command pre-handler **(new)** | 🟢 | [`src/jarvis/tools/commands.py`](src/jarvis/tools/commands.py) — registry pattern; `/start`, `/help`, `/ping` registered |

### Cross-cutting (Phase 0 scope)

| ID | Story | State | Notes |
|----|-------|-------|-------|
| US-X.4 | Secrets management | 🔵 | `gitleaks` wired in pre-commit; `sops`+`age` runbook **not yet** written (lands when first real secret is encrypted, before Phase 1) |
| US-X.6 | Prompt versioning | ⚪ | Phase 1 |
| US-X.7 | Tool-call idempotency | ⚪ | Phase 1 (when first side-effecting tool ships) |
| US-X.8 | Data retention & archival | ⚪ | Schema design lands with Phase 1 DB migrations; Beat job lands Phase 4 |

### Verification

| Gate | Result | Command |
|------|--------|---------|
| `ruff check` | ✅ All checks passed | `make lint` |
| `ruff format --check` | ✅ 32 files clean | `make lint` |
| `mypy --strict` | ✅ 23 source files, 0 errors | `make typecheck` |
| `pytest` | ✅ 28 passed, 1 deprecation warning | `make test` |
| End-to-end echo via Telegram | ⚪ Not yet — requires bot token + ngrok | manual |

### Test coverage (Phase 0)

| File | Tests | Covers |
|------|-------|--------|
| [`tests/unit/test_settings.py`](tests/unit/test_settings.py) | 4 | Required-field failure, CSV parsing, SecretStr non-leak, lru_cache |
| [`tests/unit/test_security.py`](tests/unit/test_security.py) | 5 | Allowlist match/block, secret token match/mismatch/missing |
| [`tests/unit/test_idempotency.py`](tests/unit/test_idempotency.py) | 4 | First-claim wins, duplicate loses, distinct updates independent, 24h TTL |
| [`tests/unit/test_commands.py`](tests/unit/test_commands.py) | 8 | Parse known/unknown/with-args/`@bot`, dispatch ping/help, duplicate registration |
| [`tests/unit/test_webhook.py`](tests/unit/test_webhook.py) | 7 | Bad/missing secret → 403, invalid payload → 422, blocked user → silent 200, happy path enqueues, dup → drop, non-text → ignored |

---

## What's blocking each next phase

| Decision / blocker | Owner | Phase it gates | Source |
|---|---|---|---|
| OAuth-mode decision (Workspace/Internal vs Verified vs weekly re-auth) | Operator | Phase 1 | SPEC US-1.2 |
| Anthropic API key + prepaid credits | Operator | Phase 1 | SPEC US-1.1 |
| Domain name + Hetzner VM + DNS A record | Operator | Phase 0 close (US-0.10) | SPEC US-0.10 |
| Embedding provider lock (Voyage vs OpenAI) — affects `EMBEDDING_DIM` migration | Operator | Phase 2 | SPEC §6 Q3 |
| Eval threshold confirmation (85% suggested) | Operator | Phase 1 close | SPEC §6 Q4 |

---

## Operational notes

### Local dev quick path

```bash
source .venv/bin/activate     # python 3.12
make test                     # 28 passing
make up                       # api + worker + redis + postgres
make logs                     # tail
```

### Tooling pinned

- Python 3.12 · uv 0.5.13 · ruff 0.8 · mypy 1.13
- FastAPI 0.115 · aiogram 3.13 · Celery 5.4 · SQLAlchemy 2.0 · Pydantic 2.10
- Redis 7-alpine · pgvector/pgvector:pg16 · Caddy 2-alpine

### Repository layout

```
src/jarvis/{api,workers,agents,tools,memory,integrations,core,db}/
tests/{unit,integration}/
docker/{Dockerfile,Caddyfile}
docs/{PRODUCT_SPEC,ARCHITECTURE}.md  +  docs/{runbooks,decisions}/
scripts/register_webhook.sh
prompts/                              # Phase 1+
```

---

## Changelog

### 2026-04-29 — Phase 0 scaffold

- Revised both spec docs with 10 plan-level fixes (see *Spec revisions* table above).
- Built US-0.1 through US-0.9, US-0.11, and new US-0.12 end-to-end.
- All 28 unit tests pass; ruff + mypy --strict clean.
- US-0.3 and US-0.10 documented as runbooks; remaining steps require operator hardware/identity.
- `CLAUDE.md` written at repo root with load-bearing rules (single-agent, plugin pattern, dependency direction, no-PII default).
