# Zoom RTMS Environment Variables

## Standard `.env` keys

| Variable | Required | Used for | Where to find |
| --- | --- | --- | --- |
| `ZOOM_CLIENT_ID` | OAuth mode | RTMS subscription/auth (Meetings/Webinars mode) | Zoom Marketplace -> OAuth app credentials |
| `ZOOM_CLIENT_SECRET` | OAuth mode | RTMS subscription/auth (Meetings/Webinars mode) | Zoom Marketplace -> OAuth app credentials |
| `ZOOM_ACCOUNT_ID` | S2S OAuth mode | Account-level RTMS token grants | Zoom Marketplace -> Server-to-Server OAuth app credentials |
| `ZOOM_VIDEO_SDK_KEY` | Video SDK RTMS mode | RTMS with Video SDK sessions | Zoom Marketplace -> Video SDK app credentials |
| `ZOOM_VIDEO_SDK_SECRET` | Video SDK RTMS mode | Video SDK session auth/signing | Zoom Marketplace -> Video SDK app credentials |
| `ZOOM_SECRET_TOKEN` or `WEBHOOK_SECRET_TOKEN` | Yes when validating events | Event signature verification | Zoom Marketplace -> Event Subscriptions -> Secret Token |

## Connection tuning (optional)

- `RTMS_CONNECTION_TIMEOUT_MS`
- `RTMS_CONNECTION_MAX_ATTEMPTS`
- `RTMS_CONNECTION_RETRY_DELAY_MS`
- `RTMS_RECONNECT_MAX_ATTEMPTS`
- `RTMS_RECONNECT_BASE_DELAY_MS`
- `RTMS_KEEPALIVE_INTERVAL_MS`
- `RTMS_KEEPALIVE_TIMEOUT_MS`

## Notes

- Choose one credential mode per deployment: OAuth or Video SDK credentials.
