# Decision: Google OAuth Mode for Jarvis

> **Status:** Locked
> **Date:** 2026-04-30
> **Story it unblocks:** SPEC US-1.2

## Decision

**Option (c) — Weekly re-auth ritual.**

The OAuth app stays in **"External — Testing"** mode in the Google Cloud Console. Refresh tokens issued by an External-Testing app are invalidated by Google after 7 days. The operator manually runs `scripts/authorize_google.py` every Monday to re-grant consent and persist a fresh refresh token in the `oauth_credentials` table.

## Why this and not the alternatives

| Option | Why rejected |
|---|---|
| (a) Internal app via Workspace | Requires a Google Workspace account at ~25 NIS/month. Busts the 50 NIS/mo budget on a recurring line, for a single-user system. The operator does not already have a Workspace identity. |
| (b) Submit for verification | Free, but 1–2 weeks of latency and requires a public privacy policy + verified domain. For a personal, single-user, never-public assistant, the disclosure surface is wrong. Verification also commits us to App-Store-like review on scope changes. |
| **(c) Weekly re-auth** | **Chosen.** Zero cost. Operator burden = 1 minute on Monday. Acceptable trade for a system the operator alone uses. |

## Operational implications

- `scripts/authorize_google.py` (lands with US-1.3) is the only re-auth path. It opens a browser for Google consent, captures the refresh token, encrypts it, and writes to Postgres `oauth_credentials`.
- A runbook **must exist** at `docs/runbooks/oauth-reauth.md` before Phase 1 ships so the ritual is documented in one place.
- The system should self-monitor: if a refresh attempt returns `invalid_grant`, log + alert the operator via Telegram with a "re-auth needed" message. Don't silently fail calendar calls.
- **Calendar list/read tools** degrade to "OAuth expired, run re-auth" until the operator re-authorizes. They do **not** retry indefinitely.
- **Calendar write tools** never auto-retry on `invalid_grant` — they fail explicitly with the same message and the user-facing error is "expired authorization — please re-auth".

## Revisit triggers

This decision is acceptable **for Phases 1–2 only**. Re-evaluate before Phase 3 (Gmail send) because:
- Losing Gmail send for a day is more painful than losing calendar (a missed reply is worse than a missed re-auth).
- A travel week / vacation breaks the Monday ritual.

When Phase 3 work begins, decide between:
- **(b) Verification** — by then the operator has used the system long enough to have a stable domain and a published privacy policy.
- **Migrating to (a)** if the operator has adopted Workspace for other reasons.

Until then: weekly re-auth, documented runbook, Telegram alert on `invalid_grant`.

## Pointers

- SPEC US-1.2 — the acceptance criterion this decision unblocks.
- SPEC US-1.3 — implements the re-auth CLI script.
- ARCH §10 row "OAuth refresh token expires after 7 days" — the documented failure mode.
- `docs/runbooks/oauth-reauth.md` — to be written with US-1.3.
