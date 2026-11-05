# Common Issues

Troubleshooting guide for Zoom RTMS.

## Quick Diagnostics

| Symptom | Likely Cause | Solution |
|---------|--------------|----------|
| Connection fails | Invalid signature | Check signature generation |
| Duplicate connections | Slow webhook response | Respond 200 immediately |
| No data received | Wrong media type | Check media_type bitmask |
| Connection closes | Missing heartbeat | Respond to msg_type 12 |
| Segmentation fault | Old Node.js | Upgrade to 20.3.0+ |

## Connection Issues

### Webhook Response Timing

**Problem**: Random disconnections, duplicate connections

**Cause**: If your webhook handler takes too long to respond, Zoom retries. The retry creates a second connection, which kicks out the first (only 1 connection allowed per stream).

**Solution**: Respond 200 IMMEDIATELY before any processing:

```javascript
// CORRECT
app.post('/webhook', (req, res) => {
  res.status(200).send();  // FIRST!

  // Then process asynchronously
  setImmediate(() => {
    handleRTMSEvent(req.body);
  });
});

// WRONG
app.post('/webhook', async (req, res) => {
  await heavyProcessing(req.body);  // Zoom retries while waiting!
  res.status(200).send();
});
```

### Duplicate Connection Prevention

**Problem**: Multiple connections to same stream

**Solution**: Track active sessions:

```javascript
const activeSessions = new Map();

function handleRTMSStarted(payload) {
  const streamId = payload.rtms_stream_id;

  if (activeSessions.has(streamId)) {
    console.log('Already connected, ignoring duplicate');
    return;
  }

  activeSessions.set(streamId, Date.now());
  connectToRTMS(payload);
}

function handleRTMSStopped(payload) {
  activeSessions.delete(payload.rtms_stream_id);
}
```

### Invalid Signature

**Problem**: Handshake fails with status_code 3

**Cause**: Signature generation incorrect

**Solution**: Verify format:

```javascript
// Message format: "clientId,meetingUuid,streamId"
const message = `${clientId},${meetingUuid},${streamId}`;
const signature = crypto.createHmac('sha256', clientSecret)
  .update(message)
  .digest('hex');
```

**Checklist**:
- [ ] Using correct clientId (not app name)
- [ ] Using correct clientSecret
- [ ] No extra spaces in message
- [ ] Using hex output (not base64)

### Connection Timeout

**Problem**: WebSocket connection times out

**Causes**:
- Network issues
- Firewall blocking WebSocket
- Server URL expired

**Solution**:
1. Check network connectivity
2. Ensure firewall allows WSS
3. Use fresh webhook payload (don't cache URLs)

## Heartbeat Issues

### Connection Closes Unexpectedly

**Problem**: Connection closes after ~60 seconds

**Cause**: Not responding to heartbeat

**Solution**: Respond to msg_type 12 with msg_type 13:

```javascript
ws.on('message', (data) => {
  const msg = JSON.parse(data);

  if (msg.msg_type === 12) {
    ws.send(JSON.stringify({
      msg_type: 13,
      timestamp: msg.timestamp
    }));
  }
});
```

**Timeouts**:
- Signaling: ~60 seconds
- Media: ~65 seconds

## Media Data Issues

### No Audio Data

**Causes**:
1. Wrong media_type in handshake
2. No participants speaking
3. Audio not enabled in meeting

**Solution**:
1. Verify media_type includes AUDIO (1):
   ```javascript
   media_type: 1  // Just audio
   media_type: 9  // Audio + Transcript
   media_type: 32 // All media
   ```
2. Wait for participant to speak
3. Check meeting audio settings

### No Video Data

**Causes**:
1. Wrong media_type
2. No video enabled
3. Wrong codec for FPS
4. Individual video mode enabled but no participant subscription sent

**Solution**:
1. Include VIDEO (2) in media_type
2. Use H.264 for fps > 5:
   ```javascript
   video: {
     codec: 7,        // H.264
     resolution: 2,   // HD
     fps: 25          // > 5 requires H.264
   }
   ```
3. If using `VIDEO_SINGLE_INDIVIDUAL_STREAM`, also:
   - subscribe to `PARTICIPANT_VIDEO_ON` / `PARTICIPANT_VIDEO_OFF`
   - send `VIDEO_SUBSCRIPTION_REQ` with a live `user_id`
   - remember a new request replaces the previous participant stream

### No Screen Share Data

**Problem**: Not receiving screen share even when active

**Cause**: Screen share is SEPARATE from video

**Solution**: Include DESKSHARE (4) in media_type:
```javascript
media_type: 4   // Just screen share
media_type: 5   // Audio + screen share
media_type: 32  // All media
```

### Transcript Language Delay

**Problem**: noticeable startup delay before transcription stabilizes

**Cause**: Language Identification (LID) is enabled and RTMS is auto-detecting / auto-switching languages

**Solution**: Set a source language and disable LID when you want a fixed language:
```javascript
transcript: {
  content_type: 5,
  src_language: 9,   // English
  enable_lid: false  // Fixed language, no auto-switch
}
```

**Language IDs**:
| ID | Language |
|----|----------|
| 9 | English |
| 4 | Chinese (Simplified) |
| 20 | Japanese |
| 21 | Korean |
| 28 | Spanish |

See [Data Types](../references/data-types.md#transcript-languages) for full list.

### Participant Video Events Arrive But No Video Stream Follows

**Problem**: You receive `PARTICIPANT_VIDEO_ON`, but no actual participant video frames arrive.

**Cause**: Those events only tell you whose camera is currently available. They do not automatically switch the data socket to that participant.

**Solution**:

1. open the video media socket with `VIDEO_SINGLE_INDIVIDUAL_STREAM`
2. handle `PARTICIPANT_VIDEO_ON` / `PARTICIPANT_VIDEO_OFF`
3. choose one `user_id`
4. send `VIDEO_SUBSCRIPTION_REQ`
5. wait for `VIDEO_SUBSCRIPTION_RESP`

Also remember:

- only one participant stream is supported at a time
- a newer subscription overrides the previous participant stream

### Stream Never Closes Cleanly From Backend

**Problem**: Your app finishes processing, but the RTMS stream remains open until external stop events arrive.

**Solution**: Use the new graceful-close control message on the signaling socket:

```javascript
signalingWs.send(JSON.stringify({
  msg_type: 21, // STREAM_CLOSE_REQ
  rtms_stream_id: streamId
}));
```

Treat `STREAM_CLOSE_RESP` as acknowledgement, then continue with local cleanup.

## SDK-Specific Issues

### Segmentation Fault

**Problem**: App crashes with segmentation fault

**Cause**: Node.js version < 20.3.0

**Solution**:
```bash
# Check version
node --version

# Upgrade with nvm
nvm install 24
nvm use 24

# Clear cache and reinstall
npm cache clean --force
rm -rf node_modules package-lock.json
npm install
```

### Audio Metadata Missing userId

**Problem**: `onAudioData` metadata doesn't include speaker userId

**Cause**: Using AUDIO_MIXED_STREAM (all audio combined)

**Solution**: Use `onActiveSpeakerEvent` for speaker identification:
```javascript
client.onActiveSpeakerEvent((timestamp, userId, userName) => {
  console.log(`Current speaker: ${userName}`);
});
```

Or use AUDIO_MULTI_STREAMS:
```javascript
client.setAudioParams({
  dataOpt: 2  // Per-participant streams
});
```

### Video Parameters Ignored

**Problem**: `setVideoParams` not taking effect

**Cause**: SDK bug - video params ignored after audio params

**Workaround**: Call `setVideoParams` BEFORE `setAudioParams`:
```javascript
// CORRECT ORDER
client.setVideoParams({ codec: 7, fps: 25 });
client.setAudioParams({ codec: 4, sampleRate: 3 });
client.join(payload);
```

### SDK Invalid State

**Problem**: "Invalid status" error on join

**Cause**: SDK still cleaning up from previous session

**Solution**: Retry with delay:
```javascript
try {
  client.join(payload);
} catch (error) {
  if (error.message?.includes('Invalid status')) {
    console.warn('SDK cleaning up, retrying in 2s');

    setTimeout(() => {
      client.join(payload);
    }, 2000);
  }
}
```

## Platform Issues

### Platform Not Supported

**Problem**: SDK installation fails

**Currently Supported**:
- darwin-arm64 (Apple Silicon)
- linux-x64

**Not Yet Supported**:
- Windows
- darwin-x64 (Intel Mac)
- linux-arm64

**Workaround**: Use [Manual WebSocket](../examples/manual-websocket.md) implementation.

## Status Code Reference

| Code | Name | Description |
|------|------|-------------|
| 0 | STATUS_OK | Success |
| 3 | STATUS_INVALID_SIGNATURE | Invalid signature |
| 8 | STATUS_DUPLICATE_SIGNAL_REQUEST | Already connected (signaling) |
| 16 | STATUS_DUPLICATE_MEDIA_DATA_CONNECTION | Already connected (media) |
| 40 | STATUS_INVALID_RTMS_SESSION_ID | Invalid RTMS session ID |
| 43 | STATUS_INVALID_MEDIA_TRANSCRIPT_SROUCE_LANGUAGE | Invalid transcript source language |

See [Data Types](../references/data-types.md) for complete list.

## Product-Specific Issues

### Video SDK Issues

**Problem**: Signature validation fails for Video SDK sessions

**Cause**: Using OAuth Client ID/Secret instead of SDK Key/Secret, or using `meeting_uuid` instead of `session_id`.

**Solution**:
- Video SDK apps use **SDK Key** (as `clientId`) and **SDK Secret** (as `clientSecret`).
- Video SDK webhook payloads contain `session_id`, NOT `meeting_uuid`.
- The HMAC signature must use `session_id`: `HMAC-SHA256(sdkSecret, "sdkKey,sessionId,streamId")`

```javascript
// Extract the correct ID based on product
const idValue = payload.meeting_uuid || payload.session_id;
const signature = generateSignature(clientId, idValue, streamId, clientSecret);
```

### Webinar Issues

**Problem**: Looking for `webinar_uuid` in the payload

**Cause**: Expecting a webinar-specific UUID field.

**Solution**: Webinar RTMS payloads still use `meeting_uuid` (NOT `webinar_uuid`). This is a common gotcha. The signature, connection flow, and protocol are identical to meetings.

**Problem**: Missing attendee streams in webinars

**Cause**: Webinar attendees are view-only participants.

**Solution**: Only **panelist** audio/video streams are confirmed to be available via RTMS. Attendee streams may not be available individually. Design your application to work with panelist streams only.

**Problem**: Practice session not triggering RTMS

**Cause**: Practice sessions are not documented for RTMS support.

**Solution**: RTMS events are expected when the webinar goes live to attendees, not during practice sessions. Q&A and Polls data are also not exposed via RTMS.

## Getting Help

1. **Developer Forum**: https://devforum.zoom.us/
2. **GitHub Issues**: https://github.com/zoom/rtms/issues
3. **Official Docs**: https://developers.zoom.us/docs/rtms/

## Next Steps

- **[Connection Architecture](../concepts/connection-architecture.md)** - Understand the protocol
- **[Lifecycle Flow](../concepts/lifecycle-flow.md)** - Correct connection sequence
- **[Data Types](../references/data-types.md)** - All status codes and enums
