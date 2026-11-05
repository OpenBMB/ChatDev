# RTMS 5-Minute Preflight Runbook

Use this before deep debugging. It catches the highest-frequency RTMS issues fast.

## Skill Doc Standard Note

- Agent-skill standard entrypoint is `SKILL.md`.
- This runbook is an operational convention (recommended), not a required skill file.
- `SKILL.md` is also a navigation convention for larger skill docs.

## 1) Confirm Architecture Assumption

- RTMS is backend-first media ingestion.
- Frontend is optional and should consume backend outputs (WebSocket/SSE/etc).

If implementation assumes frontend-only RTMS behavior, redesign first.

## 2) Confirm Event-Triggered Kickoff

- Processing starts only after RTMS lifecycle start events:
  - `meeting.rtms_started`
  - `webinar.rtms_started`
  - `session.rtms_started`
- Stop events should deactivate pipeline.

If media handling starts before lifecycle start, session gating is wrong.

## 3) Confirm Product-Specific IDs

- Meetings/Webinars: use `meeting_uuid`
- Video SDK: use `session_id`
- Use `rtms_stream_id` from payload for stream context

Using wrong ID field commonly breaks handshake/signature.

## 4) Confirm Webhook Handling Pattern

- Respond `200` immediately.
- Do heavy work asynchronously.
- Verify webhook signature if secret token is configured.

Slow webhook responses can trigger retries and duplicate stream attempts.

## 5) Confirm Connection and Heartbeat

- Track one active connection per stream/session reference.
- Handle heartbeat ping/pong per protocol.
- Implement reconnection strategy explicitly.

No heartbeat handling means unexpected disconnects.

## 6) Confirm Media Subscription/Gating

- Ensure requested media types match your processing path.
- Reject/ignore media packets for inactive sessions.
- Expose pipeline status endpoint for observability.

This avoids silent packet handling when lifecycle is not active.

## 7) Quick Probe Checklist

- `GET /api/health` returns service alive.
- `GET /api/pipeline/status` shows expected active session count.
- Mock/media probes show:
  - media before start -> rejected
  - start event -> pipeline active
  - media after start -> accepted

### Copy/Paste Validation Commands

```bash
curl -sS "$RTMS_BASE_URL/api/health"
curl -sS "$RTMS_BASE_URL/api/pipeline/status"
```

Expected: healthy service JSON and correct active pipeline visibility.

## 8) Fast Decision Tree

- **No media at all** -> lifecycle event not received or wrong webhook route.
- **Duplicate streams** -> delayed webhook response or no active-session guard.
- **Handshake/auth errors** -> wrong credential pair or wrong session ID field.
- **Frontend appears idle** -> backend bridge not connected, not an RTMS source issue.
