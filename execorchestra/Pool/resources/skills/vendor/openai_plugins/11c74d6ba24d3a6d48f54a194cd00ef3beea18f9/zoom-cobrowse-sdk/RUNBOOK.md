# Cobrowse 5-Minute Preflight Runbook

Use this before deep debugging. It catches the most common Cobrowse failures quickly.

## Skill Doc Standard Note

- Agent-skill standard entrypoint is `SKILL.md`.
- This runbook is an operational convention (recommended), not a required skill file.
- `SKILL.md` is also a navigation convention for larger skill docs.

## 1) Confirm Two-Role Model

- Customer role (`role_type=1`) starts session.
- Agent role (`role_type=2`) joins session.

If your demo only has one generic role, expect broken join behavior.

## 2) Confirm PIN Source of Truth

- Use customer SDK event `pincode_updated` as the only user-facing PIN.
- Agent must join with that same PIN.
- Do not show provisional/debug PIN values from backend records.

Common symptom if wrong: `Pincode is not found` / error `30308`.

## 3) Confirm JWT Claims

- Sign JWT on backend only.
- Include required claim names exactly (for example `user_id`, not custom aliases).
- Use SDK Key for SDK token context; keep SDK Secret server-side.

If claim names are wrong, token is rejected before session logic.

## 4) Confirm Session Order

Recommended sequence:
1. Customer gets customer JWT and starts session.
2. PIN is generated on customer side (`pincode_updated`).
3. Agent gets agent JWT and joins with that PIN.

Starting agent flow before customer session is active often causes join failures.

## 5) Confirm Distribution Pattern

- CDN path: customer SDK + Zoom-hosted agent desk iframe.
- npm path: custom integration (BYOP mode required for custom PIN control).

If using npm agent integration without BYOP expectations, flow mismatches happen.

## 6) Confirm Browser and Security Constraints

- HTTPS required (except loopback/local dev).
- CSP/CORS must allow Zoom domains.
- Third-party cookie/privacy settings can affect reconnect behavior.

Do not treat extension/adblock warnings as root cause until API/session checks fail.

## 7) Quick Checks (Backend + UI)

- Backend config endpoint returns expected credential flags.
- Customer page shows a single Support PIN from SDK event.
- Agent page join uses same Support PIN and returns actionable response (not generic 404).

### Copy/Paste Validation Commands

```bash
curl -sS -i "$COBROWSE_BASE_URL/customer"
curl -sS -i "$COBROWSE_BASE_URL/agent"
curl -sS -i "$COBROWSE_BASE_URL/api/config"
```

Expected: customer/agent pages load and config endpoint returns valid JSON flags.

## 8) Fast Decision Tree

- **Invalid token** -> check JWT claim names and signing secret.
- **Agent cannot find PIN** -> wrong PIN source or wrong session order.
- **Session drops on refresh** -> check reconnection window and browser privacy/cookies.
- **Works locally, fails prod** -> check HTTPS, CSP/CORS, reverse proxy pathing.
