# Zoom Cobrowse SDK Environment Variables

## Standard `.env` keys

| Variable | Required | Used for | Where to find |
| --- | --- | --- | --- |
| `ZOOM_SDK_KEY` | Yes | SDK identity | Zoom Marketplace -> Cobrowse/Contact Center SDK app -> App Credentials |
| `ZOOM_SDK_SECRET` | Yes | SDK auth signing | Zoom Marketplace -> Cobrowse/Contact Center SDK app -> App Credentials |
| `COBROWSE_BASE_URL` | Optional | Regional/tenant SDK endpoint override | Cobrowse SDK documentation or tenant provisioning details |

## Runtime-only values

- `ZOOM_COBROWSE_SESSION_TOKEN`

If your implementation mints short-lived tokens, store them in memory/cache only.

## Notes

- Keep `ZOOM_SDK_SECRET` server-side.
- Some samples use aliases (`SDK_KEY`, `SDK_SECRET`); normalize internally.
