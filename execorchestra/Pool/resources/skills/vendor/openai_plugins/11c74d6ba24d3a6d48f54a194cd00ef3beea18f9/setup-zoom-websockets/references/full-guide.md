# /setup-zoom-websockets

Background reference for persistent Zoom event streams. Prefer workflow routing first, then use this file when WebSockets are plausibly better than webhooks.

## WebSockets vs Webhooks

| Aspect | WebSockets | Webhooks |
|--------|------------|----------|
| **Connection** | Persistent, bidirectional | One-time HTTP POST |
| **Latency** | Lower (no HTTP overhead) | Higher (new connection per event) |
| **Security** | Direct connection, no exposed endpoint | Requires endpoint validation, IP whitelisting |
| **Model** | Pull (you connect to Zoom) | Push (Zoom connects to you) |
| **State** | Stateful (maintains connection) | Stateless (each event independent) |
| **Setup** | More complex (access token, connection) | Simpler (just endpoint URL) |

**Choose WebSockets when:**
- Real-time, low-latency updates are critical
- Security is paramount (banking, healthcare, finance)
- You don't want to expose a public endpoint
- You need bidirectional communication

**Choose Webhooks when:**
- Simpler setup is preferred
- Small number of event notifications
- Existing HTTP infrastructure

## Prerequisites

- Server-to-Server OAuth app in [Zoom Marketplace](https://marketplace.zoom.us/)
- Account ID, Client ID, and Client Secret
- WebSocket subscription with events enabled

> **Need help with S2S OAuth?** See the **[zoom-oauth](../../oauth/SKILL.md)** skill for complete authentication flows.

> **Start troubleshooting fast:** Use the **[5-Minute Runbook](../RUNBOOK.md)** before deep debugging.

## Quick Start

### 1. Create Server-to-Server OAuth App

1. Go to [Zoom Marketplace](https://marketplace.zoom.us/develop/create)
2. Create a **Server-to-Server OAuth** app
3. Copy Account ID, Client ID, Client Secret

### 2. Enable WebSocket Subscription

1. In your app, go to **Feature** → **Event Subscriptions**
2. Add an Event Subscription
3. Select **WebSockets** as the method type
4. Select events to subscribe to (e.g., `meeting.created`, `meeting.started`)
5. Save - an endpoint URL will be generated

### 3. Connect via WebSocket

```javascript
const WebSocket = require('ws');
const axios = require('axios');

// Step 1: Get access token
async function getAccessToken() {
  const credentials = Buffer.from(`${CLIENT_ID}:${CLIENT_SECRET}`).toString('base64');

  const response = await axios.post(
    'https://zoom.us/oauth/token',
    new URLSearchParams({
      grant_type: 'account_credentials',
      account_id: ACCOUNT_ID
    }),
    {
      headers: {
        'Authorization': `Basic ${credentials}`,
        'Content-Type': 'application/x-www-form-urlencoded'
      }
    }
  );

  return response.data.access_token;
}

// Step 2: Connect to WebSocket
async function connectWebSocket() {
  const accessToken = await getAccessToken();

  // WebSocket URL from your subscription settings
  const wsUrl = `wss://ws.zoom.us/ws?subscriptionId=${SUBSCRIPTION_ID}&access_token=${accessToken}`;

  const ws = new WebSocket(wsUrl);

  ws.on('open', () => {
    console.log('WebSocket connection established');
  });

  ws.on('message', (data) => {
    const event = JSON.parse(data);
    console.log('Event received:', event.event);

    // Handle different event types
    switch (event.event) {
      case 'meeting.started':
        console.log(`Meeting started: ${event.payload.object.topic}`);
        break;
      case 'meeting.ended':
        console.log(`Meeting ended: ${event.payload.object.uuid}`);
        break;
      case 'meeting.participant_joined':
        console.log(`Participant joined: ${event.payload.object.participant.user_name}`);
        break;
    }
  });

  ws.on('close', (code, reason) => {
    console.log(`Connection closed: ${code} - ${reason}`);
    // Implement reconnection logic
  });

  ws.on('error', (error) => {
    console.error('WebSocket error:', error);
  });

  return ws;
}

connectWebSocket();
```

## Event Format

Events received via WebSocket have the same format as webhook events:

```json
{
  "event": "meeting.started",
  "event_ts": 1706123456789,
  "payload": {
    "account_id": "abcD3ojkdbjfg",
    "object": {
      "id": 1234567890,
      "uuid": "abcdefgh-1234-5678-abcd-1234567890ab",
      "host_id": "xyz789",
      "topic": "Team Standup",
      "type": 2,
      "start_time": "2024-01-25T10:00:00Z",
      "timezone": "America/Los_Angeles"
    }
  }
}
```

## Common Events

| Event | Description |
|-------|-------------|
| `meeting.created` | Meeting scheduled |
| `meeting.updated` | Meeting settings changed |
| `meeting.deleted` | Meeting deleted |
| `meeting.started` | Meeting begins |
| `meeting.ended` | Meeting ends |
| `meeting.participant_joined` | Participant joins meeting |
| `meeting.participant_left` | Participant leaves meeting |
| `recording.completed` | Cloud recording ready |
| `user.created` | New user added |
| `user.updated` | User details changed |

## Connection Management

### Keep-Alive

WebSocket connections require periodic heartbeats. Zoom will close idle connections.

```javascript
// Send ping every 30 seconds
setInterval(() => {
  if (ws.readyState === WebSocket.OPEN) {
    ws.ping();
  }
}, 30000);
```

### Reconnection

Implement automatic reconnection for reliability:

```javascript
function connectWithReconnect() {
  const ws = connectWebSocket();

  ws.on('close', () => {
    console.log('Connection lost. Reconnecting in 5 seconds...');
    setTimeout(connectWithReconnect, 5000);
  });

  return ws;
}
```

### Single Connection Limit

**Important:** Only ONE WebSocket connection can be open per subscription at a time. Opening a new connection will close the existing one.

## Detailed References

- **[references/connection.md](../references/connection.md)** - Connection lifecycle, authentication, error handling
- **[references/events.md](../references/events.md)** - Complete event types reference

## Troubleshooting

- **[troubleshooting/common-issues.md](../troubleshooting/common-issues.md)** - Subscription URL confusion, disconnects, no-events debugging

## Sample Repositories

### Official / Community

| Type | Repository | Description |
|------|------------|-------------|
| Node.js | [just-zoomit/zoom-websockets](https://github.com/just-zoomit/zoom-websockets) | WebSocket sample with S2S OAuth |

## WebSockets vs RTMS

Don't confuse WebSockets with RTMS (Realtime Media Streams):

| Feature | WebSockets | RTMS |
|---------|------------|------|
| **Purpose** | Event notifications | Media streams |
| **Data** | Meeting events, user events | Audio, video, transcripts |
| **Use case** | React to Zoom events | AI/ML, live transcription |
| **Skill** | This skill | **rtms** |

For real-time audio/video/transcript data, use the **rtms** skill instead.

## Resources

- **WebSockets docs**: https://developers.zoom.us/docs/api/websockets/
- **Webhooks comparison**: https://www.zoom.com/en/blog/a-guide-to-webhooks-and-websockets/
- **Developer forum**: https://devforum.zoom.us/

## Environment Variables

- See [references/environment-variables.md](../references/environment-variables.md) for standardized `.env` keys and where to find each value.
