# Unreal Reference Map

## Sources

- Docs: https://developers.zoom.us/docs/meeting-sdk/unreal/
- API Reference: https://marketplacefront.zoom.us/sdk/meeting/unreal/MSDKUnrealSDKreferencedocs.html

## Crawl Coverage Snapshot

- Docs pages captured: `6`
- API reference pages captured: `1` (single consolidated mapping page)

## Reference Characteristics

- Lists many wrapper interfaces and controllers.
- Explicitly documents method availability across C++ and Blueprint wrappers.
- Notes wrapper modifications/new methods relative to base Meeting SDK behavior.
- Directs developers to Windows SDK reference for unchanged base semantics.

## Drift Signals to Watch

- Wrapper version lag relative to latest native platform SDK versions.
- Changed Blueprint node names/signatures across Unreal wrapper releases.
