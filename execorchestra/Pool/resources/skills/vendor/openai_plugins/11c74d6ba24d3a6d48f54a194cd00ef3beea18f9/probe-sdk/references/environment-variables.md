# Probe SDK Environment Variables

Probe SDK does not require Zoom Marketplace credentials for core diagnostics.

## Required `.env` keys

- None required by the SDK itself.

## Optional `.env` keys (app-level conventions)

| Key | Required | Description | Where to find value |
|-----|----------|-------------|---------------------|
| `PROBE_JS_URL` | Optional | Override URL for probe runtime JS | Hosted by your app/infrastructure (or empty to use defaults) |
| `PROBE_WASM_URL` | Optional | Override URL for probe runtime WASM loader | Hosted by your app/infrastructure (or empty to use defaults) |
| `PROBE_DOMAIN` | Optional | Domain target for diagnostic probes | Usually `zoom.us` or your approved diagnostic domain |
| `PROBE_DURATION_MS` | Optional | Probe duration in milliseconds | Chosen by your product policy (defaults align with SDK guidance) |
| `PROBE_CONNECT_TIMEOUT_MS` | Optional | Probe connect timeout in milliseconds | Chosen by your product policy |

## Notes

- Because no OAuth credentials are required, Probe SDK is suitable as a lightweight preflight page before auth-sensitive flows.
- Do not require `ZOOM_CLIENT_ID`, `ZOOM_CLIENT_SECRET`, or account-level OAuth tokens for core Probe diagnostics.
- Keep optional URLs/versioning aligned with package version to avoid JS/WASM mismatch.
