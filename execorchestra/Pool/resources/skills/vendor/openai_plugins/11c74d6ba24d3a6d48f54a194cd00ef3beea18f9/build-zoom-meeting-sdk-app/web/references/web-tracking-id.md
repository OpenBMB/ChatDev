# Meeting SDK Web - Tracking ID

Use tracking IDs to identify users across sessions.

## Overview

Tracking IDs allow you to identify users joining meetings from your application for analytics and tracking purposes.

## Setting Tracking ID

### Component View

```javascript
await client.join({
  sdkKey: SDK_KEY,
  signature: signature,
  meetingNumber: meetingNumber,
  userName: 'User Name',
  trackingId: 'your-tracking-id-here'
});
```

### Client View

```javascript
ZoomMtg.join({
  sdkKey: SDK_KEY,
  signature: signature,
  meetingNumber: meetingNumber,
  userName: 'User Name',
  trackingId: 'your-tracking-id-here'
});
```

## Use Cases

- Analytics and reporting
- User identification across meetings
- Integration with your user database
- Conversion tracking

## Tracking ID in Reports

Tracking IDs appear in:
- Meeting participant reports
- Dashboard analytics
- Webhook payloads

## Best Practices

1. Use consistent IDs across sessions
2. Don't include sensitive data in tracking IDs
3. Document your tracking ID schema

## Resources

- **Meeting SDK Web docs**: https://developers.zoom.us/docs/meeting-sdk/web/
