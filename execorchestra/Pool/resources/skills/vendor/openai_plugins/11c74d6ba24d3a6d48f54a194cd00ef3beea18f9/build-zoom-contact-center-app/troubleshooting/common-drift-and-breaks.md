# Common Drift and Breaks

## Symptom: Engagement Context Missing

Likely causes:
- App is not running in Contact Center context.
- Missing SDK capabilities in `config`.
- Identity/context token path is incomplete.

Checks:
1. Confirm running context.
2. Confirm capabilities include engagement APIs/events.
3. Confirm app manifest and feature toggles.

## Symptom: Campaign SDK Methods Throw

Likely causes:
- Calling methods before `zoomCampaignSdk:ready`.
- Invalid API key or missing campaign configuration.
- Script blocked by CSP/ad-blockers/tag-manager path.

Checks:
1. Add ready gate before method calls.
2. Validate key/env and script URL.
3. Validate CSP/domain allow lists.

## Symptom: Native Service Not Responding

Likely causes:
- SDK init executed too late.
- Wrong channel item (`entryId` vs `apiKey` mismatch).
- Listeners/delegates attached after service start.

Checks:
1. Move init earlier in app lifecycle.
2. Validate item/channel pairing.
3. Register listeners before `fetchUI`.

## Symptom: Rejoin Flow Fails

Likely causes:
- Deep link scheme/host mismatch.
- Rejoin URL or web relay page not configured.
- App lifecycle hooks/context not initialized.

Checks:
1. Verify platform URL/deep link configuration.
2. Verify admin rejoin settings.
3. Verify rejoin handler wiring.

## Symptom: Behavior Changed After Release

Likely causes:
- Minimum version enforcement date reached.
- Deprecated callback removed or changed.
- New SDK defaults in channel behavior.

Checks:
1. Confirm SDK version in production.
2. Review changelog/deprecation notes.
3. Add adapter guards for optional fields/methods.
