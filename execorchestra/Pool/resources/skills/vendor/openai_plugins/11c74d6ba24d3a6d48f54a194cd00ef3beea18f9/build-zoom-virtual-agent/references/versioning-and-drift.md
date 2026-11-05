# Versioning and Drift

## Naming Drift

- Current docs and product naming: **Virtual Agent**.
- Sample repo naming still includes legacy terms: **virtual-assistant**, **liveSDK**, `ZMLiveSDKWebviewController`.
- Integration code should follow current docs semantics while mapping legacy symbol names from samples.

## Deprecated or Legacy Patterns

- `openURL` command JSON payload is marked deprecated in 2024 sample code comments.
- Preferred URL launch patterns:
  - DOM anchor links with `target="_blank"`.
  - `window.open()` in JavaScript context.
  - Native URL interception in WebView delegates.

## Stability Strategy

- Wrap SDK calls behind readiness gates.
- Centralize bridge constants so command/event renames are isolated.
- Keep fallback path for legacy keys only where backward compatibility is required.
