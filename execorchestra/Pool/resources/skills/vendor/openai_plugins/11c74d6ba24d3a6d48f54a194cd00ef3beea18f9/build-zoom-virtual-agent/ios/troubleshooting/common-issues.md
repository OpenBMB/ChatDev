# iOS Common Issues

## Message Handlers Not Triggering

- Ensure `WKUserScript` and handlers are registered before page load.
- Verify handler names exactly match injected JS references.

## URL Opens Unexpectedly

- Explicitly branch in `decidePolicyForNavigationAction`.
- Handle `_blank`/`window.open` paths as separate cases.

## Deprecated `openURL` Command Drift

- Treat command-based open URL as fallback.
- Prefer DOM links and `window.open` with delegate-driven routing.

## File Download Inconsistency

- Download behavior via WKWebView requires iOS 14.5+ support paths.
