---
name: zoom-meeting-sdk-web
description: |
  Zoom Meeting SDK for Web - Embed Zoom meeting capabilities into web applications. Two integration
  options: Client View (full-page, familiar Zoom UI) and Component View (embeddable, Promise-based API).
  Includes SharedArrayBuffer setup for HD video, gallery view, and virtual backgrounds.
---

# Zoom Meeting SDK (Web)

Embed Zoom meeting capabilities into web applications with two integration options: **Client View** (full-page) or **Component View** (embeddable).

## How to Implement a Custom Video User Interface for a Zoom Meeting in a Web App

Use **Meeting SDK Web Component View**.

Do not use Video SDK for this question unless the user is explicitly building a non-meeting session
product.

Minimal architecture:

```text
Browser page
  -> fetch Meeting SDK signature from backend
  -> ZoomMtgEmbedded.createClient()
  -> client.init({ zoomAppRoot })
  -> client.join({ signature, sdkKey, meetingNumber, userName, password })
  -> apply layout/style/customize options around the embedded meeting container
```

Minimal implementation:

```ts
import ZoomMtgEmbedded from '@zoom/meetingsdk/embedded';

const client = ZoomMtgEmbedded.createClient();

export async function startEmbeddedMeeting(meetingNumber: string, userName: string, password: string) {
  const sigRes = await fetch('/api/signature', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ meetingNumber, role: 0 }),
  });

  if (!sigRes.ok) throw new Error(`signature_fetch_failed:${sigRes.status}`);

  const { signature, sdkKey } = await sigRes.json();

  await client.init({
    zoomAppRoot: document.getElementById('meetingSDKElement')!,
    language: 'en-US',
    patchJsMedia: true,
    leaveOnPageUnload: true,
    customize: {
      video: { isResizable: true, popper: { disableDraggable: false } },
    },
  });

  await client.join({
    signature,
    sdkKey,
    meetingNumber,
    userName,
    password,
  });
}
```

Common failure points:
- wrong route: Video SDK instead of Meeting SDK Component View
- missing backend signature endpoint
- wrong password field (`password` here, not `passWord`)
- missing OBF/ZAK requirements for meetings outside the app account
- missing SharedArrayBuffer headers when higher-end meeting features are expected

## Hard Routing Rule

If the user wants a **custom video user interface for a Zoom meeting in a web app**, route to
**Component View**, not Video SDK.

- **Meeting SDK Component View** = custom UI for a real Zoom meeting
- **Video SDK Web** = custom UI for a non-meeting video session product

For the direct custom-meeting-UI path, start with
[component-view/SKILL.md](component-view/SKILL.md).

## New to Web SDK? Start Here!

**The fastest way to master the SDK:**

1. **Choose Your View** - [Client View vs Component View](#client-view-vs-component-view) - Understand the key architectural differences
2. **Quick Start** - [Client View](#quick-start-client-view) or [Component View](#quick-start-component-view) - Get a working meeting in minutes
3. **SharedArrayBuffer** - [concepts/sharedarraybuffer.md](concepts/sharedarraybuffer.md) - Required for HD video, gallery view, virtual backgrounds
4. **Optional preflight diagnostics** - [../../probe-sdk/SKILL.md](../../probe-sdk/SKILL.md) - Validate browser/device/network before join

**Building a Custom Integration?**
- Component View gives you Promise-based API and embeddable UI
- Client View gives you the familiar full-page Zoom experience
- For a custom meeting UI, prefer **Component View** first
- Cross-product routing example: [../../general/use-cases/custom-meeting-ui-web.md](../../general/use-cases/custom-meeting-ui-web.md)
- [Browser Support](concepts/browser-support.md) - Feature matrix by browser
- Exact deep-dive path: [component-view/SKILL.md](component-view/SKILL.md)

**Having issues?**
- Join errors → Check signature generation and password spelling (`passWord` vs `password`)
- HD video not working → Enable SharedArrayBuffer headers
- Complete navigation → [SKILL.md](SKILL.md)

## Prerequisites

- Zoom app with Meeting SDK credentials from [Marketplace](https://marketplace.zoom.us/)
- SDK Key (Client ID) and Secret
- Modern browser (Chrome, Firefox, Safari, Edge)
- Backend auth endpoint for signature generation

> **Need help with authentication?** See the **[zoom-oauth](../../oauth/SKILL.md)** skill for JWT/signature generation.
>
> **Want pre-join diagnostics?** Chain **[probe-sdk](../../probe-sdk/SKILL.md)** before `init()`/`join()` to gate low-readiness environments.

## Optional Preflight Gate (Probe SDK)

For unstable first-join environments, run Probe SDK checks before calling `ZoomMtg.init()` or `client.join()`:

1. Run Probe permissions/device/network diagnostics.
2. Apply readiness policy (`allow`, `warn`, `block`).
3. Continue to Meeting SDK join only for `allow`/approved `warn`.

See [../../probe-sdk/SKILL.md](../../probe-sdk/SKILL.md) and [../../general/use-cases/probe-sdk-preflight-readiness-gate.md](../../general/use-cases/probe-sdk-preflight-readiness-gate.md).

## Client View vs Component View

**CRITICAL DIFFERENCE**: These are two completely different APIs with different patterns!

| Aspect | Client View | Component View |
|--------|-------------|----------------|
| **Object** | `ZoomMtg` (global singleton) | `ZoomMtgEmbedded.createClient()` (instance) |
| **API Style** | Callbacks | Promises |
| **UI** | Full-page takeover | Embeddable in any container |
| **Password param** | `passWord` (capital W) | `password` (lowercase) |
| **Events** | `inMeetingServiceListener()` | `on()`/`off()` |
| **Import (npm)** | `import { ZoomMtg } from '@zoom/meetingsdk'` | `import ZoomMtgEmbedded from '@zoom/meetingsdk/embedded'` |
| **CDN** | `zoom-meeting-{VERSION}.min.js` | `zoom-meeting-embedded-{VERSION}.min.js` |
| **Best For** | Quick integration, standard Zoom UI | Custom layouts, React/Vue apps |

### When to Use Which

**Use Client View when:**
- You want the familiar Zoom meeting interface
- Quick integration is priority over customization
- Full-page meeting experience is acceptable

**Use Component View when:**
- You need to embed meetings in a specific area of your page
- Building React/Vue/Angular applications
- You want Promise-based async/await syntax
- Custom positioning and resizing is required

## Installation

### NPM (Recommended)

```bash
npm install @zoom/meetingsdk --save
```

### CDN

```html
<!-- Dependencies (required for both views) -->
<script src="https://source.zoom.us/{VERSION}/lib/vendor/react.min.js"></script>
<script src="https://source.zoom.us/{VERSION}/lib/vendor/react-dom.min.js"></script>
<script src="https://source.zoom.us/{VERSION}/lib/vendor/redux.min.js"></script>
<script src="https://source.zoom.us/{VERSION}/lib/vendor/redux-thunk.min.js"></script>
<script src="https://source.zoom.us/{VERSION}/lib/vendor/lodash.min.js"></script>

<!-- Client View -->
<script src="https://source.zoom.us/zoom-meeting-{VERSION}.min.js"></script>

<!-- OR Component View -->
<script src="https://source.zoom.us/zoom-meeting-embedded-{VERSION}.min.js"></script>
```

Replace `{VERSION}` with the [latest version](https://www.npmjs.com/package/@zoom/meetingsdk) (e.g., `3.11.0`).

## Quick Start (Client View)

```javascript
import { ZoomMtg } from '@zoom/meetingsdk';

// Step 1: Check browser compatibility
console.log('System requirements:', ZoomMtg.checkSystemRequirements());

// Step 2: Preload WebAssembly for faster initialization
ZoomMtg.preLoadWasm();
ZoomMtg.prepareWebSDK();

// Step 3: Load language files (MUST complete before init)
ZoomMtg.i18n.load('en-US');
ZoomMtg.i18n.onLoad(() => {

  // Step 4: Initialize SDK
  ZoomMtg.init({
    leaveUrl: 'https://yoursite.com/meeting-ended',
    disableCORP: !window.crossOriginIsolated, // Auto-detect SharedArrayBuffer
    patchJsMedia: true,           // Auto-apply media dependency fixes
    leaveOnPageUnload: true,      // Clean up when page unloads
    externalLinkPage: './external.html', // Page for external links
    success: () => {

      // Step 5: Join meeting (note: passWord with capital W!)
      ZoomMtg.join({
        signature: signature,       // From your auth endpoint
        meetingNumber: '1234567890',
        userName: 'User Name',
        passWord: 'meeting-password', // Capital W!
        success: (res) => {
          console.log('Joined meeting:', res);

          // Post-join: Get meeting info
          ZoomMtg.getAttendeeslist({});
          ZoomMtg.getCurrentUser({
            success: (res) => console.log('Current user:', res.result.currentUser)
          });
        },
        error: (err) => {
          console.error('Join error:', err);
        }
      });
    },
    error: (err) => {
      console.error('Init error:', err);
    }
  });
});
```

## Quick Start (Component View)

```javascript
import ZoomMtgEmbedded from '@zoom/meetingsdk/embedded';

// Create client instance (do this ONCE, not on every render!)
const client = ZoomMtgEmbedded.createClient();

async function startMeeting() {
  try {
    // Initialize with container element
    await client.init({
      zoomAppRoot: document.getElementById('meetingSDKElement'),
      language: 'en-US',
      debug: true,                  // Enable debug logging
      patchJsMedia: true,           // Auto-apply media fixes
      leaveOnPageUnload: true,      // Clean up on page unload
    });

    // Join meeting (note: password lowercase!)
    await client.join({
      signature: signature,          // From your auth endpoint
      sdkKey: SDK_KEY,
      meetingNumber: '1234567890',
      userName: 'User Name',
      password: 'meeting-password',  // Lowercase!
    });

    console.log('Joined successfully!');
  } catch (error) {
    console.error('Failed to join:', error);
  }
}
```

## Authentication Endpoint (Required)

Both views require a JWT signature from a backend server. **Never expose your SDK Secret in frontend code!**

```bash
# Clone Zoom's official auth endpoint
git clone https://github.com/zoom/meetingsdk-auth-endpoint-sample --depth 1
cd meetingsdk-auth-endpoint-sample
cp .env.example .env
# Edit .env with your SDK Key and Secret
npm install && npm run start
```

### Signature Generation

The signature encodes:
- `sdkKey` (or `clientId` for newer apps)
- `meetingNumber`
- `role` (0 = participant, 1 = host)
- `iat` (issued at timestamp)
- `exp` (expiration timestamp)
- `tokenExp` (token expiration)

> **IMPORTANT (March 2026)**: Apps joining meetings outside their account will require an App Privilege Token (OBF) or ZAK token. See [Authorization Requirements](#authorization-requirements-2026-update).

## Core Workflow

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Get Signature │───►│   init()        │───►│   join()        │
│   (from backend)│    │   (SDK setup)   │    │   (enter mtg)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │                       │
                              ▼                       ▼
                       success/error            success/error
                        callback                 callback
                     (or Promise resolve)    (or Promise resolve)
```

## Client View API Reference

### ZoomMtg.init() - Key Options

```javascript
ZoomMtg.init({
  // Required
  leaveUrl: string,              // URL to redirect after leaving

  // Display Options
  showMeetingHeader: boolean,    // Show meeting number/topic (default: true)
  disableInvite: boolean,        // Hide invite button (default: false)
  disableRecord: boolean,        // Hide record button (default: false)
  disableJoinAudio: boolean,     // Hide join audio option (default: false)
  disablePreview: boolean,       // Skip A/V preview (default: false)

  // HD Video (requires SharedArrayBuffer)
  enableHD: boolean,             // Enable 720p (default: true for >=2.8.0)
  enableFullHD: boolean,         // Enable 1080p for webinars (default: false)

  // View Options
  defaultView: 'gallery' | 'speaker' | 'multiSpeaker',

  // Feature Toggles
  isSupportChat: boolean,        // Enable chat (default: true)
  isSupportCC: boolean,          // Enable closed captions (default: true)
  isSupportBreakout: boolean,    // Enable breakout rooms (default: true)
  isSupportPolling: boolean,     // Enable polling (default: true)
  isSupportQA: boolean,          // Enable Q&A for webinars (default: true)

  // Cross-Origin
  disableCORP: boolean,          // For dev without COOP/COEP headers

  // Callbacks
  success: Function,
  error: Function,
});
```

### ZoomMtg.join() - Key Options

```javascript
ZoomMtg.join({
  // Required
  signature: string,             // JWT signature from backend
  meetingNumber: string | number,
  userName: string,

  // Authentication
  passWord: string,              // Meeting password (capital W!)
  zak: string,                   // Host's ZAK token (required to start)
  tk: string,                    // Registration token (if required)
  obfToken: string,              // App Privilege Token (for 2026 requirement)

  // Optional
  userEmail: string,             // Required for webinars
  customerKey: string,           // Custom identifier (max 36 chars)

  // Callbacks
  success: Function,
  error: Function,
});
```

### Event Listeners (Client View)

```javascript
// User events
ZoomMtg.inMeetingServiceListener('onUserJoin', (data) => {
  console.log('User joined:', data);
});

ZoomMtg.inMeetingServiceListener('onUserLeave', (data) => {
  console.log('User left:', data);
  // data.reasonCode values:
  // 0: OTHER
  // 1: HOST_ENDED_MEETING
  // 2: SELF_LEAVE_FROM_IN_MEETING
  // 3: SELF_LEAVE_FROM_WAITING_ROOM
  // 4: SELF_LEAVE_FROM_WAITING_FOR_HOST_START
  // 5: MEETING_TRANSFER
  // 6: KICK_OUT_FROM_MEETING
  // 7: KICK_OUT_FROM_WAITING_ROOM
  // 8: LEAVE_FROM_DISCLAIMER
});

ZoomMtg.inMeetingServiceListener('onUserUpdate', (data) => {
  console.log('User updated:', data);
});

// Meeting status
ZoomMtg.inMeetingServiceListener('onMeetingStatus', (data) => {
  // status: 1=connecting, 2=connected, 3=disconnected, 4=reconnecting
  console.log('Meeting status:', data.status);
});

// Waiting room
ZoomMtg.inMeetingServiceListener('onUserIsInWaitingRoom', (data) => {
  console.log('User in waiting room:', data);
});

// Active speaker detection
ZoomMtg.inMeetingServiceListener('onActiveSpeaker', (data) => {
  // [{userId: number, userName: string}]
  console.log('Active speaker:', data);
});

// Network quality monitoring
ZoomMtg.inMeetingServiceListener('onNetworkQualityChange', (data) => {
  // {level: 0-5, userId, type: 'uplink'}
  // 0-1 = bad, 2 = normal, 3-5 = good
  if (data.level <= 1) {
    console.warn('Poor network quality');
  }
});

// Join performance metrics
ZoomMtg.inMeetingServiceListener('onJoinSpeed', (data) => {
  console.log('Join speed metrics:', data);
  // Useful for performance monitoring dashboards
});

// Chat
ZoomMtg.inMeetingServiceListener('onReceiveChatMsg', (data) => {
  console.log('Chat message:', data);
});

// Recording
ZoomMtg.inMeetingServiceListener('onRecordingChange', (data) => {
  console.log('Recording status:', data);
});

// Screen sharing
ZoomMtg.inMeetingServiceListener('onShareContentChange', (data) => {
  console.log('Share content changed:', data);
});

// Transcription (requires "save closed captions" enabled)
ZoomMtg.inMeetingServiceListener('onReceiveTranscriptionMsg', (data) => {
  console.log('Transcription:', data);
});

// Breakout room status
ZoomMtg.inMeetingServiceListener('onRoomStatusChange', (data) => {
  // status: 2=InProgress, 3=Closing, 4=Closed
  console.log('Breakout room status:', data);
});
```

### Common Methods (Client View)

```javascript
// Get current user info
ZoomMtg.getCurrentUser({
  success: (res) => console.log(res.result.currentUser)
});

// Get all attendees
ZoomMtg.getAttendeeslist({});

// Audio/Video control
ZoomMtg.mute({ userId, mute: true });
ZoomMtg.muteAll({ muteAll: true });

// Chat
ZoomMtg.sendChat({ message: 'Hello!', userId: 0 }); // 0 = everyone

// Leave/End
ZoomMtg.leaveMeeting({});
ZoomMtg.endMeeting({});

// Host controls
ZoomMtg.makeHost({ userId });
ZoomMtg.makeCoHost({ oderId });
ZoomMtg.expel({ userId });  // Remove participant
ZoomMtg.putOnHold({ oderId, bHold: true });

// Breakout rooms
ZoomMtg.createBreakoutRoom({ rooms: [...] });
ZoomMtg.openBreakoutRooms({});
ZoomMtg.closeBreakoutRooms({});

// Virtual background
ZoomMtg.setVirtualBackground({ imageUrl: '...' });
```

## Component View API Reference

### client.init() - Key Options

```javascript
await client.init({
  // Required
  zoomAppRoot: HTMLElement,      // Container element

  // Display
  language: string,              // e.g., 'en-US'
  debug: boolean,                // Enable debug logging (default: false)

  // Media
  patchJsMedia: boolean,         // Auto-apply media fixes (default: false)
  leaveOnPageUnload: boolean,    // Clean up on page unload (default: false)

  // Video
  enableHD: boolean,             // Enable 720p
  enableFullHD: boolean,         // Enable 1080p

  // Customization
  customize: {
    video: {
      isResizable: boolean,
      viewSizes: { default: { width, height } }
    },
    meetingInfo: ['topic', 'host', 'mn', 'pwd', 'telPwd', 'invite', 'participant', 'dc', 'enctype'],
    toolbar: {
      buttons: [
        {
          text: 'Custom Button',
          className: 'custom-btn',
          onClick: () => {
            console.log('Custom button clicked');
          }
        }
      ]
    }
  },

  // For ZFG
  webEndpoint: string,
  assetPath: string,             // Custom path for AV libraries (self-hosting)
});
```

### client.join() - Key Options

```javascript
await client.join({
  // Required
  signature: string,
  sdkKey: string,
  meetingNumber: string | number,
  userName: string,

  // Authentication
  password: string,              // Lowercase! (different from Client View)
  zak: string,                   // Host's ZAK token
  tk: string,                    // Registration token

  // Optional
  userEmail: string,
});
```

### Event Listeners (Component View)

```javascript
// Connection state
client.on('connection-change', (payload) => {
  // payload.state: 'Connecting', 'Connected', 'Reconnecting', 'Closed'
  console.log('Connection:', payload.state);
});

// User events
client.on('user-added', (payload) => {
  console.log('Users added:', payload);
});

client.on('user-removed', (payload) => {
  console.log('Users removed:', payload);
});

client.on('user-updated', (payload) => {
  console.log('Users updated:', payload);
});

// Active speaker
client.on('active-speaker', (payload) => {
  console.log('Active speaker:', payload);
});

// Video state
client.on('video-active-change', (payload) => {
  console.log('Video active:', payload);
});

// Unsubscribe
client.off('connection-change', handler);
```

### Common Methods (Component View)

```javascript
// Get current user
const currentUser = client.getCurrentUser();

// Get all participants
const participants = client.getParticipantsList();

// Audio control
await client.mute(true);
await client.muteAudio(userId, true);

// Video control
await client.muteVideo(userId, true);

// Leave
client.leaveMeeting();

// End (host only)
client.endMeeting();
```

## SharedArrayBuffer (CRITICAL for HD)

SharedArrayBuffer enables advanced features:
- 720p/1080p video
- Gallery view
- Virtual backgrounds
- Background noise suppression

### Enable with HTTP Headers

```
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Embedder-Policy: require-corp
```

### Verify in Browser

```javascript
if (typeof SharedArrayBuffer === 'function') {
  console.log('SharedArrayBuffer enabled!');
} else {
  console.warn('HD features will be limited');
}

// Or check cross-origin isolation
console.log('Cross-origin isolated:', window.crossOriginIsolated);
```

### Platform-Specific Setup

See [concepts/sharedarraybuffer.md](concepts/sharedarraybuffer.md) for:
- Vercel, Netlify, AWS CloudFront configuration
- nginx/Apache configuration
- Service worker fallback for GitHub Pages

### Development Setup (Two-Server Pattern)

The official samples use a **two-server pattern** for development because COOP/COEP headers can break navigation:

```javascript
// Server 1: Main app (port 9999) - NO isolation headers
// Serves index.html, navigation works normally

// Server 2: Meeting page (port 9998) - WITH isolation headers
// Serves meeting.html with SharedArrayBuffer support

// Main server proxies to meeting server
proxy: [{
  path: '/meeting.html',
  target: 'http://YOUR_MEETING_SERVER_HOST:9998/'
}]
```

**Vite config with headers:**
```typescript
// vite.config.ts
export default defineConfig({
  server: {
    headers: {
      'Cross-Origin-Embedder-Policy': 'require-corp',
      'Cross-Origin-Opener-Policy': 'same-origin',
    }
  }
});
```

## Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| **Join fails with signature error** | Verify signature generation, check sdkKey format |
| **"passWord" typo** | Client View uses `passWord` (capital W), Component View uses `password` |
| **No HD video** | Enable SharedArrayBuffer headers, check browser support |
| **Callbacks not firing** | Ensure `inMeetingServiceListener` called after init success |
| **Virtual background not working** | Requires SharedArrayBuffer + Chrome/Edge |
| **Screen share fails on Safari** | Safari 17+ with macOS 14+ required for client view |

**Complete troubleshooting**: [troubleshooting/common-issues.md](troubleshooting/common-issues.md)

## Browser Support Matrix

| Feature | Chrome | Firefox | Safari | Edge | iOS | Android |
|---------|--------|---------|--------|------|-----|---------|
| 720p (receive) | Yes | Yes | Yes | Yes | Yes | Yes |
| 720p (send) | Yes* | Yes* | Yes* | Yes* | Yes* | Yes* |
| Virtual background | Yes | Yes | No | Yes | No | No |
| Screen share (send) | Yes | Yes | Safari 17+ | Yes | No | No |
| Gallery view | Yes | Yes | Yes** | Yes | Yes | Yes |

*Requires SharedArrayBuffer
**Safari 17+ with macOS Sonoma

See [concepts/browser-support.md](concepts/browser-support.md) for complete matrix.

## Authorization Requirements (2026 Update)

> **IMPORTANT**: Beginning **March 2, 2026**, apps joining meetings outside their account must be authorized.

### Options

1. **App Privilege Token (OBF)** - Recommended for bots
   ```javascript
   ZoomMtg.join({
     ...
     obfToken: 'your-app-privilege-token'
   });
   ```

2. **ZAK Token** - For host operations
   ```javascript
   ZoomMtg.join({
     ...
     zak: 'host-zak-token'
   });
   ```

## Zoom for Government (ZFG)

### Option 1: ZFG-specific NPM Package

```json
{
  "dependencies": {
    "@zoom/meetingsdk": "3.11.2-zfg"
  }
}
```

### Option 2: Configure ZFG Endpoints

**Client View:**
```javascript
ZoomMtg.setZoomJSLib('https://source.zoomgov.com/{VERSION}/lib', '/av');
ZoomMtg.init({
  webEndpoint: 'www.zoomgov.com',
  ...
});
```

**Component View:**
```javascript
await client.init({
  webEndpoint: 'www.zoomgov.com',
  assetPath: 'https://source.zoomgov.com/{VERSION}/lib/av',
  ...
});
```

## China CDN

```javascript
// Set before preLoadWasm()
ZoomMtg.setZoomJSLib('https://jssdk.zoomus.cn/{VERSION}/lib', '/av');
```

## React Integration

### Official Pattern (from zoom/meetingsdk-react-sample)

The official React sample uses **imperative initialization** rather than React hooks:

```tsx
import { ZoomMtg } from '@zoom/meetingsdk';

// Preload at module level (outside component)
ZoomMtg.preLoadWasm();
ZoomMtg.prepareWebSDK();

function App() {
  const authEndpoint = import.meta.env.VITE_AUTH_ENDPOINT;
  const meetingNumber = '';
  const passWord = '';
  const role = 0;
  const userName = 'React User';

  const getSignature = async () => {
    const response = await fetch(authEndpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        meetingNumber,
        role,
      }),
    });
    const data = await response.json();
    startMeeting(data.signature);
  };

  const startMeeting = (signature: string) => {
    document.getElementById('zmmtg-root')!.style.display = 'block';

    ZoomMtg.init({
      leaveUrl: window.location.origin,
      patchJsMedia: true,
      leaveOnPageUnload: true,
      success: () => {
        ZoomMtg.join({
          signature,
          meetingNumber,
          userName,
          passWord,
          success: (res) => console.log('Joined:', res),
          error: (err) => console.error('Join error:', err),
        });
      },
      error: (err) => console.error('Init error:', err),
    });
  };

  return (
    <button onClick={getSignature}>Join Meeting</button>
  );
}
```

### React Gotchas (from official samples)

| Issue | Problem | Solution |
|-------|---------|----------|
| **Client Recreation** | `createClient()` in component body runs every render | Use `useRef` to persist client |
| **No useEffect** | Official sample doesn't use React lifecycle hooks | SDK's `leaveOnPageUnload` handles cleanup |
| **Direct DOM** | Sample uses `getElementById` | Use `useRef<HTMLDivElement>` in production |
| **No Error State** | Silent failures | Add `useState` for error handling |
| **Module-Scope Side Effects** | `preLoadWasm()` at top level | May cause issues with SSR |

### Production-Ready React Pattern

```tsx
import { useEffect, useRef, useState, useCallback } from 'react';
import ZoomMtgEmbedded from '@zoom/meetingsdk/embedded';

type ZoomClient = ReturnType<typeof ZoomMtgEmbedded.createClient>;

function ZoomMeeting({ meetingNumber, password, userName }: Props) {
  const clientRef = useRef<ZoomClient | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [isJoining, setIsJoining] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Create client once
  useEffect(() => {
    if (!clientRef.current) {
      clientRef.current = ZoomMtgEmbedded.createClient();
    }
  }, []);

  const joinMeeting = useCallback(async () => {
    if (!clientRef.current || !containerRef.current) return;

    setIsJoining(true);
    setError(null);

    try {
      // Get signature from your backend
      const response = await fetch('/api/signature', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ meetingNumber, role: 0 }),
      });
      const { signature, sdkKey } = await response.json();

      await clientRef.current.init({
        zoomAppRoot: containerRef.current,
        language: 'en-US',
        patchJsMedia: true,
        leaveOnPageUnload: true,
      });

      await clientRef.current.join({
        signature,
        sdkKey,
        meetingNumber,
        password,
        userName,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to join');
    } finally {
      setIsJoining(false);
    }
  }, [meetingNumber, password, userName]);

  return (
    <div>
      <div ref={containerRef} style={{ width: '100%', height: '500px' }} />
      <button onClick={joinMeeting} disabled={isJoining}>
        {isJoining ? 'Joining...' : 'Join Meeting'}
      </button>
      {error && <div className="error">{error}</div>}
    </div>
  );
}
```

### Environment Variables (Vite)

```bash
# .env.local
VITE_AUTH_ENDPOINT=http://YOUR_AUTH_SERVER_HOST:4000
VITE_SDK_KEY=your_sdk_key
```

```tsx
const authEndpoint = import.meta.env.VITE_AUTH_ENDPOINT;
const sdkKey = import.meta.env.VITE_SDK_KEY;
```

## Detailed References

### Core Documentation
- **[SKILL.md](SKILL.md)** - Complete navigation guide
- **[client-view/SKILL.md](client-view/SKILL.md)** - Full Client View reference
- **[component-view/SKILL.md](component-view/SKILL.md)** - Full Component View reference

### Concepts
- **[concepts/sharedarraybuffer.md](concepts/sharedarraybuffer.md)** - HD video requirements
- **[concepts/browser-support.md](concepts/browser-support.md)** - Feature matrix by browser

### Troubleshooting
- **[troubleshooting/error-codes.md](troubleshooting/error-codes.md)** - All SDK error codes
- **[troubleshooting/common-issues.md](troubleshooting/common-issues.md)** - Quick diagnostics

### Examples
- **[client-view/SKILL.md](client-view/SKILL.md)** - Complete Client View guide
- **[component-view/SKILL.md](component-view/SKILL.md)** - Component View React integration

## Helper Utilities

### Extract Meeting Number from Invite Link

```javascript
// Users can paste full Zoom invite links
document.getElementById('meeting_number').addEventListener('input', (e) => {
  // Extract meeting number (9-11 digits)
  let meetingNumber = e.target.value.replace(/([^0-9])+/i, '');
  if (meetingNumber.match(/([0-9]{9,11})/)) {
    meetingNumber = meetingNumber.match(/([0-9]{9,11})/)[1];
  }

  // Auto-extract password from invite link
  const pwdMatch = e.target.value.match(/pwd=([\d,\w]+)/);
  if (pwdMatch) {
    document.getElementById('password').value = pwdMatch[1];
  }
});
```

### Dynamic Language Switching

```javascript
// Change language at runtime
document.getElementById('language').addEventListener('change', (e) => {
  const lang = e.target.value;
  ZoomMtg.i18n.load(lang);
  ZoomMtg.i18n.reload(lang);
  ZoomMtg.reRender({ lang });
});
```

### Check System Requirements

```javascript
// Check browser compatibility before initializing
const requirements = ZoomMtg.checkSystemRequirements();
console.log('Browser info:', JSON.stringify(requirements));

if (!requirements.browserInfo.isChrome && !requirements.browserInfo.isFirefox) {
  alert('For best experience, use Chrome or Firefox');
}
```

## Sample Repositories

| Repository | Description |
|------------|-------------|
| [meetingsdk-web-sample](https://github.com/zoom/meetingsdk-web-sample) | Official samples (Client View & Component View) |
| [meetingsdk-react-sample](https://github.com/zoom/meetingsdk-react-sample) | React integration with TypeScript + Vite |
| [meetingsdk-web](https://github.com/zoom/meetingsdk-web) | SDK source with helper.html |
| [meetingsdk-auth-endpoint-sample](https://github.com/zoom/meetingsdk-auth-endpoint-sample) | Signature generation backend |

## Official Resources

- **Official docs**: https://developers.zoom.us/docs/meeting-sdk/web/
- **Client View API Reference**: https://marketplacefront.zoom.us/sdk/meeting/web/index.html
- **Component View API Reference**: https://marketplacefront.zoom.us/sdk/meeting/web/components/index.html
- **Developer forum**: https://devforum.zoom.us/

---

**Documentation Version**: Based on Zoom Web Meeting SDK v3.11+

**Need help?** Start with [SKILL.md](SKILL.md) for complete navigation.


## Merged from meeting-sdk/web/SKILL.md

# Zoom Meeting SDK (Web) - Documentation Index

Quick navigation guide for all Web SDK documentation.

## Start Here

| Document | Description |
|----------|-------------|
| **[SKILL.md](SKILL.md)** | Main entry point - Quick starts for both Client View and Component View |

## By View Type

### Client View (Full-Page)
| Document | Description |
|----------|-------------|
| **[client-view/SKILL.md](client-view/SKILL.md)** | Complete Client View reference |

### Component View (Embeddable)
| Document | Description |
|----------|-------------|
| **[component-view/SKILL.md](component-view/SKILL.md)** | Complete Component View reference |

## Concepts

| Document | Description |
|----------|-------------|
| **[concepts/sharedarraybuffer.md](concepts/sharedarraybuffer.md)** | HD video requirements, COOP/COEP headers |
| **[concepts/browser-support.md](concepts/browser-support.md)** | Feature matrix by browser |

## Examples

| Document | Description |
|----------|-------------|
| [examples/client-view-basic.md](examples/client-view-basic.md) | Basic Client View integration |
| [examples/component-view-react.md](examples/component-view-react.md) | React integration with Component View |

## Troubleshooting

| Document | Description |
|----------|-------------|
| **[troubleshooting/error-codes.md](troubleshooting/error-codes.md)** | All SDK error codes (3000-10000 range) |
| **[troubleshooting/common-issues.md](troubleshooting/common-issues.md)** | Quick diagnostics and fixes |

## By Topic

### Authentication
- [SKILL.md#authentication-endpoint](SKILL.md#authentication-endpoint-required) - Signature generation
- [SKILL.md#authorization-requirements-2026-update](SKILL.md#authorization-requirements-2026-update) - OBF tokens

### HD Video & Performance
- [concepts/sharedarraybuffer.md](concepts/sharedarraybuffer.md) - Enable 720p/1080p

### Events & Callbacks
- [SKILL.md#event-listeners-client-view](SKILL.md#event-listeners-client-view) - Client View events
- [SKILL.md#event-listeners-component-view](SKILL.md#event-listeners-component-view) - Component View events

### Government (ZFG)
- [SKILL.md#zoom-for-government-zfg](SKILL.md#zoom-for-government-zfg) - ZFG configuration

### China CDN
- [SKILL.md#china-cdn](SKILL.md#china-cdn) - China-specific CDN

## Quick Reference

### Client View vs Component View

| Aspect | Client View | Component View |
|--------|-------------|----------------|
| **Object** | `ZoomMtg` | `ZoomMtgEmbedded.createClient()` |
| **API Style** | Callbacks | Promises |
| **Password param** | `passWord` (capital W) | `password` (lowercase) |
| **Events** | `inMeetingServiceListener()` | `on()`/`off()` |

### Key Gotchas

1. **Password spelling differs between views!**
   - Client View: `passWord` (capital W)
   - Component View: `password` (lowercase)

2. **SharedArrayBuffer required for HD features**
   - 720p/1080p video
   - Gallery view (25 videos)
   - Virtual backgrounds

3. **March 2026 Authorization Change**
   - Apps joining external meetings need OBF or ZAK tokens

## External Resources

- **Official docs**: https://developers.zoom.us/docs/meeting-sdk/web/
- **Client View API**: https://marketplacefront.zoom.us/sdk/meeting/web/index.html
- **Component View API**: https://marketplacefront.zoom.us/sdk/meeting/web/components/index.html
- **GitHub samples**: https://github.com/zoom/meetingsdk-web-sample

## Operations

- [RUNBOOK.md](RUNBOOK.md) - 5-minute preflight and debugging checklist.
