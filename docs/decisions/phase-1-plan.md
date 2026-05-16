# Phase 1 Slicing Plan

> **Status:** Approved (operator, 2026-05-17)
> **Phase:** Phase 1 — Calendar Agent
> **Stories covered:** US-1.1 through US-1.16 + US-X.6, US-X.7, US-X.8 (19 total)
> **Estimate:** 9–14 days
> **Deliverable cadence:** one PR per slice, merged to `main` after operator review.

## Sequencing principles

1. **Read-only before write.** First mutation (US-1.8 create-event) lands *with* idempotency (US-X.7), never before, never after.
2. **Eval harness lands at slice 3.** Earlier than that we have <1 tool, evals don't earn their keep.
3. **Operator gates each slice.** Each slice merges before the next starts.
4. **Risk first within each slice.** When two stories could go either way, the riskier one ships first.
5. **No streaming on tool-call turns.** Gemini's parallel-tool-call streaming has known bugs (per `decisions/llm-provider.md`); sequential non-streaming matches our Celery worker model.

## Slices

### Slice 1 — Foundation (no agent, no Google APIs) — 1–2 days

**What lands:**
- `core/settings.py` additions: `GEMINI_API_KEY`, `GROQ_API_KEY`, `LANGSMITH_API_KEY` (all `SecretStr | None`; fail-fast at first use in later slices, not at boot)
- `core/datetime.py` (**US-1.11**): `now_jerusalem()`, `to_jerusalem()`, `to_utc()`, `format_for_prompt()`. Tests cover Israel DST boundaries (Friday-before-last-Sunday of March/October).
- `tools/base.py` (**US-1.4**): `BaseTool` ABC, `ToolDefinition` dataclass, `ToolRegistry` singleton with `register()` / `get()` / `list_for_llm()`. JSON-schema emission compatible with Gemini + Anthropic + OpenAI function-calling.
- `agents/llm_router.py` (**LLMRouter skeleton**): provider selection logic (default Gemini, `complexity_hint=trivial` → Groq, Hebrew detected → pin to Gemini regardless). Stub implementations raise `NotImplementedError` — Slice 2 wires real SDKs. Unit tests cover the routing decision (no real API calls).
- `prompts/system_v1.md` (**US-X.6**) + `core/prompts.py` loader. First system prompt: identity, timezone, language policy, tool-calling stance.
- `db/migrations/` (**US-X.8**): Alembic initialized. Migrations for `audit_log` (partitioned by month on `timestamp`, no DELETE permission for app role), `messages`, `langgraph_checkpoints`, `oauth_credentials`. **Not** Phase 2 tables (`semantic_facts`, `procedural_patterns`).

**Operator-visible win:** None. All internal. Slice succeeds when ruff + mypy --strict + pytest pass with new tests added.

**Acceptance gate:** new unit tests pass; `alembic upgrade head` works on a clean DB; `tools.list_for_llm()` returns valid JSON schemas for a sample tool registered in the test suite.

### Slice 2 — First working agent (read-only calendar) — 2–3 days

**What lands:**
- `scripts/authorize_google.py` (**US-1.3**): one-time CLI, opens browser, captures refresh token, encrypts with Fernet, writes to `oauth_credentials`. Runbook at `docs/runbooks/oauth-reauth.md` documents the Monday re-auth ritual.
- `integrations/google_calendar.py`: async httpx client; Fernet-decrypts token; auto-refresh; raises `OAuthExpired` on `invalid_grant` (operator alert handled in Slice 4 hardening).
- `tools/calendar/list_events.py` (**US-1.6**): `list_calendar_events` tool. Returns events in `Asia/Jerusalem`. Read-only — no idempotency wrapper needed.
- `agents/graph.py` + `agents/nodes.py` (**US-1.5**): LangGraph with `load_context → agent ⇄ tool_executor → respond → END`. Gemini Flash via `google-genai` SDK, non-streaming, system+tools prompt-cached. Postgres checkpointer.
- `workers/tasks.py` extension: existing echo path is removed; non-slash messages now invoke the agent.
- `core/audit.py` (**US-1.13 partial**): append-only writer; logs every tool execution regardless of outcome.
- `integrations/langsmith.py` (**US-1.15**): graceful — if `LANGSMITH_API_KEY` absent, no tracing, no error.
- `core/llm_budget.py` (**US-1.16 partial**): per-conversation 30K-token cap; Redis-backed daily RPD counter for Gemini with alert at 80%, pause at 96%.

**Operator-visible win:** Telegram message *"מה יש לי ביומן היום?"* / *"What's on my calendar today?"* → bot answers with the day's events in the user's language.

**Acceptance gate:** end-to-end manual test (operator on Telegram + prod or staging); audit log shows the tool call; LangSmith trace captured (if key present); RPD counter increments.

**Operator inputs needed before Slice 2:**
- Google AI Studio API key
- Groq API key
- GCP project + OAuth client JSON
- LangSmith API key (optional but operator confirmed yes)

### Slice 3 — Find slots + eval harness + Hebrew gate — 1–2 days

**What lands:**
- `tools/calendar/find_slots.py` (**US-1.7**): `find_free_slots`. Default working hours 09:00–19:00, `min_buffer_minutes=10`.
- `evals/runner.py`, `evals/judge.py` (**US-1.14**): CLI `python -m jarvis.evals run --suite calendar`. Gemini Flash as judge.
- `evals/suites/calendar.yaml`: ~15 seed prompts including 5 Hebrew (**US-1.12**). Hebrew prompts assert router pins to Gemini (never Groq).
- Results dumped to `evals/results/<timestamp>.json`; latest committed.

**Operator-visible win:** Operator can `make eval` (or `python -m jarvis.evals run --suite calendar`) and see tool-selection accuracy %. *"Find me an hour tomorrow morning"* works end-to-end.

**Acceptance gate:** eval suite runs cleanly; tool-selection accuracy reported (no fixed threshold yet — that's Slice 6).

### Slice 4 — First mutation (riskiest slice) — 2–3 days

**What lands:**
- `core/idempotency.py` extension (**US-X.7**): `tool_idempotency_key(thread_id, tool_name, params)` + `redis_setnx_or_get_cached(key, ttl=300)`. Read-only tools skip; side-effecting tools require.
- `tools/calendar/create_event.py` (**US-1.8**): `create_calendar_event`, `requires_confirmation=True`, wraps execution in idempotency layer.
- `tools/confirmation.py` (**US-1.10**): pending state in Redis (TTL 5 min, keyed by `confirmation_id`); inline-keyboard buttons (✅ Confirm / ❌ Cancel); callback handler on the webhook; expired-tap returns "expired" message; never silently fails.
- Critical unit test: simulate Celery worker crash mid-tool (raise after Google API success, before ack). Verify retry returns the cached result and Google Calendar shows exactly one event.

**Operator-visible win:** *"Schedule a haircut next Tuesday 5pm"* → confirmation card with all parameters → operator taps ✅ → event lands in Google Calendar. Exactly once, even if the worker is killed mid-call.

**Acceptance gate:** idempotency unit test passes; manual end-to-end confirms event-create flow; audit log shows the create with confirmed=true.

### Slice 5 — Update + delete + cost/audit slash-commands — 1–2 days

**What lands:**
- `tools/calendar/update_delete.py` (**US-1.9**): `update_calendar_event` (partial), `delete_calendar_event`. Both require confirmation + idempotency. Recurring events prompt for `instance` vs `series` scope.
- `tools/commands.py` extensions: `/audit today`, `/audit yesterday` (**US-1.13 full**), `/cost` (**US-1.16 full**) — RPD used today, top 3 turns by token count, NIS spend.
- End-of-day Celery Beat task: send digest via Telegram (**US-1.16 full**).

**Operator-visible win:** All 4 calendar tools work. `/audit today` returns the day's actions. End-of-day digest arrives in Telegram at ~22:00 local.

**Acceptance gate:** all 4 calendar tools have eval coverage in `calendar.yaml`; slash-commands tested; digest task runs in Beat schedule.

### Slice 6 — Hardening + Phase 1 close — 1–2 days

**What lands:**
- `core/circuit_breaker.py` (**US-X.5**): `tenacity` retry + `pybreaker` circuit breaker decorators around Google Calendar, Gemini, Groq calls. Degradation messages returned to the agent on open circuit.
- Full eval pass against fixed seed. Document results in `evals/results/phase-1-close.json`.
- PROGRESS.md updated to 🟢 Phase 1; Phase 2 unblocked.
- Operator-visible Telegram message: "Phase 1 complete — N stories, M eval pass rate, 0 NIS spent this month."

**Acceptance gate:** Phase 1 DoD met — 4 tools end-to-end with confirms, eval ≥85%, audit log 100%, monthly LLM cost = 0 NIS on free tier.

## Risks & open questions

- **Gemini free-tier quota cut.** Mitigation lives in [`llm-provider.md`](llm-provider.md): RPD guard + one-env-var swap to paid Tier 1.
- **OAuth re-auth ritual reliability.** Operator runs `authorize_google.py` Monday; if missed, calendar calls fail with a clear "expired authorization" message (no silent retries). Runbook in `docs/runbooks/oauth-reauth.md` lands in Slice 2.
- **Eval threshold.** Spec says 85%. Operator to confirm before Slice 6 (open question in SPEC §6 Q4 — defer until we have eval data).
- **LangGraph Postgres checkpointer.** Need to verify the `langgraph-checkpoint-postgres` package is healthy and async-compatible with our SQLAlchemy 2.0 async session. Validate in Slice 2 spike before committing to the design.
- **Gemini context caching.** Gemini's implicit caching is automatic; explicit is opt-in. Validate that our system+tools prompt is large enough to hit the implicit-cache 1K-token threshold; if not, use explicit. Validate in Slice 2.

## Operator inputs needed (by slice)

| Slice | Needed | When |
|---|---|---|
| 1 | Nothing | — |
| 2 | Gemini key, Groq key, GCP OAuth client JSON, LangSmith key (optional) | Before Slice 2 starts |
| 3 | Nothing new | — |
| 4 | Nothing new (the Telegram confirmation UX is operator-tested manually) | — |
| 5 | Nothing new | — |
| 6 | Final eval threshold confirmation (default 85%) | Before Slice 6 starts |
