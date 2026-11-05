# RTMS Connection Architecture

RTMS uses a **two-phase WebSocket design** to separate control plane from data plane.

## Overview

> **Multi-Product Note**: The two-phase WebSocket design described here is **identical** for all RTMS products (meetings, webinars, and Video SDK sessions). The only difference is the initial webhook event name and payload ID field. Once connected, the signaling and media protocols are the same.

```
┌─────────────────────────────────────────────────────────────┐
│                    Zoom Meeting                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Zoom RTMS Backend                         │
│  ┌─────────────────────┐    ┌─────────────────────────────┐ │
│  │  Signaling Server   │    │     Media Server            │ │
│  │  (Control Plane)    │    │     (Data Plane)            │ │
│  └──────────┬──────────┘    └──────────────┬──────────────┘ │
└─────────────┼───────────────────────────────┼───────────────┘
              │                               │
              ▼                               ▼
┌─────────────────────────────────────────────────────────────┐
│                      Your Server                             │
│  ┌─────────────────────┐    ┌─────────────────────────────┐ │
│  │  Signaling Socket   │    │     Media Socket            │ │
│  │  - Handshake        │    │     - Audio data            │ │
│  │  - Start/Stop       │    │     - Video data            │ │
│  │  - Heartbeat        │    │     - Transcript            │ │
│  └─────────────────────┘    └─────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Two-Phase Design

### Phase 1: Signaling WebSocket (Control Plane)

**Purpose**: Authentication, session control, heartbeats

| Responsibility | Description |
|----------------|-------------|
| Authentication | Validate signature, establish session |
| Media Server Discovery | Returns media server URL in handshake response |
| Stream Control | Start/stop streaming commands |
| Heartbeat | Keep connection alive (msg_type 12/13) |
| Event Notifications | Participant join/leave, sharing start/stop |

**URL Source**: From `server_urls` in webhook payload

**Message Flow**:
```
Client                          Signaling Server
  │                                    │
  │──── Handshake Request (1) ────────>│
  │<─── Handshake Response (2) ────────│  <- Contains media_server.server_urls
  │                                    │
  │──── Client Ready (7) ─────────────>│  <- After media handshake complete
  │                                    │
  │<─── Keep Alive Request (12) ───────│
  │──── Keep Alive Response (13) ─────>│
  │                                    │
```

### Phase 2: Media WebSocket (Data Plane)

**Purpose**: Actual audio, video, transcript, chat, screen share data

| Responsibility | Description |
|----------------|-------------|
| Media Configuration | Set audio/video parameters (codec, resolution, fps) |
| Media Streaming | Receive binary media data |
| Heartbeat | Keep connection alive (msg_type 12/13) |

**URL Source**: From signaling handshake response (`media_server.server_urls.all`)

**Message Flow**:
```
Client                          Media Server
  │                                    │
  │──── Media Handshake Request (3) ──>│  <- With media_params
  │<─── Media Handshake Response (4) ──│
  │                                    │
  │<─── Audio Data (14) ───────────────│
  │<─── Video Data (15) ───────────────│
  │<─── Screen Share Data (16) ────────│
  │<─── Transcript Data (17) ──────────│
  │<─── Chat Data (18) ────────────────│
  │                                    │
  │<─── Keep Alive Request (12) ───────│
  │──── Keep Alive Response (13) ─────>│
  │                                    │
```

## Why Two Connections?

| Benefit | Explanation |
|---------|-------------|
| **Separation of Concerns** | Control logic doesn't interfere with media streaming |
| **Independent Scaling** | Signaling and media servers scale differently |
| **Fault Isolation** | Media reconnection doesn't require re-auth |
| **Split Mode Support** | Each media type can have its own connection |

## Connection Modes

### Split Mode (Recommended)

Each media type gets its own dedicated WebSocket connection:

```
Signaling WS ─────┬───> Audio WS
                  ├───> Video WS
                  ├───> Transcript WS
                  └───> Screen Share WS
```

**Advantages**:
- Independent reconnection per media type
- Better reliability
- Fault isolation

### Unified Mode

One media WebSocket for all media types:

```
Signaling WS ─────> Media WS (all types)
```

**When to use**:
- Real-time audio+video muxing where sync matters
- Simpler implementation for small projects

## Signature Generation

Both signaling and media handshakes require HMAC-SHA256 signature:

```javascript
// For meetings and webinars: use meeting_uuid
const message = `${clientId},${meetingUuid},${streamId}`;
// For Video SDK: use session_id
const message = `${clientId},${sessionId},${streamId}`;

// Generic approach: use whichever ID is present
const idValue = payload.meeting_uuid || payload.session_id;
const message = `${clientId},${idValue},${streamId}`;
const signature = crypto.createHmac('sha256', clientSecret)
  .update(message)
  .digest('hex');
```

> **Important**: Webinars use `meeting_uuid` (not `webinar_uuid`). Video SDK uses `session_id`.

**Components**:
- `clientId`: OAuth Client ID (General App) or SDK Key (Video SDK App)
- `meetingUuid` / `sessionId`: From webhook payload (`meeting_uuid` for meetings/webinars, `session_id` for Video SDK)
- `streamId`: From webhook payload (`rtms_stream_id`)
- `clientSecret`: OAuth Client Secret (General App) or SDK Secret (Video SDK App)

## Heartbeat Protocol

**CRITICAL**: Both connections require heartbeat responses.

When you receive `msg_type: 12` (Keep Alive Request):

```javascript
// Immediately respond with msg_type: 13
ws.send(JSON.stringify({
  msg_type: 13,
  timestamp: receivedMessage.timestamp
}));
```

**Timeout**:
- Signaling: ~60 seconds without heartbeat response
- Media: ~65 seconds without heartbeat response

**Failure to respond = connection closed!**

## Reconnection

RTMS does **NOT** auto-reconnect. You must implement:

```javascript
ws.on('close', (code, reason) => {
  console.log(`Connection closed: ${code} ${reason}`);

  // Implement exponential backoff
  setTimeout(() => {
    reconnect();
  }, retryDelay);

  retryDelay = Math.min(retryDelay * 2, 30000);
});
```

**Timeouts**:
| Connection | Reconnection Window |
|------------|---------------------|
| Signaling | 60 seconds |
| Media | 65 seconds |

## Server URL Geo-Routing

Server URLs contain region codes:

| Code | Location |
|------|----------|
| `sjc` | San Jose, California |
| `iad` | Washington DC |
| `sin` | Singapore |
| `fra` | Frankfurt, Germany |
| `syd` | Sydney, Australia |

**Example**: `wss://rtms-sjc1.zoom.us/...`

For production, route to workers in the same region as the Zoom server for lower latency.

## Next Steps

- **[Lifecycle Flow](lifecycle-flow.md)** - Complete webhook-to-streaming sequence
- **[SDK Quickstart](../examples/sdk-quickstart.md)** - SDK handles all this for you
- **[Manual WebSocket](../examples/manual-websocket.md)** - Full protocol implementation
