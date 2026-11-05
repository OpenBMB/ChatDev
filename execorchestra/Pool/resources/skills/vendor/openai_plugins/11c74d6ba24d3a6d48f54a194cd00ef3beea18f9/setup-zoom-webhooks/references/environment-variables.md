# Zoom Webhooks Environment Variables

## Standard `.env` keys

| Variable | Required | Used for | Where to find |
| --- | --- | --- | --- |
| `ZOOM_WEBHOOK_SECRET` | Yes | HMAC signature verification for webhook payloads | Zoom Marketplace -> Event Subscriptions -> Secret Token |
| `WEBHOOK_SECRET_TOKEN` | Alias | Same secret token under alternate naming | Same as above |
| `ZOOM_VERIFICATION_TOKEN` | Legacy only | Legacy endpoint verification | Marketplace legacy field (older app configs) |

## Notes

- Prefer `ZOOM_WEBHOOK_SECRET` / Secret Token for current implementations.
- Keep webhook secret in server-side secret storage only.
