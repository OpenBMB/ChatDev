# Samples Validation

Validated repositories:
- https://github.com/zoom/virtual-assistant-android-sample
- https://github.com/zoom/virtual-assistant-iOS-sample

Latest commit observed during validation:
- Android sample: `faab2b6` (2024-10-16), commit message references `OpenUrl` deprecation.
- iOS sample: `dd31e95` (2024-10-16), commit message references URL opening method update.

## Confirmed Relevant Patterns

- `zoomCampaignSdk:ready` event gating before native bridge registration.
- `window.zoomCampaignSdk.native.exitHandler/commonHandler` bridge contract.
- `support_handoff` event forwarding from JavaScript to native.
- WebView URL policy split between in-app browsing and system browser.

## Contradictions and Caveats

- Samples still document legacy command contract (`{"cmd":"openURL","value":"..."}`) while marking it deprecated.
- Naming in sample classes uses "LiveSDK" and "Virtual Assistant" while docs use "Virtual Agent".
- Treat sample repos as implementation patterns, not canonical naming source.
