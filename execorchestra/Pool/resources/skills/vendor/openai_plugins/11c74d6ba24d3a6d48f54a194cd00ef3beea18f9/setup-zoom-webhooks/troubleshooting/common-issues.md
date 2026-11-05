# Common Issues

Quick diagnostics for Zoom Webhooks integrations.

## Signature Verification Fails (401 / "Invalid signature")

**Common causes**:
- You are computing the HMAC over a **re-serialized** body (different whitespace/key order).
- You are using the wrong secret (webhook secret vs OAuth secret).
- You are not including the `v0:{timestamp}:{body}` prefix exactly.

**Fix**:
- Verify signatures using the exact raw request body bytes (capture raw body before JSON parsing).
- Validate both `x-zm-signature` and `x-zm-request-timestamp` and reject stale timestamps (replay protection).

See: [verification.md](../references/verification.md)

## Timeouts / Retries / Duplicate Events

**Symptom**: Zoom retries delivery, you process the same event multiple times.

**Fix**:
- Respond fast (acknowledge ASAP, then enqueue work).
- Make handlers idempotent (dedupe by event ID/timestamp + payload identifiers).

## URL Validation Fails

**Symptom**: You can’t enable the webhook endpoint in Marketplace; validation fails.

**Fix**:
- Implement `endpoint.url_validation` response correctly (plainToken + encryptedToken).

See: [verification.md](../references/verification.md)
