# RTMS Bot (Real-Time Media Streams)

Build resilient RTMS bots that access meeting audio, video, transcription, screen share, and chat without joining as a visible participant.

## Overview

RTMS bots are invisible read-only services that subscribe to meeting media streams via WebSockets. They do NOT appear in the participant list.

**Use this approach when:**
- You only need to observe/transcribe (no interaction needed)
- You want invisible operation
- You're processing external meetings (with permission)
- You want minimal resource usage

**Alternative:** See [Meeting SDK Bot (Linux)](../../meeting-sdk/linux/meeting-sdk-bot.md) for visible participant bots with full meeting control.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        RTMS BOT FLOW                                 │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ 1. Trigger RTMS: REST API or In-Meeting Start                       │
│    └── POST /meetings/{meetingId}/rtms                              │
│    └── Or: Start RTMS manually from Zoom client                     │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 2. Wait for Webhook: meeting.rtms_started                           │
│    └── Zoom sends signaling + media WebSocket URLs                  │
│    └── No webhook = RTMS unavailable (no polling fallback)          │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 3. Connect: Signaling WebSocket (Handshake with HMAC)               │
│    └── Generate HMAC-SHA256 signature                               │
│    └── Send handshake message                                       │
│    └── Receive session confirmation                                 │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 4. Connect: Media WebSocket (Subscribe to Streams)                  │
│    └── Subscribe to: audio, video, transcription, share, chat       │
│    └── Send keep-alive pings                                        │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 5. Process Media Data                                               │
│    └── Audio: Opus/PCM streams per speaker                          │
│    └── Video: H.264 encoded frames                                  │
│    └── Transcription: Real-time text with speaker labels            │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 6. Mid-Stream: Connection Monitoring                                │
│    └── Detect WebSocket close → Exponential backoff retry           │
│    └── Stop after N reconnection attempts                           │
└─────────────────────────────────────────────────────────────────────┘
```

## Skills Required

| Skill | Purpose |
|-------|---------|
| **zoom-rest-api** | Trigger RTMS start (optional - can also start manually) |
| **rtms** | WebSocket connection, media processing |
| **webhooks** | Receive `meeting.rtms_started` event |

## Prerequisites

- Zoom app with RTMS features enabled
- Webhook endpoint (HTTPS, publicly accessible)
- Event subscriptions: `meeting.rtms_started`, `meeting.rtms_stopped`
- Scopes: `meeting:read:admin`, `meeting:write:admin` (if triggering via API)
- RTMS SDK or native WebSocket implementation

## Configuration

### Retry Parameters (Customizable)

```javascript
// config.js or environment variables
const rtmsConfig = {
    // WebSocket connection (initial)
    connection_timeout_ms: 10000,        // Handshake timeout (default: 10s)
    connection_max_attempts: 5,          // Max connection attempts (default: 5)
    connection_retry_delay_ms: 5000,     // Constant retry: 5s (default: 5s)

    // Mid-stream reconnection (network failures)
    reconnect_max_attempts: 3,           // Max reconnection attempts (default: 3)
    reconnect_base_delay_ms: 2000,       // Initial delay: 2s (default: 2s)
    // Exponential backoff: 2s, 4s, 8s...

    // Keep-alive ping
    keepalive_interval_ms: 5000,         // Send ping every 5s (default: 5s, min: 3s)
    keepalive_timeout_ms: 15000,         // Expect pong within 15s (default: 15s)

    // Webhook wait timeout
    webhook_wait_timeout_ms: 300000      // Wait 5min for webhook (default: 5min)
};

// Load from environment variables (recommended for production)
function loadConfig() {
    return {
        connection_timeout_ms:
            parseInt(process.env.RTMS_CONNECTION_TIMEOUT_MS) || 10000,
        connection_max_attempts:
            parseInt(process.env.RTMS_CONNECTION_MAX_ATTEMPTS) || 5,
        connection_retry_delay_ms:
            parseInt(process.env.RTMS_CONNECTION_RETRY_DELAY_MS) || 5000,
        reconnect_max_attempts:
            parseInt(process.env.RTMS_RECONNECT_MAX_ATTEMPTS) || 3,
        reconnect_base_delay_ms:
            parseInt(process.env.RTMS_RECONNECT_BASE_DELAY_MS) || 2000,
        keepalive_interval_ms:
            Math.max(parseInt(process.env.RTMS_KEEPALIVE_INTERVAL_MS) || 5000, 3000),
        keepalive_timeout_ms:
            parseInt(process.env.RTMS_KEEPALIVE_TIMEOUT_MS) || 15000,
        webhook_wait_timeout_ms:
            parseInt(process.env.RTMS_WEBHOOK_WAIT_TIMEOUT_MS) || 300000
    };
}
```

### Customization Guide

| Parameter | Default | When to Increase | When to Decrease |
|-----------|---------|------------------|------------------|
| `connection_max_attempts` | 5 | Slow/congested networks | Fast failure detection needed |
| `connection_retry_delay_ms` | 5000 (5s) | High network latency | Local network, low latency |
| `reconnect_max_attempts` | 3 | Critical meetings, unstable network | Cost-sensitive, batch processing |
| `reconnect_base_delay_ms` | 2000 (2s) | International connections | Local network |
| `keepalive_interval_ms` | 5000 (5s) | Aggressive connection monitoring | Reduce bandwidth overhead |
| `webhook_wait_timeout_ms` | 300000 (5min) | Meetings may start late | Fast failure detection |

**Recommended Ranges:**
- Connection attempts: 3-10
- Connection retry delay: 2s-15s
- Reconnect attempts: 2-5
- Reconnect base delay: 1s-5s
- Keep-alive interval: 3s-30s (min: 3s per Zoom docs)

**Examples:**

```bash
# High-priority production bot (aggressive)
export RTMS_CONNECTION_MAX_ATTEMPTS=10
export RTMS_CONNECTION_RETRY_DELAY_MS=3000      # 3s
export RTMS_RECONNECT_MAX_ATTEMPTS=5
export RTMS_RECONNECT_BASE_DELAY_MS=1000        # 1s
export RTMS_KEEPALIVE_INTERVAL_MS=3000          # 3s (minimum)

# Cost-sensitive batch processing (conservative)
export RTMS_CONNECTION_MAX_ATTEMPTS=3
export RTMS_CONNECTION_RETRY_DELAY_MS=10000     # 10s
export RTMS_RECONNECT_MAX_ATTEMPTS=2
export RTMS_RECONNECT_BASE_DELAY_MS=5000        # 5s
export RTMS_KEEPALIVE_INTERVAL_MS=15000         # 15s

# Development/testing (fail fast)
export RTMS_CONNECTION_MAX_ATTEMPTS=2
export RTMS_CONNECTION_RETRY_DELAY_MS=2000      # 2s
export RTMS_RECONNECT_MAX_ATTEMPTS=1
export RTMS_RECONNECT_BASE_DELAY_MS=1000        # 1s
export RTMS_WEBHOOK_WAIT_TIMEOUT_MS=60000       # 1min
```

## Step 1: Trigger RTMS (Optional - REST API)

You can start RTMS programmatically or manually from the Zoom client.

### Option A: REST API Trigger

```bash
# Start RTMS for a meeting
curl -X POST "https://api.zoom.us/v2/meetings/{meetingId}/rtms" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "meeting"
  }'
```

**Response:**
```json
{
  "rtms_id": "abc123def456",
  "status": "starting"
}
```

### Option B: Manual Start (In-Meeting)

Host clicks **Apps** → Your RTMS App → **Start RTMS**

**Both trigger the same webhook** → `meeting.rtms_started`

## Step 2: Wait for Webhook (Required)

**CRITICAL:** RTMS requires a webhook. There is NO polling alternative. If webhook doesn't arrive, RTMS is unavailable.

### Webhook Handler

```javascript
const express = require('express');
const crypto = require('crypto');
const app = express();

const config = loadConfig();
const pendingConnections = new Map();  // Track webhook waiters

app.post('/webhook', express.json(), async (req, res) => {
    // 1. Verify webhook signature
    const signature = req.headers['x-zm-signature'];
    const timestamp = req.headers['x-zm-request-timestamp'];

    if (!verifyWebhookSignature(req.body, signature, timestamp)) {
        return res.status(403).send('Invalid signature');
    }

    // 2. Respond immediately (Zoom expects 200 within 3s)
    res.status(200).send();

    // 3. Process webhook asynchronously
    const event = req.body;

    if (event.event === 'meeting.rtms_started') {
        console.log('[WEBHOOK] RTMS started for meeting:', event.payload.object.uuid);

        const rtmsInfo = {
            meetingUuid: event.payload.object.uuid,
            signalingUrl: event.payload.object.signaling_url,
            mediaUrl: event.payload.object.media_url,
            sessionKey: event.payload.object.session_key
        };

        // Notify waiting connection
        const waiter = pendingConnections.get(rtmsInfo.meetingUuid);
        if (waiter) {
            waiter.resolve(rtmsInfo);
            pendingConnections.delete(rtmsInfo.meetingUuid);
        } else {
            // No waiter - proactive start
            connectToRTMS(rtmsInfo);
        }
    }
});

function verifyWebhookSignature(body, signature, timestamp) {
    const message = `v0:${timestamp}:${JSON.stringify(body)}`;
    const hmac = crypto.createHmac('sha256', WEBHOOK_SECRET_TOKEN);
    const computed = 'v0=' + hmac.update(message).digest('hex');
    return crypto.timingSafeEqual(
        Buffer.from(signature),
        Buffer.from(computed)
    );
}
```

### Wait for Webhook (with Timeout)

```javascript
async function waitForRTMSWebhook(meetingUuid) {
    return new Promise((resolve, reject) => {
        const timeoutId = setTimeout(() => {
            pendingConnections.delete(meetingUuid);
            reject(new Error(
                `RTMS webhook not received within ${config.webhook_wait_timeout_ms}ms. ` +
                `Possible causes: ` +
                `(1) Meeting hasn't started, ` +
                `(2) RTMS not enabled for this meeting, ` +
                `(3) Webhook endpoint unreachable.`
            ));
        }, config.webhook_wait_timeout_ms);

        pendingConnections.set(meetingUuid, {
            resolve: (rtmsInfo) => {
                clearTimeout(timeoutId);
                resolve(rtmsInfo);
            },
            reject
        });
    });
}

// Usage
try {
    console.log('[RTMS] Waiting for webhook...');
    const rtmsInfo = await waitForRTMSWebhook(MEETING_UUID);
    console.log('[RTMS] Webhook received, connecting...');
    await connectToRTMS(rtmsInfo);
} catch (error) {
    console.error('[RTMS] ABORT:', error.message);
}
```

**Error if no webhook:** ABORT. No webhook = RTMS unavailable. No polling alternative.

## Step 3: Connect to Signaling WebSocket

### Connection with Retry

```javascript
const WebSocket = require('ws');

async function connectSignalingWithRetry(signalingUrl, sessionKey) {
    for (let attempt = 1; attempt <= config.connection_max_attempts; attempt++) {
        console.log(`[SIGNALING] Attempt ${attempt}/${config.connection_max_attempts}`);

        try {
            const ws = await connectSignalingSocket(signalingUrl, sessionKey);
            console.log('[SIGNALING] Connected successfully');
            return ws;
        } catch (error) {
            console.error(`[SIGNALING] Attempt ${attempt} failed:`, error.message);

            if (attempt < config.connection_max_attempts) {
                const delay = config.connection_retry_delay_ms;
                console.log(`[SIGNALING] Retrying in ${delay}ms...`);
                await sleep(delay);
            }
        }
    }

    throw new Error(
        `Failed to connect signaling WebSocket after ${config.connection_max_attempts} attempts`
    );
}

function connectSignalingSocket(signalingUrl, sessionKey) {
    return new Promise((resolve, reject) => {
        const ws = new WebSocket(signalingUrl);
        const timeoutId = setTimeout(() => {
            ws.close();
            reject(new Error('Signaling connection timeout'));
        }, config.connection_timeout_ms);

        ws.on('open', () => {
            console.log('[SIGNALING] WebSocket opened, sending handshake...');

            // Generate HMAC signature
            const timestamp = Date.now();
            const message = `${timestamp}:${sessionKey}`;
            const signature = crypto
                .createHmac('sha256', WEBHOOK_SECRET_TOKEN)
                .update(message)
                .digest('hex');

            // Send handshake
            ws.send(JSON.stringify({
                type: 'handshake',
                timestamp,
                signature
            }));
        });

        ws.on('message', (data) => {
            const msg = JSON.parse(data);

            if (msg.type === 'handshake_response') {
                clearTimeout(timeoutId);

                if (msg.status === 'success') {
                    console.log('[SIGNALING] Handshake successful');
                    resolve(ws);
                } else {
                    ws.close();
                    reject(new Error(`Handshake failed: ${msg.error}`));
                }
            }
        });

        ws.on('error', (error) => {
            clearTimeout(timeoutId);
            reject(error);
        });

        ws.on('close', (code, reason) => {
            clearTimeout(timeoutId);
            reject(new Error(`Connection closed: ${code} ${reason}`));
        });
    });
}
```

## Step 4: Connect to Media WebSocket

```javascript
async function connectMediaWithRetry(mediaUrl, signalingWs) {
    for (let attempt = 1; attempt <= config.connection_max_attempts; attempt++) {
        console.log(`[MEDIA] Attempt ${attempt}/${config.connection_max_attempts}`);

        try {
            const ws = await connectMediaSocket(mediaUrl);
            console.log('[MEDIA] Connected successfully');
            subscribeToStreams(ws);
            setupKeepAlive(ws);
            return ws;
        } catch (error) {
            console.error(`[MEDIA] Attempt ${attempt} failed:`, error.message);

            if (attempt < config.connection_max_attempts) {
                const delay = config.connection_retry_delay_ms;
                console.log(`[MEDIA] Retrying in ${delay}ms...`);
                await sleep(delay);
            }
        }
    }

    throw new Error(
        `Failed to connect media WebSocket after ${config.connection_max_attempts} attempts`
    );
}

function subscribeToStreams(mediaWs) {
    // Subscribe to all available streams
    mediaWs.send(JSON.stringify({
        type: 'subscribe',
        streams: ['audio', 'video', 'transcription', 'share', 'chat']
    }));

    console.log('[MEDIA] Subscribed to: audio, video, transcription, share, chat');
}
```

## Step 5: Keep-Alive Management

```javascript
function setupKeepAlive(ws) {
    let lastPongReceived = Date.now();
    let keepAliveInterval;
    let timeoutCheck;

    // Send ping periodically
    keepAliveInterval = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
            ws.ping();
            console.log('[KEEPALIVE] Ping sent');
        }
    }, config.keepalive_interval_ms);

    // Check for pong timeout
    timeoutCheck = setInterval(() => {
        const timeSinceLastPong = Date.now() - lastPongReceived;

        if (timeSinceLastPong > config.keepalive_timeout_ms) {
            console.error('[KEEPALIVE] Pong timeout, closing connection');
            clearInterval(keepAliveInterval);
            clearInterval(timeoutCheck);
            ws.close(1000, 'Keep-alive timeout');
        }
    }, 1000);

    ws.on('pong', () => {
        lastPongReceived = Date.now();
        console.log('[KEEPALIVE] Pong received');
    });

    ws.on('close', () => {
        clearInterval(keepAliveInterval);
        clearInterval(timeoutCheck);
    });
}
```

## Step 6: Mid-Stream Reconnection

```javascript
class ResilientRTMSConnection {
    constructor(rtmsInfo, config) {
        this.rtmsInfo = rtmsInfo;
        this.config = config;
        this.reconnectionAttempt = 0;
        this.signalingWs = null;
        this.mediaWs = null;
    }

    async connect() {
        try {
            this.signalingWs = await connectSignalingWithRetry(
                this.rtmsInfo.signalingUrl,
                this.rtmsInfo.sessionKey
            );

            this.mediaWs = await connectMediaWithRetry(
                this.rtmsInfo.mediaUrl,
                this.signalingWs
            );

            this.setupReconnectionHandlers();

        } catch (error) {
            console.error('[RTMS] Initial connection failed:', error);
            throw error;
        }
    }

    setupReconnectionHandlers() {
        const handleDisconnection = (wsType) => async (code, reason) => {
            console.error(`[${wsType}] Disconnected: ${code} ${reason}`);

            this.reconnectionAttempt++;

            if (this.reconnectionAttempt > this.config.reconnect_max_attempts) {
                console.error(
                    `[RECONNECT] Giving up after ${this.reconnectionAttempt} attempts`
                );
                this.cleanup();
                return;
            }

            // Exponential backoff: 2s, 4s, 8s...
            const delay = this.config.reconnect_base_delay_ms
                          * Math.pow(2, this.reconnectionAttempt - 1);

            console.log(
                `[RECONNECT] Attempt ${this.reconnectionAttempt}/` +
                `${this.config.reconnect_max_attempts} in ${delay}ms...`
            );

            await sleep(delay);

            try {
                await this.connect();
                console.log('[RECONNECT] Successfully reconnected');
                this.reconnectionAttempt = 0;  // Reset counter
            } catch (error) {
                console.error('[RECONNECT] Failed:', error.message);
                // Handler will be called again if connection fails
            }
        };

        this.signalingWs.on('close', handleDisconnection('SIGNALING'));
        this.mediaWs.on('close', handleDisconnection('MEDIA'));

        this.signalingWs.on('error', (error) => {
            console.error('[SIGNALING] Error:', error.message);
        });

        this.mediaWs.on('error', (error) => {
            console.error('[MEDIA] Error:', error.message);
        });
    }

    cleanup() {
        if (this.signalingWs) this.signalingWs.close();
        if (this.mediaWs) this.mediaWs.close();
    }
}
```

### Customizing Reconnection Behavior

```javascript
// Example: Capped exponential backoff (max 30s)
const delay = Math.min(
    config.reconnect_base_delay_ms * Math.pow(2, reconnectionAttempt - 1),
    30000  // Cap at 30s
);

// Example: Linear backoff instead of exponential
const delay = config.reconnect_base_delay_ms * reconnectionAttempt;

// Example: Jittered backoff (avoid thundering herd)
const baseDelay = config.reconnect_base_delay_ms * Math.pow(2, reconnectionAttempt - 1);
const jitter = Math.random() * 1000;  // Random 0-1000ms
const delay = baseDelay + jitter;
```

## Complete Resilient Bot Example

```javascript
const config = loadConfig();

async function main() {
    try {
        // 1. Optional: Trigger RTMS via REST API
        console.log('[RTMS] Triggering RTMS start...');
        await triggerRTMSStart(MEETING_ID);

        // 2. Wait for webhook
        console.log('[RTMS] Waiting for meeting.rtms_started webhook...');
        const rtmsInfo = await waitForRTMSWebhook(MEETING_UUID);

        // 3. Connect with resilience
        const rtms = new ResilientRTMSConnection(rtmsInfo, config);
        await rtms.connect();

        console.log('[RTMS] Bot is running, processing streams...');

        // 4. Process media data
        rtms.mediaWs.on('message', (data) => {
            const frame = parseMediaFrame(data);
            processMediaFrame(frame);
        });

        // 5. Handle graceful shutdown
        process.on('SIGINT', () => {
            console.log('[RTMS] Shutting down...');
            rtms.cleanup();
            process.exit(0);
        });

    } catch (error) {
        console.error('[RTMS] ABORT:', error.message);
        process.exit(1);
    }
}

main();
```

## Comparison: RTMS Bot vs Meeting SDK Bot

| Aspect | RTMS Bot | Meeting SDK Bot |
|--------|----------|-----------------|
| **Visibility** | Invisible (read-only service) | Visible participant |
| **Authentication** | REST API trigger + webhook | JWT + OBF token |
| **Join Dependency** | No dependency on participants | Owner must be present |
| **Retry Logic** | Not applicable (webhook-based) | Required (owner presence) |
| **Media Access** | Audio/video/text/share/chat via WebSocket | Raw audio/video/share via SDK |
| **Recording Control** | None (read-only) | Full (local, cloud, raw) |
| **Interaction** | Cannot interact | Can send chat, reactions |
| **Resource Usage** | Lower (WebSocket only) | Higher (full SDK) |
| **Use Case** | Passive transcription, analytics | Interactive bots, recording, moderation |

**Choose RTMS Bot when:**
- You only need to observe/transcribe
- You want minimal resource usage
- You prefer invisible operation
- You're processing external meetings (with permission)

**Choose Meeting SDK Bot when:**
- You need to interact with the meeting (chat, reactions)
- You need local recording control
- You want to be visible in participant list
- You're processing your own meetings

## Troubleshooting

### Webhook Never Arrives

**Symptom:** `waitForRTMSWebhook()` times out

**Solution:**
1. Verify webhook endpoint is HTTPS and publicly accessible
2. Check Event Subscriptions in Zoom Marketplace: `meeting.rtms_started` enabled
3. Verify RTMS was actually started (check Zoom client or REST API response)
4. Increase `webhook_wait_timeout_ms` if meeting starts later than expected
5. Test webhook delivery: `curl -X POST YOUR_WEBHOOK_URL`

### Signaling Handshake Fails

**Symptom:** Connection closes immediately after handshake

**Solution:**
1. Verify HMAC signature generation matches Zoom docs
2. Check timestamp is current (not stale)
3. Verify `WEBHOOK_SECRET_TOKEN` matches Zoom Marketplace config
4. Check signaling URL hasn't expired (short TTL)

### Keep-Alive Timeout

**Symptom:** Connection closes with "Keep-alive timeout"

**Solution:**
1. Network congestion - increase `keepalive_timeout_ms`
2. Server overloaded - increase `keepalive_interval_ms`
3. Verify ping/pong implementation is correct
4. Check firewall/proxy not blocking WebSocket pings

### Frequent Reconnections

**Symptom:** Bot reconnects multiple times, then gives up

**Solution:**
1. Increase `reconnect_max_attempts` (e.g., 5 instead of 3)
2. Increase `reconnect_base_delay_ms` if network is slow
3. Monitor server resources (CPU/memory/network)
4. Check for rate limiting (too many connection attempts)

## Resources

- **RTMS Docs**: https://developers.zoom.us/docs/rtms/
- **RTMS WebSocket Guide**: https://developers.zoom.us/docs/api/websockets/
- **RTMS SDK**: https://github.com/zoom/rtms
- **Webhook Reference**: [../references/webhooks.md](../references/webhooks.md)
- **Connection Architecture**: [../concepts/connection-architecture.md](../concepts/connection-architecture.md)
- **Meeting SDK Bot Alternative**: [Meeting SDK Bot (Linux)](../../meeting-sdk/linux/meeting-sdk-bot.md)
