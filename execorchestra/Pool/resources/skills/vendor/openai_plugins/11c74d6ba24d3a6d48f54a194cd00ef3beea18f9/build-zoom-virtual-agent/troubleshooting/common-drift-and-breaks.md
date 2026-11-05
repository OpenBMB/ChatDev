# Common Drift and Breaks

## SDK Not Ready

Symptoms:
- `window.zoomCampaignSdk` is undefined.

Fix:
- Register logic only after `zoomCampaignSdk:ready`.
- Prefer `waitForReady()` when available.

## Campaign Configured but Not Showing

Checks:
- Confirm campaign targeting includes mobile when using Android/iOS WebView.
- Validate style/config API network responses.

## Subdomain/Login Failures

Symptoms:
- Login fails due to subdomain connection issue.

Fix:
- Verify subdomain allowlist and environment settings in Virtual Agent preferences.

## Script Tag Loads Inconsistently

Cause:
- `defer` can break execution order in certain third-party-link flows.

Fix:
- Remove `defer` or use `async` based on page lifecycle.

## Deprecated URL Command Usage

Symptoms:
- Legacy `openURL` command path behaves unpredictably across versions.

Fix:
- Use DOM links (`target="_blank"`) or `window.open` and explicit native navigation handlers.
