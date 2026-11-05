# Webhooks - Events

Complete reference of Zoom webhook events.

## Overview

Zoom sends webhook events for various actions across meetings, users, recordings, and more.

## Meeting Events

| Event | Description |
|-------|-------------|
| `meeting.created` | Meeting created |
| `meeting.updated` | Meeting updated |
| `meeting.deleted` | Meeting deleted |
| `meeting.started` | Meeting started |
| `meeting.ended` | Meeting ended |
| `meeting.participant_joined` | Participant joined |
| `meeting.participant_left` | Participant left |
| `meeting.sharing_started` | Screen share started |
| `meeting.sharing_ended` | Screen share ended |

## Recording Events

| Event | Description |
|-------|-------------|
| `recording.started` | Recording started |
| `recording.stopped` | Recording stopped |
| `recording.paused` | Recording paused |
| `recording.resumed` | Recording resumed |
| `recording.completed` | Recording ready for download |
| `recording.trashed` | Recording moved to trash |
| `recording.deleted` | Recording permanently deleted |

## User Events

| Event | Description |
|-------|-------------|
| `user.created` | User created |
| `user.updated` | User updated |
| `user.deleted` | User deleted |
| `user.activated` | User activated |
| `user.deactivated` | User deactivated |

## Webinar Events

| Event | Description |
|-------|-------------|
| `webinar.created` | Webinar created |
| `webinar.updated` | Webinar updated |
| `webinar.deleted` | Webinar deleted |
| `webinar.started` | Webinar started |
| `webinar.ended` | Webinar ended |

## Event Payload Structure

```json
{
  "event": "meeting.started",
  "event_ts": 1234567890,
  "payload": {
    "account_id": "account_id",
    "object": {
      "id": "meeting_id",
      "topic": "Meeting Topic",
      "host_id": "host_user_id",
      "start_time": "2024-01-15T10:00:00Z"
    }
  }
}
```

## Resources

- **Events reference**: https://developers.zoom.us/docs/api/rest/reference/zoom-api/events/
