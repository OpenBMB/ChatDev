# Android JS Bridge Patterns

## Inject Native Bridge

```kotlin
private fun injectJavaScriptFunction() {
    val js = """
        javascript: window.addEventListener('zoomCampaignSdk:ready', () => {
            if (window.zoomCampaignSdk) {
                window.zoomCampaignSdk.native = {
                    exitHandler: { handle: function() { AndroidExit.handleExit(); } },
                    commonHandler: { handle: function(e) { AndroidCommon.handleCommon(JSON.stringify(e)); } }
                };
            }
        });
    """.trimIndent()
    webView.loadUrl(js)
}
```

## Handoff Relay

```kotlin
private fun injectHandoffFunction() {
    val js = """
        javascript: window.addEventListener('support_handoff', (e) => {
            AndroidHandoff.handleHandoff(JSON.stringify(e.detail));
        });
    """.trimIndent()
    webView.loadUrl(js)
}
```

## URL Governance

- Use `shouldOverrideUrlLoading` for in-app vs system-browser policy.
- Use multi-window callbacks for `target="_blank"` handling.
