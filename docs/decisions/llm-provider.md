# Decision: LLM Provider for Phase 1 Calendar Agent

> **Status:** Approved (operator, 2026-05-16)
> **Date:** 2026-05-16
> **Context:** Operator will not prepay Anthropic credits (see PROGRESS.md DECISION 2, 2026-04-30). Spec's "Claude Haiku 4.5 primary" plan needs replacement with a free-tier LLM that supports reliable tool calling.

## Constraints (non-negotiable)

- Tool-calling reliability — calendar mutation is destructive.
- Hebrew + English — operator code-switches; weak Hebrew means wrong tool selection.
- 50 NIS/month total ceiling still applies.
- `LLMRouter` abstraction stays — provider swap is config, not code rewrite.
- ~30–100 turns/day expected (single user, Telegram).

## Candidates

| | **Gemini 2.5 Flash** (AI Studio free) | **Groq Llama 3.3 70B Versatile** (free) | **OpenRouter `:free` models** |
|---|---|---|---|
| **Free tier** | ~10 RPM / **~250 RPD** / 250K TPM | 30 RPM / 1,000 RPD / **12K TPM** | 20 RPM / **200 RPD** (1,000 with $10 credit unlock) |
| **Tool calling** | Native; reliable in **non-streaming sequential**. Parallel-tool-call streaming is buggy (400s, drops). | Partial. Llama 3.3 70B is the supported tool-use model post-deprecation, but strict schema validation rejects schemas other providers coerce. | Varies per model. Best-effort SLA — free hosts go offline. DeepSeek V4, Qwen3 Coder, Llama 3.3 70B `:free`, gpt-oss-{20b,120b} `:free` have native FC. |
| **Hebrew** | **Strong** (Google's multilingual is broadest among the three) | **Weak / unverified.** Hebrew is NOT in Llama 3.3's 8 officially-trained languages. Date / calendar terminology is high-risk. | DeepSeek V3/V4 reported "usable"; no benchmarks. Unknown for the rest. |
| **p50 latency** | TTFT ~0.65 s | TTFT ~150–300 ms; ~276 tok/s output (fastest) | Highly variable — routing-dependent, no SLA |
| **Risk (one line)** | Google has silently cut free RPD by 90%+ once (Dec 2025); could happen again mid-day. | Hebrew unsupported; 12K TPM means a single long turn can exhaust the per-minute budget. | "Best-effort" hosts can vanish mid-task — wrong fit for a mutation-heavy agent. |

Sources: Google AI Studio rate-limits forum threads; [`console.groq.com/docs/rate-limits`](https://console.groq.com/docs/rate-limits); [`openrouter.ai/collections/tool-calling-models`](https://openrouter.ai/collections/tool-calling-models). Full citations in research log.

## Recommendation

**Primary: Gemini 2.5 Flash via AI Studio free tier.**
**Trivial routing: keep Groq Llama 3.3 70B** for classification only — already in the spec, no Hebrew exposure there.

**Reasoning:**
1. **Hebrew is decisive.** Of the three, only Gemini handles Hebrew reliably. A calendar agent that mis-parses "מחר אחה״צ" or names events in mojibake is worse than no agent.
2. **250 RPD covers the use case** with 2.5–8× headroom (30–100 turns/day expected). 250K TPM is far beyond what a single user can hit.
3. **Tool calling works** in the mode we'll use anyway — synchronous, sequential, one tool per turn. Telegram is not a streaming UX; the parallel-tool-call streaming bug doesn't affect us.
4. **Latency is fine.** ~0.65s TTFT + tool call + final response stays well inside the SPEC §5 p95 <15s target.

**Mitigations baked into the design:**
- **No streaming** for tool-call turns. Use synchronous request/response (matches our Celery worker model anyway).
- **RPD budget guard.** Daily request counter in Redis; alert at 200/day so we see ceiling approach in advance, not at miss-time.
- **Provider-swap drill.** `LLMRouter` keeps a Groq-only fallback path. If Google cuts quota again, swap primary to Groq for English-only flows and either pause Hebrew or escalate to a paid Tier 1 Gemini key (Tier 1 is ~$0 base + pay-per-token, fits the 50 NIS/mo budget for our volume).

**Why not Groq primary:** Hebrew. Llama 3.3 was not trained on Hebrew; cross-lingual transfer is unreliable for date-and-name parsing. Disqualified for this user.

**Why not OpenRouter primary:** No availability SLA on free tier. For a mutation-heavy agent (creates/deletes calendar events), unpredictable model uptime is the wrong trade.

## Paid swap path

The free tier is the starting point, not the destination. The operator is willing to spend within the 50 NIS/mo ceiling once we have evidence (eval gaps, quota cuts, latency complaints) that paying buys something. Documenting the swap here so it isn't a surprise later:

**Trigger to swap:** any one of —
- Free-tier RPD ceiling hit twice in one week (the operator outgrows the free tier);
- Google announces or silently applies another quota cut;
- Hebrew eval (US-1.12) shows tool-selection accuracy <85% on free-tier Flash and Gemini's paid `2.5-pro` outperforms it in a 10-prompt A/B.

**Swap mechanic:** one environment variable. `LLM_PROVIDER_GEMINI_KEY` switches from the AI Studio free key to a Tier 1 billing-attached key. No code changes; `LLMRouter` is the abstraction. Same model identifier (`gemini-2.5-flash`), different quota class.

**Cost projection at the swap (Gemini 2.5 Flash, Tier 1 pay-as-you-go):**

| Daily turns | Est. monthly cost | NIS/mo (≈$1 = 3.7 NIS) | Headroom under 32 NIS LLM budget |
|---|---|---|---|
| 30 | ~$1.20 | ~4 NIS | 28 NIS spare |
| 60 | ~$6 | ~22 NIS | 10 NIS spare |
| 100 | ~$12 | ~44 NIS | **−12 NIS (over)** |

Projection assumes ~5K input + 1K output tokens/turn average, no prompt caching. With prompt caching (system prompt + tool definitions, ~75% of input), input cost drops ~60% — the 100-turn/day row lands ~28 NIS, back inside budget. **Prompt caching is therefore a Phase 1 requirement, not an optimization, if/when we swap to paid.**

**Future tier-routing slot:** US-1.5 already reserves `complexity_hint=high` for a future escalation lane. That slot is where Gemini 2.5 Pro (or Claude Sonnet, if we revisit Anthropic) will plug in when an eval shows Flash isn't enough for a specific class of prompt. **Not** implemented in Phase 1 — Phase 1 ships with Flash + Groq only.

## What this changes in the spec docs (after approval)

- ARCH §4.2: AI Stack table — replace "Primary LLM: Claude Haiku 4.5" with "Primary LLM: Gemini 2.5 Flash (AI Studio free)". Drop the "Complex reasoning LLM: Claude Sonnet" row (no paid escalation in Phase 1).
- ARCH ADR-005: rewrite as "Gemini Primary, Multi-Provider via Adapter". `LLMRouter` rationale preserved.
- ARCH §7.3 cost table: zero out Anthropic lines; LLM cost target drops to ~0 NIS for Phase 1 (Groq + Gemini both free).
- SPEC US-1.1: drop the "Anthropic API key + prepaid credits" requirement. Replace with "Gemini AI Studio key + Groq key (both free)". Daily LLM cost cap line becomes a daily-RPD guard.
- SPEC US-1.5: replace "Claude Haiku 4.5 by default, Sonnet on complexity_hint=high" with "Gemini 2.5 Flash by default; Groq Llama 3.3 70B for `complexity_hint=trivial` (classification/routing only, English-only)".
- SPEC US-1.12: keep Hebrew eval weight unchanged (5 prompts), but explicitly add an eval that Hebrew prompts route to Gemini (never Groq).

PROGRESS.md "Spec revisions" table gets a new row recording this change (matches the established style for the 10 pre-Phase-0 fixes).
