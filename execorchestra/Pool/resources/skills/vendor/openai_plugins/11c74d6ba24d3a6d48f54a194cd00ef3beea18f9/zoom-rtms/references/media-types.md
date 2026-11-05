# RTMS - Media Types

Audio, video, transcript, chat, and screen share data formats.

## Media Type Bitmask

Use bitwise OR to combine types:

| Type | Value | Event Name | Description |
|------|-------|------------|-------------|
| Audio | 1 | `audio` | PCM audio samples |
| Video | 2 | `video` | H.264 encoded frames |
| Screen Share | 4 | `sharescreen` | **Separate from video!** |
| Transcript | 8 | `transcript` | Real-time speech-to-text |
| Chat | 16 | `chat` | In-meeting chat messages |
| All | 32 | all events | All media types |

**Example**: Audio + Transcript = `1 | 8` = `9`

```javascript
const mediaTypes = RTMSManager.MEDIA.AUDIO | RTMSManager.MEDIA.TRANSCRIPT;  // 9
```

## Audio

| Property | Options |
|----------|---------|
| Sample Rate | 8kHz (0), **16kHz (1)**, 32kHz (2), 48kHz (3) |
| Codec | **L16/PCM (1)**, G.711 (2), G.722 (3), Opus (4) |
| Channels | **Mono (1)**, Stereo (2) |
| Data Option | **Mixed (1)**, Multi-stream (2) |
| Send Rate | **20ms** (recommended) |

**Important**: Stereo is ONLY supported with Opus codec!

### Audio Configuration Example

```javascript
const audioParams = {
  content_type: 1,  // MEDIA_CONTENT_TYPE_RTP
  sample_rate: 1,   // 16kHz
  channel: 1,       // Mono
  codec: 1,         // L16 (PCM)
  data_opt: 1,      // Mixed stream (all participants)
  send_rate: 20     // 20ms intervals
};
```

### Processing Audio

```javascript
RTMSManager.on('audio', ({ buffer, userName, timestamp }) => {
  // buffer = PCM 16-bit samples
  // Send to transcription service, save to file, etc.
  transcriptionService.process(buffer);
});
```

## Video

| Property | Options |
|----------|---------|
| Codec | **H.264 (7)**, JPG (5), PNG (6) |
| Resolution | SD (1), **HD 720p (2)**, FHD 1080p (3), QHD 2K (4) |
| FPS | 1-30 (typically 25) |
| Data Option | **Single active (3)**, Speaker view (4), Gallery view (5), **Single individual stream** (March 2026) |

**Rule**: Use JPG/PNG when fps <= 5, H.264 when fps > 5

### Video Configuration Example

```javascript
const videoParams = {
  codec: 7,         // H.264
  resolution: 2,    // HD 720p
  fps: 25,
  data_opt: 3       // Single active speaker
};
```

### Single Individual Participant Video

March 2026 added a new pattern for selecting **one participant camera stream at a time**.

Use it when you need:

- per-user vision processing
- a moderator-selected camera feed
- deterministic participant focus instead of active speaker switching

Configuration rules:

- set the video `data_opt` to `VIDEO_SINGLE_INDIVIDUAL_STREAM`
- subscribe to `PARTICIPANT_VIDEO_ON` / `PARTICIPANT_VIDEO_OFF`
- send `VIDEO_SUBSCRIPTION_REQ` with the chosen `user_id`
- a new subscription overrides the previous participant stream

This is not a multi-participant subscription feature. RTMS currently supports only **one** individual participant video stream at a time.

### Processing Video

```javascript
RTMSManager.on('video', ({ buffer, userName, timestamp }) => {
  // buffer = H.264 NAL units
  // Decode with FFmpeg, save, or stream
  videoDecoder.decode(buffer);
});
```

## Screen Share (SEPARATE from Video!)

Screen share has a **different event** from regular video (msg_type 16 vs 15).

| Property | Options |
|----------|---------|
| Codec | **JPG (5)**, PNG (6), H.264 (7) |
| Resolution | SD (1), **HD 720p (2)**, FHD 1080p (3), QHD 2K (4) |
| FPS | **1-5** for static content, 15-30 for animations |

### Screen Share Configuration

```javascript
const deskshareParams = {
  codec: 5,         // JPG (good for static slides)
  resolution: 2,    // HD
  fps: 1            // Low FPS for slides
};
```

### Processing Screen Share

```javascript
RTMSManager.on('sharescreen', ({ buffer, userName, timestamp }) => {
  // buffer = JPG/PNG image or H.264 frame
  saveScreenCapture(buffer);
});
```

## Transcript

| Property | Value |
|----------|-------|
| Format | JSON text |
| Content Type | 5 (MEDIA_CONTENT_TYPE_TEXT) |
| Languages | 36 supported (see below) |
| `src_language` | Fixed requested language |
| `enable_lid` | Toggle Language Identification (default enabled) |

### Language IDs (Common)

| Language | ID |
|----------|-----|
| English | 9 |
| Chinese (Simplified) | 4 |
| Chinese (Traditional) | 5 |
| Japanese | 20 |
| Korean | 21 |
| Spanish | 28 |
| French (France) | 13 |
| German | 14 |

**Tip**: Use `src_language` plus `enable_lid: false` to force a fixed language. Leave `enable_lid` enabled when you want automatic language switching.

### Transcript Structure

```json
{
  "user_id": "user_id",
  "user_name": "Speaker Name",
  "text": "Transcribed text content",
  "timestamp": 1234567890,
  "is_final": true
}
```

### Processing Transcript

```javascript
RTMSManager.on('transcript', ({ text, userName, timestamp }) => {
  // text = transcribed speech
  // is_final = true for finalized segments
  saveTranscript(userName, text);
});
```

## Chat

| Property | Value |
|----------|-------|
| Format | JSON text |
| Content Type | 5 (MEDIA_CONTENT_TYPE_TEXT) |

### Processing Chat

```javascript
RTMSManager.on('chat', ({ text, userName, timestamp }) => {
  console.log(`[Chat] ${userName}: ${text}`);
  saveChatMessage(userName, text);
});
```

## Complete Media Configuration

```javascript
const mediaParams = {
  audio: {
    content_type: 1,  // RTP
    sample_rate: 1,   // 16kHz
    channel: 1,       // Mono
    codec: 1,         // L16 (PCM)
    data_opt: 1,      // Mixed stream
    send_rate: 20
  },
  video: {
    codec: 7,         // H.264
    resolution: 2,    // HD 720p
    fps: 25,
    data_opt: 3       // Single active speaker
  },
  deskshare: {
    codec: 5,         // JPG
    resolution: 2,    // HD
    fps: 1
  },
  transcript: {
    content_type: 5,  // TEXT
    src_language: 9,  // English
    enable_lid: false
  },
  chat: {
    content_type: 5   // TEXT
  }
};
```

## Resources

- **Data types**: https://developers.zoom.us/docs/rtms/data-types/
- **Media params**: https://developers.zoom.us/docs/rtms/media-parameter-definition/
- **MEDIA_PARAMETERS.md**: https://github.com/zoom/rtms-samples/blob/main/MEDIA_PARAMETERS.md
