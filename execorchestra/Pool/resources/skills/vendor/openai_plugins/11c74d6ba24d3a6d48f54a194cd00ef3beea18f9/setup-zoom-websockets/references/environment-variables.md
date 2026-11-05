# Zoom WebSockets Environment Variables

## Standard `.env` keys

| Variable | Required | Used for | Where to find |
| --- | --- | --- | --- |
| `ZOOM_CLIENT_ID` | Yes | OAuth app identity for WebSocket subscriptions | Zoom Marketplace -> OAuth app -> App Credentials |
| `ZOOM_CLIENT_SECRET` | Yes | OAuth app secret | Zoom Marketplace -> OAuth app -> App Credentials |
| `ZOOM_ACCOUNT_ID` | S2S OAuth mode | Account-level token grant for service apps | Zoom Marketplace -> Server-to-Server OAuth app credentials |
| `ZOOM_SUBSCRIPTION_ID` | After setup | Persisted subscription identifier for reconnect/resume | Returned by subscription create API response |

## Runtime-only values

- `ZOOM_ACCESS_TOKEN`

## Notes

- `ZOOM_SUBSCRIPTION_ID` is not from Marketplace UI; your app stores it after calling the subscription API.
