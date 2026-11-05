# Start Meeting Pattern

```tsx
import { useZoom } from '@zoom/meetingsdk-react-native';

const zoom = useZoom();

await zoom.startMeeting({
  userName: 'host-name',
  meetingNumber: '123456789',
  zoomAccessToken: '<ZAK>',
});
```

Notes:

- `zoomAccessToken` is required for host start in wrapper validation.
- Missing/expired ZAK returns native start failure code.
