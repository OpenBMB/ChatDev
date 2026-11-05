# iOS Common Issues

## Service Starts But View Never Appears

Cause:
- Missing `fetchUI` handling or wrong navigation presentation path.

Fix:
- Ensure returned view controller is pushed/presented on main thread.

## App Background/Foreground Breaks Session

Cause:
- App lifecycle callbacks not forwarded to SDK.

Fix:
- Wire app delegate lifecycle methods to `ZoomCCInterface`.

## Rejoin URL Arrives But Rejoin Fails

Cause:
- URL scheme mismatch or context not initialized.

Fix:
- Verify URL types config, rejoin URL settings, and context setup before calling rejoin API.

## Duplicate or Stale Channel Sessions

Cause:
- Previous service instance left active during channel switches.

Fix:
- End current engagement and rebuild service item when changing channel/campaign context.

## Error Callback Signature Drift

Cause:
- Implemented only deprecated callback signature.

Fix:
- Implement `onService:error:detail:description:` and keep compatibility wrappers as needed.
