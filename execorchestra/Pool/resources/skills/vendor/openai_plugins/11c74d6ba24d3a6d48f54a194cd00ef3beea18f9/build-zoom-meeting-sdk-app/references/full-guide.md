# /build-zoom-meeting-sdk-app

Background reference for embedded Zoom meetings across web, mobile, desktop, and Linux bot environments. Prefer `build-zoom-meeting-app` or `build-zoom-bot` first, then route here for platform detail.

# Zoom Meeting SDK

Embed the full Zoom meeting experience into web, mobile, desktop, and headless integrations.

## Hard Routing Guardrail (Read First)

- If the user asks to embed/join meetings inside their app UI, route to Meeting SDK implementation.
- Do not switch to REST-only meeting link flow unless the user explicitly asks for meeting resource management or browser `join_url` links.
- Meeting SDK join path requires SDK signature + SDK join call; REST `join_url` is not a Meeting SDK join payload.

## Prerequisites

- Zoom app with Meeting SDK credentials
- SDK Key and Secret from Marketplace
- Platform-specific development environment (Web, Android, iOS, macOS, Unreal, Electron, Linux, or Windows)

> **Need help with OAuth or signatures?** See the **[zoom-oauth](../../oauth/SKILL.md)** skill for authentication flows.

> **Need pre-join diagnostics on web?** Use **[probe-sdk](../../probe-sdk/SKILL.md)** before Meeting SDK init/join to gate low-readiness devices/networks.

> **Start troubleshooting fast:** Use the **[5-Minute Runbook](../RUNBOOK.md)** before deep debugging.

## Quick Start (Web - Client View via CDN)

```html
<script src="https://source.zoom.us/3.1.6/lib/vendor/react.min.js"></script>
<script src="https://source.zoom.us/3.1.6/lib/vendor/react-dom.min.js"></script>
<script src="https://source.zoom.us/3.1.6/lib/vendor/redux.min.js"></script>
<script src="https://source.zoom.us/3.1.6/lib/vendor/redux-thunk.min.js"></script>
<script src="https://source.zoom.us/3.1.6/lib/vendor/lodash.min.js"></script>
<script src="https://source.zoom.us/3.1.6/zoom-meeting-3.1.6.min.js"></script>

<script>
// CDN provides ZoomMtg (Client View - full page)
// For ZoomMtgEmbedded (Component View), use npm instead

ZoomMtg.preLoadWasm();
ZoomMtg.prepareWebSDK();

ZoomMtg.init({
  leaveUrl: window.location.href,
  patchJsMedia: true,
  disableCORP: !window.crossOriginIsolated,
  success: function() {
    ZoomMtg.join({
      sdkKey: 'YOUR_SDK_KEY',
      signature: 'YOUR_SIGNATURE',  // Generate server-side!
      meetingNumber: 'MEETING_NUMBER',
      userName: 'User Name',
      passWord: '',  // Note: camelCase with capital W
      success: function(res) { console.log('Joined'); },
      error: function(err) { console.error(err); }
    });
  },
  error: function(err) { console.error(err); }
});
</script>
```

## Critical Notes (Web)

### 1. CDN vs npm - Different APIs!

| Distribution | Global Object | View Type | API Style |
|--------------|---------------|-----------|-----------|
| CDN (`zoom-meeting-{ver}.min.js`) | `ZoomMtg` | Client View (full-page) | Callbacks |
| npm (`@zoom/meetingsdk`) | `ZoomMtgEmbedded` | Component View (embeddable) | Promises |

### 2. Backend Required for Production

**Never expose SDK Secret in client code.** Generate signatures server-side:

```javascript
// server.js (Node.js example)
const KJUR = require('jsrsasign');

app.post('/api/signature', (req, res) => {
  const { meetingNumber, role } = req.body;
  const iat = Math.floor(Date.now() / 1000) - 30;
  const exp = iat + 60 * 60 * 2;

  const header = { alg: 'HS256', typ: 'JWT' };
  const payload = {
    sdkKey: process.env.ZOOM_SDK_KEY,
    mn: String(meetingNumber).replace(/\D/g, ''),
    role: parseInt(role, 10),
    iat, exp, tokenExp: exp
  };

  const signature = KJUR.jws.JWS.sign('HS256',
    JSON.stringify(header),
    JSON.stringify(payload),
    process.env.ZOOM_SDK_SECRET
  );

  res.json({ signature, sdkKey: process.env.ZOOM_SDK_KEY });
});
```

### 3. CSS Conflicts - Avoid Global Resets

Global `* { margin: 0; }` breaks Zoom's UI. Scope your styles:

```css
/* BAD */
* { margin: 0; padding: 0; }

/* GOOD */
.your-app, .your-app * { box-sizing: border-box; }
```

### 4. Client View Toolbar Cropping Fix

If toolbar falls off screen, scale down the Zoom UI:

```css
#zmmtg-root {
  position: fixed !important;
  top: 0 !important;
  left: 0 !important;
  right: 0 !important;
  bottom: 0 !important;
  width: 100vw !important;
  height: 100vh !important;
  /* Critical for SPAs (React/Next/etc): ensure Zoom UI isn't behind your app shell/overlays. */
  z-index: 9999 !important;
  transform: scale(0.95) !important;
  transform-origin: top center !important;
}
```

### 5. Hide Your App When Meeting Starts

Client View takes over full page. Hide your UI:

```javascript
// In ZoomMtg.init success callback:
document.documentElement.classList.add('meeting-active');
document.body.classList.add('meeting-active');
```

```css
body.meeting-active .your-app { display: none !important; }
body.meeting-active { background: #000 !important; }
```

## UI Options (Web)

Meeting SDK provides **Zoom's UI with customization options**:

| View | Description |
|------|-------------|
| **Component View** | Extractable, customizable UI - embed meeting in a div |
| **Client View** | Full-page Zoom UI experience |

**Note**: Unlike Video SDK where you build the UI from scratch, Meeting SDK uses Zoom's UI as the base with customization on top.

## Key Concepts

| Concept | Description |
|---------|-------------|
| SDK Key/Secret | Credentials from Marketplace |
| Signature | JWT signed with SDK Secret |
| Component View | Extractable, customizable UI (Web) |
| Client View | Full-page Zoom UI (Web) |

## Detailed References

### Platform Guides
- **[android/SKILL.md](../android/SKILL.md)** - Android SDK (default/custom UI, join/start/auth lifecycle, mobile integration)
- **[android/references/android-reference-map.md](../android/references/android-reference-map.md)** - Android API surface map and drift watchpoints
- **[ios/SKILL.md](../ios/SKILL.md)** - iOS SDK (default/custom UI, join/start/auth lifecycle, mobile integration)
- **[ios/references/ios-reference-map.md](../ios/references/ios-reference-map.md)** - iOS API surface map and drift watchpoints
- **[macos/SKILL.md](../macos/SKILL.md)** - macOS SDK (desktop default/custom UI, service controllers, host flows)
- **[macos/references/macos-reference-map.md](../macos/references/macos-reference-map.md)** - macOS API surface map and drift watchpoints
- **[unreal/SKILL.md](../unreal/SKILL.md)** - Unreal Engine wrapper (C++/Blueprint wrapper behavior and SDK mapping)
- **[unreal/references/unreal-reference-map.md](../unreal/references/unreal-reference-map.md)** - Unreal wrapper reference map and version-lag notes
- **[references/android.md](../references/android.md)** - Android pointer doc for fast routing from broad Meeting SDK queries
- **[references/ios.md](../references/ios.md)** - iOS pointer doc for fast routing from broad Meeting SDK queries
- **[references/macos.md](../references/macos.md)** - macOS pointer doc for fast routing from broad Meeting SDK queries
- **[references/unreal.md](../references/unreal.md)** - Unreal pointer doc for fast routing from broad Meeting SDK queries
- **[linux/SKILL.md](../linux/SKILL.md)** - Linux SDK headless bot skill entrypoint
- **[linux/linux.md](../linux/linux.md)** - Linux SDK (C++ headless bots, raw media access)
- **[linux/references/linux-reference.md](../linux/references/linux-reference.md)** - Linux dependencies, Docker, troubleshooting
- **[react-native/SKILL.md](../react-native/SKILL.md)** - React Native SDK (iOS/Android wrapper, join/start flows, bridge setup)
- **[react-native/SKILL.md](../react-native/SKILL.md)** - React Native complete navigation
- **[electron/SKILL.md](../electron/SKILL.md)** - Electron SDK (desktop wrapper, auth/join flows, module controllers, raw data)
- **[electron/SKILL.md](../electron/SKILL.md)** - Electron complete navigation
- **[windows/SKILL.md](../windows/SKILL.md)** - Windows SDK (C++ desktop applications, raw media access)
- **[windows/references/windows-reference.md](../windows/references/windows-reference.md)** - Windows dependencies, Visual Studio setup, troubleshooting
- **[web/references/web.md](../web/references/web.md)** - Web SDK (Component + Client View)
- **[web/references/web-tracking-id.md](../web/references/web-tracking-id.md)** - Tracking ID configuration

### Features
- **[references/authorization.md](../references/authorization.md)** - SDK JWT generation
- **[references/bot-authentication.md](../references/bot-authentication.md)** - ZAK vs OBF vs JWT tokens for bots
- **[references/breakout-rooms.md](../references/breakout-rooms.md)** - Programmatic breakout room management
- **[references/ai-companion.md](../references/ai-companion.md)** - AI Companion controls in meetings
- **[references/webinars.md](../references/webinars.md)** - Webinar SDK features
- **[references/forum-top-questions.md](../references/forum-top-questions.md)** - Common forum question patterns (what to cover)
- **[references/triage-intake.md](../references/triage-intake.md)** - What to ask first (turn vague reports into answers)
- **[references/signature-playbook.md](../references/signature-playbook.md)** - Signature/root-cause playbook
- **[references/multiple-meetings.md](../references/multiple-meetings.md)** - Joining multiple meetings / multiple instances
- **[references/troubleshooting.md](../references/troubleshooting.md)** - Common issues and solutions

## Sample Repositories

### Official (by Zoom)

| Type | Repository | Stars |
|------|------------|-------|
| Linux Headless | [meetingsdk-headless-linux-sample](https://github.com/zoom/meetingsdk-headless-linux-sample) | 4 |
| Linux Raw Data | [meetingsdk-linux-raw-recording-sample](https://github.com/zoom/meetingsdk-linux-raw-recording-sample) | 0 |
| Web | [meetingsdk-web-sample](https://github.com/zoom/meetingsdk-web-sample) | 643 |
| Web NPM | [meetingsdk-web](https://github.com/zoom/meetingsdk-web) | 324 |
| React | [meetingsdk-react-sample](https://github.com/zoom/meetingsdk-react-sample) | 177 |
| Auth | [meetingsdk-auth-endpoint-sample](https://github.com/zoom/meetingsdk-auth-endpoint-sample) | 124 |
| Angular | [meetingsdk-angular-sample](https://github.com/zoom/meetingsdk-angular-sample) | 60 |
| Vue.js | [meetingsdk-vuejs-sample](https://github.com/zoom/meetingsdk-vuejs-sample) | 42 |

**Full list**: See [general/references/community-repos.md](../../general/references/community-repos.md)

## Resources

- **Official docs**: https://developers.zoom.us/docs/meeting-sdk/
- **Developer forum**: https://devforum.zoom.us/

## Environment Variables

- See [references/environment-variables.md](../references/environment-variables.md) for standardized `.env` keys and where to find each value.
