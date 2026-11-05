# Android WebView Lifecycle

1. Build intent with URL and policy flags.
2. Configure WebView (`JavaScriptEnabled`, optional multi-window support).
3. Inject user context config before page interaction.
4. Inject bridge script on `zoomCampaignSdk:ready`.
5. Handle callbacks via `@JavascriptInterface`.
6. Route URL actions and handoff payloads.
7. Close view and clean references on exit.
