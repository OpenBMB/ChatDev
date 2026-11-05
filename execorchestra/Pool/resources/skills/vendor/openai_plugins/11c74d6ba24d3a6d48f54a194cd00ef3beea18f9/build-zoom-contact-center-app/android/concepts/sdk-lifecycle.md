# Android SDK Lifecycle

## Startup

1. Initialize once in `Application.onCreate`.
2. Optionally set/update context user name before channel launch.

## Channel Initialization

1. Get service from `ZoomCCInterface`.
2. Build `ZoomCCItem` with:
- `sdkType`
- `entryId` or `apiKey`
- `serverType`
- campaign fields when needed
3. `service.init(item)`.
4. Add listener(s).

## Launch

1. Chat/ZVA:
- call `login()` then `fetchUI()`.
2. Video:
- configure preview/auto-join options as needed.
- call `fetchUI()`; login is typically internal for video flow.
3. Scheduled callback:
- init with `apiKey`.
- `fetchUI()`.

## End and Cleanup

1. End engagement (`endChat` / `endVideo`) when needed.
2. `logoff()` when you need to stop callbacks.
3. `releaseZoomCCService(key)` in teardown paths (`onDestroy`).

## Campaign Mode

1. Request campaigns with campaign API key.
2. Select channel from campaign metadata.
3. Reinitialize service using campaign-mode item.
4. Release or end conflicting channel services before switch.
