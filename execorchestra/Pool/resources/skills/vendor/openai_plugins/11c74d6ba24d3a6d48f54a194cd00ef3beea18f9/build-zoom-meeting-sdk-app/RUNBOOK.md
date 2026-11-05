# Meeting SDK 5-Minute Preflight Runbook

Use this before deep debugging. It catches high-frequency Meeting SDK failures quickly.

## Skill Doc Standard Note

- Agent-skill standard entrypoint is `SKILL.md`.
- This runbook is an operational convention (recommended), not a required skill file.
- `SKILL.md` is also a navigation convention for larger skill docs.

## 1) Confirm Integration Mode

- Web Client View (CDN/global `ZoomMtg`) or Web Component View (npm `ZoomMtgEmbedded`).
- Do not mix APIs between modes.

## 2) Confirm Signature Path

- Generate signature server-side with SDK Secret.
- Never expose SDK Secret in browser code.
- Confirm `meetingNumber` and `role` in signature payload match join request.

## 3) Confirm Join Payload Hygiene

- Pass only valid values; avoid undefined optional fields.
- Ensure meeting number is normalized as digits string.
- If rendering issues appear, test with safer default view settings.

## 4) Confirm Browser + Security Prereqs

- If using advanced media features, validate cross-origin isolation setup (COOP/COEP) when required.
- Avoid global CSS resets that break Zoom UI layouts.
- Ensure page overlays/z-index do not hide meeting container.

## 5) Confirm Routing and Base Path

- Signature endpoint must be reachable from frontend (same origin proxy recommended).
- In subpath deployments, verify fetch URLs and reverse proxy rewrites.

## 6) Quick Probes

- Signature endpoint returns JSON with non-empty signature.
- Join call returns actionable SDK errors (not generic 404 HTML).
- Browser console has no obvious mixed-content/CORS blocks.

### Copy/Paste Validation Commands

```bash
# 1) Verify signature endpoint responds with JSON
curl -sS -i "$MEETING_SDK_BASE_URL/api/signature"

# 2) Verify app page is reachable and returns HTML
curl -sS -i "$MEETING_SDK_BASE_URL"
```

Expected: endpoints return valid JSON/HTML (not generic 404/502 pages).

## 7) Fast Decision Tree

- **Black/blank UI** -> check CSS/z-index, mode mismatch, and payload field hygiene.
- **Join fails quickly** -> signature payload mismatch or expired signature.
- **Intermittent load issues** -> cross-origin isolation or browser extension interference.

## 8) SDK Selection Guardrail

- Use Meeting SDK when embedding Zoom meeting experiences.
- Use Video SDK when building fully custom video UX.

## 9) Wrong-Path Detector (SDK vs REST)

- If implementation is producing `join_url` links instead of SDK join calls, you are on REST path.
- If code depends on `GET/POST /v2/meetings` but user asked for embedded in-app join UX, you are on wrong path.
- For Meeting SDK MVP, require: signature endpoint + frontend `ZoomMtg`/`ZoomMtgEmbedded` join.
