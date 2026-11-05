# RTMS - Quickstart

Get started with Zoom Realtime Media Streams.

## Prerequisites

1. **Node.js 20.3.0+** (24 LTS recommended)
2. Zoom General App (for meetings/webinars), Video SDK App (for Video SDK), or approved Contact Center / RTMS integration for Zoom Contact Center Voice
3. Webhook endpoint configured
4. Server to handle WebSocket connections

## Environment Setup

```bash
# .env file
ZOOM_CLIENT_ID=your_client_id          # From App Credentials
ZOOM_CLIENT_SECRET=your_client_secret  # From App Credentials
ZOOM_SECRET_TOKEN=your_webhook_token   # From Feature → Webhook
```

## Option 1: RTMSManager (Recommended)

Clone the official samples and use RTMSManager:

```bash
git clone https://github.com/zoom/rtms-samples.git
cd rtms-samples/boilerplate/working_js
npm install
```

```javascript
import { RTMSManager } from './library/javascript/rtmsManager/RTMSManager.js';
import express from 'express';
import crypto from 'crypto';

const app = express();
app.use(express.json());

// Initialize with credentials
await RTMSManager.init({
  credentials: {
    meeting: {
      clientId: process.env.ZOOM_CLIENT_ID,
      clientSecret: process.env.ZOOM_CLIENT_SECRET,
      secretToken: process.env.ZOOM_SECRET_TOKEN,
    }
  },
  // Use bitmask: AUDIO(1) | TRANSCRIPT(8) = 9
  mediaTypes: RTMSManager.MEDIA.AUDIO | RTMSManager.MEDIA.TRANSCRIPT,
  logging: 'info'
});

// Handle media events
RTMSManager.on('audio', ({ buffer, userName }) => {
  console.log(`Audio from ${userName}: ${buffer.length} bytes`);
});

RTMSManager.on('transcript', ({ text, userName }) => {
  console.log(`${userName}: ${text}`);
});

RTMSManager.on('chat', ({ text, userName }) => {
  console.log(`[Chat] ${userName}: ${text}`);
});

RTMSManager.on('sharescreen', ({ buffer, userName }) => {
  console.log(`Screen share from ${userName}`);
});

// CRITICAL: Respond 200 IMMEDIATELY before any processing!
app.post('/webhook', (req, res) => {
  res.status(200).send();  // FIRST!

  const { event, payload } = req.body;

  // Handle URL validation challenge
  if (event === 'endpoint.url_validation') {
    const hash = crypto
      .createHmac('sha256', process.env.ZOOM_SECRET_TOKEN)
      .update(payload.plainToken)
      .digest('hex');
    return res.json({ plainToken: payload.plainToken, encryptedToken: hash });
  }

  // Feed RTMS events to manager
  RTMSManager.handleEvent(event, payload);
});

await RTMSManager.start();
app.listen(3000, () => console.log('RTMS server on port 3000'));
```

## Option 2: @zoom/rtms SDK

```bash
npm install @zoom/rtms express
```

```javascript
import rtms from "@zoom/rtms";

const RTMS_EVENTS = ["meeting.rtms_started", "webinar.rtms_started", "session.rtms_started"];

rtms.onWebhookEvent(({ event, payload }) => {
  if (!RTMS_EVENTS.includes(event)) return;

  const client = new rtms.Client();

  client.onAudioData((data, timestamp, metadata) => {
    console.log(`Audio from ${metadata.userName}`);
  });

  client.onTranscriptData((data, timestamp, metadata) => {
    console.log(`${metadata.userName}: ${data}`);
  });

  client.onChatData((data, timestamp, metadata) => {
    console.log(`[Chat] ${metadata.userName}: ${data}`);
  });

  client.onScreenShareData((data, timestamp, metadata) => {
    console.log(`Screen share from ${metadata.userName}`);
  });

  // SDK accepts both meeting_uuid and session_id transparently
  client.join(payload);
});
```

## Zoom App Setup Steps

### For Meetings and Webinars (General App)

1. Go to [marketplace.zoom.us](https://marketplace.zoom.us)
2. Click **Develop** → **Build App**
3. Choose **General App** → **User-Managed**
4. Features → Access → **Enable Event Subscription**
5. Add Events → Search "rtms" → Select RTMS endpoints:
   - `meeting.rtms_started`
   - `meeting.rtms_stopped`
   - `webinar.rtms_started` (if using webinars)
   - `webinar.rtms_stopped` (if using webinars)
6. Scopes → Add Scopes → Search "rtms" → Add:
   - `meeting:read:meeting_audio`
   - `meeting:read:meeting_video`
   - `meeting:read:meeting_transcript`
   - `meeting:read:meeting_chat`
   - `webinar:read:webinar_audio` (if using webinars)
   - `webinar:read:webinar_video` (if using webinars)
   - `webinar:read:webinar_transcript` (if using webinars)
   - `webinar:read:webinar_chat` (if using webinars)

### For Video SDK (Video SDK App)

1. Go to [marketplace.zoom.us](https://marketplace.zoom.us)
2. Click **Develop** → **Build App**
3. Choose **Video SDK App**
4. Add Events:
   - `session.rtms_started`
   - `session.rtms_stopped`
5. Use SDK Key and SDK Secret for authentication (not OAuth credentials)

## How to Start RTMS

RTMS must be started for each meeting/webinar/session. Options:

| Product | How to Start | Webhook Event |
|---------|--------------|---------------|
| Meeting | Zoom client, REST API, Zoom App SDK, or **autostart** (zoom.us settings) | `meeting.rtms_started` |
| Webinar | Zoom client, REST API, Zoom App SDK, or **autostart** (zoom.us settings) | `webinar.rtms_started` |
| Video SDK | Video SDK client or REST API | `session.rtms_started` |
| Zoom Contact Center Voice | Product-specific RTMS/ZCC Voice flow | Product-specific RTMS/ZCC Voice events |

> **Webinar note**: Panelists have full audio/video streams. Attendee streams may not be available individually.

> **March 2026 note**: transcript handshakes now support `src_language` plus `enable_lid`, media socket keep-alive tolerance is now about **65s**, and RTMS supports one selected participant camera stream at a time via `VIDEO_SINGLE_INDIVIDUAL_STREAM` + `VIDEO_SUBSCRIPTION_REQ`.

## Deployment with Reverse Proxy

When deploying behind nginx with a path prefix (e.g., `/my-app/`):

1. **Socket.IO path must match nginx config**:
```javascript
const socketPath = window.location.pathname.includes('/my-app')
    ? '/my-app/rtms-socket'
    : '/rtms-socket';
const socket = io({ path: socketPath });
```

2. **API calls must use relative paths**:
```javascript
const basePath = window.location.pathname.replace(/\/$/, '');
fetch(`${basePath}/api/sessions`);  // NOT fetch('/api/sessions')
```

3. **Nginx WebSocket proxy**:
```nginx
location /my-app/rtms-socket {
    proxy_pass http://YOUR_RTMS_BACKEND_HOST:3000/rtms-socket;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}
```

## Next Steps

- [Media Types](media-types.md) - All 5 data types (audio, video, transcript, chat, screen share)
- [Connection](connection.md) - WebSocket protocol & message types
- [Webhooks](webhooks.md) - Event subscription details

## Resources

- **RTMS docs**: https://developers.zoom.us/docs/rtms/
- **rtms-samples**: https://github.com/zoom/rtms-samples
