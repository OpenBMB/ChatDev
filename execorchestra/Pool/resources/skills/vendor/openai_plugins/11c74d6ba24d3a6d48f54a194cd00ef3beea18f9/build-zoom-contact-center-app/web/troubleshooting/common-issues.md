# Web Common Issues

## `zoomCampaignSdk` Is Undefined

Cause:
- Calls happen before readiness event.

Fix:
- Wait for `zoomCampaignSdk:ready` before calling SDK methods.

## Widget Does Not Load

Cause:
- CSP or domain allow-list blocks script/network access.

Fix:
- Update CSP headers and Marketplace domain allow list entries.

## App Context Header Missing in PWA

Cause:
- PWA path does not provide `x-zoom-app-context` header consistently.

Fix:
- Use `getAppContext()` and backend token decryption flow.

## Engagement Data Gets Overwritten

Cause:
- State keyed globally instead of by `engagementId`.

Fix:
- Persist and restore state per engagement key.

## Smart Embed Events Not Received

Cause:
- postMessage listener origin/type filtering missing or incorrect.

Fix:
- Implement strict message handling and respond to required init/search events.
