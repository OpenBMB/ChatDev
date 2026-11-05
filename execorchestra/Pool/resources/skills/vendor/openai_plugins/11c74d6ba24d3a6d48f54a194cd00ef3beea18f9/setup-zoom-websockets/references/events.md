# WebSockets - Event Types

Complete reference for events available via Zoom WebSockets.

## Event Structure

All WebSocket events follow this structure:

```json
{
  "event": "event.type",
  "event_ts": 1706123456789,
  "payload": {
    "account_id": "abcD3ojkdbjfg",
    "object": {
      // Event-specific data
    }
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `event` | string | Event type identifier |
| `event_ts` | number | Unix timestamp (milliseconds) |
| `payload.account_id` | string | Zoom account ID |
| `payload.object` | object | Event-specific payload |

## Meeting Events

### meeting.created

Triggered when a meeting is scheduled.

```json
{
  "event": "meeting.created",
  "payload": {
    "account_id": "abcD3ojkdbjfg",
    "object": {
      "id": 1234567890,
      "uuid": "abcdefgh-1234-5678-abcd-1234567890ab",
      "host_id": "xyz789",
      "topic": "Weekly Team Sync",
      "type": 2,
      "start_time": "2024-01-25T10:00:00Z",
      "duration": 60,
      "timezone": "America/Los_Angeles"
    }
  }
}
```

### meeting.updated

Triggered when meeting settings are changed.

```json
{
  "event": "meeting.updated",
  "payload": {
    "account_id": "abcD3ojkdbjfg",
    "object": {
      "id": 1234567890,
      "topic": "Updated: Weekly Team Sync"
    },
    "old_object": {
      "topic": "Weekly Team Sync"
    }
  }
}
```

### meeting.deleted

Triggered when a meeting is deleted.

```json
{
  "event": "meeting.deleted",
  "payload": {
    "account_id": "abcD3ojkdbjfg",
    "object": {
      "id": 1234567890,
      "uuid": "abcdefgh-1234-5678-abcd-1234567890ab",
      "host_id": "xyz789"
    }
  }
}
```

### meeting.started

Triggered when a meeting begins.

```json
{
  "event": "meeting.started",
  "payload": {
    "account_id": "abcD3ojkdbjfg",
    "object": {
      "id": 1234567890,
      "uuid": "abcdefgh-1234-5678-abcd-1234567890ab",
      "host_id": "xyz789",
      "topic": "Weekly Team Sync",
      "type": 2,
      "start_time": "2024-01-25T10:00:00Z",
      "timezone": "America/Los_Angeles"
    }
  }
}
```

### meeting.ended

Triggered when a meeting ends.

```json
{
  "event": "meeting.ended",
  "payload": {
    "account_id": "abcD3ojkdbjfg",
    "object": {
      "id": 1234567890,
      "uuid": "abcdefgh-1234-5678-abcd-1234567890ab",
      "host_id": "xyz789",
      "topic": "Weekly Team Sync",
      "start_time": "2024-01-25T10:00:00Z",
      "end_time": "2024-01-25T11:05:00Z",
      "duration": 65
    }
  }
}
```

### meeting.participant_joined

Triggered when a participant joins the meeting.

```json
{
  "event": "meeting.participant_joined",
  "payload": {
    "account_id": "abcD3ojkdbjfg",
    "object": {
      "id": 1234567890,
      "uuid": "abcdefgh-1234-5678-abcd-1234567890ab",
      "host_id": "xyz789",
      "participant": {
        "id": "participant123",
        "user_id": "user456",
        "user_name": "John Doe",
        "email": "john@example.com",
        "join_time": "2024-01-25T10:02:00Z"
      }
    }
  }
}
```

### meeting.participant_left

Triggered when a participant leaves the meeting.

```json
{
  "event": "meeting.participant_left",
  "payload": {
    "account_id": "abcD3ojkdbjfg",
    "object": {
      "id": 1234567890,
      "uuid": "abcdefgh-1234-5678-abcd-1234567890ab",
      "participant": {
        "id": "participant123",
        "user_name": "John Doe",
        "leave_time": "2024-01-25T10:45:00Z",
        "leave_reason": "left the meeting"
      }
    }
  }
}
```

### meeting.sharing_started

Triggered when screen sharing begins.

```json
{
  "event": "meeting.sharing_started",
  "payload": {
    "account_id": "abcD3ojkdbjfg",
    "object": {
      "id": 1234567890,
      "uuid": "abcdefgh-1234-5678-abcd-1234567890ab",
      "participant": {
        "id": "participant123",
        "user_name": "John Doe"
      },
      "sharing_details": {
        "content": "screen",
        "date_time": "2024-01-25T10:15:00Z"
      }
    }
  }
}
```

### meeting.sharing_ended

Triggered when screen sharing ends.

```json
{
  "event": "meeting.sharing_ended",
  "payload": {
    "account_id": "abcD3ojkdbjfg",
    "object": {
      "id": 1234567890,
      "uuid": "abcdefgh-1234-5678-abcd-1234567890ab",
      "participant": {
        "id": "participant123",
        "user_name": "John Doe"
      }
    }
  }
}
```

## Recording Events

### recording.started

Triggered when cloud recording starts.

```json
{
  "event": "recording.started",
  "payload": {
    "account_id": "abcD3ojkdbjfg",
    "object": {
      "id": 1234567890,
      "uuid": "abcdefgh-1234-5678-abcd-1234567890ab",
      "host_id": "xyz789",
      "topic": "Weekly Team Sync",
      "start_time": "2024-01-25T10:00:00Z",
      "recording_start": "2024-01-25T10:01:00Z"
    }
  }
}
```

### recording.stopped

Triggered when cloud recording stops (paused or ended).

```json
{
  "event": "recording.stopped",
  "payload": {
    "account_id": "abcD3ojkdbjfg",
    "object": {
      "id": 1234567890,
      "uuid": "abcdefgh-1234-5678-abcd-1234567890ab",
      "recording_start": "2024-01-25T10:01:00Z",
      "recording_end": "2024-01-25T11:00:00Z"
    }
  }
}
```

### recording.completed

Triggered when cloud recording is processed and ready for download.

```json
{
  "event": "recording.completed",
  "payload": {
    "account_id": "abcD3ojkdbjfg",
    "object": {
      "id": 1234567890,
      "uuid": "abcdefgh-1234-5678-abcd-1234567890ab",
      "host_id": "xyz789",
      "topic": "Weekly Team Sync",
      "start_time": "2024-01-25T10:00:00Z",
      "duration": 60,
      "total_size": 157286400,
      "recording_count": 2,
      "recording_files": [
        {
          "id": "file123",
          "meeting_id": "abcdefgh-1234-5678-abcd-1234567890ab",
          "recording_start": "2024-01-25T10:01:00Z",
          "recording_end": "2024-01-25T11:00:00Z",
          "file_type": "MP4",
          "file_size": 104857600,
          "download_url": "https://zoom.us/rec/download/...",
          "status": "completed"
        },
        {
          "id": "file124",
          "file_type": "TRANSCRIPT",
          "file_size": 52428800,
          "download_url": "https://zoom.us/rec/download/..."
        }
      ]
    }
  }
}
```

### recording.trashed

Triggered when recording is moved to trash.

### recording.deleted

Triggered when recording is permanently deleted.

### recording.recovered

Triggered when recording is restored from trash.

## User Events

### user.created

Triggered when a new user is added to the account.

```json
{
  "event": "user.created",
  "payload": {
    "account_id": "abcD3ojkdbjfg",
    "object": {
      "id": "user789",
      "first_name": "Jane",
      "last_name": "Smith",
      "email": "jane.smith@example.com",
      "type": 2,
      "created_at": "2024-01-25T09:00:00Z"
    }
  }
}
```

### user.updated

Triggered when user details are changed.

```json
{
  "event": "user.updated",
  "payload": {
    "account_id": "abcD3ojkdbjfg",
    "object": {
      "id": "user789",
      "first_name": "Jane",
      "last_name": "Smith-Jones"
    },
    "old_object": {
      "last_name": "Smith"
    }
  }
}
```

### user.deleted

Triggered when a user is removed from the account.

```json
{
  "event": "user.deleted",
  "payload": {
    "account_id": "abcD3ojkdbjfg",
    "object": {
      "id": "user789",
      "email": "jane.smith@example.com"
    }
  }
}
```

### user.deactivated

Triggered when a user is deactivated.

### user.activated

Triggered when a user is activated.

## Webinar Events

### webinar.created

### webinar.updated

### webinar.deleted

### webinar.started

### webinar.ended

### webinar.registration_created

Triggered when someone registers for a webinar.

```json
{
  "event": "webinar.registration_created",
  "payload": {
    "account_id": "abcD3ojkdbjfg",
    "object": {
      "id": 9876543210,
      "uuid": "webinar-uuid-here",
      "registrant": {
        "id": "registrant123",
        "email": "attendee@example.com",
        "first_name": "Attendee",
        "last_name": "User",
        "join_url": "https://zoom.us/w/..."
      }
    }
  }
}
```

## Event Handling Example

```javascript
const eventHandlers = {
  // Meeting events
  'meeting.created': (payload) => {
    console.log(`New meeting: ${payload.object.topic}`);
    notifyCalendarService(payload.object);
  },

  'meeting.started': (payload) => {
    console.log(`Meeting started: ${payload.object.topic}`);
    updateMeetingStatus(payload.object.id, 'in_progress');
  },

  'meeting.ended': (payload) => {
    console.log(`Meeting ended: ${payload.object.uuid}`);
    updateMeetingStatus(payload.object.id, 'completed');
    calculateAttendance(payload.object);
  },

  'meeting.participant_joined': (payload) => {
    const { participant } = payload.object;
    console.log(`${participant.user_name} joined`);
    trackAttendance(payload.object.id, participant);
  },

  // Recording events
  'recording.completed': (payload) => {
    console.log(`Recording ready: ${payload.object.topic}`);
    downloadRecordings(payload.object.recording_files);
  },

  // User events
  'user.created': (payload) => {
    console.log(`New user: ${payload.object.email}`);
    sendWelcomeEmail(payload.object);
  }
};

ws.on('message', (data) => {
  const event = JSON.parse(data);
  const handler = eventHandlers[event.event];

  if (handler) {
    handler(event.payload);
  } else {
    console.log(`Unhandled event: ${event.event}`);
  }
});
```

## Subscribing to Events

Configure which events to receive in your Zoom Marketplace app:

1. Go to **Feature** → **Event Subscriptions**
2. Select **WebSockets** as method type
3. Check the events you want to receive
4. Save the subscription

**Note:** You can modify subscriptions at any time. Changes take effect immediately.

## Event Filtering

If you're receiving too many events, consider:

1. **Subscribe selectively** - Only subscribe to events you need
2. **Filter in handler** - Drop events that don't match your criteria
3. **Use multiple subscriptions** - Route different events to different handlers

```javascript
// Filter example: Only process events for specific hosts
ws.on('message', (data) => {
  const event = JSON.parse(data);

  // Only process meetings from specific hosts
  const allowedHosts = ['host1@example.com', 'host2@example.com'];

  if (event.event.startsWith('meeting.') &&
      event.payload.object.host_id &&
      !allowedHosts.includes(getHostEmail(event.payload.object.host_id))) {
    return; // Skip this event
  }

  processEvent(event);
});
```

## Resources

- **Event reference**: https://developers.zoom.us/docs/api/rest/reference/zoom-api/events/
- **WebSockets docs**: https://developers.zoom.us/docs/api/websockets/
