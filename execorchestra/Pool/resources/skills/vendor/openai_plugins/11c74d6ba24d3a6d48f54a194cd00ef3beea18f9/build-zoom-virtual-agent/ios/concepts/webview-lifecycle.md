# iOS WKWebView Lifecycle

1. Create `WKWebViewConfiguration` and `WKUserContentController`.
2. Add user scripts for context injection and bridge handlers.
3. Register message handlers before navigation.
4. Push/present webview controller with campaign URL.
5. Process callbacks in `userContentController:didReceiveScriptMessage:`.
6. Route navigation and external links in WKNavigation delegate callbacks.
7. Remove message handlers during teardown.
