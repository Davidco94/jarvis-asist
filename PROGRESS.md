# Jarvis — Progress Log

> **Authoritative spec:** [docs/PRODUCT_SPEC.md](docs/PRODUCT_SPEC.md) and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
> This file tracks what's actually shipped, what's pending, and what's blocked.
> Update as work lands. Keep it terse.

## Status snapshot

| Phase | State | Started | Closed |
|-------|-------|---------|--------|
| **Phase 0** — Foundation Infrastructure | 🟢 Deployed; E2E verified on prod | 2026-04-29 | 2026-04-30 |
| Phase 1 — Calendar Agent | 🟡 Decisions locked (OAuth mode = weekly re-auth; LLM = Gemini 2.5 Flash free) — spec revised, ready to slice | 2026-05-17 | — |
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

## Spec revisions (pre-Phase-1, 2026-05-17)

Two operator decisions taken on 2026-04-30 landed in the docs today:

| # | Concern | Where it landed |
|---|---------|-----------------|
| 11 | OAuth refresh-token expiry policy → option (c) weekly re-auth ritual | New [docs/decisions/oauth-mode.md](docs/decisions/oauth-mode.md); referenced from SPEC US-1.2 |
| 12 | LLM provider swap: Anthropic prepay → free Gemini 2.5 Flash primary + Groq trivial | New [docs/decisions/llm-provider.md](docs/decisions/llm-provider.md); ARCH §2 diagram, §4.2, ADR-005, §6 Phase 1/2, §7.3 cost table, §8, §10, §11; SPEC US-1.1, US-1.4, US-1.5, US-1.11, US-1.12, US-1.14, US-1.16 |

---

## Phase 0 — Foundation Infrastructure

> **Definition of Done:** Send Telegram message → bot echoes within 5s, deployed on Hetzner, allowlisted, deduplicated, fully logged, no AI. `/start`, `/help`, `/ping` work without invoking the (future) agent.

**Current state:** ✅ **Definition of Done met.** Stack live at `https://jarvis.dave-ail.cc`. All four interaction patterns verified end-to-end from Telegram on 2026-04-30 (`/ping`, `/help`, `/start`, plain-text echo).

**Production stack:**
- Host: Hetzner CX23, Helsinki, Ubuntu 24.04, IPv4 `62.238.28.161`
- Domain: `jarvis.dave-ail.cc` (Cloudflare DNS-only, gray cloud)
- Containers: `api`, `worker`, `redis`, `postgres`, `caddy` (all running, all healthcheck-passing)
- TLS: Let's Encrypt (auto-renewing via Caddy)
- Hardening: UFW (22/80/443), fail2ban, key-only SSH, password auth disabled, unattended-upgrades

### Stories

| ID | Story | State | Files / notes |
|----|-------|-------|---------------|
| US-0.1 | Project skeleton | 🟢 | [`pyproject.toml`](pyproject.toml), [`.gitignore`](.gitignore), [`.pre-commit-config.yaml`](.pre-commit-config.yaml), [`README.md`](README.md), full `src/jarvis/` tree |
| US-0.2 | Local dev environment | 🟢 | [`docker-compose.yml`](docker-compose.yml) + [`docker-compose.prod.yml`](docker-compose.prod.yml) + [`Dockerfile`](docker/Dockerfile) + [`Caddyfile`](docker/Caddyfile) + [`Makefile`](Makefile) + [`.env.example`](.env.example) |
| US-0.3 | Telegram bot registration | 🟢 | Bot live; webhook registered at `https://jarvis.dave-ail.cc/webhooks/telegram`; runbook at [`docs/runbooks/bot-registration.md`](docs/runbooks/bot-registration.md) |
| US-0.4 | FastAPI webhook + `/health` | 🟢 | [`src/jarvis/api/webhooks.py`](src/jarvis/api/webhooks.py), [`src/jarvis/api/health.py`](src/jarvis/api/health.py), [`src/jarvis/api/main.py`](src/jarvis/api/main.py) |
| US-0.5 | Idempotency layer | 🟢 | [`src/jarvis/core/idempotency.py`](src/jarvis/core/idempotency.py) — Redis `SET NX EX 86400` |
| US-0.6 | Allowlist middleware | 🟢 | [`src/jarvis/core/security.py`](src/jarvis/core/security.py) — silent drop, no info leak |
| US-0.7 | Async task queue | 🟢 | [`src/jarvis/workers/celery_app.py`](src/jarvis/workers/celery_app.py) — `acks_late=True`, `reject_on_worker_lost=True`, time limits, retry backoff |
| US-0.8 | Structured logging | 🟢 | [`src/jarvis/core/logging.py`](src/jarvis/core/logging.py) — JSON in prod / pretty in dev, PII redaction by default, `correlation_id` propagation |
| US-0.9 | Echo worker (no AI) | 🟢 | [`src/jarvis/workers/tasks.py`](src/jarvis/workers/tasks.py) — 2s sleep + echo, retries on send failure |
| US-0.10 | Hetzner deployment | 🟢 | CX23 Helsinki + Cloudflare DNS + Let's Encrypt all up; runbook at [`docs/runbooks/deploy-hetzner.md`](docs/runbooks/deploy-hetzner.md) |
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
| External HTTPS `/health` (prod) | ✅ `{"status":"ok","redis":true}` | `curl https://jarvis.dave-ail.cc/health` |
| Telegram `getWebhookInfo` (prod) | ✅ `pending_update_count: 0`, IP correct | manual |
| End-to-end Telegram round-trip (prod) | ✅ `/ping`, `/help`, `/start`, plain echo all working | manual, 2026-04-30 |

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

| Decision / blocker | Owner | Phase it gates | Source | Status |
|---|---|---|---|---|
| ~~OAuth-mode decision~~ | Operator | Phase 1 | SPEC US-1.2 | ✅ Locked 2026-04-30 — weekly re-auth (docs/decisions/oauth-mode.md) |
| ~~Anthropic API key + prepaid credits~~ | Operator | Phase 1 | SPEC US-1.1 | ✅ Superseded 2026-05-17 — Gemini 2.5 Flash free tier (docs/decisions/llm-provider.md) |
| Google AI Studio API key (Gemini free) | Operator | Phase 1 | SPEC US-1.1 | ⚪ TODO (operator to obtain) |
| Groq API key (free) | Operator | Phase 1 | SPEC US-1.1 | ⚪ TODO (operator to obtain) |
| GCP project + OAuth client for Calendar | Operator | Phase 1 | SPEC US-1.2 | ⚪ TODO (operator to provision) |
| ~~Domain name + Hetzner VM + DNS A record~~ | Operator | Phase 0 close (US-0.10) | SPEC US-0.10 | ✅ Done 2026-04-30 |
| Embedding provider lock (Voyage vs OpenAI) — affects `EMBEDDING_DIM` migration | Operator | Phase 2 | SPEC §6 Q3 | ⚪ Phase 2 |
| Eval threshold confirmation (85% suggested) | Operator | Phase 1 close | SPEC §6 Q4 | ⚪ Phase 1 close |

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

### 2026-05-17 — Phase 1 unblocked: OAuth + LLM decisions locked, spec revised

- **OAuth mode locked:** option (c) weekly re-auth ritual. Operator runs `scripts/authorize_google.py` each Monday. Decision recorded in `docs/decisions/oauth-mode.md`. Reason: paid Workspace busts the 50 NIS/mo budget; verification is wrong disclosure surface for a single-user system.
- **LLM provider locked:** Gemini 2.5 Flash (AI Studio free tier) primary; Groq Llama 3.3 70B Versatile for trivial English-only routing. Decision recorded in `docs/decisions/llm-provider.md`. Hebrew was the deciding factor — Llama 3.3 isn't officially trained on it. Paid Tier 1 Gemini documented as one-env-var swap when justified.
- **Spec docs revised:**
  - `docs/PRODUCT_SPEC.md`: US-1.1 (LLM setup + RPD/TPM guards), US-1.4 (multi-provider schema), US-1.5 (LLMs + no streaming + Hebrew pinning), US-1.11 (LLM-resolved dates wording), US-1.12 (Hebrew routing assertion + paid-swap trigger), US-1.14 (Gemini Flash as judge), US-1.16 (Gemini context caching).
  - `docs/ARCHITECTURE.md`: §2 diagram bottom-row, §4.2 AI stack table, ADR-005 rewritten, §6 Phase 0/1/2 component lists, §7.3 cost table + enforcement, §8 llm_router.py annotation, §10 failure modes (Gemini API down + quota cut), §11 references.
- No code yet. Next: Phase 1 slicing plan.

### 2026-04-30 — Phase 0 closed (production deploy + E2E)

- GitHub repo created at [Davidco94/jarvis-asist](https://github.com/Davidco94/jarvis-asist); main pushed.
- Hetzner CX23 provisioned in Helsinki; Ubuntu 24.04, IPv4 `62.238.28.161`.
- Cloudflare DNS A record `jarvis.dave-ail.cc` → server IP, **DNS-only mode** (gray cloud) so Caddy could complete LE HTTP-01 challenge.
- Server hardened: UFW (22/80/443 only), fail2ban, key-only SSH, password auth disabled, unattended-upgrades.
- Two Dockerfile fixes pushed during deploy:
  - `python:3.12-slim` → `python:3.12-slim-bookworm` (Trixie sync gap on `deb.debian.org` was returning 404 for `linux-libc-dev`).
  - `COPY pyproject.toml README.md ./` (hatchling validates the README at build time).
- One compose fix pushed: `env_file: [.env]` on the `caddy` service so `{$DOMAIN}` in the Caddyfile gets substituted.
- All 5 containers running and healthy; Let's Encrypt cert obtained on first start.
- Telegram webhook registered; `getWebhookInfo` confirms.
- E2E verified from operator's Telegram: `/ping`, `/help`, `/start`, plain-text echo all working.
- US-0.3 and US-0.10 closed.

### 2026-04-29 — Phase 0 scaffold

- Revised both spec docs with 10 plan-level fixes (see *Spec revisions* table above).
- Built US-0.1 through US-0.9, US-0.11, and new US-0.12 end-to-end.
- All 28 unit tests pass; ruff + mypy --strict clean.
- US-0.3 and US-0.10 documented as runbooks; remaining steps required operator hardware/identity.
- `CLAUDE.md` written at repo root with load-bearing rules (single-agent, plugin pattern, dependency direction, no-PII default).
