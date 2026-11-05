# iOS JS Bridge Patterns

## Inject Exit and Common Handlers

```swift
let exitHandlerScript = """
window.addEventListener('zoomCampaignSdk:ready', () => {
  if (window.zoomCampaignSdk) {
    window.zoomCampaignSdk.native = {
      exitHandler: { handle: function() { window.webkit.messageHandlers.zoomLiveSDKMessageHandler.postMessage('close_web_vc'); } },
      commonHandler: { handle: function(e) { window.webkit.messageHandlers.commonMessageHandler.postMessage(JSON.stringify(e)); } }
    };
  }
});
"""
```

## Inject Support Handoff

```swift
let handoffScript = """
window.addEventListener('support_handoff', (e) => {
  window.webkit.messageHandlers.support_handoff.postMessage(JSON.stringify(e.detail));
});
"""
```

## URL Handling Policy

- `WKNavigationActionPolicyAllow` for trusted in-app routes.
- `UIApplication.openURL` for system-browser policy.
- Optional in-app browser route (for example `SFSafariViewController`).
