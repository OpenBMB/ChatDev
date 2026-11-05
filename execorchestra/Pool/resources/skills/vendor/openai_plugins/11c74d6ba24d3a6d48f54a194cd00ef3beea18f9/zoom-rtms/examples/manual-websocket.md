# Manual WebSocket Implementation

Full RTMS protocol implementation without the SDK. Use this for:
- Languages without SDK support
- Custom protocol requirements
- Learning the underlying protocol

## Overview

RTMS requires two WebSocket connections:
1. **Signaling WebSocket** - Control plane (handshake, heartbeat, start/stop)
2. **Media WebSocket** - Data plane (audio, video, transcript, chat, share)

## Complete Implementation

```javascript
const WebSocket = require('ws');
const crypto = require('crypto');
const express = require('express');

const app = express();
app.use(express.json());

// Configuration
const CLIENT_ID = process.env.ZOOM_CLIENT_ID;
const CLIENT_SECRET = process.env.ZOOM_CLIENT_SECRET;
const SECRET_TOKEN = process.env.ZOOM_SECRET_TOKEN;

// Active connections
const signalingConnections = new Map();
const mediaConnections = new Map();
const activeSessions = new Map();
const activeVideoUsers = new Map();

// ============================================
// SIGNATURE GENERATION
// Uses meeting_uuid for meetings/webinars, session_id for Video SDK
// ============================================

function generateSignature(clientId, idValue, streamId, clientSecret) {
  const message = `${clientId},${idValue},${streamId}`;
  return crypto.createHmac('sha256', clientSecret)
    .update(message)
    .digest('hex');
}

// ============================================
// WEBHOOK HANDLER
// ============================================

const RTMS_EVENTS = ['meeting.rtms_started', 'webinar.rtms_started', 'session.rtms_started'];
const RTMS_STOP_EVENTS = ['meeting.rtms_stopped', 'webinar.rtms_stopped', 'session.rtms_stopped'];

app.post('/webhook', (req, res) => {
  // CRITICAL: Respond 200 IMMEDIATELY before any processing!
  res.status(200).send();

  const { event, payload } = req.body;

  // Handle URL validation challenge
  if (event === 'endpoint.url_validation') {
    const hash = crypto
      .createHmac('sha256', SECRET_TOKEN)
      .update(payload.plainToken)
      .digest('hex');
    return res.json({
      plainToken: payload.plainToken,
      encryptedToken: hash
    });
  }

  // Handle RTMS events (meetings, webinars, and Video SDK)
  if (RTMS_EVENTS.includes(event)) {
    handleRTMSStarted(payload.object);
  } else if (RTMS_STOP_EVENTS.includes(event)) {
    handleRTMSStopped(payload.object);
  }
});

// ============================================
// RTMS START HANDLER
// ============================================

function handleRTMSStarted(payload) {
  const { rtms_stream_id, server_urls } = payload;
  // meeting_uuid for meetings/webinars, session_id for Video SDK
  const idValue = payload.meeting_uuid || payload.session_id;

  // Prevent duplicate connections
  if (activeSessions.has(rtms_stream_id)) {
    console.log('Already connected to this stream, ignoring');
    return;
  }

  activeSessions.set(rtms_stream_id, {
    idValue: idValue,
    startTime: Date.now()
  });

  connectToSignaling(idValue, rtms_stream_id, server_urls);
}

// ============================================
// SIGNALING WEBSOCKET
// ============================================

function connectToSignaling(idValue, streamId, serverUrl) {
  console.log('Connecting to signaling:', serverUrl);

  const signature = generateSignature(CLIENT_ID, idValue, streamId, CLIENT_SECRET);
  const ws = new WebSocket(serverUrl);

  signalingConnections.set(streamId, ws);

  ws.on('open', () => {
    console.log('Signaling connected, sending handshake');

    ws.send(JSON.stringify({
      msg_type: 1,                    // SIGNALING_HAND_SHAKE_REQ
      protocol_version: 1,
      meeting_uuid: idValue,          // Works for both meeting_uuid and session_id
      rtms_stream_id: streamId,
      sequence: Math.floor(Math.random() * 1000000),
      signature: signature,
      media_type: 9                   // AUDIO(1) | TRANSCRIPT(8)
    }));
  });

  ws.on('message', (data) => {
    const msg = JSON.parse(data.toString());
    handleSignalingMessage(msg, idValue, streamId);
  });

  ws.on('close', (code, reason) => {
    console.log('Signaling closed:', code, reason.toString());
    signalingConnections.delete(streamId);
    // Implement reconnection logic if needed
  });

  ws.on('error', (error) => {
    console.error('Signaling error:', error);
  });
}

function handleSignalingMessage(msg, idValue, streamId) {
  switch (msg.msg_type) {
    case 2:  // SIGNALING_HAND_SHAKE_RESP
      if (msg.status_code === 0) {
        console.log('Signaling handshake success');

        // Extract media server URL and connect
        const mediaUrl = msg.media_server.server_urls.all;
        connectToMedia(idValue, streamId, mediaUrl);
      } else {
        console.error('Signaling handshake failed:', msg.status_code);
      }
      break;

    case 6:  // EVENT_UPDATE
      handleEventUpdate(msg, streamId);
      break;

    case 8:  // STREAM_STATE_UPDATE
      console.log('Stream state:', msg.state);
      break;

    case 9:  // SESSION_STATE_UPDATE
      console.log('Session state:', msg.state);
      break;

    case 12:  // KEEP_ALIVE_REQ
      const signalingWs = signalingConnections.get(streamId);
      if (signalingWs) {
        signalingWs.send(JSON.stringify({
          msg_type: 13,               // KEEP_ALIVE_RESP
          timestamp: msg.timestamp
        }));
      }
      break;
  }
}

function handleEventUpdate(msg, streamId) {
  const eventType = msg.event?.event_type ?? msg.event_type;
  const participants = msg.event?.participants ?? [];

  switch (eventType) {
    case 2:  // ACTIVE_SPEAKER_CHANGE
      console.log('Active speaker:', msg.user_name);
      break;
    case 3:  // PARTICIPANT_JOIN
      console.log('Participant joined:', msg.user_name);
      break;
    case 4:  // PARTICIPANT_LEAVE
      console.log('Participant left:', msg.user_name);
      break;
    case 5:  // SHARING_START
      console.log('Sharing started by:', msg.user_name);
      break;
    case 6:  // SHARING_STOP
      console.log('Sharing stopped');
      break;
    case 8:  // PARTICIPANT_VIDEO_ON
      for (const participant of participants) {
        const set = activeVideoUsers.get(streamId) || new Set();
        set.add(participant.user_id);
        activeVideoUsers.set(streamId, set);
      }
      break;
    case 9:  // PARTICIPANT_VIDEO_OFF
      for (const participant of participants) {
        activeVideoUsers.get(streamId)?.delete(participant.user_id);
      }
      break;
  }
}

// ============================================
// MEDIA WEBSOCKET
// ============================================

function connectToMedia(idValue, streamId, mediaUrl) {
  console.log('Connecting to media:', mediaUrl);

  const signature = generateSignature(CLIENT_ID, idValue, streamId, CLIENT_SECRET);
  const ws = new WebSocket(mediaUrl);

  mediaConnections.set(streamId, ws);

  ws.on('open', () => {
    console.log('Media connected, sending handshake');

    ws.send(JSON.stringify({
      msg_type: 3,                    // DATA_HAND_SHAKE_REQ
      protocol_version: 1,
      meeting_uuid: idValue,          // Works for both meeting_uuid and session_id
      rtms_stream_id: streamId,
      signature: signature,
      media_type: 9,                  // AUDIO(1) | TRANSCRIPT(8)
      payload_encryption: false,
      media_params: {
        audio: {
          content_type: 2,            // RAW_AUDIO
          sample_rate: 1,             // 16kHz
          channel: 1,                 // Mono
          codec: 1,                   // L16 (PCM)
          data_opt: 1,                // Mixed stream
          send_rate: 20               // 20ms chunks
        },
        transcript: {
          content_type: 5,            // TEXT
          src_language: 9,            // English
          enable_lid: false           // Fixed language, no auto-switch
        }
      }
    }));
  });

  ws.on('message', (data) => {
    const msg = JSON.parse(data.toString());
    handleMediaMessage(msg, streamId);
  });

  ws.on('close', (code, reason) => {
    console.log('Media closed:', code, reason.toString());
    mediaConnections.delete(streamId);
  });

  ws.on('error', (error) => {
    console.error('Media error:', error);
  });
}

function handleMediaMessage(msg, streamId) {
  switch (msg.msg_type) {
    case 4:  // DATA_HAND_SHAKE_RESP
      if (msg.status_code === 0) {
        console.log('Media handshake success, sending client ready');

        // Tell signaling we're ready to receive
        const signalingWs = signalingConnections.get(streamId);
        if (signalingWs) {
          signalingWs.send(JSON.stringify({
            msg_type: 7,              // CLIENT_READY_ACK
            rtms_stream_id: streamId
          }));
        }
      } else {
        console.error('Media handshake failed:', msg.status_code);
      }
      break;

    case 12:  // KEEP_ALIVE_REQ
      const mediaWs = mediaConnections.get(streamId);
      if (mediaWs) {
        mediaWs.send(JSON.stringify({
          msg_type: 13,               // KEEP_ALIVE_RESP
          timestamp: msg.timestamp
        }));
      }
      break;

    case 14:  // MEDIA_DATA_AUDIO
      handleAudioData(msg);
      break;

    case 15:  // MEDIA_DATA_VIDEO
      handleVideoData(msg);
      break;

    case 16:  // MEDIA_DATA_SHARE
      handleShareData(msg);
      break;

    case 17:  // MEDIA_DATA_TRANSCRIPT
      handleTranscriptData(msg);
      break;

    case 18:  // MEDIA_DATA_CHAT
      handleChatData(msg);
      break;
  }
}

// ============================================
// MEDIA DATA HANDLERS
// ============================================

function handleAudioData(msg) {
  const audioBuffer = Buffer.from(msg.content, 'base64');
  console.log(`Audio: ${audioBuffer.length} bytes from ${msg.user_name || 'mixed'}`);

  // Process audio:
  // - Send to transcription service
  // - Save to file
  // - Stream to output
}

function handleVideoData(msg) {
  const videoBuffer = Buffer.from(msg.content, 'base64');
  console.log(`Video: ${videoBuffer.length} bytes from ${msg.user_name}`);

  // Process video:
  // - Decode H.264/JPG
  // - Save frames
  // - AI analysis
}

function handleShareData(msg) {
  const shareBuffer = Buffer.from(msg.content, 'base64');
  console.log(`Share: ${shareBuffer.length} bytes from ${msg.user_name}`);
}

function handleTranscriptData(msg) {
  console.log(`[${msg.user_name}]: ${msg.content}`);

  // Save transcript, process with AI, etc.
}

function handleChatData(msg) {
  console.log(`[Chat] ${msg.user_name}: ${msg.content}`);
}

// ============================================
// RTMS STOP HANDLER
// ============================================

function handleRTMSStopped(payload) {
  const streamId = payload.rtms_stream_id;

  console.log('RTMS stopped:', streamId);

  // Close connections
  const signalingWs = signalingConnections.get(streamId);
  const mediaWs = mediaConnections.get(streamId);

  if (signalingWs) signalingWs.close();
  if (mediaWs) mediaWs.close();

  // Cleanup
  signalingConnections.delete(streamId);
  mediaConnections.delete(streamId);
  activeSessions.delete(streamId);
}

// ============================================
// START SERVER
// ============================================

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`RTMS server running on port ${PORT}`);
});
```

## Message Type Reference

### Signaling Messages

| msg_type | Name | Direction | Description |
|----------|------|-----------|-------------|
| 1 | SIGNALING_HAND_SHAKE_REQ | Client -> Server | Initial handshake |
| 2 | SIGNALING_HAND_SHAKE_RESP | Server -> Client | Handshake response with media URL |
| 5 | EVENT_SUBSCRIPTION | Client -> Server | Subscribe to events |
| 6 | EVENT_UPDATE | Server -> Client | Event notification |
| 7 | CLIENT_READY_ACK | Client -> Server | Ready to receive media |
| 8 | STREAM_STATE_UPDATE | Server -> Client | Stream state changed |
| 9 | SESSION_STATE_UPDATE | Server -> Client | Session state changed |
| 12 | KEEP_ALIVE_REQ | Server -> Client | Heartbeat ping |
| 13 | KEEP_ALIVE_RESP | Client -> Server | Heartbeat pong |

### Media Messages

| msg_type | Name | Direction | Description |
|----------|------|-----------|-------------|
| 3 | DATA_HAND_SHAKE_REQ | Client -> Server | Media handshake with params |
| 4 | DATA_HAND_SHAKE_RESP | Server -> Client | Media handshake response |
| 12 | KEEP_ALIVE_REQ | Server -> Client | Heartbeat ping |
| 13 | KEEP_ALIVE_RESP | Client -> Server | Heartbeat pong |
| 14 | MEDIA_DATA_AUDIO | Server -> Client | Audio data |
| 15 | MEDIA_DATA_VIDEO | Server -> Client | Video data |
| 16 | MEDIA_DATA_SHARE | Server -> Client | Screen share data |
| 17 | MEDIA_DATA_TRANSCRIPT | Server -> Client | Transcript data |
| 18 | MEDIA_DATA_CHAT | Server -> Client | Chat message |

## Media Parameters

### Audio Parameters

```javascript
{
  content_type: 2,     // 1=RTP, 2=RAW_AUDIO
  sample_rate: 1,      // 0=8kHz, 1=16kHz, 2=32kHz, 3=48kHz
  channel: 1,          // 1=Mono, 2=Stereo (OPUS only)
  codec: 1,            // 1=L16, 2=G.711, 3=G.722, 4=OPUS
  data_opt: 1,         // 1=Mixed, 2=Multi-streams
  send_rate: 20        // Chunk size in ms (multiple of 20)
}

function subscribeToParticipantVideo(streamId, userId) {
  const signalingWs = signalingConnections.get(streamId);
  if (!signalingWs) return;

  signalingWs.send(JSON.stringify({
    msg_type: 28, // VIDEO_SUBSCRIPTION_REQ
    user_id: userId,
    subscribe: true,
    timestamp: Date.now()
  }));
}

function closeStream(streamId) {
  const signalingWs = signalingConnections.get(streamId);
  if (!signalingWs) return;

  signalingWs.send(JSON.stringify({
    msg_type: 21, // STREAM_CLOSE_REQ
    rtms_stream_id: streamId
  }));
}
```

## March 2026 Notes

- The new `PARTICIPANT_VIDEO_ON` / `PARTICIPANT_VIDEO_OFF` events tell you which participants currently have subscribable camera streams.
- To receive one participant camera feed, use `VIDEO_SINGLE_INDIVIDUAL_STREAM` in the video media handshake and then send `VIDEO_SUBSCRIPTION_REQ`.
- RTMS currently supports only **one** individual participant video stream at a time. A new subscription replaces the previous one.
- `STREAM_CLOSE_REQ` / `STREAM_CLOSE_RESP` let the backend terminate a stream cleanly.
- Exact numeric values:
  - `PARTICIPANT_VIDEO_ON = 8`
  - `PARTICIPANT_VIDEO_OFF = 9`
  - `STREAM_CLOSE_REQ = 21`
  - `STREAM_CLOSE_RESP = 22`
  - `VIDEO_SUBSCRIPTION_REQ = 28`
  - `VIDEO_SUBSCRIPTION_RESP = 29`

### Video Parameters

```javascript
{
  content_type: 3,     // 3=RAW_VIDEO
  codec: 7,            // 5=JPG, 6=PNG, 7=H.264
  resolution: 2,       // 1=SD, 2=HD, 3=FHD, 4=QHD
  fps: 25,             // 1-30 (JPG/PNG max 5)
  data_opt: 3          // 3=Single active speaker
}
```

### Screen Share Parameters

```javascript
{
  content_type: 3,     // 3=RAW_VIDEO
  codec: 5,            // 5=JPG, 6=PNG, 7=H.264
  resolution: 3,       // 1=SD, 2=HD, 3=FHD, 4=QHD
  fps: 1               // 1-30 (JPG/PNG max 1)
}
```

### Transcript Parameters

```javascript
{
  content_type: 5,     // 5=TEXT
  src_language: 9,     // 9=English
  enable_lid: false    // Fixed language, no auto-switch
}
```

## Status Codes

| Code | Name | Description |
|------|------|-------------|
| 0 | STATUS_OK | Success |
| 3 | STATUS_INVALID_SIGNATURE | Invalid signature |
| 8 | STATUS_DUPLICATE_SIGNAL_REQUEST | Duplicate signaling connection |
| 16 | STATUS_DUPLICATE_MEDIA_DATA_CONNECTION | Duplicate media connection |
| 40 | STATUS_INVALID_RTMS_SESSION_ID | Invalid RTMS session ID |
| 43 | STATUS_INVALID_MEDIA_TRANSCRIPT_SROUCE_LANGUAGE | Invalid transcript source language |

See [Data Types](../references/data-types.md) for complete list.

## Error Handling

```javascript
// Implement exponential backoff for reconnection
let retryDelay = 1000;

ws.on('close', (code, reason) => {
  console.log('Connection closed:', code, reason);

  // Don't reconnect if intentionally closed
  if (code === 1000) return;

  setTimeout(() => {
    reconnect();
  }, retryDelay);

  retryDelay = Math.min(retryDelay * 2, 30000);
});

ws.on('error', (error) => {
  console.error('WebSocket error:', error);
  // Connection will close, triggering reconnection
});
```

## Gap-Filled Audio Recording

Fill gaps with silence for continuous playback:

```javascript
function handleAudioData(msg, streamId) {
  const now = msg.timestamp;
  const last = lastTimestamps.get(streamId) || now;
  const gap = now - last;

  // Fill gaps >= 500ms with silence
  if (gap >= 500) {
    const silentFrames = Math.floor(gap / 20);
    console.log(`Filling ${silentFrames} silent frames`);

    for (let i = 0; i < silentFrames; i++) {
      const silentFrame = Buffer.alloc(640); // 20ms @ 16kHz mono
      writeToFile(silentFrame);
    }
  }

  lastTimestamps.set(streamId, now);

  const audioBuffer = Buffer.from(msg.content, 'base64');
  writeToFile(audioBuffer);
}
```

## Next Steps

- **[SDK Quickstart](sdk-quickstart.md)** - SDK handles all this complexity
- **[AI Integration](ai-integration.md)** - Transcription and analysis
- **[Data Types](../references/data-types.md)** - All enums and constants
