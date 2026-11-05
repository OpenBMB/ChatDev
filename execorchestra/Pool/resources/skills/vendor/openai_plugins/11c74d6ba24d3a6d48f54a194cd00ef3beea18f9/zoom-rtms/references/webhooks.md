# RTMS - Webhooks

RTMS-related webhook events and configuration.

## CRITICAL: Respond 200 IMMEDIATELY!

**The #1 cause of random disconnects:**

If your webhook handler takes too long to respond, Zoom assumes failure and retries. The retry creates a second connection, which kicks out your first connection (only 1 connection allowed per stream).

```javascript
// CORRECT: Respond first, process async
app.post('/webhook', (req, res) => {
  res.status(200).send();  // IMMEDIATELY!

  // Then process asynchronously
  handleRTMSEvent(req.body);
});

// WRONG: Processing before responding
app.post('/webhook', async (req, res) => {
  await heavyProcessing(req.body);  // Zoom may retry while waiting!
  res.status(200).send();
});
```

## URL Validation Challenge

When configuring your webhook URL, Zoom sends a validation challenge:

```javascript
app.post('/webhook', (req, res) => {
  const { event, payload } = req.body;

  // Handle URL validation
  if (event === 'endpoint.url_validation') {
    const hash = crypto
      .createHmac('sha256', process.env.ZOOM_SECRET_TOKEN)
      .update(payload.plainToken)
      .digest('hex');

    return res.json({
      plainToken: payload.plainToken,
      encryptedToken: hash
    });
  }

  res.status(200).send();
  // ... handle other events
});
```

## Events

### meeting.rtms_started

Sent when RTMS stream is ready for a meeting.

```json
{
  "event": "meeting.rtms_started",
  "payload": {
    "account_id": "account_id",
    "object": {
      "meeting_id": "meeting_id",
      "meeting_uuid": "meeting_uuid",
      "host_id": "host_user_id",
      "rtms_stream_id": "stream_id",
      "server_urls": "wss://rtms-sjc1.zoom.us/...",
      "signature": "auth_signature"
    }
  }
}
```

### meeting.rtms_stopped

Sent when RTMS stream ends.

```json
{
  "event": "meeting.rtms_stopped",
  "payload": {
    "account_id": "account_id",
    "object": {
      "meeting_id": "meeting_id",
      "rtms_stream_id": "stream_id"
    }
  }
}
```

### webinar.rtms_started

Sent when RTMS stream is ready for a webinar.

```json
{
  "event": "webinar.rtms_started",
  "payload": {
    "account_id": "account_id",
    "object": {
      "meeting_id": "meeting_id",
      "meeting_uuid": "meeting_uuid",
      "host_id": "host_user_id",
      "rtms_stream_id": "stream_id",
      "server_urls": "wss://rtms-sjc1.zoom.us/...",
      "signature": "auth_signature"
    }
  }
}
```

> **Important**: Webinar payloads use `meeting_uuid`, NOT `webinar_uuid`. The signature and connection flow are identical to meetings.

**Webinar-specific considerations:**
- **Panelists**: Full audio/video streams are available for panelists.
- **Attendees**: View-only participants; individual streams may not be available.
- **Practice sessions**: Not documented for RTMS.
- **Q&A/Polls**: Not exposed via RTMS.

### webinar.rtms_stopped

Sent when RTMS stream ends for a webinar.

```json
{
  "event": "webinar.rtms_stopped",
  "payload": {
    "account_id": "account_id",
    "object": {
      "meeting_id": "meeting_id",
      "rtms_stream_id": "stream_id"
    }
  }
}
```

### session.rtms_started

Sent when RTMS stream is ready for a Video SDK session.

```json
{
  "event": "session.rtms_started",
  "payload": {
    "account_id": "account_id",
    "object": {
      "session_id": "session_id",
      "rtms_stream_id": "stream_id",
      "server_urls": "wss://rtms-sjc1.zoom.us/...",
      "signature": "auth_signature"
    }
  }
}
```

> **Important**: Video SDK payloads use `session_id` instead of `meeting_uuid`. The HMAC signature must use `session_id` in place of `meeting_uuid`.

**Video SDK-specific considerations:**
- Uses **SDK Key/Secret** (not OAuth Client ID/Secret) for authentication.
- Requires a **Video SDK App** (not a General App) in Zoom Marketplace.
- Once connected, the WebSocket protocol is identical to meetings.

### session.rtms_stopped

Sent when RTMS stream ends for a Video SDK session.

```json
{
  "event": "session.rtms_stopped",
  "payload": {
    "account_id": "account_id",
    "object": {
      "session_id": "session_id",
      "rtms_stream_id": "stream_id"
    }
  }
}
```

### Screen Share Events (via msg_type 5)

Subscribe to receive `SHARING_START` and `SHARING_STOP` events when participants start/stop screen sharing.

## Payload Fields

| Field | Description |
|-------|-------------|
| `rtms_stream_id` | Unique stream identifier |
| `server_urls` | WebSocket signaling server URL |
| `meeting_uuid` | Meeting unique identifier (needed for signature) |
| `signature` | Pre-computed auth signature (alternative to self-generating) |

## Server URL Geo-Routing

Server URLs contain airport/region codes:

| Code | Location |
|------|----------|
| `sjc` | San Jose, California |
| `iad` | Washington DC |
| `sin` | Singapore |
| `fra` | Frankfurt, Germany |
| `syd` | Sydney, Australia |

```javascript
// Extract region from server URL
const hostname = new URL(serverUrl).hostname;  // rtms-sjc1.zoom.us
const region = hostname.split('-')[1].replace(/[0-9]/g, '');  // sjc
```

**Tip**: For production, route webhooks to workers in the same region as the Zoom server.

## Subscribing to RTMS Events

### In Zoom Marketplace (General App - Meetings and Webinars)

1. Go to your app settings
2. Navigate to **Features** → **Access**
3. **Enable Event Subscription**
4. Click **Add Event Subscription**
5. Enter your webhook endpoint URL
6. Search "rtms" and select:
   - `meeting.rtms_started`
   - `meeting.rtms_stopped`
   - `webinar.rtms_started` (if using webinars)
   - `webinar.rtms_stopped` (if using webinars)
7. Click **Done** then **Save**

### In Zoom Marketplace (Video SDK App)

1. Go to your Video SDK app settings
2. Add Event Subscription:
   - `session.rtms_started`
   - `session.rtms_stopped`

### Required Scopes

**For Meetings** (Features → Scopes → Add Scopes → search "rtms"):

| Scope | Purpose |
|-------|---------|
| `meeting:read:meeting_audio` | Access meeting audio |
| `meeting:read:meeting_video` | Access meeting video |
| `meeting:read:meeting_transcript` | Access transcripts |
| `meeting:read:meeting_chat` | Access chat messages |

**For Webinars** (add these in addition to meeting scopes):

| Scope | Purpose |
|-------|---------|
| `webinar:read:webinar_audio` | Access webinar audio |
| `webinar:read:webinar_video` | Access webinar video |
| `webinar:read:webinar_transcript` | Access webinar transcripts |
| `webinar:read:webinar_chat` | Access webinar chat messages |

**For Video SDK**: Uses SDK Key/Secret credentials instead of OAuth scopes.

## Products Supporting RTMS

| Product | Start Event | Stop Event | Payload ID | App Type |
|---------|-------------|------------|------------|----------|
| **Zoom Meetings** | `meeting.rtms_started` | `meeting.rtms_stopped` | `meeting_uuid` | General App |
| **Zoom Webinars** | `webinar.rtms_started` | `webinar.rtms_stopped` | `meeting_uuid` (not webinar_uuid!) | General App |
| **Zoom Video SDK** | `session.rtms_started` | `session.rtms_stopped` | `session_id` | Video SDK App |
| Zoom Contact Center | `contactcenter.rtms_*` | `contactcenter.rtms_*` | See Zoom docs | Contact Center App |
| Zoom Phone | `phone.rtms_*` | `phone.rtms_*` | See Zoom docs | General App |

> **Key differences**: Meetings and webinars use a General App with OAuth credentials. Video SDK uses a Video SDK App with SDK Key/Secret. Once connected, the WebSocket protocol is identical across all products.

## Resources

- **Event reference**: https://developers.zoom.us/docs/rtms/event-reference/
- **RTMS docs**: https://developers.zoom.us/docs/rtms/
