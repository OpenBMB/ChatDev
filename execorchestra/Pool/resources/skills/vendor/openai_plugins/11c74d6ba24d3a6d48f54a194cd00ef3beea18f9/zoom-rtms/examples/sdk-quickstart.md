# SDK Quickstart

The fastest way to receive RTMS media using the official `@zoom/rtms` SDK.

## Installation

```bash
# Requires Node.js 20.3.0+ (24 LTS recommended)
npm install @zoom/rtms express
```

## Environment Setup

```bash
# .env
ZM_RTMS_CLIENT=your_client_id
ZM_RTMS_SECRET=your_client_secret
```

## Multi-Product Support

The SDK accepts both `meeting_uuid` (meetings/webinars) and `session_id` (Video SDK) via `client.join(payload)` transparently. You only need to handle the different webhook event names -- the rest of the protocol is identical.

```javascript
// These constants cover all RTMS products
const RTMS_EVENTS = ["meeting.rtms_started", "webinar.rtms_started", "session.rtms_started"];
const RTMS_STOP_EVENTS = ["meeting.rtms_stopped", "webinar.rtms_stopped", "session.rtms_stopped"];
```

## Minimal Example

```javascript
import rtms from "@zoom/rtms";

const RTMS_EVENTS = ["meeting.rtms_started", "webinar.rtms_started", "session.rtms_started"];

// Handle webhook events - SDK starts webhook server automatically
rtms.onWebhookEvent(({ event, payload }) => {
  if (!RTMS_EVENTS.includes(event)) return;

  const client = new rtms.Client();

  client.onTranscriptData((data, timestamp, metadata) => {
    const text = data.toString('utf8');
    console.log(`${metadata.userName}: ${text}`);
  });

  // SDK handles all WebSocket complexity
  // Accepts both meeting_uuid and session_id transparently
  client.join(payload);
});
```

## Complete Example with All Media Types

```javascript
import rtms from "@zoom/rtms";
import fs from 'fs';

const RTMS_EVENTS = ["meeting.rtms_started", "webinar.rtms_started", "session.rtms_started"];
const RTMS_STOP_EVENTS = ["meeting.rtms_stopped", "webinar.rtms_stopped", "session.rtms_stopped"];

const clients = new Map();

rtms.onWebhookEvent(({ event, payload }) => {
  const streamId = payload?.rtms_stream_id;

  // Handle session end (meetings, webinars, and Video SDK)
  if (RTMS_STOP_EVENTS.includes(event)) {
    const client = clients.get(streamId);
    if (client) {
      client.leave();
      clients.delete(streamId);
    }
    return;
  }

  if (!RTMS_EVENTS.includes(event)) return;

  // Prevent duplicate connections
  if (clients.has(streamId)) {
    console.log('Already connected to this stream');
    return;
  }

  const client = new rtms.Client();
  clients.set(streamId, client);

  // Join confirmation
  client.onJoinConfirm((reason) => {
    console.log(`Joined meeting: ${reason}`);
  });

  // Audio data
  client.onAudioData((buffer, timestamp, metadata) => {
    console.log(`Audio from ${metadata.userName}: ${buffer.length} bytes`);
    // Save to file, send to transcription service, etc.
  });

  // Video data
  client.onVideoData((buffer, timestamp, trackId, metadata) => {
    console.log(`Video from ${metadata.userName}: ${buffer.length} bytes`);
    // H.264 NAL units or JPG/PNG frames
  });

  // Transcript (real-time speech-to-text from Zoom)
  client.onTranscriptData((buffer, timestamp, metadata) => {
    const text = buffer.toString('utf8');
    console.log(`[${metadata.userName}]: ${text}`);
  });

  // Chat messages
  client.onChatData((buffer, timestamp, metadata) => {
    const text = buffer.toString('utf8');
    console.log(`[Chat] ${metadata.userName}: ${text}`);
  });

  // Screen share
  client.onShareData((buffer, timestamp, metadata) => {
    console.log(`Screen share from ${metadata.userName}: ${buffer.length} bytes`);
  });

  // Participant events
  client.onParticipantEvent((event, timestamp, participants) => {
    participants.forEach(p => {
      console.log(`Participant ${event}: ${p.userName}`);
    });
  });

  // Active speaker changed
  client.onActiveSpeakerEvent((timestamp, userId, userName) => {
    console.log(`Active speaker: ${userName}`);
  });

  // Screen sharing started/stopped
  client.onSharingEvent((event, timestamp, userId, userName) => {
    console.log(`Sharing ${event}: ${userName}`);
  });

  // Session ended
  client.onLeave((reason) => {
    console.log(`Left meeting: ${reason}`);
    clients.delete(streamId);
  });

  // Join the meeting
  client.join(payload);
});
```

## Configuring Audio Parameters

```javascript
import rtms from "@zoom/rtms";

const client = new rtms.Client();

// Set audio parameters before joining
client.setAudioParams({
  contentType: 2,    // RAW_AUDIO
  codec: 4,          // OPUS (default)
  sampleRate: 3,     // 48kHz
  channel: 2,        // Stereo (only with OPUS)
  dataOpt: 2,        // AUDIO_MULTI_STREAMS (per-participant)
  duration: 20,      // 20ms chunks
  frameSize: 960     // Samples per frame
});

client.join(payload);
```

### Audio Parameter Options

| Parameter | Options |
|-----------|---------|
| `contentType` | 1=RTP, 2=RAW_AUDIO |
| `codec` | 1=L16 (PCM), 2=G.711, 3=G.722, 4=OPUS |
| `sampleRate` | 0=8kHz, 1=16kHz, 2=32kHz, 3=48kHz |
| `channel` | 1=Mono, 2=Stereo (OPUS only!) |
| `dataOpt` | 1=Mixed stream, 2=Multi-streams (per participant) |
| `duration` | Chunk size in ms (multiple of 20, max 1000) |

## Configuring Video Parameters

```javascript
client.setVideoParams({
  contentType: 3,    // RAW_VIDEO
  codec: 7,          // H.264
  resolution: 2,     // HD (720p)
  fps: 25,
  dataOpt: 3         // Single active speaker
});
```

### Video Parameter Options

| Parameter | Options |
|-----------|---------|
| `codec` | 5=JPG, 6=PNG, 7=H.264 |
| `resolution` | 1=SD (480p), 2=HD (720p), 3=FHD (1080p), 4=QHD (1440p) |
| `fps` | 1-30 (JPG/PNG max 5, H.264 max 30) |
| `dataOpt` | 3=Single active speaker |

## With Express Webhook Handler

```javascript
import rtms from "@zoom/rtms";
import express from "express";

const app = express();
app.use(express.json());

const RTMS_EVENTS = ["meeting.rtms_started", "webinar.rtms_started", "session.rtms_started"];

// Use SDK's webhook handler
app.post('/webhook', rtms.createWebhookHandler(({ event, payload }) => {
  if (!RTMS_EVENTS.includes(event)) return;

  const client = new rtms.Client();

  client.onTranscriptData((data, timestamp, metadata) => {
    console.log(`${metadata.userName}: ${data.toString('utf8')}`);
  });

  client.join(payload);
}, '/webhook'));

app.listen(3000, () => {
  console.log('Server running on port 3000');
});
```

## Class-Based Approach (Multiple Connections)

For applications needing multiple concurrent connections:

```javascript
import rtms from "@zoom/rtms";

// Initialize SDK once
rtms.Client.initialize();

// Create multiple clients
const client1 = new rtms.Client();
const client2 = new rtms.Client();

client1.onTranscriptData((data, ts, meta) => {
  console.log(`[Meeting 1] ${meta.userName}: ${data.toString('utf8')}`);
});

client2.onTranscriptData((data, ts, meta) => {
  console.log(`[Meeting 2] ${meta.userName}: ${data.toString('utf8')}`);
});

// Join different meetings
client1.join(meeting1Payload);
client2.join(meeting2Payload);
```

## Error Handling

```javascript
client.onJoinConfirm((reason) => {
  if (reason !== 0) {
    console.error(`Join failed with reason: ${reason}`);
    // Handle error
  }
});

client.onLeave((reason) => {
  console.log(`Left meeting with reason: ${reason}`);

  // Cleanup
  clients.delete(streamId);

  // Optionally reconnect
  if (reason === /* unexpected disconnect */) {
    setTimeout(() => reconnect(), 2000);
  }
});
```

## Python SDK

```python
import rtms
from dotenv import load_dotenv

load_dotenv()

RTMS_EVENTS = ['meeting.rtms_started', 'webinar.rtms_started', 'session.rtms_started']
RTMS_STOP_EVENTS = ['meeting.rtms_stopped', 'webinar.rtms_stopped', 'session.rtms_stopped']

clients = {}

@rtms.onWebhookEvent
def handle_webhook(webhook):
    event = webhook.get('event')
    payload = webhook.get('payload', {})
    stream_id = payload.get('rtms_stream_id')

    if event in RTMS_STOP_EVENTS:
        if stream_id in clients:
            clients[stream_id].leave()
            del clients[stream_id]
        return

    if event not in RTMS_EVENTS:
        return

    client = rtms.Client()
    clients[stream_id] = client

    @client.onTranscriptData
    def on_transcript(data, size, timestamp, metadata):
        text = data.decode('utf-8')
        print(f'[{metadata.userName}]: {text}')

    @client.onJoinConfirm
    def on_join(reason):
        print(f'Joined: {reason}')

    @client.onLeave
    def on_leave(reason):
        print(f'Left: {reason}')

    # SDK accepts both meeting_uuid and session_id transparently
    client.join(payload)

# Main loop
if __name__ == '__main__':
    print('Webhook server running...')
    rtms.run()
```

## Environment Variables Reference

```bash
# Required
ZM_RTMS_CLIENT=your_client_id
ZM_RTMS_SECRET=your_client_secret

# Optional
ZM_RTMS_PORT=8080           # Webhook server port
ZM_RTMS_PATH=/webhook       # Webhook endpoint path

# Logging
ZM_RTMS_LOG_LEVEL=info      # error, warn, info, debug, trace
ZM_RTMS_LOG_FORMAT=progressive  # progressive or json
ZM_RTMS_LOG_ENABLED=true
```

## Common Issues

| Issue | Solution |
|-------|----------|
| Segmentation fault | Upgrade to Node.js 20.3.0+ (24 LTS recommended) |
| Audio metadata missing userId | Use `onActiveSpeakerEvent` for speaker identification with mixed stream |
| Video params ignored | Call `setVideoParams` BEFORE `setAudioParams` |

## Next Steps

- **[Manual WebSocket](manual-websocket.md)** - Full protocol control without SDK
- **[AI Integration](ai-integration.md)** - Transcription and analysis patterns
- **[Media Types](../references/media-types.md)** - All configuration options
