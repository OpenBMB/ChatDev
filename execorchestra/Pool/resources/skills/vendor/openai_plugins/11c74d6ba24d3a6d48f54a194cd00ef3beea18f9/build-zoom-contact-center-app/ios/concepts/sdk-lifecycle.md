# iOS SDK Lifecycle

## Context Initialization

1. Create `ZoomCCContext`.
2. Configure user name, cache folder, and optional share settings.
3. Set context on `ZoomCCInterface.sharedInstance()`.

## Service Initialization Pattern

1. Build `ZoomCCItem`.
2. Select channel type:
- `.chat`
- `.video`
- `.ZVA`
- `.scheduledCallback`
3. Populate `entryId` or `apiKey` depending on channel.
4. Get service instance.
5. Set delegate.
6. Call `initialize(with:)`.
7. Call `login()` where required.
8. `fetchUI` and push returned view controller.

## Lifecycle Bridging

Forward these app delegate callbacks:
- `applicationDidBecomeActive` -> `appDidBecomeActive`
- `applicationWillResignActive` -> `appWillResignActive`
- `applicationDidEnterBackground` -> `appDidEnterBackgroud`
- `applicationWillTerminate` -> `appWillTerminate`

## Rejoin Flow

1. Configure app URL scheme and admin rejoin URL.
2. Forward `open url` callback to rejoin handler.
3. Call video service rejoin API with prepared `ZoomCCItem`.
4. Push returned view controller in completion block.

## Cleanup

- End service-specific engagement methods:
- `endChat`
- `endVideo`
- `endScheduledCallback`
- Use service `logout` / uninitialize patterns when needed by flow design.
