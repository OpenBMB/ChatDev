# Zoom Realtime Media Streams (RTMS)

Background reference for live Zoom media pipelines. Prefer `build-zoom-bot` first, then use this skill for stream types, capabilities, and RTMS-specific implementation constraints.

# Zoom Realtime Media Streams (RTMS)

Expert guidance for accessing live audio, video, transcript, chat, and screen share data from Zoom meetings, webinars, Video SDK sessions, and Zoom Contact Center Voice in real-time. RTMS uses a WebSocket-based protocol with open standards and does not require a meeting bot to capture the media plane.

## Read This First (Critical)

RTMS is primarily a **backend media ingestion service**.

- Your backend receives and processes live media: **audio, video, screen share, chat, transcript**.
- RTMS is not a frontend UI SDK by itself.
- Processing is **event-triggered**: backend waits for RTMS start webhook events before stream handling begins.

Optional architecture (common):

- Add a **Zoom App SDK** frontend for in-client UI/controls.
- Stream backend RTMS outputs to frontend via **WebSocket** (or SSE, gRPC, queue workers, etc.).

Use RTMS for media/data plane, and use frontend frameworks/Zoom Apps for presentation + user interactions.

**Official Documentation**: https://developers.zoom.us/docs/rtms/
**SDK Reference (JS)**: https://zoom.github.io/rtms/js/
**SDK Reference (Python)**: https://zoom.github.io/rtms/py/
**Sample Repository**: https://github.com/zoom/rtms-samples

## Quick Links

**New to RTMS? Follow this path:**

1. **[Connection Architecture](../concepts/connection-architecture.md)** - Two-phase WebSocket design
2. **[SDK Quickstart](../examples/sdk-quickstart.md)** - Fastest way to receive media (recommended)
3. **[Manual WebSocket](../examples/manual-websocket.md)** - Full protocol control without SDK
4. **[Media Types](../references/media-types.md)** - Audio, video, transcript, chat, screen share

**Complete Implementation:**
- **[RTMS Bot](../examples/rtms-bot.md)** - End-to-end bot implementation guide

**Reference:**
- **[Lifecycle Flow](../concepts/lifecycle-flow.md)** - Complete webhook-to-streaming flow
- **[Data Types](../references/data-types.md)** - All enums and constants
- **[Webhooks](../references/webhooks.md)** - Event subscription details
- **[Environment Variables](../references/environment-variables.md)** - credential modes and runtime knobs
- **[Quickstart Notes](../references/quickstart.md)** - Secondary quickstart guide
- **Integrated Index** - see the section below in this file

**Having issues?**
- Connection fails -> [Common Issues](../troubleshooting/common-issues.md)
- Duplicate connections -> [Webhook Gotchas](../troubleshooting/common-issues.md)
- No audio/video -> [Media Configuration](../references/media-types.md)
- Start with preflight checks -> [5-Minute Runbook](../RUNBOOK.md)

## Supported Products

| Product | Webhook Event | Payload ID | App Type |
|---------|--------------|------------|----------|
| **Meetings** | `meeting.rtms_started` / `meeting.rtms_stopped` | `meeting_uuid` | General App |
| **Webinars** | `webinar.rtms_started` / `webinar.rtms_stopped` | `meeting_uuid` (same!) | General App |
| **Video SDK** | `session.rtms_started` / `session.rtms_stopped` | `session_id` | Video SDK App |
| **Zoom Contact Center Voice** | Product-specific RTMS/ZCC Voice events | Product-specific stream/session identifiers | Contact Center / approved RTMS integration |

Once connected, the core signaling/media socket model is shared across products. Meetings, webinars, and Video SDK sessions use the familiar start/stop webhooks. Zoom Contact Center Voice adds its own RTMS/ZCC Voice event family and should be treated as the same transport model with product-specific event payloads.

## RTMS Overview

RTMS is a data pipeline that gives your app access to live media from Zoom meetings, webinars, and Video SDK sessions **without participant bots**. Instead of having automated clients join meetings, use RTMS to collect media data directly from Zoom's infrastructure.

### What RTMS Provides

| Media Type | Format | Use Cases |
|------------|--------|-----------|
| **Audio** | PCM (L16), G.711, G.722, Opus | Transcription, voice analysis, recording |
| **Video** | H.264, JPG, PNG | Recording, AI vision, thumbnails, active participant selection |
| **Screen Share** | H.264, JPG, PNG | Content capture, slide extraction |
| **Transcript** | JSON text | Meeting notes, search, compliance |
| **Chat** | JSON text | Archive, sentiment analysis |

### March 2026 Protocol Changes

- **Zoom Contact Center Voice support**: RTMS now covers Contact Center Voice audio and transcript scenarios.
- **Transcript Language Identification control**: transcript media handshakes now support `src_language` and `enable_lid`. Default behavior is LID enabled. Set `enable_lid: false` to force a fixed language.
- **Single individual video stream subscription**: RTMS can now stream one participant's camera feed at a time when `data_opt` is set to `VIDEO_SINGLE_INDIVIDUAL_STREAM`.
- **Graceful client-initiated shutdown**: backends can send `STREAM_CLOSE_REQ` over the signaling socket and wait for `STREAM_CLOSE_RESP`.
- **Media keep-alive tolerance increased**: media socket keep-alive timeout is now **65 seconds**, not 35.

### Two Approaches

| Approach | Best For | Complexity |
|----------|----------|------------|
| **SDK** (`@zoom/rtms`) | Most use cases | Low - handles WebSocket complexity |
| **Manual WebSocket** | Custom protocols, other languages | High - full protocol implementation |

## Prerequisites

- **Node.js 20.3.0+** (24 LTS recommended) for JavaScript SDK
- **Python 3.10+** for Python SDK
- Zoom General App (for meetings/webinars) or Video SDK App (for Video SDK) with RTMS feature enabled
- Webhook endpoint for RTMS events
- Server to receive WebSocket streams

> **Need RTMS access?** Post in [Zoom Developer Forum](https://devforum.zoom.us/) requesting RTMS access with your use case.

## Quick Start (SDK - Recommended)

```javascript
import rtms from "@zoom/rtms";

// All RTMS start/stop events across products
const RTMS_EVENTS = ["meeting.rtms_started", "webinar.rtms_started", "session.rtms_started"];

// Handle webhook events
rtms.onWebhookEvent(({ event, payload }) => {
  if (!RTMS_EVENTS.includes(event)) return;

  const client = new rtms.Client();

  client.onAudioData((data, timestamp, metadata) => {
    console.log(`Audio from ${metadata.userName}: ${data.length} bytes`);
  });

  client.onTranscriptData((data, timestamp, metadata) => {
    const text = data.toString('utf8');
    console.log(`${metadata.userName}: ${text}`);
  });

  client.onJoinConfirm((reason) => {
    console.log(`Joined session: ${reason}`);
  });

  // SDK handles all WebSocket connections automatically
  // Accepts both meeting_uuid and session_id transparently
  client.join(payload);
});
```

## Quick Start (Manual WebSocket)

For full control or non-SDK languages, implement the two-phase WebSocket protocol:

```javascript
const WebSocket = require('ws');
const crypto = require('crypto');

const RTMS_EVENTS = ['meeting.rtms_started', 'webinar.rtms_started', 'session.rtms_started'];

// 1. Generate signature
// For meetings/webinars: uses meeting_uuid. For Video SDK: uses session_id.
function generateSignature(clientId, idValue, streamId, clientSecret) {
  const message = `${clientId},${idValue},${streamId}`;
  return crypto.createHmac('sha256', clientSecret).update(message).digest('hex');
}

// 2. Handle webhook
app.post('/webhook', (req, res) => {
  res.status(200).send();  // CRITICAL: Respond immediately!

  const { event, payload } = req.body;
  if (RTMS_EVENTS.includes(event)) {
    connectToRTMS(payload);
  }
});

// 3. Connect to signaling WebSocket
function connectToRTMS(payload) {
  const { server_urls, rtms_stream_id } = payload;
  // meeting_uuid for meetings/webinars, session_id for Video SDK
  const idValue = payload.meeting_uuid || payload.session_id;
  const signature = generateSignature(CLIENT_ID, idValue, rtms_stream_id, CLIENT_SECRET);

  const signalingWs = new WebSocket(server_urls);

  signalingWs.on('open', () => {
    signalingWs.send(JSON.stringify({
      msg_type: 1,  // Handshake request
      protocol_version: 1,
      meeting_uuid: idValue,
      rtms_stream_id,
      signature,
      media_type: 9  // AUDIO(1) | TRANSCRIPT(8)
    }));
  });

  // ... handle responses, connect to media WebSocket
}
```

**See**: [Manual WebSocket Guide](../examples/manual-websocket.md) for complete implementation.

## Media Type Bitmask

Combine types with bitwise OR:

| Type | Value | Description |
|------|-------|-------------|
| Audio | 1 | PCM audio samples |
| Video | 2 | H.264/JPG video frames |
| Screen Share | 4 | **Separate from video!** |
| Transcript | 8 | Real-time speech-to-text |
| Chat | 16 | In-meeting chat messages |
| All | 32 | All media types |

**Example**: Audio + Transcript = `1 | 8` = `9`

## Critical Gotchas

| Issue | Solution |
|-------|----------|
| **Only 1 connection allowed** | New connections kick out existing ones. Track active sessions! |
| **Respond 200 immediately** | If webhook delays, Zoom retries creating duplicate connections |
| **Heartbeat mandatory** | Respond to msg_type 12 with msg_type 13, or connection dies |
| **Reconnection is YOUR job** | RTMS doesn't auto-reconnect. Media keep-alive tolerance is now about **65s**; signaling remains around **60s** |
| **Transcript language drift** | Use `src_language` plus `enable_lid: false` when you want fixed-language transcription instead of automatic language switching |
| **Single participant video only** | `VIDEO_SINGLE_INDIVIDUAL_STREAM` supports one participant at a time. A new `VIDEO_SUBSCRIPTION_REQ` overrides the previous selection |
| **Graceful close is explicit now** | Use `STREAM_CLOSE_REQ` / `STREAM_CLOSE_RESP` when your backend wants to terminate the stream cleanly |

## Environment Variables

### SDK Environment Variables

```bash
# Required - Authentication
ZM_RTMS_CLIENT=your_client_id          # Zoom OAuth Client ID
ZM_RTMS_SECRET=your_client_secret      # Zoom OAuth Client Secret

# Optional - Webhook server
ZM_RTMS_PORT=8080                      # Default: 8080
ZM_RTMS_PATH=/webhook                  # Default: /

# Optional - Logging
ZM_RTMS_LOG_LEVEL=info                 # error, warn, info, debug, trace
ZM_RTMS_LOG_FORMAT=progressive         # progressive or json
ZM_RTMS_LOG_ENABLED=true
```

### Manual Implementation Variables

```bash
ZOOM_CLIENT_ID=your_client_id
ZOOM_CLIENT_SECRET=your_client_secret
ZOOM_SECRET_TOKEN=your_webhook_token   # For webhook validation
```

## Zoom App Setup

### For Meetings and Webinars (General App)

1. Go to [marketplace.zoom.us](https://marketplace.zoom.us) -> Develop -> Build App
2. Choose **General App** -> **User-Managed**
3. Features -> Access -> **Enable Event Subscription**
4. Add Events -> Search "rtms" -> Select:
   - `meeting.rtms_started`
   - `meeting.rtms_stopped`
   - `webinar.rtms_started` (if using webinars)
   - `webinar.rtms_stopped` (if using webinars)
5. Scopes -> Add Scopes -> Search "rtms" -> Add:
   - `meeting:read:meeting_audio`
   - `meeting:read:meeting_video`
   - `meeting:read:meeting_transcript`
   - `meeting:read:meeting_chat`
   - `webinar:read:webinar_audio` (if using webinars)
   - `webinar:read:webinar_video` (if using webinars)
   - `webinar:read:webinar_transcript` (if using webinars)
   - `webinar:read:webinar_chat` (if using webinars)

### For Video SDK (Video SDK App)

1. Go to [marketplace.zoom.us](https://marketplace.zoom.us) -> Develop -> Build App
2. Choose **Video SDK App**
3. Use your SDK Key and SDK Secret (not OAuth Client ID/Secret)
4. Add Events:
   - `session.rtms_started`
   - `session.rtms_stopped`

## Sample Repositories

### Official Samples

| Repository | Description |
|------------|-------------|
| [rtms-samples](https://github.com/zoom/rtms-samples) | RTMSManager, boilerplates, AI samples |
| [rtms-quickstart-js](https://github.com/zoom/rtms-quickstart-js) | JavaScript SDK quickstart |
| [rtms-quickstart-py](https://github.com/zoom/rtms-quickstart-py) | Python SDK quickstart |
| [rtms-sdk-cpp](https://github.com/zoom/rtms-sdk-cpp) | C++ SDK |
| [zoom-rtms](https://github.com/zoom/rtms) | Main SDK repository |

### AI Integration Samples

| Sample | Description |
|--------|-------------|
| [rtms-meeting-assistant-starter-kit](https://github.com/zoom/rtms-meeting-assistant-starter-kit) | AI meeting assistant with summaries |
| [arlo-meeting-assistant](https://github.com/zoom/arlo-meeting-assistant) | Production meeting assistant with DB |
| [videosdk-rtms-transcribe-audio](https://github.com/zoom/videosdk-rtms-transcribe-audio) | Whisper transcription |

## Complete Documentation

### Concepts
- **[Connection Architecture](../concepts/connection-architecture.md)** - Two-phase WebSocket design
- **[Lifecycle Flow](../concepts/lifecycle-flow.md)** - Webhook to streaming flow

### Examples
- **[SDK Quickstart](../examples/sdk-quickstart.md)** - Using @zoom/rtms SDK
- **[Manual WebSocket](../examples/manual-websocket.md)** - Raw protocol implementation
- **[RTMS Bot](../examples/rtms-bot.md)** - Complete bot implementation guide
- **[AI Integration](../examples/ai-integration.md)** - Transcription and analysis patterns

### References
- **[Media Types](../references/media-types.md)** - Audio, video, transcript, chat, screen share
- **[Data Types](../references/data-types.md)** - All enums and constants
- **[Connection](../references/connection.md)** - WebSocket protocol details
- **[Webhooks](../references/webhooks.md)** - Event subscription

### Troubleshooting
- **[Common Issues](../troubleshooting/common-issues.md)** - FAQ and solutions

## Resources

- **Official docs**: https://developers.zoom.us/docs/rtms/
- **Data types**: https://developers.zoom.us/docs/rtms/data-types/
- **Media params**: https://developers.zoom.us/docs/rtms/media-parameter-definition/
- **Developer forum**: https://devforum.zoom.us/

---

**Need help?** Start with Integrated Index section below for complete navigation.

---

## Integrated Index

_This section was migrated from `SKILL.md`._

RTMS provides real-time access to live audio, video, transcript, chat, and screen share from Zoom meetings, webinars, and Video SDK sessions.

## Critical Positioning

Treat RTMS as a **backend service** for receiving and processing media streams.

- Backend role: ingest audio/video/share/chat/transcript, run AI/analytics, persist/forward data.
- Optional frontend role: Zoom App SDK or web dashboard that consumes processed stream data from backend transport (WebSocket/SSE/other).
- Kickoff model: backend waits for RTMS start webhook events, then starts stream processing.

Do not model RTMS as a frontend-only SDK.

## Quick Start Path

**If you're new to RTMS, follow this order:**

1. **Run preflight checks first** -> [RUNBOOK.md](../RUNBOOK.md)
2. **Understand the architecture** -> [concepts/connection-architecture.md](../concepts/connection-architecture.md)
   - Two-phase WebSocket: Signaling + Media
   - Why RTMS doesn't use bots

3. **Choose your approach** -> SDK or Manual
   - SDK (recommended): [examples/sdk-quickstart.md](../examples/sdk-quickstart.md)
   - Manual WebSocket: [examples/manual-websocket.md](../examples/manual-websocket.md)

4. **Understand the lifecycle** -> [concepts/lifecycle-flow.md](../concepts/lifecycle-flow.md)
   - Webhook -> Signaling -> Media -> Streaming

5. **Configure media types** -> [references/media-types.md](../references/media-types.md)
   - Audio, video, transcript, chat, screen share

6. **Troubleshoot issues** -> [troubleshooting/common-issues.md](../troubleshooting/common-issues.md)
   - Connection problems, duplicate webhooks, missing data

---

## Documentation Structure

```
rtms/
├── SKILL.md                           # Main skill overview
├── SKILL.md                           # This file - navigation guide
│
├── concepts/                          # Core architectural patterns
│   ├── connection-architecture.md     # Two-phase WebSocket design
│   └── lifecycle-flow.md              # Webhook to streaming flow
│
├── examples/                          # Complete working code
│   ├── sdk-quickstart.md              # Using @zoom/rtms SDK
│   ├── manual-websocket.md            # Raw protocol implementation
│   ├── rtms-bot.md                    # Complete RTMS bot implementation
│   └── ai-integration.md              # Transcription and analysis
│
├── references/                        # Reference documentation
│   ├── media-types.md                 # Audio, video, transcript, chat, share
│   ├── data-types.md                  # All enums and constants
│   ├── connection.md                  # WebSocket protocol details
│   └── webhooks.md                    # Event subscription
│
└── troubleshooting/                   # Problem solving guides
    └── common-issues.md               # FAQ and solutions
```

---

## By Use Case

### I want to get meeting transcripts
1. [SDK Quickstart](../examples/sdk-quickstart.md) - Fastest approach
2. [Media Types](../references/media-types.md) - Transcript configuration
3. [AI Integration](../examples/ai-integration.md) - Whisper, Deepgram, AssemblyAI

### I want to record meetings
1. [Media Types](../references/media-types.md) - Audio + Video configuration
2. [SDK Quickstart](../examples/sdk-quickstart.md) - Receiving media
3. [AI Integration](../examples/ai-integration.md) - Gap-filled recording

### I want to build an AI meeting assistant
1. [AI Integration](../examples/ai-integration.md) - Complete patterns
2. [SDK Quickstart](../examples/sdk-quickstart.md) - Media ingestion
3. [Lifecycle Flow](../concepts/lifecycle-flow.md) - Event handling

### I want to build a complete RTMS bot
1. [RTMS Bot](../examples/rtms-bot.md) - **Complete implementation guide**
2. [Lifecycle Flow](../concepts/lifecycle-flow.md) - Webhook to streaming flow
3. [Connection Architecture](../concepts/connection-architecture.md) - Two-phase design

### I need full protocol control
1. [Manual WebSocket](../examples/manual-websocket.md) - **START HERE**
2. [Connection Architecture](../concepts/connection-architecture.md) - Two-phase design
3. [Data Types](../references/data-types.md) - All message types and enums
4. [Connection](../references/connection.md) - Protocol details

### I'm getting connection errors
1. [Common Issues](../troubleshooting/common-issues.md) - Diagnostic checklist
2. [Connection Architecture](../concepts/connection-architecture.md) - Verify flow
3. [Webhooks](../references/webhooks.md) - Validation and timing

### I want to understand the architecture
1. [Connection Architecture](../concepts/connection-architecture.md) - Two-phase WebSocket
2. [Lifecycle Flow](../concepts/lifecycle-flow.md) - Complete flow diagram
3. [Data Types](../references/data-types.md) - Protocol constants

---

## By Product

### I'm building for Zoom Meetings
- Standard RTMS setup. Webhook event: `meeting.rtms_started`. Uses General App with OAuth.
- Start with [SDK Quickstart](../examples/sdk-quickstart.md) or [Manual WebSocket](../examples/manual-websocket.md).

### I'm building for Zoom Webinars
- Same as meetings, but webhook event is `webinar.rtms_started`. Payload still uses `meeting_uuid` (NOT `webinar_uuid`).
- Add webinar scopes and event subscriptions. See [Webhooks](../references/webhooks.md).
- Only **panelist** streams are confirmed available. Attendee streams may not be individual.

### I'm building for Zoom Video SDK
- Webhook event: `session.rtms_started`. Payload uses `session_id` (NOT `meeting_uuid`).
- Requires a **Video SDK App** with SDK Key/Secret (not OAuth Client ID/Secret).
- Once connected, the protocol is **identical** to meetings.
- See [Webhooks](../references/webhooks.md) for payload details.

---

## Key Documents

### 1. Connection Architecture (CRITICAL)
**[concepts/connection-architecture.md](../concepts/connection-architecture.md)**

RTMS uses **two separate WebSocket connections**:
- **Signaling WebSocket**: Authentication, control, heartbeats
- **Media WebSocket**: Actual audio/video/transcript data

### 2. SDK vs Manual (DECISION POINT)
**[examples/sdk-quickstart.md](../examples/sdk-quickstart.md)** vs **[examples/manual-websocket.md](../examples/manual-websocket.md)**

| SDK | Manual |
|-----|--------|
| Handles WebSocket complexity | Full protocol control |
| Automatic reconnection | DIY reconnection |
| Less code | More code |
| Best for most use cases | Best for custom requirements |

### 3. Critical Gotchas (MOST COMMON ISSUES)
**[troubleshooting/common-issues.md](../troubleshooting/common-issues.md)**

1. **Respond 200 immediately** - Delayed webhook responses cause duplicates
2. **Only 1 connection per stream** - New connections kick out existing
3. **Heartbeat required** - Must respond to keep-alive or connection dies
4. **Track active sessions** - Prevent duplicate join attempts

---

## Key Learnings

### Critical Discoveries:

1. **Two-Phase WebSocket Design**
   - Signaling: Control plane (handshake, heartbeat, start/stop)
   - Media: Data plane (audio, video, transcript, chat, share)
   - See: [Connection Architecture](../concepts/connection-architecture.md)

2. **Webhook Response Timing**
   - MUST respond 200 BEFORE any processing
   - Delayed response -> Zoom retries -> duplicate connections
   - See: [Common Issues](../troubleshooting/common-issues.md)

3. **Heartbeat is Mandatory**
   - Signaling: Receive msg_type 12, respond with msg_type 13
   - Media: Same pattern
   - Failure to respond = connection closed
   - See: [Connection](../references/connection.md)

4. **Signature Generation**
   - Format: `HMAC-SHA256(clientSecret, "clientId,meetingUuid,streamId")`
   - For Video SDK, use `session_id` in place of `meetingUuid`
   - Webinars still use `meeting_uuid` (not `webinar_uuid`)
   - Required for both signaling and media handshakes
   - See: [Manual WebSocket](../examples/manual-websocket.md)

5. **Media Types are Bitmasks**
   - Audio=1, Video=2, Share=4, Transcript=8, Chat=16, All=32
   - Combine with OR: Audio+Transcript = 1|8 = 9
   - See: [Media Types](../references/media-types.md)

6. **Screen Share is SEPARATE from Video**
   - Different msg_type (16 vs 15)
   - Different media flag (4 vs 2)
   - Must subscribe separately
   - See: [Media Types](../references/media-types.md)

---

## Quick Reference

### "Connection fails"
-> [Common Issues](../troubleshooting/common-issues.md)

### "Duplicate connections"
-> [Webhook timing](../troubleshooting/common-issues.md)

### "No audio/video data"
-> [Media Types](../references/media-types.md) - Check configuration

### "How do I implement manually?"
-> [Manual WebSocket](../examples/manual-websocket.md)

### "What message types exist?"
-> [Data Types](../references/data-types.md)

### "How do I integrate AI?"
-> [AI Integration](../examples/ai-integration.md)

---

## Document Version

Based on **Zoom RTMS SDK v1.x** and official documentation as of 2026.

---

**Happy coding!**

Remember: Start with [SDK Quickstart](../examples/sdk-quickstart.md) for the fastest path, or [Manual WebSocket](../examples/manual-websocket.md) if you need full control.
