# Android Common Issues

## Bridge Callback Never Fires

- Ensure JS bridge injection runs after page load and SDK readiness.
- Ensure `addJavascriptInterface` names match injected handler names.

## Link Opens in Wrong Context

- Implement both `shouldOverrideUrlLoading` and multi-window behavior.
- Distinguish `_self` and `_blank` paths explicitly.

## Deprecated `openURL` Path

- Avoid relying on `{"cmd":"openURL"...}` as primary flow.
- Prefer anchor or `window.open` plus native interception policy.

## Campaign Works on Web but Not Mobile

- Verify campaign targeting includes mobile.
- Verify same API key/env pair used in WebView build.
