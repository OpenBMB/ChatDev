# WebSockets 5-Minute Preflight Runbook

Use this before deep debugging. It catches common Zoom WebSockets failures quickly.

## Skill Doc Standard Note

- Agent-skill standard entrypoint is `SKILL.md`.
- This runbook is an operational convention (recommended), not a required skill file.
- `SKILL.md` is also a navigation convention for larger skill docs.

## 1) Confirm OAuth Token Generation

- Use S2S credentials and account ID.
- Token endpoint: `https://zoom.us/oauth/token`.
- Refresh token before expiry.

### Token Sanity Checks

- Verify token response is JSON and contains `access_token`.
- Record token expiry and refresh proactively.
- If auth intermittently fails, check for clock skew and stale cached tokens.

## 2) Confirm Subscription Configuration

- Event subscription created with WebSockets delivery type.
- Required event types selected and saved.

## 3) Confirm Connection URL and Auth

- Use exact WebSocket URL from Zoom subscription config.
- Attach access token as required by protocol/headers.

## 4) Confirm Runtime Reliability

- Implement reconnect with backoff.
- Handle heartbeat/ping-pong and connection lifecycle events.
- Prevent duplicate consumers if multiple workers run.

### Minimal Reliability Policy

- Backoff: exponential with jitter.
- Cap retries and alert after sustained failures.
- Ensure only one active consumer per subscription stream in each environment.

## 5) Confirm Event Processing Semantics

- Handle ordering assumptions carefully.
- Make event handlers idempotent.
- Log event IDs and delivery timestamps.

## 6) Quick Probes

- Access token request succeeds and returns JSON.
- WebSocket connects and receives at least one subscribed event.
- Reconnect path works after forced disconnect.

### Copy/Paste Validation Commands

```bash
# 1) Validate S2S token request
curl -X POST "https://zoom.us/oauth/token" \
  -H "Authorization: Basic $(printf '%s:%s' "$ZOOM_CLIENT_ID" "$ZOOM_CLIENT_SECRET" | base64)" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=account_credentials&account_id=$ZOOM_ACCOUNT_ID"

# 2) Basic Zoom API probe with token
curl -X GET "https://api.zoom.us/v2/users/me" \
  -H "Authorization: Bearer $ZOOM_ACCESS_TOKEN"

# 3) Tail app logs while forcing reconnect tests
pm2 logs your-websocket-service --lines 120
```

Expected: token/API probes return JSON; websocket service logs show connect -> receive -> reconnect sequence.

## 7) Fast Decision Tree

- **Connection refused/closed** -> token invalid, wrong URL, or subscription config issue.
- **Connected but no events** -> wrong event selection or no triggering activity.
- **Event storms/duplicates** -> missing dedupe/idempotency logic.

## 8) WebSockets vs Webhooks Guardrail

- If your use case does not need persistent low-latency delivery, webhook delivery may be simpler to operate.
- Choose WebSockets when you can own connection lifecycle monitoring and reconnect behavior.
