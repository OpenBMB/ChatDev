# Common Issues

Quick diagnostics for Zoom WebSockets event subscriptions.

## "Where Is the WebSocket URL?"

**Symptom**: You can’t find a generic `wss://...` endpoint that works for everyone.

**Reality**: Your connection is parameterized by your subscription (`subscriptionId`) and an access token.

See: [connection.md](../references/connection.md)

## Disconnects / Reconnect Loops

**Common causes**:
- Access token expired (typically ~1 hour).
- Single-connection limit per subscription (a new connection may close the previous one).
- No heartbeat/keep-alive handling in your client.

**Fix**:
- Refresh token proactively and reconnect with the new token.
- Implement exponential backoff (with jitter).
- Ensure only one active connection per subscription.

## No Events Received

**Common causes**:
- Subscribed event topics don’t match what you’re testing.
- App/subscription not enabled or not deployed as required by your account settings.

**Fix**:
- Confirm topics in Marketplace and generate an event you actually subscribed to.
- Log raw incoming messages and validate parsing.
