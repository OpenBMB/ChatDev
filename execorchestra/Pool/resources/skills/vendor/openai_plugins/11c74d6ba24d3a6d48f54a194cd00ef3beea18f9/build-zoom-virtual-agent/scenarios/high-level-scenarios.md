# High-Level Scenarios

## 1. Website Campaign Entry

- Use campaign embed snippet to control initial bot routing without code redeploys.
- Use `show()/hide()/open()/close()` for page-specific behavior.

## 2. Native Mobile Wrapper (Android/iOS)

- Host campaign URL in WebView/WKWebView.
- Inject customer context (`language`, name, profile fields).
- Route exit and handoff messages into native app state.

## 3. Bot-to-Agent Escalation

- Listen for `support_handoff` payload.
- Persist payload to backend for CRM/ticket enrichment.
- Route customer into live support workflow.

## 4. URL Navigation Governance

- Open trusted links inside app.
- Send external links to system browser when policy requires.
- Handle `target="_blank"` and `window.open` explicitly.

## 5. Knowledge-Base Sync Pipeline

- Use web sync for crawlable documentation.
- Use custom API connector for external CMS pull/push synchronization.
- Re-run sync on content release cadence.
