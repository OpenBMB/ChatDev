# Join Meeting Pattern

```tsx
import { useZoom } from '@zoom/meetingsdk-react-native';

const zoom = useZoom();

await zoom.joinMeeting({
  userName: 'participant-name',
  meetingNumber: '123456789',
  password: 'meeting-password',
  userType: 1,
});
```

Notes:

- `meetingNumber` and `userName` are required by wrapper validation.
- `password` is optional in API shape, but may be mandatory by meeting settings.
