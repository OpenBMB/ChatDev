# Webhooks 5-Minute Preflight Runbook

Use this before deep debugging. It catches common webhook failures quickly.

## Skill Doc Standard Note

- Agent-skill standard entrypoint is `SKILL.md`.
- This runbook is an operational convention (recommended), not a required skill file.
- `SKILL.md` is also a navigation convention for larger skill docs.

## 1) Confirm Endpoint Reachability

- Public HTTPS endpoint is reachable from Zoom.
- Reverse proxy routes to the correct service path.

## 2) Confirm Signature Verification

- Verify `x-zm-signature` with raw request body.
- Use `x-zm-request-timestamp` and reject stale timestamps.
- Do not re-serialize parsed JSON for signature material.

### Signature Formula Reminder

```text
payload = "v0:" + x-zm-request-timestamp + ":" + raw_body
expected = "v0=" + HMAC_SHA256(webhook_secret, payload)
```

If `raw_body` differs from original bytes (pretty print/re-stringify), verification fails.

## 3) Confirm URL Validation Handling

- Handle `endpoint.url_validation` challenge correctly.
- Return expected `plainToken` and computed `encryptedToken` when required.

### URL Validation Reminder

On `event = endpoint.url_validation`, hash `payload.plainToken` with your webhook secret and return both values exactly.

## 4) Confirm Event Subscription Setup

- Feature/Event subscriptions enabled in app config.
- Required event types selected and saved.

## 5) Confirm Processing Pattern

- Respond HTTP 200 quickly.
- Process business logic asynchronously.
- Make handlers idempotent for retries.

## 6) Quick Probes

- Local test payload verifies signature path.
- Zoom test event reaches endpoint and is logged.
- No repeated non-200 responses in logs.

### Copy/Paste Validation Commands

```bash
# 1) Reachability check (replace with your webhook route)
curl -sS -i "https://your-domain.example/webhook"

# 2) Check service logs quickly while sending test events
# (replace command with your runtime: pm2/docker/systemd)
pm2 logs your-service --lines 100

# 3) Basic endpoint health check if available
curl -sS -i "https://your-domain.example/health"
```

Expected: endpoint is reachable over HTTPS, events appear once, and responses are consistently 2xx.

## 7) Fast Decision Tree

- **No events received** -> endpoint unreachable or wrong subscription.
- **401 invalid signature** -> raw body mismatch/secret mismatch.
- **Duplicate events** -> no idempotency or delayed responses.

## 8) Retry and Idempotency Guardrail

- Treat webhook delivery as at-least-once.
- Deduplicate by event ID/timestamp/resource key before side effects.
- Keep handlers safe to re-run.
