# Android Common Issues

## SDK Works Inconsistently Across Screens

Cause:
- SDK initialized too late.

Fix:
- Initialize in `Application.onCreate`.

## `NoClassDefFoundError` / viewBinding Errors

Cause:
- Missing expected dependencies or view binding configuration.

Fix:
- Match SDK package module requirements.
- Ensure build config aligns with current SDK release notes.

## Video/Chat UI Does Not Open

Cause:
- Wrong identifier type in `ZoomCCItem`.

Fix:
- `entryId` for chat/video/ZVA.
- `apiKey` for scheduled callback/campaign.

## Events Not Firing

Cause:
- Listener attached after service launch or removed early.

Fix:
- Add listeners before `fetchUI`.

## Rejoin Link Opens Browser But Not App

Cause:
- Deep-link host/scheme mismatch.

Fix:
- Align Android manifest intent filters with generated rejoin URL format.
