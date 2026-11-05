# RTMS - Connection

WebSocket connection protocol details.

## Connection Flow

```
1. Receive meeting/webinar/session.rtms_started webhook
           ↓
2. Extract server_urls, stream_id, and meeting_uuid or session_id
           ↓
3. Generate signature (HMAC-SHA256) using meeting_uuid or session_id
           ↓
4. Connect to signaling WebSocket
           ↓
5. Send handshake request (msg_type 1)
           ↓
6. Receive handshake response (msg_type 2) with media server URL
           ↓
7. Connect to media WebSocket(s)
           ↓
8. Send media handshake (msg_type 3)
           ↓
9. Receive media handshake response (msg_type 4)
           ↓
10. Send ready to receive (msg_type 7)
           ↓
11. Receive media data (msg_type 14-18)
           ↓
12. Respond to heartbeats (msg_type 12 → 13)
           ↓
13. Optionally react to `PARTICIPANT_VIDEO_ON/OFF`, send `VIDEO_SUBSCRIPTION_REQ`, or gracefully terminate with `STREAM_CLOSE_REQ`
```

## Signature Generation

```javascript
const crypto = require('crypto');

// For meetings and webinars: use meeting_uuid
// For Video SDK: use session_id
// Webinars still use meeting_uuid (NOT webinar_uuid)
function generateSignature(clientId, idValue, streamId, clientSecret) {
  const message = `${clientId},${idValue},${streamId}`;
  return crypto.createHmac('sha256', clientSecret).update(message).digest('hex');
}

// Extract the correct ID from any product's webhook payload
const idValue = payload.meeting_uuid || payload.session_id;
```

## Signaling Message Types

| msg_type | Name | Direction | Description |
|----------|------|-----------|-------------|
| 1 | Handshake Request | Client → Server | Initiate connection |
| 2 | Handshake Response | Server → Client | Returns media server URL |
| 3 | Media Handshake Request | Client → Server | Request specific media types |
| 4 | Media Handshake Response | Server → Client | Confirms media subscription |
| 7 | Ready to Receive | Client → Server | Signal ready for data |
| 12 | Keep Alive Request | Server → Client | Heartbeat ping |
| 13 | Keep Alive Response | Client → Server | Heartbeat pong |

## Media Message Types

| msg_type | Media Type |
|----------|------------|
| 14 | Audio |
| 15 | Video |
| 16 | Screen Share |
| 17 | Transcript |
| 18 | Chat |

## Critical Gotchas

### 1. Only ONE Connection Per Stream!

```javascript
// WRONG - Connecting twice kicks out first connection
connectToRTMS(serverUrl, streamId);  // Connection 1
connectToRTMS(serverUrl, streamId);  // Connection 2 - kicks out Connection 1!

// CORRECT - Only connect once
if (!activeConnections.has(streamId)) {
  connectToRTMS(serverUrl, streamId);
  activeConnections.set(streamId, ws);
}
```

### 2. Heartbeat is MANDATORY

When you receive msg_type 12, you MUST respond with msg_type 13:

```javascript
ws.on('message', (data) => {
  const msg = JSON.parse(data);

  if (msg.msg_type === 12) {  // Keep Alive Request
    ws.send(JSON.stringify({
      msg_type: 13,  // Keep Alive Response
      timestamp: msg.timestamp
    }));
  }
});
```

### 3. Reconnection is YOUR Responsibility

RTMS does NOT auto-reconnect. Implement your own retry logic:

| Server Type | Timeout |
|-------------|---------|
| Media Server | 65 seconds keep-alive tolerance before timeout |
| Signaling Server | 60 seconds to reconnect |

```javascript
ws.on('close', () => {
  // Implement exponential backoff
  setTimeout(() => reconnect(), retryDelay);
  retryDelay = Math.min(retryDelay * 2, 30000);
});
```

## Transcript LID Control

The transcript media handshake now supports explicit Language Identification control.

```javascript
mediaWs.send(JSON.stringify({
  msg_type: 3,
  protocol_version: 1,
  meeting_uuid: idValue,
  rtms_stream_id: streamId,
  signature,
  media_type: 8, // TRANSCRIPT
  media_params: {
    transcript: {
      content_type: 5,   // TEXT
      src_language: 9,   // English
      enable_lid: false  // Lock to src_language instead of auto-switching
    }
  }
}));
```

Use `enable_lid: false` when:

- the meeting should stay on a known language
- language-switching is undesirable
- you want more predictable downstream transcript processing

## Single Individual Video Subscription Flow

RTMS now supports subscribing to **one participant camera stream at a time**.

1. Open a video media socket with `data_opt = VIDEO_SINGLE_INDIVIDUAL_STREAM`
2. Subscribe to `PARTICIPANT_VIDEO_ON` and `PARTICIPANT_VIDEO_OFF`
3. When an event arrives, choose the `user_id` you want
4. Send `VIDEO_SUBSCRIPTION_REQ` on the signaling socket
5. Wait for `VIDEO_SUBSCRIPTION_RESP`
6. Expect the newest successful subscription to replace the previous participant stream

```javascript
// Signaling socket: subscribe to control-plane events
signalingWs.send(JSON.stringify({
  msg_type: 5, // EVENT_SUBSCRIPTION
  events: [
    { event_type: 8, subscribe: true }, // PARTICIPANT_VIDEO_ON
    { event_type: 9, subscribe: true }  // PARTICIPANT_VIDEO_OFF
  ]
}));

// Signaling socket: select a participant stream
signalingWs.send(JSON.stringify({
  msg_type: 28, // VIDEO_SUBSCRIPTION_REQ
  user_id: selectedUserId,
  subscribe: true,
  timestamp: Date.now()
}));
```

The March 2026 changelog did not publish the numeric values for the new message types. Use the protocol definitions before hard-coding them.

## Graceful Stream Closure

The backend can now request clean shutdown over the signaling socket:

```javascript
signalingWs.send(JSON.stringify({
  msg_type: 21, // STREAM_CLOSE_REQ
  rtms_stream_id: streamId
}));
```

Expect:

- `STREAM_CLOSE_RESP`
- then normal connection shutdown / cleanup

Use this when your app wants deterministic teardown instead of waiting for a stop webhook or socket failure.

## Split vs Unified Mode

| Mode | Description | Best For |
|------|-------------|----------|
| **Split** | One connection per media type | Most use cases. Media server supports multiple connections with different media types |
| **Unified** | One connection for all media | Real-time audio+video streaming/muxing where sync matters |

## Low-Level Connection Example

```javascript
const WebSocket = require('ws');
const crypto = require('crypto');

async function connectRTMS(webhookPayload) {
  const { server_urls, rtms_stream_id } = webhookPayload;
  // meeting_uuid for meetings/webinars, session_id for Video SDK
  const idValue = webhookPayload.meeting_uuid || webhookPayload.session_id;

  // Generate signature
  const signature = crypto
    .createHmac('sha256', process.env.ZOOM_CLIENT_SECRET)
    .update(`${process.env.ZOOM_CLIENT_ID},${idValue},${rtms_stream_id}`)
    .digest('hex');

  // Connect to signaling server
  const signalingWs = new WebSocket(server_urls, {
    headers: {
      'X-Zoom-RTMS-Stream-Id': rtms_stream_id,
      'X-Zoom-RTMS-Signature': signature
    }
  });

  signalingWs.on('open', () => {
    // Send handshake request
    signalingWs.send(JSON.stringify({
      msg_type: 1,
      protocol_version: 1,
      client_id: process.env.ZOOM_CLIENT_ID,
      meeting_uuid: idValue,          // Works for both meeting_uuid and session_id
      stream_id: rtms_stream_id,
      signature: signature,
      media_type: 9  // AUDIO(1) | TRANSCRIPT(8)
    }));
  });

  signalingWs.on('message', (data) => {
    const msg = JSON.parse(data);

    switch (msg.msg_type) {
      case 2:  // Handshake response
        // Connect to media server from msg.media_server_url
        connectMediaServer(msg.media_server_url);
        break;
      case 12:  // Keep alive request
        signalingWs.send(JSON.stringify({ msg_type: 13, timestamp: msg.timestamp }));
        break;
    }
  });

  signalingWs.on('error', (error) => {
    console.error('Signaling error:', error);
  });

  signalingWs.on('close', (code, reason) => {
    console.log('Signaling closed:', code, reason);
    // Implement reconnection logic
  });
}
```

## Resources

- **RTMS_CONNECTION_FLOW.md**: https://github.com/zoom/rtms-samples/blob/main/RTMS_CONNECTION_FLOW.md
- **ARCHITECTURE.md**: https://github.com/zoom/rtms-samples/blob/main/ARCHITECTURE.md
- **TROUBLESHOOTING.md**: https://github.com/zoom/rtms-samples/blob/main/TROUBLESHOOTING.md
