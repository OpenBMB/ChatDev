# Samples Validation Summary

This summary captures lifecycle and architecture checks against these references:

- Web:
- https://github.com/zoom/ZCC-Zoom-App-Advanced-Sample
- https://github.com/zoom/zcc-javascript-quickstart
- https://github.com/zoom/zcc-nextjs-sample
- iOS package: `ios-zccsdk-5.2.0.zip`
- Android package: `android-zccsdk-5.2.0.zip`

## Confirmed Lifecycle Patterns

1. Contact Center App (Zoom Apps SDK):
- Configure capabilities.
- Query engagement context/status.
- Subscribe to engagement change events.
- Persist state by `engagementId`.

2. Android Native:
- Initialize in `Application.onCreate`.
- Service `init` with `ZoomCCItem`.
- Use `fetchUI` to present channel.
- `logoff` and `releaseZoomCCService` on cleanup.

3. iOS Native:
- Set `ZoomCCInterface.sharedInstance().context`.
- Initialize service with item.
- Use `fetchUI` to present.
- Forward app lifecycle callbacks to SDK.
- Use rejoin handler path for video reconnect.

## Contradictions and Drift Signals

- Some docs show simplified `service.init("EntryId")` signatures while current references emphasize item-based initialization.
- iOS deprecated error callback still appears in older sample/docs.
- Some public sample manifests contain values that conflict with expected Contact Center embedding configuration and should be reviewed per environment.
- Scraped reference pages include parser artifacts (`TODO`/error pages) and should not be treated as canonical API surfaces.

## Operational Guidance

- Treat samples as architecture guidance, not immutable source of truth.
- Resolve conflicts in this order:
1. Current official docs.
2. Current platform API reference.
3. Latest shipped SDK headers/binaries.
4. Samples.
