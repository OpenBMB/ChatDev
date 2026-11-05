# Meeting SDK - Web

Embed Zoom meetings in web applications.

## Overview

The Zoom Meeting SDK for Web embeds the full Zoom meeting experience into your web application with two view options: Component View and Client View.

## Forum-Derived Hotspots

- SharedArrayBuffer / gallery view: [sharedarraybuffer-gallery-view.md](sharedarraybuffer-gallery-view.md)
- Joining meeting timeout / browser restriction: [web-timeout-browser-restriction.md](web-timeout-browser-restriction.md)
- Performance/CPU guidance: [web-performance-cpu.md](web-performance-cpu.md)
- Component View UI customization: [component-view-ui-customization.md](component-view-ui-customization.md)
- Component View breakout rooms: [component-view-breakout-rooms.md](component-view-breakout-rooms.md)

## Prerequisites

- Meeting SDK credentials from [Marketplace](https://marketplace.zoom.us/) (sign-in required)
- SDK Key and Secret
- Modern browser (Chrome, Firefox, Safari, Edge)

## View Options

| View | Description | Use Case |
|------|-------------|----------|
| **Component View** | Flexible, embeddable UI components | Custom layouts, React/Vue integration |
| **Client View** | Full-page Zoom meeting experience | Quick integration, standard Zoom UI |

## Implementation Approaches

| Approach | Technology | Port | View | Best For |
|----------|-----------|------|------|----------|
| **Components** | React + TypeScript + Vite | 3000 | Component | Modern, flexible integration |
| **Local** | React + Webpack + NPM | 9999 | Client | Traditional npm-based setup |
| **CDN** | Vanilla JS + CDN | 9999 | Client | Simple, no build tools |

## Installation

### Component View (Recommended)

```bash
npm install @zoom/meetingsdk
```

### Client View (CDN)

```html
<script src="https://source.zoom.us/3.1.6/lib/vendor/react.min.js"></script>
<script src="https://source.zoom.us/3.1.6/lib/vendor/react-dom.min.js"></script>
<script src="https://source.zoom.us/3.1.6/lib/vendor/redux.min.js"></script>
<script src="https://source.zoom.us/3.1.6/lib/vendor/redux-thunk.min.js"></script>
<script src="https://source.zoom.us/3.1.6/lib/vendor/lodash.min.js"></script>
<script src="https://source.zoom.us/3.1.6/zoom-meeting-3.1.6.min.js"></script>
```

> **Note:** CDN provides `ZoomMtg` (Client View). For `ZoomMtgEmbedded` (Component View), use npm.

### Auth Endpoint (Required)

The Meeting SDK requires a signature from an authentication backend:

```bash
# Clone Zoom's auth endpoint sample
git clone https://github.com/zoom/meetingsdk-auth-endpoint-sample --depth 1
cd meetingsdk-auth-endpoint-sample
cp .env.example .env
# Edit .env with your SDK credentials
npm install && npm run start
```

## Quick Start (Component View)

```javascript
import ZoomMtgEmbedded from '@zoom/meetingsdk/embedded';

const client = ZoomMtgEmbedded.createClient();

await client.init({
  zoomAppRoot: document.getElementById('meetingSDKElement'),
  language: 'en-US',
});

await client.join({
  sdkKey: SDK_KEY,
  signature: signature,
  meetingNumber: meetingNumber,
  userName: 'User',
  password: password,
});
```

## WebRTC Optimizations

Meeting SDK Web uses WebRTC for real-time communication with optimizations for:
- HD video (720p/1080p)
- Low latency audio
- Adaptive bitrate

### Codec Support
- H.264 for video
- VP8 as fallback
- Opus for audio

## HD Video

### Check System Requirements

```javascript
// Check browser compatibility
const compatibility = client.checkSystemRequirements();
console.log('Video supported:', compatibility.video);
console.log('Audio supported:', compatibility.audio);
console.log('Screen share supported:', compatibility.screen);
```

### Check SharedArrayBuffer (Required for HD)

```javascript
// SharedArrayBuffer is REQUIRED for 720p, gallery view, virtual background
const sabAvailable = typeof SharedArrayBuffer === 'function';

if (!sabAvailable) {
  console.warn('HD features require SharedArrayBuffer');
  console.warn('Enable COOP/COEP headers on your server');
}
```

### Enable HD in Init

```javascript
await client.init({
  zoomAppRoot: document.getElementById('meetingSDKElement'),
  language: 'en-US',

  // Enable 720p (default true for SDK >= 2.8.0)
  enableHD: true,

  // Enable 1080p for webinar attendees (SDK >= 2.9.0)
  enableFullHD: true,
});
```

### HD Requirements

To enable 720p:
1. Contact Zoom Support to enable on your account
2. Enable "Group HD" in Zoom profile settings
3. SharedArrayBuffer must be available (COOP/COEP headers)
4. Solid internet connection and low CPU usage

**Resolution tiers:**
- 1:1 calls: Up to 1080p
- Small groups (2-4): Up to 720p
- Larger meetings: Adaptive

**Key limitation:** If a 3rd participant turns video on, quality reverts to standard definition.

## SharedArrayBuffer

For optimal performance, configure these headers:

```
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Embedder-Policy: require-corp
```

## Event Handling

### Component View Events

```javascript
client.on('connection-change', (payload) => {
  console.log('Connection state:', payload.state);
});

client.on('user-added', (payload) => {
  console.log('User joined:', payload);
});

client.on('user-removed', (payload) => {
  console.log('User left:', payload);
});
```

### Client View In-Meeting Listeners

```javascript
// User events
ZoomMtg.inMeetingServiceListener('onUserJoin', (data) => {
  console.log('User joined:', data);
});

ZoomMtg.inMeetingServiceListener('onUserLeave', (data) => {
  console.log('User left:', data);
});

// Waiting room
ZoomMtg.inMeetingServiceListener('onUserIsInWaitingRoom', (data) => {
  console.log('User in waiting room:', data);
});

// Meeting status changes
ZoomMtg.inMeetingServiceListener('onMeetingStatus', (data) => {
  console.log('Meeting status:', data);
});
```

## Common Tasks

### Join Meeting
```javascript
await client.join({
  sdkKey: SDK_KEY,
  signature: signature,
  meetingNumber: meetingNumber,
  userName: 'User',
});
```

### Leave Meeting
```javascript
client.leaveMeeting();
```

## Client View Full Example

```javascript
import { ZoomMtg } from '@zoom/meetingsdk';

// Check system requirements
console.log(ZoomMtg.checkSystemRequirements());

// Preload WebAssembly for faster init
ZoomMtg.preLoadWasm();
ZoomMtg.prepareWebSDK();

// Initialize and join
ZoomMtg.init({
  leaveUrl: '/meeting-ended',
  disableCORP: !window.crossOriginIsolated, // Disable if no COOP/COEP
  success: () => {
    ZoomMtg.join({
      meetingNumber: '123456789',
      userName: 'User Name',
      signature: signature, // From auth endpoint
      userEmail: 'user@example.com',
      passWord: 'meeting-password',
      success: (res) => {
        console.log('Joined meeting');
        ZoomMtg.getAttendeeslist({});
        ZoomMtg.getCurrentUser({
          success: (res) => console.log('Current user:', res.result.currentUser)
        });
      },
      error: (err) => console.error('Join error:', err)
    });
  },
  error: (err) => console.error('Init error:', err)
});
```

## China CDN

For users in China, use the China-specific CDN:

```javascript
// Set before preLoadWasm()
ZoomMtg.setZoomJSLib('https://jssdk.zoomus.cn/{VERSION}/lib', '/av');
```

## Zoom for Government (ZFG)

For government applications, apply for SDK credentials at [ZFG Marketplace](https://marketplace.zoomgov.com/).

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
});
```

**Component View:**
```javascript
const client = ZoomMtgEmbedded.createClient();
client.init({
  assetPath: 'https://source.zoomgov.com/{VERSION}/lib/av',
  webEndpoint: 'www.zoomgov.com'
});
```

## Resources

- **Official docs**: https://developers.zoom.us/docs/meeting-sdk/web/
- **Component View sample**: https://github.com/zoom/meetingsdk-web-sample
- **Client View sample**: https://github.com/zoom/meetingsdk-sample-signature-node.js
