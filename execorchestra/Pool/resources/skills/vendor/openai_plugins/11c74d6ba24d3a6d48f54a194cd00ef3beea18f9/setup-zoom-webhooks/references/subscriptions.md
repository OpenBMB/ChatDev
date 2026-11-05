# Webhooks - Subscriptions

Configure webhook event subscriptions for real-time notifications.

## Overview

Subscribe to Zoom events to receive real-time notifications at your endpoint. This enables:
- Real-time meeting tracking (started, ended, participant changes)
- Automated recording processing pipelines
- User lifecycle management
- Skill chaining: Combine REST API calls with event-driven workflows

## Configuring Subscriptions

### Method 1: Via Marketplace Portal (Recommended for Setup)

1. Go to your app in [Marketplace](https://marketplace.zoom.us/)
2. Navigate to **Feature** → **Event Subscriptions**
3. Add subscription name and endpoint URL
4. Select events to subscribe to
5. Save and activate

### Method 2: Via API (Programmatic Management)

Use the Webhook Subscriptions API for programmatic subscription management.

#### Create Subscription

```bash
POST /webhooks/options
```

```json
{
  "notification_endpoint_url": "https://your-server.com/zoom/webhook",
  "events": [
    "meeting.started",
    "meeting.ended",
    "meeting.participant_joined",
    "recording.completed"
  ]
}
```

#### Get Subscription

```bash
GET /webhooks/options
```

**Response:**
```json
{
  "notification_endpoint_url": "https://your-server.com/zoom/webhook",
  "events": [
    "meeting.started",
    "meeting.ended",
    "meeting.participant_joined",
    "recording.completed"
  ]
}
```

#### Update Subscription

```bash
PATCH /webhooks/options
```

```json
{
  "events": [
    "meeting.started",
    "meeting.ended",
    "recording.completed",
    "user.created"
  ]
}
```

### Subscription Settings

| Setting | Description | Required |
|---------|-------------|----------|
| **notification_endpoint_url** | Your HTTPS endpoint (must be publicly accessible) | Yes |
| **events** | Array of event types to subscribe to | Yes |

## Event Categories

### Meeting Events
| Event | Trigger |
|-------|---------|
| `meeting.created` | Meeting scheduled |
| `meeting.updated` | Meeting settings changed |
| `meeting.deleted` | Meeting deleted |
| `meeting.started` | Meeting begins |
| `meeting.ended` | Meeting ends |
| `meeting.participant_joined` | Participant joins |
| `meeting.participant_left` | Participant leaves |
| `meeting.sharing_started` | Screen share begins |
| `meeting.sharing_ended` | Screen share ends |

### Recording Events
| Event | Trigger |
|-------|---------|
| `recording.started` | Cloud recording begins |
| `recording.stopped` | Cloud recording paused/stopped |
| `recording.paused` | Cloud recording paused |
| `recording.resumed` | Cloud recording resumed |
| `recording.completed` | Recording processed and available |
| `recording.trashed` | Recording moved to trash |
| `recording.deleted` | Recording permanently deleted |
| `recording.recovered` | Recording restored from trash |

### User Events
| Event | Trigger |
|-------|---------|
| `user.created` | New user added |
| `user.updated` | User details changed |
| `user.deleted` | User removed |
| `user.deactivated` | User deactivated |
| `user.activated` | User activated |

### Webinar Events
| Event | Trigger |
|-------|---------|
| `webinar.created` | Webinar scheduled |
| `webinar.started` | Webinar begins |
| `webinar.ended` | Webinar ends |
| `webinar.registration_created` | New registration |

## Subscription Object Schema

```json
{
  "notification_endpoint_url": "string (HTTPS URL)",
  "events": ["array of event type strings"],
  "secret_token": "string (for signature verification)"
}
```

## Code Examples

### JavaScript - Express Webhook Handler with Subscription Check

```javascript
const express = require('express');
const crypto = require('crypto');
const axios = require('axios');

const app = express();
app.use(express.json());

// Verify webhook signature
function verifyWebhookSignature(req, secret) {
  const message = `v0:${req.headers['x-zm-request-timestamp']}:${JSON.stringify(req.body)}`;
  const hashForVerify = crypto
    .createHmac('sha256', secret)
    .update(message)
    .digest('hex');

  const signature = `v0=${hashForVerify}`;
  return signature === req.headers['x-zm-signature'];
}

// Handle webhook events
app.post('/zoom/webhook', (req, res) => {
  const WEBHOOK_SECRET = process.env.ZOOM_WEBHOOK_SECRET;

  if (!verifyWebhookSignature(req, WEBHOOK_SECRET)) {
    return res.status(401).send('Unauthorized');
  }

  const { event, payload } = req.body;

  switch (event) {
    case 'meeting.started':
      console.log(`Meeting started: ${payload.object.topic}`);
      break;
    case 'meeting.ended':
      console.log(`Meeting ended: ${payload.object.uuid}`);
      break;
    case 'recording.completed':
      processRecording(payload.object);
      break;
  }

  res.status(200).send('OK');
});
```

### JavaScript - Manage Subscriptions via API

```javascript
async function updateWebhookSubscription(accessToken, events) {
  const response = await axios.patch(
    'https://api.zoom.us/v2/webhooks/options',
    { events },
    {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json'
      }
    }
  );
  return response.data;
}

// Add new events to subscription
await updateWebhookSubscription(token, [
  'meeting.started',
  'meeting.ended',
  'recording.completed',
  'user.created',  // New event
  'user.deleted'   // New event
]);
```

## Multiple Subscriptions

You can create multiple subscriptions to:
- Send different events to different endpoints
- Separate production and development endpoints
- Organize by event type
- Route events to different microservices

## Skill Chaining

Webhooks are commonly combined with REST API in skill chains:

| Chain | Pattern | Use Case |
|-------|---------|----------|
| REST API → Webhooks | Create meeting, subscribe to events | Track meeting lifecycle |
| Webhooks → REST API | Receive event, fetch details | Recording download on completion |
| Users API → Webhooks | Create user, subscribe to user events | User lifecycle tracking |

**Example: Meeting creation with event tracking**
```javascript
// Step 1: Subscribe to meeting events (one-time setup)
await updateWebhookSubscription(token, ['meeting.started', 'meeting.ended']);

// Step 2: Create meeting via REST API
const meeting = await createMeeting(token, { topic: 'Team Standup', type: 2 });

// Step 3: When meeting.started webhook arrives, track it
// Step 4: When meeting.ended webhook arrives, process attendance
```

See [meeting-details-with-events.md](../../general/use-cases/meeting-details-with-events.md) for complete skill chaining patterns.

## Testing Webhooks

1. **Local development**: Use [ngrok](https://ngrok.com/) to expose local endpoint
   ```bash
   ngrok http 3000
   ```
2. **Webhook logs**: Check Marketplace portal → App → Webhooks → Logs
3. **Test endpoint**: Validate signature handling before going live
4. **Retry behavior**: Zoom retries failed webhooks (5xx responses) up to 3 times

## Required Scopes

| Scope | Operations |
|-------|------------|
| `webhook:read:admin` | View webhook settings |
| `webhook:write:admin` | Modify webhook settings |

## Resources

- **Webhooks overview**: https://developers.zoom.us/docs/api/rest/webhook-reference/
- **Event types**: https://developers.zoom.us/docs/api/rest/reference/zoom-api/events/
- **Signature verification**: See [signature-verification.md](signature-verification.md)
