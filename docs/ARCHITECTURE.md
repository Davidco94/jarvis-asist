# Jarvis - Technical Architecture & Stack

> **Companion document to:** `PRODUCT_SPEC.md`
> **Status:** Draft v1.0
> **Last updated:** 2026-04-29

---

## 1. Architectural Principles

These principles drive every technical decision in this project. When in doubt, defer to them.

1. **Single agent, many tools.** No supervisor pattern. No agent-to-agent messaging. The LLM is one orchestrator that calls registered tools.
2. **Stateless API, stateful workers.** The webhook handler holds no state. State lives in Postgres (durable) and Redis (ephemeral).
3. **Tools are plugins.** Adding a capability = adding a file in `tools/`. The graph never changes.
4. **Async everywhere on the hot path.** No synchronous I/O in webhook handlers or agent nodes.
5. **Fail loudly, degrade gracefully.** Errors surface to logs/Sentry; user-facing failures return helpful messages, never silent.
6. **Cost is a constraint, not an afterthought.** Every architectural choice is evaluated against the 50 NIS/month ceiling.
7. **Reversibility before optimization.** Choose simple, replaceable components first. Optimize only with measurements in hand.
8. **Production-grade from day zero.** No "we'll add tests/logging/security later." Phase 0 ships with all of these.

---

## 2. High-Level System Architecture

```
                              ┌────────────────────┐
                              │   Telegram User    │
                              │   (operator only)  │
                              └─────────┬──────────┘
                                        │ HTTPS
                                        ▼
                              ┌────────────────────┐
                              │  Telegram Servers  │
                              └─────────┬──────────┘
                                        │ webhook POST
                                        ▼
┌────────────────────────────────────────────────────────────────────┐
│                       Hetzner CAX11 (ARM, 4GB)                     │
│                                                                    │
│  ┌──────────────────┐                                              │
│  │      Caddy       │  TLS termination, automatic Let's Encrypt    │
│  │  reverse proxy   │  HTTP→HTTPS redirect                         │
│  └────────┬─────────┘                                              │
│           │                                                        │
│           ▼                                                        │
│  ┌──────────────────┐    ┌─────────────────────────────────────┐   │
│  │   FastAPI app    │───►│  Redis (queue + cache + idempotency)│   │
│  │   - aiogram v3   │    │  - Celery broker                    │   │
│  │   - allowlist    │    │  - dedup keys (24h TTL)             │   │
│  │   - signature    │    │  - short-term memory cache          │   │
│  │   - returns 200  │    │  - confirmation pending state       │   │
│  └──────────────────┘    └──────────────┬──────────────────────┘   │
│                                         │                          │
│                                         ▼                          │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    Celery Worker(s)                          │  │
│  │                                                              │  │
│  │  ┌──────────────────────────────────────────────────────┐    │  │
│  │  │              LangGraph Single Agent                  │    │  │
│  │  │                                                      │    │  │
│  │  │  load_context → agent ⇄ tool_executor → respond     │    │  │
│  │  │                  ▲                                   │    │  │
│  │  │                  │ uses                              │    │  │
│  │  │  ┌───────────────┴────────────────┐                  │    │  │
│  │  │  │       Tool Registry            │                  │    │  │
│  │  │  │   (auto-registered plugins)    │                  │    │  │
│  │  │  └─────┬──────────────┬───────────┘                  │    │  │
│  │  │        │              │                              │    │  │
│  │  └────────┼──────────────┼──────────────────────────────┘    │  │
│  │           │              │                                   │  │
│  │           ▼              ▼                                   │  │
│  │  ┌─────────────┐  ┌─────────────┐                            │  │
│  │  │  Calendar   │  │    Gmail    │  ... future tools          │  │
│  │  │   tools     │  │    tools    │                            │  │
│  │  └──────┬──────┘  └──────┬──────┘                            │  │
│  └─────────┼────────────────┼──────────────────────────────────-┘  │
│            │                │                                      │
│            ▼                ▼                                      │
│  ┌──────────────────────────────────────────┐                      │
│  │  PostgreSQL 16 + pgvector                │                      │
│  │  - oauth_credentials (encrypted)         │                      │
│  │  - audit_log (append-only)               │                      │
│  │  - messages, semantic_facts (vector)     │                      │
│  │  - procedural_patterns                   │                      │
│  │  - langgraph checkpoints                 │                      │
│  └──────────────────────────────────────────┘                      │
└────────────────────────────────────────────────────────────────────┘
                │            │              │              │
                ▼            ▼              ▼              ▼
       ┌──────────────┐ ┌─────────┐ ┌──────────────┐ ┌───────────┐
       │ Anthropic API│ │  Groq   │ │Google APIs   │ │ LangSmith │
       │ Haiku/Sonnet │ │  Llama  │ │ Cal + Gmail  │ │ tracing   │
       └──────────────┘ └─────────┘ └──────────────┘ └───────────┘
```

---

## 3. Request Flow (Happy Path)

```
1. User sends message in Telegram
2. Telegram → POST /webhooks/telegram (with X-Telegram-Bot-Api-Secret-Token header)
3. FastAPI:
   a. Verify secret_token   → 403 if mismatch
   b. Parse Update          → 422 if invalid
   c. Allowlist check       → silent 200 if not allowed
   d. Idempotency check     → silent 200 if duplicate
   e. Enqueue Celery task   → return 200 OK (within 50ms)
4. Celery worker picks up task:
   a. **Slash-command short-circuit:** if message starts with `/` and matches a registered
      command (`/start`, `/help`, `/ping`, `/audit`, `/cost`, `/status`, `/forget`, `/memory`),
      handle directly, send response, exit. No LLM call, no LangSmith trace.
   b. Load conversation context from Redis (short-term)
   c. Load relevant facts from pgvector (long-term)
   d. Load procedural patterns from Postgres
   e. Compose prompt: system + memory + history + new message
   f. Invoke LangGraph agent
        - Agent decides: respond directly OR call tool(s)
        - If tool call → tool_executor runs handler → result back to agent
        - **Per-tool-call idempotency:** for side-effecting tools, compute
          `key = sha256(thread_id || tool_name || canonical_params)` and check Redis
          `SET NX EX 300`. On hit, reuse cached result instead of re-executing
          (guards against Celery `acks_late` retry of partially-applied tools).
        - If destructive tool → emit confirmation, save pending state, exit graph
        - Loop until agent emits final response
   g. Send response via Telegram Bot API
   h. Persist new messages to Redis + Postgres
   i. Trigger async fact extraction (separate task)
5. Done. Trace flushed to LangSmith.
```

---

## 4. Tech Stack

### 4.1 Core Stack

| Layer | Technology | Version | Rationale |
|-------|-----------|---------|-----------|
| Language | Python | 3.12+ | LangGraph/LangChain ecosystem, mature async, type hints |
| Package manager | `uv` | latest | 10-100x faster than pip; lockfile reproducibility |
| Web framework | FastAPI | 0.115+ | Async-native, Pydantic-integrated, auto-validation |
| Telegram lib | aiogram | 3.x | Modern, fully async, idiomatic for bots; cleaner than python-telegram-bot |
| Async tasks | Celery | 5.4+ | Industry standard; mature; well-documented retries |
| Message broker | Redis | 7.x | Doubles as cache and idempotency store; saves a service |
| Database | PostgreSQL | 16+ | + pgvector extension for embeddings; ACID; rich types |
| ORM / Migrations | SQLAlchemy 2.0 + Alembic | latest | Industry standard; async support; declarative migrations |
| Validation | Pydantic | 2.x | Required by FastAPI; runtime type safety |
| Settings | pydantic-settings | latest | Type-safe env var loading with validation |
| Logging | structlog | latest | Structured JSON logging; context propagation |
| HTTP client | httpx | latest | Async; full HTTP/2; replaces requests |
| Reverse proxy | Caddy | 2.x | Automatic Let's Encrypt; simpler than nginx |
| Containers | Docker + Compose | latest | Reproducible local + prod environments |

### 4.2 AI Stack

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| Agent framework | LangGraph | State-machine semantics, checkpointing, the de facto standard for tool-using agents |
| Primary LLM | Claude Haiku 4.5 | Best cost/quality ratio for tool-calling; strong Hebrew |
| Complex reasoning LLM | Claude Sonnet 4.7 | For multi-step planning, escalated complexity |
| Trivial routing LLM | Llama 3.3 70B via Groq (free tier) | Free; near-instant; sufficient for classification |
| Embeddings | Voyage AI `voyage-3-lite` | Cheap (~$0.02/M tokens), competitive quality |
| Tracing | LangSmith free tier | 5K traces/month sufficient for personal use |
| Eval | Custom + LLM-as-judge (Haiku) | Lightweight, version-controlled YAML cases |

### 4.3 Quality / Tooling

| Tool | Purpose |
|------|---------|
| ruff | Linting + formatting (replaces black, isort, flake8) |
| mypy | Static type checking (`--strict` mode) |
| pytest + pytest-asyncio | Unit + integration tests |
| hypothesis | Property-based testing for parsers |
| pre-commit | Git hooks for lint/types/secrets before commit |
| `gitleaks` | Pre-commit secret scanning (chosen over `detect-secrets`: single binary, faster, better default ruleset) |
| `tenacity` | Retry logic |
| `pybreaker` | Circuit breaker pattern |

### 4.4 Hosting & Ops

| Component | Choice | Cost (NIS/month) |
|-----------|--------|-----------------|
| VPS | Hetzner CAX11 (ARM, 2vCPU, 4GB RAM, 40GB SSD) | ~14 |
| TLS | Caddy + Let's Encrypt | 0 |
| Domain | Cloudflare or Namecheap (.dev or .me TLD) | ~3-5 (amortized) |
| Backups | Hetzner Storage Box BX11 OR Cloudflare R2 free tier | 0-5 |
| Error reporting | Sentry free tier OR self-hosted GlitchTip | 0 |
| Tracing | LangSmith free tier | 0 |

---

## 5. Architectural Decisions (Mini-ADRs)

### ADR-001: Single Agent with Tool Calling, Not Multi-Agent Supervisor
**Decision:** Use a single LangGraph agent with a tool registry, not a supervisor-and-specialists pattern.

**Reasoning:**
- For a single-user productivity assistant, multi-agent introduces orchestration complexity without proportional benefit.
- Modern Claude / GPT-4 class models route between 20+ tools reliably; supervisor pattern was a workaround for weaker models.
- One agent = one prompt to debug, one trace to read, one place to add tools.

**Reversibility:** Easy. Promote to multi-agent if >15 tools cause routing degradation in evals.

---

### ADR-002: Telegram, Not WhatsApp
**Decision:** Telegram Bot API.

**Reasoning:**
- Free; WhatsApp Business API charges per conversation.
- Instant setup; WhatsApp requires Meta Business verification.
- Better developer ergonomics (inline keyboards, file handling, voice).
- No per-message limits or template approvals.

**Reversibility:** Medium. Channel layer is decoupled; could add WhatsApp gateway later if business need emerges.

---

### ADR-003: Celery + Redis, Not Inline Async or Dramatiq/Arq
**Decision:** Celery with Redis broker for background tasks.

**Reasoning:**
- Industry-standard; transferable knowledge to senior roles.
- Mature retry, scheduling, monitoring ecosystem (Flower).
- Redis already required for cache/idempotency - no additional service.

**Trade-off:** Heavier than Arq/Dramatiq. Acceptable for stability + ecosystem.

**Reversibility:** Medium. Migrating to Arq/Dramatiq is a swap of decorators; tasks remain pure functions.

---

### ADR-004: pgvector, Not Pinecone/Weaviate
**Decision:** Use PostgreSQL + pgvector extension for vector storage.

**Reasoning:**
- Already running Postgres for relational data; no new service.
- Free; Pinecone starts at $70/month.
- HNSW index in pgvector ≥ 0.5 has competitive recall and latency for <1M vectors.
- Single-source-of-truth: relational + vector queries can join in one transaction.

**Reversibility:** Easy. Embedding pipeline is provider-agnostic; swap target store with adapter change.

---

### ADR-005: Anthropic Primary, Multi-Provider via Adapter
**Decision:** Claude Haiku 4.5 as default; Claude Sonnet for complex; Groq Llama for trivial. All hidden behind an `LLMRouter` interface.

**Reasoning:**
- Best Hebrew handling among major providers.
- Strong tool-calling reliability.
- Cost ramps gracefully (Haiku << Sonnet).
- Groq's free tier handles classification/routing without cost.

**Reversibility:** Easy. `LLMRouter` interface allows swapping providers per task type via config.

---

### ADR-006: aiogram 3, Not python-telegram-bot
**Decision:** aiogram 3 for Telegram client.

**Reasoning:**
- Pure async (matches FastAPI/Celery async-first stance).
- Modern API; better filter/router primitives for inline-keyboard callbacks.
- python-telegram-bot is more popular but has historical sync baggage.

**Reversibility:** Hard once handlers are written. Acceptable risk; both libraries are healthy.

---

### ADR-007: Sops + Age for Secrets, Not Vault
**Decision:** Encrypted `.env.production` committed to repo, decrypted at deploy time.

**Reasoning:**
- HashiCorp Vault / AWS Secrets Manager are overkill for single-user.
- `sops` + `age` allow secret-in-git workflow with strong encryption.
- Zero monthly cost; rotation = re-encrypt + push.

**Key management:**
- Production private key on host: `/root/.config/sops/age/keys.txt`, `chmod 600`, owned by root.
- Operator's local key: `~/.config/sops/age/keys.txt`, `chmod 600`.
- Both keys backed up to a password manager off-host. Loss of all copies = unrecoverable secrets.
- Public keys (`.age.pub`) committed to `docs/secrets.md` so anyone with the repo can re-encrypt.
- Rotation playbook: `scripts/rotate-secrets.sh` re-encrypts with current recipients list.

**Reversibility:** Easy. Migrate to Doppler / Infisical later if multi-machine deployment needed.

---

### ADR-008: Caddy, Not Nginx
**Decision:** Caddy as reverse proxy.

**Reasoning:**
- Automatic Let's Encrypt with zero config.
- Caddyfile is dramatically simpler than nginx.conf.
- Performance differences negligible at single-VPS scale.

---

## 6. Per-Phase Stack Integration Map

> What gets added in each phase. Use this to prevent scope creep.

### Phase 0: Foundation
**New components introduced:**
- Python project + uv + ruff + mypy + pre-commit
- FastAPI + aiogram (webhook only)
- Celery + Redis (idempotency + queue)
- PostgreSQL 16 + Alembic (no domain tables yet, just `schema_versions`)
- structlog
- Caddy + Let's Encrypt
- Docker Compose
- Hetzner CAX11 + UFW + fail2ban + unattended-upgrades

**Critical integration points:**
- Webhook → Idempotency check (Redis) → Allowlist (env config) → Enqueue (Celery)
- Worker → Echo handler → Telegram Bot API send

**NOT YET:** No LangGraph, no Anthropic, no Google APIs, no memory.

---

### Phase 1: Calendar Agent
**New components introduced:**
- LangGraph + LangChain core
- Anthropic SDK + Claude Haiku 4.5 + Sonnet 4.7 (Sonnet on-demand only)
- Groq SDK (Llama 3.3 free tier) for trivial routing
- LangSmith client
- google-auth + google-api-python-client + google-auth-oauthlib
- `cryptography.fernet` for OAuth token encryption
- `dateparser` for natural language date parsing
- `tenacity` for retries; `pybreaker` for circuit breakers
- Eval framework (custom Python + YAML)

**Critical integration points:**
- Worker → LangGraph agent → Tool Registry → Calendar tool → Google Calendar API (with circuit breaker)
- Agent → Confirmation flow → Redis pending state → Telegram inline keyboard → Callback handler → Resume action
- Every LLM call → traced via LangSmith
- Every tool execution → audit_log table

**Database tables added:**
- `oauth_credentials`
- `audit_log`
- `langgraph_checkpoints`

---

### Phase 2: Memory Layer
**New components introduced:**
- pgvector PostgreSQL extension
- Voyage AI client for embeddings
- Async fact-extraction worker (separate Celery task)

**Critical integration points:**
- After each turn → async task → Haiku call → extract facts → embed → upsert in `semantic_facts`
- Before each agent call → similarity search → top-K facts injected into system prompt
- `/forget` commands → audit-logged deletions

**Embedding dimension:** taken from the selected model at migration time, **not hardcoded**.
Voyage `voyage-3-lite` = 512; OpenAI `text-embedding-3-small` = 1536. The Alembic migration
reads `EMBEDDING_DIM` from settings; switching models requires a re-embed migration.

**Database tables added:**
- `messages`
- `semantic_facts` (with HNSW index, `vector(EMBEDDING_DIM)`)
- `procedural_patterns`

---

### Phase 3: Email Agent
**New components introduced:**
- Gmail API client (already authorized via existing GCP project, new scopes)
- HTML-to-text conversion (`html2text` or `beautifulsoup4`)

**Critical integration points:**
- New tools registered in same registry as calendar
- Send email tool uses double-confirmation pattern
- Memory layer can recall email-related facts (no new memory infra)

**Database tables added:**
- `email_send_log` (rate limiting + audit)

---

### Phase 4+: Future
- **Voice:** Whisper API + audio download from Telegram + cost monitoring
- **RAG over docs:** Reuse pgvector; new `documents` table; chunking strategy
- **Vision:** Claude vision API; image download from Telegram
- **Proactive:** Celery Beat for scheduled tasks (morning briefing, reminders)
- **CLI:** Click-based CLI hitting same FastAPI endpoints (Telegram becomes one of many channels)

---

## 7. Cross-Cutting Concerns

### 7.1 Security Layers

```
External attack surface:
┌─────────────────────────────────────────────────┐
│  L1: Network                                    │
│  - UFW: only :22 (SSH), :80, :443 open          │
│  - fail2ban on SSH                              │
│  - SSH: key-only, no root login                 │
│  - Unattended security upgrades                 │
├─────────────────────────────────────────────────┤
│  L2: Transport                                  │
│  - Caddy enforces HTTPS, HSTS, modern ciphers   │
│  - HTTP automatically redirects to HTTPS        │
├─────────────────────────────────────────────────┤
│  L3: Application                                │
│  - Telegram secret_token validates webhook src  │
│  - Allowlist of Telegram user_id                │
│  - Pydantic validates all inputs                │
│  - SQLAlchemy parameterized queries (no SQLi)   │
├─────────────────────────────────────────────────┤
│  L4: Data                                       │
│  - OAuth tokens encrypted at rest (Fernet)      │
│  - .env files chmod 600, owned by app user      │
│  - Postgres role with least privilege           │
│  - Audit log append-only (revoked DELETE perm)  │
├─────────────────────────────────────────────────┤
│  L5: Agent                                      │
│  - Destructive tools require confirmation       │
│  - Send-email rate limited                      │
│  - Tool scopes checked before execution         │
│  - Audit log of every action                    │
└─────────────────────────────────────────────────┘
```

### 7.2 Observability Stack

| Signal | Tool | Free tier sufficient? |
|--------|------|----------------------|
| Application logs | structlog → stdout → Docker | Yes |
| Agent traces | LangSmith | Yes (5K/month) |
| Errors / exceptions | Sentry | Yes (5K events/month) |
| Cost tracking | Custom (in `audit_log`) + daily summary task | N/A |
| Health | `/health` endpoint + uptime monitor (UptimeRobot free) | Yes |

**Correlation:** Every request tagged with `correlation_id = telegram_update_id`. Flows through logs, traces, and audit log.

### 7.3 Cost Control

```
Cost categories per month (NIS):
┌────────────────────────┬─────────┐
│ Hetzner CAX11          │   ~14   │
│ Domain (amortized)     │    ~4   │
│ Anthropic (Haiku+cache)│  15-20  │
│ Anthropic (Sonnet)     │   2-5   │
│ Voyage embeddings      │    ~1   │
│ Groq (free tier)       │     0   │
│ LangSmith (free)       │     0   │
│ Sentry (free)          │     0   │
│ Backups (R2 free)      │     0   │
├────────────────────────┼─────────┤
│ Total target           │  35-45  │
│ Budget                 │     50  │
└────────────────────────┴─────────┘
```

**Enforcement mechanisms:**
1. **Per-conversation cap:** 30K tokens; agent forced to summarize on approach.
2. **Prompt caching:** Anthropic prompt caching for system prompt + tool defs (~90% discount on cached portion).
3. **Tier routing:** Trivial tasks → Groq; standard → Haiku; complex → Sonnet.
4. **Daily monitor:** End-of-day Telegram message summarizing usage.
5. **Hard cap:** If MTD spend > 90% of budget, system pauses with operator alert.

### 7.4 Deployment Topology

**Single-server topology (all phases):**

```
Hetzner CAX11
├── Docker Compose stack
│   ├── caddy        (reverse proxy)              [prod overlay only]
│   ├── api          (FastAPI, 1 instance)
│   ├── worker       (Celery, 2 concurrency)
│   ├── beat         (Celery scheduler, Phase 4+)
│   ├── postgres     (with pgvector)
│   └── redis        (with AOF persistence)
└── Host services
    ├── ufw          (firewall)
    ├── fail2ban     (intrusion prevention)
    └── unattended-upgrades
```

**Two compose files, one stack:**
- `docker-compose.yml` — base / dev. Postgres + Redis ports exposed on localhost; source
  bind-mounts for hot reload; **no Caddy** (use ngrok or direct port for local Telegram testing).
- `docker-compose.prod.yml` — overlay. Adds `caddy`; removes exposed Postgres/Redis ports;
  removes source mounts; sets `restart: unless-stopped`. Deployed via
  `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build`.

**No load balancer, no multi-AZ, no autoscaling.** This is a single-user system.

**CI/CD:** Lightweight - GitHub Actions runs lint + tests + evals on PR. Manual deploy via SSH + `git pull` + `docker compose up -d --build`. (Can graduate to GitHub Actions deploy with SSH key in Phase 4+.)

---

## 8. Key Module Boundaries

```
src/jarvis/
│
├── api/                    # FastAPI app (HTTP layer only - thin)
│   ├── main.py
│   ├── webhooks.py         # /webhooks/telegram, /webhooks/oauth
│   └── health.py
│
├── workers/                # Celery tasks (orchestration)
│   ├── celery_app.py
│   ├── tasks.py            # process_telegram_update, extract_facts, etc.
│   └── beat_schedule.py    # Phase 4+
│
├── agents/                 # LangGraph definition + nodes
│   ├── graph.py
│   ├── nodes.py            # load_context, agent_node, tool_executor, respond
│   ├── state.py            # AgentState TypedDict
│   └── llm_router.py       # Haiku/Sonnet/Groq selection
│
├── tools/                  # Tool registry + handlers (the plugin system)
│   ├── registry.py
│   ├── base.py             # ToolDefinition, BaseTool
│   ├── calendar/
│   │   ├── list_events.py
│   │   ├── find_slots.py
│   │   ├── create_event.py
│   │   └── update_delete.py
│   └── email/              # Phase 3
│       ├── search.py
│       ├── read.py
│       ├── summarize.py
│       └── send.py
│
├── memory/                 # Phase 2
│   ├── manager.py          # MemoryManager (the public API)
│   ├── short_term.py       # Redis-backed
│   ├── semantic.py         # pgvector-backed
│   ├── procedural.py
│   └── extractor.py        # async fact extraction
│
├── integrations/           # External service clients
│   ├── telegram.py         # aiogram setup, send helpers
│   ├── anthropic_client.py
│   ├── groq_client.py
│   ├── google_oauth.py
│   ├── google_calendar.py
│   ├── google_gmail.py     # Phase 3
│   └── voyage_client.py    # Phase 2
│
├── core/                   # Cross-cutting infrastructure
│   ├── settings.py         # Pydantic Settings
│   ├── logging.py          # structlog config
│   ├── exceptions.py
│   ├── security.py         # encryption helpers, allowlist
│   └── circuit_breaker.py
│
├── db/                     # Persistence
│   ├── base.py
│   ├── session.py
│   ├── models/             # SQLAlchemy models
│   │   ├── audit.py
│   │   ├── oauth.py
│   │   ├── memory.py       # Phase 2
│   │   └── checkpoints.py
│   └── migrations/         # Alembic
│
└── evals/                  # Eval harness
    ├── runner.py
    ├── judge.py            # LLM-as-judge
    └── suites/
        ├── calendar.yaml
        ├── memory.yaml     # Phase 2
        └── email.yaml      # Phase 3
```

**Dependency direction (strict):**
```
api → workers → agents → tools → integrations → core
                  ↓
               memory (Phase 2+)
```
- `core/` depends on nothing else in the project.
- `integrations/` depends only on `core/`.
- `tools/` depends on `integrations/` and `core/`.
- No circular imports. No reaching across layers.

---

## 9. Testing Strategy

| Test type | Scope | Frameworks | When run |
|-----------|-------|-----------|----------|
| Unit | Pure functions, parsers, validators | pytest, hypothesis | Every commit (pre-commit) |
| Integration | DB, Redis, Celery in-process | pytest + testcontainers | PR, pre-deploy |
| Tool contract | Each tool with mocked external API | pytest + respx | PR |
| Evals | Agent behavior on golden prompts | Custom harness + LLM judge | Before phase completion + pre-deploy |
| Smoke | End-to-end Telegram → response | Manual + scripted | Post-deploy |

**Coverage target:** 70% line coverage. Quality > quantity - integration & evals matter more than unit %.

---

## 10. Failure Modes & Mitigations

| Failure | Symptom | Mitigation |
|---------|---------|-----------|
| Anthropic API down | Agent calls fail | Circuit breaker; user message: "AI offline, retry in 1 min" |
| Google API rate limit | Tool failures | Exponential backoff; user-visible degradation message |
| Worker crash mid-task | Task lost | Celery retry policy (3 attempts) + acks_late |
| Redis full | New requests rejected | Redis eviction policy `volatile-lru`; alert on usage > 80% |
| Postgres connection exhaustion | All queries fail | Connection pool sized + SQLAlchemy `pool_pre_ping=True` |
| OAuth token expired without refresh | Calendar/Gmail calls 401 | Auto-refresh; rotation persisted; alert if refresh fails |
| Webhook delivered while worker is down | Message lost | 200 OK from API ensures Telegram doesn't retry forever; queue persists in Redis with AOF |
| Cost spike | MTD spend exceeds budget | Daily monitor; auto-pause at 90% with alert |
| Hebrew prompt with weak model | Wrong tool called | Eval suite catches; tier router promotes Hebrew to Haiku/Sonnet |
| Worker retry of partially-applied destructive tool | Duplicate calendar event / sent email | Per-tool-call idempotency key in Redis (5 min TTL): hash of `thread_id+tool+params`; skip on hit |
| Unbounded growth of `messages`, `langgraph_checkpoints`, `audit_log` | Disk fills, queries slow | Beat job (Phase 4): archive `messages` >90d to object storage; prune `langgraph_checkpoints` >30d; partition `audit_log` monthly, never delete |
| OAuth refresh token expires after 7 days | Calendar/Gmail calls 401 with no recovery | App must be in "Internal" (Workspace) or fully verified before Phase 1 ships; otherwise weekly re-auth ritual is documented |

---

## 11. References & Reading

- LangGraph docs: https://langchain-ai.github.io/langgraph/
- aiogram 3 docs: https://docs.aiogram.dev/en/latest/
- Anthropic prompt caching: https://docs.claude.com/en/docs/build-with-claude/prompt-caching
- pgvector: https://github.com/pgvector/pgvector
- Twelve-Factor App: https://12factor.net/ (still relevant; informs config + logs)
- "Building effective agents" (Anthropic): https://www.anthropic.com/research/building-effective-agents
