# WebSockets - Connection Management

Detailed guide for managing WebSocket connections to Zoom.

## Connection Lifecycle

```
1. Generate access token (S2S OAuth)
         ↓
2. Open WebSocket connection with token
         ↓
3. Receive events in real-time
         ↓
4. Handle disconnects and reconnect
         ↓
5. Close connection when done
```

## Authentication

WebSocket connections require a valid Server-to-Server OAuth access token.

### Generate Access Token

```javascript
const axios = require('axios');

async function getAccessToken(accountId, clientId, clientSecret) {
  const credentials = Buffer.from(`${clientId}:${clientSecret}`).toString('base64');

  const response = await axios.post(
    'https://zoom.us/oauth/token',
    new URLSearchParams({
      grant_type: 'account_credentials',
      account_id: accountId
    }),
    {
      headers: {
        'Authorization': `Basic ${credentials}`,
        'Content-Type': 'application/x-www-form-urlencoded'
      }
    }
  );

  return {
    accessToken: response.data.access_token,
    expiresIn: response.data.expires_in // Usually 3600 seconds (1 hour)
  };
}
```

### Token Refresh

Access tokens expire after 1 hour. Implement token refresh before expiration:

```javascript
class ZoomWebSocketClient {
  constructor(accountId, clientId, clientSecret, subscriptionId) {
    this.accountId = accountId;
    this.clientId = clientId;
    this.clientSecret = clientSecret;
    this.subscriptionId = subscriptionId;
    this.ws = null;
    this.tokenExpiry = null;
  }

  async refreshTokenIfNeeded() {
    const now = Date.now();
    const bufferTime = 5 * 60 * 1000; // 5 minutes before expiry

    if (!this.tokenExpiry || now >= this.tokenExpiry - bufferTime) {
      const { accessToken, expiresIn } = await getAccessToken(
        this.accountId, this.clientId, this.clientSecret
      );
      this.accessToken = accessToken;
      this.tokenExpiry = now + (expiresIn * 1000);

      // Reconnect with new token
      if (this.ws) {
        this.ws.close();
        await this.connect();
      }
    }
  }

  async connect() {
    await this.refreshTokenIfNeeded();

    const wsUrl = `wss://ws.zoom.us/ws?subscriptionId=${this.subscriptionId}&access_token=${this.accessToken}`;
    this.ws = new WebSocket(wsUrl);

    // Set up event handlers...
  }
}
```

## Connection URL

```
wss://ws.zoom.us/ws?subscriptionId={SUBSCRIPTION_ID}&access_token={ACCESS_TOKEN}
```

| Parameter | Description |
|-----------|-------------|
| `subscriptionId` | Your WebSocket subscription ID from Marketplace |
| `access_token` | Valid S2S OAuth access token |

## Connection Limits

| Limit | Value |
|-------|-------|
| **Connections per subscription** | 1 (opening new connection closes existing) |
| **Connection timeout** | Varies (implement keep-alive) |
| **Message size** | Check Zoom docs for current limits |

## Keep-Alive / Heartbeat

Maintain connection with periodic pings:

```javascript
class WebSocketManager {
  constructor() {
    this.ws = null;
    this.pingInterval = null;
  }

  startHeartbeat() {
    // Ping every 30 seconds
    this.pingInterval = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.ping();
        console.log('Ping sent');
      }
    }, 30000);
  }

  stopHeartbeat() {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }

  connect(url) {
    this.ws = new WebSocket(url);

    this.ws.on('open', () => {
      console.log('Connected');
      this.startHeartbeat();
    });

    this.ws.on('pong', () => {
      console.log('Pong received - connection alive');
    });

    this.ws.on('close', () => {
      this.stopHeartbeat();
    });
  }
}
```

## Reconnection Strategy

Implement exponential backoff for reconnection:

```javascript
class ReconnectingWebSocket {
  constructor(config) {
    this.config = config;
    this.ws = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 10;
    this.baseDelay = 1000; // 1 second
    this.maxDelay = 30000; // 30 seconds
  }

  async connect() {
    try {
      const token = await getAccessToken(
        this.config.accountId,
        this.config.clientId,
        this.config.clientSecret
      );

      const url = `wss://ws.zoom.us/ws?subscriptionId=${this.config.subscriptionId}&access_token=${token.accessToken}`;

      this.ws = new WebSocket(url);

      this.ws.on('open', () => {
        console.log('Connected successfully');
        this.reconnectAttempts = 0; // Reset on successful connection
      });

      this.ws.on('close', (code, reason) => {
        console.log(`Disconnected: ${code} - ${reason}`);
        this.scheduleReconnect();
      });

      this.ws.on('error', (error) => {
        console.error('WebSocket error:', error.message);
      });

      this.ws.on('message', (data) => {
        this.handleMessage(JSON.parse(data));
      });

    } catch (error) {
      console.error('Connection failed:', error.message);
      this.scheduleReconnect();
    }
  }

  scheduleReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max reconnection attempts reached');
      return;
    }

    // Exponential backoff with jitter
    const delay = Math.min(
      this.baseDelay * Math.pow(2, this.reconnectAttempts) + Math.random() * 1000,
      this.maxDelay
    );

    console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts + 1})`);

    setTimeout(() => {
      this.reconnectAttempts++;
      this.connect();
    }, delay);
  }

  handleMessage(event) {
    // Override this method to handle events
    console.log('Event:', event.event, event.payload);
  }

  close() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}
```

## Error Handling

### Common Error Codes

| Code | Meaning | Action |
|------|---------|--------|
| 1000 | Normal closure | Clean shutdown |
| 1001 | Going away | Server shutting down, reconnect |
| 1006 | Abnormal closure | Network issue, reconnect |
| 1008 | Policy violation | Check token validity |
| 1011 | Internal error | Server error, retry later |

### Error Handling Example

```javascript
ws.on('close', (code, reason) => {
  switch (code) {
    case 1000:
      console.log('Connection closed normally');
      break;
    case 1001:
    case 1006:
      console.log('Connection lost, reconnecting...');
      scheduleReconnect();
      break;
    case 1008:
      console.log('Auth error - refreshing token');
      refreshTokenAndReconnect();
      break;
    default:
      console.log(`Unexpected close: ${code} - ${reason}`);
      scheduleReconnect();
  }
});

ws.on('error', (error) => {
  console.error('WebSocket error:', error);
  // The 'close' event will follow, handle reconnection there
});
```

## Complete Example

```javascript
const WebSocket = require('ws');
const axios = require('axios');

class ZoomWebSocketClient {
  constructor(config) {
    this.config = config;
    this.ws = null;
    this.accessToken = null;
    this.tokenExpiry = null;
    this.pingInterval = null;
    this.reconnectAttempts = 0;
    this.handlers = new Map();
  }

  on(event, handler) {
    this.handlers.set(event, handler);
  }

  async getAccessToken() {
    const credentials = Buffer.from(
      `${this.config.clientId}:${this.config.clientSecret}`
    ).toString('base64');

    const response = await axios.post(
      'https://zoom.us/oauth/token',
      new URLSearchParams({
        grant_type: 'account_credentials',
        account_id: this.config.accountId
      }),
      {
        headers: {
          'Authorization': `Basic ${credentials}`,
          'Content-Type': 'application/x-www-form-urlencoded'
        }
      }
    );

    this.accessToken = response.data.access_token;
    this.tokenExpiry = Date.now() + (response.data.expires_in * 1000);

    return this.accessToken;
  }

  async connect() {
    await this.getAccessToken();

    const url = `wss://ws.zoom.us/ws?subscriptionId=${this.config.subscriptionId}&access_token=${this.accessToken}`;

    this.ws = new WebSocket(url);

    this.ws.on('open', () => {
      console.log('WebSocket connected');
      this.reconnectAttempts = 0;
      this.startPing();
      this.scheduleTokenRefresh();
    });

    this.ws.on('message', (data) => {
      const event = JSON.parse(data);
      const handler = this.handlers.get(event.event);
      if (handler) {
        handler(event.payload);
      }
    });

    this.ws.on('close', (code, reason) => {
      console.log(`Disconnected: ${code}`);
      this.stopPing();
      if (code !== 1000) {
        this.reconnect();
      }
    });

    this.ws.on('error', (error) => {
      console.error('Error:', error.message);
    });
  }

  startPing() {
    this.pingInterval = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.ping();
      }
    }, 30000);
  }

  stopPing() {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
    }
  }

  scheduleTokenRefresh() {
    const refreshIn = this.tokenExpiry - Date.now() - 300000; // 5 min before expiry
    setTimeout(() => this.refreshToken(), refreshIn);
  }

  async refreshToken() {
    await this.getAccessToken();
    // Close and reconnect with new token
    this.ws?.close(1000);
    await this.connect();
  }

  reconnect() {
    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
    this.reconnectAttempts++;
    console.log(`Reconnecting in ${delay}ms...`);
    setTimeout(() => this.connect(), delay);
  }

  disconnect() {
    this.stopPing();
    this.ws?.close(1000);
  }
}

// Usage
const client = new ZoomWebSocketClient({
  accountId: process.env.ZOOM_ACCOUNT_ID,
  clientId: process.env.ZOOM_CLIENT_ID,
  clientSecret: process.env.ZOOM_CLIENT_SECRET,
  subscriptionId: process.env.ZOOM_SUBSCRIPTION_ID
});

client.on('meeting.started', (payload) => {
  console.log(`Meeting started: ${payload.object.topic}`);
});

client.on('meeting.ended', (payload) => {
  console.log(`Meeting ended: ${payload.object.uuid}`);
});

client.on('meeting.participant_joined', (payload) => {
  console.log(`Participant joined: ${payload.object.participant.user_name}`);
});

client.connect();
```

## Resources

- **WebSockets docs**: https://developers.zoom.us/docs/api/websockets/
- **S2S OAuth guide**: https://developers.zoom.us/docs/internal-apps/s2s-oauth/
