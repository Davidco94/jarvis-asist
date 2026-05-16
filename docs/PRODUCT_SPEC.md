# Jarvis - Personal AI Assistant - Product Specification

> **Owner:** David
> **Status:** Draft v1.0
> **Last updated:** 2026-04-29

---

## 1. Vision & Goals

### 1.1 Vision
Build a personal AI assistant that lives alongside the user as a productivity partner - not a chatbot. The system is accessible through Telegram, executes real actions on the user's behalf (calendar, email, and beyond), and improves over time through persistent memory and learned preferences.

### 1.2 Core Principles
- **Action-oriented, not chat-oriented.** Default outcome of any interaction is an action taken or a decision made, not a conversation.
- **Plugin-based scalability.** New capabilities are added as registered tools, never by modifying the core graph.
- **Memory as first-class citizen.** The system distinguishes between working, episodic, semantic, and procedural memory.
- **Trust through transparency.** Every destructive action requires confirmation. Every action is logged.
- **Cost-disciplined.** Architectural decisions are evaluated against a 50 NIS/month operational ceiling.

### 1.3 Non-Goals (Explicit Out-of-Scope)
- ❌ Multi-tenant / multi-user system
- ❌ Multi-agent supervisor pattern (single agent + tool calling only)
- ❌ Custom LLM training or fine-tuning
- ❌ Native mobile app (Telegram is the interface)
- ❌ Web dashboard / GUI in v1
- ❌ Voice interface in Phase 1-3
- ❌ Image / document analysis in Phase 1-3
- ❌ RAG over personal documents in Phase 1-3
- ❌ Public exposure (single allowlisted user only)

---

## 2. Personas & Primary Use Cases

### 2.1 Persona: "The Operator" (David)
- Single user, owner-operator of the system
- Communicates in Hebrew and English
- Located in `Asia/Jerusalem`
- Expects 24/7 availability with sub-15s response latency
- Privacy-conscious; data stays on user-controlled infrastructure

### 2.2 Primary Use Cases (Phase 1-3)
| ID | Use Case | Phase |
|----|----------|-------|
| UC-1 | "What's on my calendar today/this week?" | 1 |
| UC-2 | "Find me a free 30-minute slot tomorrow afternoon" | 1 |
| UC-3 | "Schedule a haircut for next Tuesday at 5pm" | 1 |
| UC-4 | "Cancel my 3pm meeting on Thursday" | 1 |
| UC-5 | "Reschedule my dentist appointment to next week" | 1 |
| UC-6 | "What's in my inbox today?" | 3 |
| UC-7 | "Summarize the email from [sender]" | 3 |
| UC-8 | "Draft a reply to the latest email from my manager" | 3 |
| UC-9 | "Remember that I prefer morning meetings" (procedural) | 2 |
| UC-10 | "What did we decide about the trip to Greece?" (semantic recall) | 2 |

---

## 3. Roadmap Overview

| Phase | Name | Duration | Outcome |
|-------|------|----------|---------|
| **Phase 0** | Foundation Infrastructure | 1 week | Telegram echo bot, deployed, idempotent, allowlisted - **no AI yet** |
| **Phase 1** | Calendar Agent | 2 weeks | Functional calendar management with confirmations and eval harness |
| **Phase 2** | Memory Layer | 1 week | Short-term + long-term memory operational; personalization emerging |
| **Phase 3** | Email Agent | 1 week | Read, search, summarize, draft, send (with double confirmation) |
| **Phase 4+** | Future Capabilities | TBD | Voice, RAG, vision, proactive briefings, additional integrations |

**Hard rule:** Do not start Phase N+1 until Phase N's Definition of Done is met, including its evals passing at the agreed threshold.

---

## 4. Epics & User Stories

> **Story format:** Each story is atomic - completable in a single focused session (2-6 hours). Stories include explicit acceptance criteria. ID convention: `US-{phase}.{number}`.

---

### EPIC 0: Foundation Infrastructure

**Goal:** Establish a production-grade async pipeline that processes Telegram messages, before any AI logic exists. This phase de-risks all the non-AI complexity.

#### US-0.1: Project Skeleton
**As** the operator
**I want** a clean Python project skeleton with tooling configured
**So that** all subsequent work happens in a consistent, maintainable codebase.

**Acceptance Criteria:**
- [ ] Python 3.12 project with `pyproject.toml` (using `uv` or `poetry`)
- [ ] `ruff` configured for linting + formatting
- [ ] `mypy --strict` passes on empty project
- [ ] `pytest` configured with `pytest-asyncio`
- [ ] `pre-commit` hooks installed (ruff, mypy, secret detection)
- [ ] `.gitignore` includes `.env`, `*.pyc`, `__pycache__`, `.venv`
- [ ] `README.md` with quick-start instructions
- [ ] Repository structure:
  ```
  src/jarvis/
    api/          # FastAPI app
    workers/      # Celery workers
    agents/       # LangGraph (added in Phase 1)
    tools/        # Tool registry + implementations
    memory/       # Memory layer (Phase 2)
    integrations/ # External APIs (Calendar, Gmail, Telegram)
    core/         # Settings, logging, exceptions
    db/           # SQLAlchemy models, migrations
  tests/
  docker/
  ```

#### US-0.2: Local Development Environment
**As** the operator
**I want** a one-command local environment with all services
**So that** development is reproducible and matches production.

**Acceptance Criteria:**
- [ ] **Two compose files**: `docker-compose.yml` (base/dev — Postgres+Redis ports exposed on localhost, source bind-mounts for hot-reload, no Caddy) and `docker-compose.prod.yml` (overlay — adds `caddy`, removes exposed Postgres/Redis ports, removes source mounts, sets `restart: unless-stopped`).
- [ ] Dev services: `api`, `worker`, `redis`, `postgres`. Prod adds `caddy`.
- [ ] `make up` / `make down` / `make logs` commands work; `make prod-up` uses both compose files.
- [ ] PostgreSQL has pgvector extension preloaded
- [ ] Redis is configured with persistence (AOF)
- [ ] All services have healthchecks
- [ ] `.env.example` documents all required variables

#### US-0.3: Telegram Bot Registration
**As** the operator
**I want** a registered Telegram bot with webhook configured
**So that** the system can receive messages.

**Acceptance Criteria:**
- [ ] Bot created via @BotFather, token stored securely
- [ ] Bot has descriptive name, @username, and command list (`/start`, `/help`)
- [ ] Webhook URL set with **secret token** (Telegram's built-in `secret_token` parameter)
- [ ] Webhook validates the secret token on every incoming request
- [ ] Documentation of how to re-register webhook on a new server

#### US-0.4: FastAPI Webhook Endpoint
**As** the system
**I want** to receive Telegram updates via HTTP POST
**So that** messages enter the processing pipeline.

**Acceptance Criteria:**
- [ ] `POST /webhooks/telegram` endpoint exists
- [ ] Endpoint returns `200 OK` within 50ms (no processing in handler)
- [ ] Invalid `secret_token` returns `403`
- [ ] Request body is validated with Pydantic models matching Telegram's `Update` schema
- [ ] Endpoint logs structured event for every received update (with `update_id`)
- [ ] Health check endpoint at `/health` returns DB + Redis connectivity status

#### US-0.5: Idempotency Layer
**As** the system
**I want** to deduplicate webhook deliveries
**So that** retries from Telegram don't cause double-execution.

**Acceptance Criteria:**
- [ ] Before enqueueing, system checks Redis for `processed:{update_id}`
- [ ] Uses `SET NX EX 86400` pattern (atomic check-and-set, 24h TTL)
- [ ] Duplicate updates are silently dropped (still return 200)
- [ ] Duplicate detection is logged at INFO level
- [ ] Unit test verifies behavior under simulated double-delivery

#### US-0.6: Allowlist Middleware
**As** the operator
**I want** only my Telegram user_id to be processed
**So that** strangers cannot interact with my private assistant.

**Acceptance Criteria:**
- [ ] `ALLOWED_TELEGRAM_USER_IDS` is a configurable list (env var, comma-separated)
- [ ] Updates from non-allowlisted users are silently dropped
- [ ] Dropped attempts are logged at WARNING level with sender info
- [ ] No response is sent to non-allowlisted users (no information leak)
- [ ] Unit tests cover both allowed and blocked paths

#### US-0.7: Async Task Queue Setup
**As** the system
**I want** to process messages asynchronously
**So that** the webhook can return 200 OK instantly while processing happens in background.

**Acceptance Criteria:**
- [ ] Celery configured with Redis as broker and result backend
- [ ] At least one worker process consumes from the default queue
- [ ] Task definitions live in `src/jarvis/workers/tasks.py`
- [ ] Task `process_telegram_update` enqueued by webhook handler
- [ ] Tasks have explicit `time_limit` (60s) and `soft_time_limit` (45s)
- [ ] Failed tasks retry with exponential backoff (max 3 attempts)
- [ ] `acks_late=True` + `reject_on_worker_lost=True` so a crashed worker re-delivers; this implies tool-call-level idempotency is mandatory once tools exist (see US-X.7)
- [ ] Worker logs go to the same structured pipeline as API

#### US-0.8: Structured Logging
**As** the operator
**I want** all logs to be structured JSON
**So that** I can debug issues across services.

**Acceptance Criteria:**
- [ ] `structlog` configured for JSON output in production, pretty in dev
- [ ] Every log line includes: `timestamp`, `level`, `service` (api/worker), `event`, contextual fields
- [ ] `correlation_id` (= `update_id`) flows from webhook through worker logs
- [ ] No PII (message content, sender names) in logs by default - opt-in via `LOG_PII=true`
- [ ] Logs go to stdout (Docker captures them)

#### US-0.9: Echo Worker (No AI)
**As** the operator
**I want** the bot to echo my messages with a delay
**So that** I can validate the entire pipeline before adding AI.

**Acceptance Criteria:**
- [ ] Worker receives task, sleeps 2s (simulating LLM latency), echoes back
- [ ] Response is sent via Telegram Bot API as a text reply
- [ ] Worker logs each step with correlation_id
- [ ] Failure to send response triggers retry
- [ ] End-to-end test: send message → receive echo within 5s

#### US-0.10: Production Deployment to Hetzner
**As** the operator
**I want** the bot deployed to a public server with HTTPS
**So that** Telegram can reach the webhook.

**Acceptance Criteria:**
- [ ] Hetzner CAX11 VM provisioned (Ubuntu 24.04, ARM)
- [ ] SSH key-only authentication; password auth disabled
- [ ] UFW firewall: only ports 22, 80, 443 open
- [ ] `fail2ban` configured for SSH
- [ ] Unattended automatic security updates enabled
- [ ] Caddy installed as reverse proxy with automatic Let's Encrypt
- [ ] Domain (or subdomain) pointing to server
- [ ] Docker + Docker Compose installed
- [ ] App deployed, webhook registered with HTTPS URL
- [ ] Echo flow works end-to-end from production

#### US-0.11: Configuration Management
**As** the operator
**I want** a single source of truth for all configuration
**So that** environment variables are validated and typed.

**Acceptance Criteria:**
- [ ] `pydantic-settings` based `Settings` class
- [ ] All env vars are typed and documented
- [ ] Missing required vars cause startup failure with clear error
- [ ] Secrets are never logged (Pydantic `SecretStr` for tokens/keys)
- [ ] Settings cached with `@lru_cache`

#### US-0.12: Slash-Command Pre-Handler
**As** the operator
**I want** built-in commands to bypass the LLM agent
**So that** observability/admin commands work even if the LLM is offline and don't burn tokens.

**Acceptance Criteria:**
- [ ] Worker checks if message starts with `/` and matches a registered command **before** invoking the agent
- [ ] Phase 0 commands: `/start` (welcome message), `/help` (lists available commands), `/ping` (returns "pong" + server local time)
- [ ] Command registry is the same plugin pattern as the tool registry (single import-time decorator)
- [ ] Future commands plug in via the registry: `/audit` (Phase 1), `/cost` (Phase 1), `/status` (Phase 1), `/forget`, `/memory dump` (Phase 2)
- [ ] Unknown `/foo` falls through to the agent (which decides how to respond)
- [ ] Command handlers are async; failures return a friendly error and are logged at ERROR
- [ ] Slash-command responses bypass LangSmith tracing (no LLM call)
- [ ] Unit tests cover: registered command, unknown command, agent fallthrough, handler raising

**Definition of Done for Phase 0:**
> Send a Telegram message → bot echoes within 5s, deployed on Hetzner, accessible only by the operator, deduplicated, fully logged, with no AI involved. `/start`, `/help`, `/ping` work without invoking the (future) agent.

---

### EPIC 1: Calendar Agent

**Goal:** First real AI-powered capability. Establish the agent loop, tool registry pattern, and confirmation flows that all future capabilities will reuse.

#### US-1.1: LLM Provider Setup & Quota Monitoring
**Acceptance Criteria:**
- [ ] Google AI Studio free-tier API key for Gemini 2.5 Flash (no billing attached). See [docs/decisions/llm-provider.md](decisions/llm-provider.md) for the provider decision and paid-swap path.
- [ ] Groq free-tier API key for Llama 3.3 70B Versatile (trivial routing only, English-only).
- [ ] LangSmith API key configured if available; absent key is acceptable (US-1.15 graceful degradation).
- [ ] Local middleware logs token usage per request (input/output/cached).
- [ ] **Daily RPD guard (free tier):** Redis counter `gemini:rpd:{YYYY-MM-DD}` increments per Gemini call. At 200/day (80% of the ~250 RPD free cap), system sends Telegram self-alert. At 240/day, system pauses LLM-using tasks (slash commands still work). Resets at local midnight.
- [ ] **Daily TPM guard (Groq):** if any Groq call returns 429, mark Groq circuit open for 60s; trivial-route prompts fall back to Gemini.
- [ ] **MTD total cost cap = 50 NIS** (all line items, including infra). Tracked even at zero LLM spend; the cap exists so a paid swap (see decision doc) can't silently breach the ceiling. At 90% (45 NIS), system pauses with operator alert.

#### US-1.2: Google Cloud Project & Calendar API Enablement
**Acceptance Criteria:**
- [ ] GCP project created
- [ ] Google Calendar API enabled
- [ ] OAuth 2.0 client ID configured for "desktop application" type
- [ ] Scopes requested: `calendar.events` (write) + `calendar.readonly`
- [ ] Credentials JSON stored encrypted in repo (sops+age) or in secret manager
- [ ] **Refresh-token longevity decision (BLOCKER for US-1.3):** "External - Testing" mode invalidates refresh tokens after 7 days. Choose ONE before proceeding:
   - **(a) Internal app via Workspace** — preferred. Requires a Google Workspace account (~25 NIS/mo, busts the budget) OR using an existing Workspace identity if available. Tokens never expire.
   - **(b) Submit for verification** — free, takes 1–2 weeks, requires privacy policy URL + verified domain. Tokens never expire after approval.
   - **(c) Weekly re-auth ritual** — operator runs `scripts/authorize_google.py` every Monday. Documented in `docs/runbooks/oauth-reauth.md`. Acceptable for v1 personal use; revisit before Phase 3 (Gmail send is more painful to lose).
- [ ] Decision recorded in `docs/decisions/oauth-mode.md` with date and reasoning.

#### US-1.3: OAuth Authorization Flow (One-Time CLI Script)
**Acceptance Criteria:**
- [ ] CLI script `scripts/authorize_google.py` opens browser for OAuth consent
- [ ] Refresh token + access token stored in PostgreSQL `oauth_credentials` table
- [ ] Tokens encrypted at rest (Fernet symmetric encryption with key from env)
- [ ] Token refresh logic in production code handles expiry transparently
- [ ] Refresh token rotation is persisted on every refresh

#### US-1.4: Tool Registry Pattern
**Acceptance Criteria:**
- [ ] `ToolDefinition` dataclass: name, description, category, handler, requires_confirmation, scopes, json_schema
- [ ] `ToolRegistry` singleton with `register()`, `get()`, `list_for_llm()`
- [ ] Registry auto-discovers tools via Python entry points or explicit registration on import
- [ ] Tool descriptions emit a JSON-Schema-based definition compatible with the chosen provider's function-calling format (Gemini in Phase 1; the same schema feeds Anthropic / OpenAI / Groq through the `LLMRouter` adapter)
- [ ] Unit tests for registration, retrieval, and schema generation

#### US-1.5: Single Agent with LangGraph
**Acceptance Criteria:**
- [ ] LangGraph state object: `messages`, `tool_calls`, `tool_results`, `user_id`, `confirmation_pending`
- [ ] Graph nodes: `agent` (LLM call) → conditional → `tool_executor` → loop back to `agent` → `END`
- [ ] Uses **Gemini 2.5 Flash** (AI Studio free tier) by default for the agent loop; Groq Llama 3.3 70B Versatile for `complexity_hint=trivial` (English-only classification/routing); `complexity_hint=high` is a reserved slot for a future paid escalation lane (Gemini 2.5 Pro or equivalent) — **not implemented in Phase 1**.
- [ ] **No streaming on tool-call turns** (Gemini's parallel-tool-call streaming has known bugs; sequential non-streaming matches our Celery worker model anyway).
- [ ] Hebrew prompts are pinned to Gemini (never routed to Groq); language detection is conservative — default to Gemini if uncertain.
- [ ] LangGraph checkpointer uses PostgreSQL for thread persistence
- [ ] Each conversation has a `thread_id` derived from Telegram chat_id
- [ ] System prompt loaded from `prompts/system_v1.md` (versioned file)
- [ ] Token usage per turn is captured in trace metadata

#### US-1.6: Calendar Tool - List Events
**Tool name:** `list_calendar_events`
**Acceptance Criteria:**
- [ ] Parameters: `start_iso`, `end_iso`, `max_results=50`
- [ ] Returns list of events with: id, title, start, end, location, attendees count
- [ ] All times returned in user's timezone (`Asia/Jerusalem`)
- [ ] Handles empty calendar gracefully
- [ ] Error from Google API returns structured error to agent (not crashes)
- [ ] Eval cases: "what's on my calendar today", "this week", "next 3 days"

#### US-1.7: Calendar Tool - Find Free Slots
**Tool name:** `find_free_slots`
**Acceptance Criteria:**
- [ ] Parameters: `duration_minutes`, `search_start_iso`, `search_end_iso`, `working_hours_only=true`, `min_buffer_minutes=10`
- [ ] Default working hours: 09:00-19:00, configurable per user
- [ ] Excludes weekends if `working_hours_only=true`
- [ ] Returns up to 5 best slot suggestions
- [ ] Eval cases: "find me 30 min tomorrow", "find an hour next week morning"

#### US-1.8: Calendar Tool - Create Event
**Tool name:** `create_calendar_event`
**Acceptance Criteria:**
- [ ] Parameters: `title`, `start_iso`, `end_iso`, `description`, `location`, `attendees[]`
- [ ] `requires_confirmation=true` - never auto-creates
- [ ] Returns event ID and direct link on success
- [ ] Validates that end > start
- [ ] Defaults reminder to 30 min before for non-all-day events

#### US-1.9: Calendar Tool - Update / Delete Event
**Tool name:** `update_calendar_event` / `delete_calendar_event`
**Acceptance Criteria:**
- [ ] `requires_confirmation=true`
- [ ] Update supports partial: only specified fields are changed
- [ ] Delete returns event details in confirmation prompt for safety
- [ ] Recurring events: prompt user for `instance` vs `series` scope

#### US-1.10: Inline Keyboard Confirmation Flow
**Acceptance Criteria:**
- [ ] When `requires_confirmation=true`, agent emits a confirmation message with inline buttons: "✅ Confirm" / "❌ Cancel"
- [ ] Pending action is stored in Redis with TTL 5 min, keyed by `confirmation_id`
- [ ] User taps button → callback handler retrieves action → executes / cancels
- [ ] Confirmation messages are explicit: include all parameters in human-readable form
- [ ] Expired confirmations are gracefully handled (button tap returns "expired" message)

#### US-1.11: Timezone & Date Handling
**Acceptance Criteria:**
- [ ] All datetimes stored in UTC in DB
- [ ] All datetimes presented to user in `Asia/Jerusalem`
- [ ] System prompt includes current local **date, time, and weekday** in `Asia/Jerusalem` (refreshed on every turn, not cached)
- [ ] DST transitions tested explicitly (Israel DST ≠ Europe DST; Israel transitions on the Friday before the last Sunday in March / October)
- [ ] **Natural language dates resolved by the LLM** (not `dateparser`). Reason: `dateparser` does not reliably handle Hebrew expressions ("מחר", "השבוע הבא", "בעוד שבועיים"); a modern multilingual LLM (Gemini 2.5 Flash for Phase 1) resolves these correctly when given today's date in the system prompt.
- [ ] Eval suite includes adversarial date prompts: relative ("in 3 days"), absolute ("April 5"), Hebrew relative ("מחר אחה״צ"), mixed-language ("schedule תור at 5pm next Tuesday"), DST-boundary, and ambiguous ("next Friday" said on a Friday).
- [ ] Tool parameters always carry resolved ISO-8601 datetimes (`start_iso`, `end_iso`); the LLM is responsible for the resolution and the tool refuses non-ISO input.

#### US-1.12: Hebrew Language Validation
**Acceptance Criteria:**
- [ ] Eval set includes **5 Hebrew prompts** (unchanged weight: Hebrew matters but isn't the majority of traffic).
- [ ] Agent responds in the language the user wrote in.
- [ ] Hebrew date expressions ("מחר", "השבוע הבא") resolve correctly.
- [ ] System prompt explicitly instructs RTL-aware formatting in responses.
- [ ] **Routing constraint:** Hebrew detection in the router pins the request to Gemini (never Groq's Llama 3.3, which is not trained on Hebrew). The eval suite includes an explicit assertion that a Hebrew prompt selects the Gemini path.
- [ ] If Hebrew tool-selection accuracy drops below 85% on Flash, that's the trigger to A/B against paid Gemini 2.5 Pro (see [docs/decisions/llm-provider.md](decisions/llm-provider.md) "Paid swap path").

#### US-1.13: Audit Log
**Acceptance Criteria:**
- [ ] PostgreSQL table `audit_log`: id, timestamp, user_id, tool_name, parameters_json, result_status, response_summary
- [ ] Append-only (no UPDATE/DELETE permissions in app role)
- [ ] Every tool execution is logged regardless of success
- [ ] Telegram command `/audit today` returns recent actions

#### US-1.14: Eval Framework v1
**Acceptance Criteria:**
- [ ] `evals/` directory with prompt-and-expected-result YAML files
- [ ] CLI: `python -m jarvis.evals run --suite calendar`
- [ ] Each eval has: prompt, expected_tool_called, expected_parameters_match (loose), expected_response_contains
- [ ] Tool-selection accuracy measured (% of evals where correct tool called)
- [ ] LLM-as-judge for response-quality scoring (Gemini 2.5 Flash as judge — same provider keeps eval cost at zero)
- [ ] Results dumped to JSON; latest result committed to repo
- [ ] Initial threshold: 85% tool-selection accuracy on 20-prompt eval set

#### US-1.15: LangSmith Integration
**Acceptance Criteria:**
- [ ] LangSmith API key configured
- [ ] Every agent invocation is traced
- [ ] Tags include: phase, tool_called, latency_bucket
- [ ] Free tier (5k traces/month) is sufficient for personal use
- [ ] Fallback: if LangSmith key absent, system runs without tracing (graceful degradation)

#### US-1.16: Cost & Quota Guard Rails
**Acceptance Criteria:**
- [ ] Per-conversation token budget: 30,000 tokens max.
- [ ] On approach (80%): agent injects "approaching context limit, summarizing".
- [ ] System prompt + tool definitions are cached using **Gemini implicit/explicit context caching** (Gemini supports caching natively; ~60% input-cost discount on cached portion when we move to paid). On the free tier caching reduces TPM pressure rather than dollar cost.
- [ ] Daily quota usage reported to operator at end of day via Telegram (RPD used / cap, top 3 expensive turns by token count).
- [ ] When the paid-swap trigger fires (per [docs/decisions/llm-provider.md](decisions/llm-provider.md)), the daily report includes actual NIS spend.

**Definition of Done for Phase 1:**
> All 4 calendar tools work end-to-end with confirmations. Eval suite passes at ≥85% tool-selection accuracy. **Phase 1 total monthly LLM cost = 0 NIS (free tier).** Total infra-only spend under 25 NIS/mo. Audit log captures every action.

---

### EPIC 2: Memory Layer

**Goal:** Transform the assistant from stateless to stateful. The system begins to "know" the operator.

#### US-2.1: Memory Schema Design
**Acceptance Criteria:**
- [ ] `messages` table: id, thread_id, role, content, tokens, timestamp
- [ ] `semantic_facts` table: id, content (text), embedding (`vector(EMBEDDING_DIM)`), metadata jsonb, created_at
- [ ] **Embedding dimension is parameterized** via the `EMBEDDING_DIM` setting (Voyage `voyage-3-lite` = 512; OpenAI `text-embedding-3-small` = 1536). Migration reads the setting; do **not** hardcode 1536.
- [ ] Switching embedding models is a separate migration story (re-embed all facts, swap column type) — not part of this story.
- [ ] `procedural_patterns` table: id, pattern_text, confidence, last_reinforced_at
- [ ] pgvector index (HNSW) on `semantic_facts.embedding` with operator class matching the chosen distance metric (`vector_cosine_ops`)
- [ ] Alembic migrations for all tables

#### US-2.2: Short-Term Memory (Redis)
**Acceptance Criteria:**
- [ ] Last N=20 messages per thread cached in Redis list
- [ ] Cache writes happen async after each turn (don't block response)
- [ ] On cache miss, fetch from Postgres and rebuild
- [ ] Configurable TTL (default 30 days)

#### US-2.3: Long-Term Memory - Semantic Store
**Acceptance Criteria:**
- [ ] Embeddings via Voyage AI (cheaper than OpenAI), or OpenAI `text-embedding-3-small` as fallback
- [ ] Embedding cost monitored as separate budget line
- [ ] Insert API: `memory.remember(fact, metadata)`
- [ ] Query API: `memory.recall(query, k=5, threshold=0.75)`
- [ ] Query results returned with similarity scores

#### US-2.4: Fact Extraction Pipeline
**Acceptance Criteria:**
- [ ] After each conversation turn, an async task extracts "memorable facts" via a small LLM call
- [ ] Extraction prompt is conservative: only durable preferences, identities, and relationships
- [ ] Examples it should extract: "User's wife is named X", "User prefers morning meetings", "User's project Alpha launches Q2"
- [ ] Examples it should NOT extract: "User asked about the weather", "User said hello"
- [ ] Duplicate facts are detected via similarity search before insertion (>0.92 = duplicate)
- [ ] Extraction is non-blocking; failures don't affect user response

#### US-2.5: Memory Injection in Agent Loop
**Acceptance Criteria:**
- [ ] Before LLM call, top-K relevant facts retrieved from semantic store
- [ ] Top-K based on similarity to current user message
- [ ] Retrieved facts injected into system prompt (clearly labeled section)
- [ ] Memory injection adds at most 1500 tokens to context
- [ ] Disabled in evals (or controlled via fixed seed memory) for reproducibility

#### US-2.6: Procedural Memory
**Acceptance Criteria:**
- [ ] Pattern format: short imperative statement ("When David asks about budget, show monthly chart")
- [ ] Created via explicit user instruction: "Remember to always X" / "From now on, Y"
- [ ] Stored separately from semantic facts (different table, different prompt slot)
- [ ] Reinforced when user confirms behavior; weakened on contradiction
- [ ] Top 10 active patterns always included in system prompt

#### US-2.7: Privacy Controls
**Acceptance Criteria:**
- [ ] `/forget last` removes the last extracted fact
- [ ] `/forget about <topic>` performs similarity search and shows facts to delete (with confirmation)
- [ ] `/memory dump` returns all stored facts (for transparency)
- [ ] All memory operations are audit-logged

**Definition of Done for Phase 2:**
> System recalls relevant facts from prior conversations. Operator can verify, control, and delete memory. Eval suite extended with memory-dependent prompts; ≥80% accuracy.

---

### EPIC 3: Email Agent

**Goal:** Add Gmail capabilities. Validate that the tool registry pattern scales to a second domain without core changes.

#### US-3.1: Gmail API Enablement & Scopes
**Acceptance Criteria:**
- [ ] Gmail API enabled in same GCP project
- [ ] Scopes: `gmail.readonly` initially, `gmail.send` and `gmail.modify` only when send/draft features ship
- [ ] Re-authorization script supports incremental scope addition

#### US-3.2: Email Tool - Search Emails
**Tool name:** `search_emails`
**Acceptance Criteria:**
- [ ] Parameters: `query` (Gmail search syntax), `max_results=20`
- [ ] Returns: id, sender, subject, snippet, received_at, has_attachments
- [ ] Body NOT returned in search (separate tool)

#### US-3.3: Email Tool - Read Email
**Tool name:** `read_email`
**Acceptance Criteria:**
- [ ] Parameters: `message_id`
- [ ] Returns full body (HTML stripped to plain text)
- [ ] Truncates at 10,000 chars with truncation notice
- [ ] Handles multipart MIME correctly

#### US-3.4: Email Tool - Summarize Inbox
**Tool name:** `summarize_inbox`
**Acceptance Criteria:**
- [ ] Parameters: `since_iso` (default: 24h ago), `max_emails=20`
- [ ] Tool internally calls `search_emails` + `read_email` for each
- [ ] Final summary produced by the agent, not the tool (tool returns raw data)
- [ ] Summary categorizes: requires-reply, informational, automated

#### US-3.5: Email Tool - Draft Reply
**Tool name:** `draft_reply`
**Acceptance Criteria:**
- [ ] Parameters: `in_reply_to_message_id`, `body`, `tone_hint`
- [ ] Creates a Gmail draft (does NOT send)
- [ ] Returns draft URL for user to review
- [ ] `requires_confirmation=true` even for drafts (avoid spam-like behavior)

#### US-3.6: Email Tool - Send Email
**Tool name:** `send_email`
**Acceptance Criteria:**
- [ ] Parameters: `to[]`, `cc[]`, `subject`, `body`, `in_reply_to_message_id?`
- [ ] **Double confirmation**: agent asks once, user confirms, agent shows full message preview, user confirms again
- [ ] Send is logged in audit log with full body archived
- [ ] Rate-limited at 10 sends/day initially (configurable)

**Definition of Done for Phase 3:**
> Inbox summary and reply drafting workflows are reliable. Send requires double confirmation. Memory layer can recall email-related facts ("Did the manager send the doc yet?"). Eval suite extended; ≥85%.

---

### EPIC 4 (Cross-cutting): Observability, Quality, Security

> These stories are NOT a single phase. They are picked up incrementally throughout Phases 0-3 as their context becomes relevant. Each story below should be completed before its corresponding phase ends.

#### US-X.1: Health Dashboard (Telegram-native)
- [ ] `/status` command returns: uptime, last 10 actions, current cost MTD, queue depth
- [ ] `/cost` returns daily breakdown for last 7 days

#### US-X.2: Error Reporting
- [ ] Sentry configured (free tier - 5K events/month) OR self-hosted GlitchTip
- [ ] Unhandled exceptions trigger Telegram alert to operator
- [ ] Error rate exceeding 5/hour triggers cooldown mode

#### US-X.3: Backup & Recovery
- [ ] Daily Postgres backup via `pg_dump`, encrypted, uploaded to Hetzner Storage Box / Cloudflare R2
- [ ] Retention: 7 daily + 4 weekly + 3 monthly
- [ ] Documented restore procedure (tested at least once)

#### US-X.4: Secrets Management
- [ ] Production: secrets in encrypted `.env` (using `sops` + `age`)
- [ ] Development: `.env` from `.env.example` (never committed)
- [ ] Rotation playbook documented for each external API key
- [ ] **age key locations documented** in `docs/secrets.md`:
  - Production host: `/root/.config/sops/age/keys.txt` (chmod 600, owned by root)
  - Operator local: `~/.config/sops/age/keys.txt` (chmod 600)
  - Both keys backed up to a password manager off-host (loss of all copies = unrecoverable secrets)
  - Public keys (`.age.pub`) committed in `docs/secrets.md` so anyone with the repo can re-encrypt
- [ ] `scripts/rotate-secrets.sh` re-encrypts the secrets file with the current recipients list
- [ ] `gitleaks` runs on every pre-commit and in CI; bypass requires `--no-verify` + reviewer sign-off

#### US-X.5: Circuit Breakers for External Tools
- [ ] Each tool wraps external API calls with timeout (10s) + retry (max 2, exp backoff)
- [ ] Circuit breaker opens after 5 failures/minute, stays open 2 min
- [ ] Tool returns degradation message to agent when circuit is open
- [ ] Implementation: `tenacity` for retry, `pybreaker` for circuit breaking

#### US-X.6: Prompt Versioning
- [ ] All prompts in `prompts/` directory as markdown files with semver in filename
- [ ] Active prompt version selected via env var (rollback capability)
- [ ] Prompt changes require eval pass before merge

#### US-X.7: Tool-Call Idempotency (lands with Phase 1)
- [ ] Before any side-effecting tool runs (Calendar create/update/delete, Gmail draft/send), worker computes idempotency key = `sha256(thread_id || tool_name || canonical_params_json)`
- [ ] Key checked via Redis `SET NX EX 300` (5-min TTL); on hit, return the cached result instead of re-executing
- [ ] On successful execution, the result is cached under the same key for the TTL window
- [ ] Read-only tools (`list_calendar_events`, `find_free_slots`, `search_emails`, `read_email`, `summarize_inbox`) skip the cache and always execute fresh
- [ ] **Why:** Celery `acks_late=True` re-delivers a task whose tool already partially succeeded (e.g., event created in Google Calendar but worker died before ack). Without this guard, retry creates a duplicate.
- [ ] Unit test: simulate worker crash mid-tool, verify retry returns cached result and Google Calendar shows exactly one event.

#### US-X.8: Data Retention & Archival
- [ ] Schema designed in Phase 0 (partitioning), enforcement Beat job lands in Phase 4 — but disk-usage alert ships in Phase 0.
- [ ] `audit_log` declaratively partitioned by month (`PARTITION BY RANGE (timestamp)`); partitions older than 12 months moved to cold storage but **never deleted** (compliance posture).
- [ ] `messages` rows older than 90 days archived to compressed JSONL in object storage; row deleted from Postgres only after the archive write is confirmed.
- [ ] `langgraph_checkpoints` older than 30 days pruned (no archive — they're recoverable from `messages`).
- [ ] Disk-usage alert at 70% of VM disk; auto-pause at 90% with operator alert.
- [ ] Restore-from-archive procedure documented in `docs/runbooks/data-restore.md` and tested at least once before Phase 4 closes.

---

## 5. Success Metrics

| Metric | Phase | Target |
|--------|-------|--------|
| End-to-end p95 latency | All | < 15s |
| End-to-end p99 latency | All | < 30s |
| Tool-selection accuracy | 1+ | ≥ 85% |
| Monthly infra + LLM cost | All | ≤ 50 NIS |
| Daily uptime | 0+ | ≥ 99.5% |
| Memory recall precision | 2+ | ≥ 80% |
| Confirmation prompts shown for destructive actions | 1+ | 100% |
| Audit log coverage of executed tool calls | 1+ | 100% |

---

## 6. Open Questions / Decisions to Lock Before Phase 1

1. **Telegram bot identity:** dedicated phone number for the bot? (recommended for separation, ~10 NIS one-time SIM)
2. **Domain name:** purchase a domain or use IP + DuckDNS? (domain ~3-5 NIS/month amortized; recommended)
3. **Embeddings provider:** Voyage AI vs OpenAI? Decision driven by cost + Hebrew quality.
4. **Eval threshold for blocking phase progression:** 85% suggested - confirm acceptable.
5. **Prompt language:** English-only in system prompt vs bilingual? (Recommend English-only, with explicit instruction to respond in user's language.)

---

## 7. Glossary

- **Tool**: A registered capability that the agent can invoke (e.g., `list_calendar_events`)
- **Agent loop**: The LLM-call → tool-call → result → LLM-call cycle
- **Episodic memory**: Recent conversation history (last N messages)
- **Semantic memory**: Vector-indexed durable facts about the user
- **Procedural memory**: Behavioral patterns ("how to act in situation X")
- **Confirmation flow**: Inline keyboard prompt requiring explicit user approval
- **Idempotency key**: Unique identifier preventing double-execution of webhooks
- **Audit log**: Append-only record of every tool execution
