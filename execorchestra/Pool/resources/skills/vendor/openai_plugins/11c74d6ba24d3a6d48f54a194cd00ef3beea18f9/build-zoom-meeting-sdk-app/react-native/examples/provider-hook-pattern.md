# Provider Hook Pattern

Use wrapper context consistently.

```tsx
import { ZoomSDKProvider, useZoom } from '@zoom/meetingsdk-react-native';

function MeetingActions() {
  const zoom = useZoom();
  // zoom.joinMeeting / zoom.startMeeting / zoom.cleanup
}
```

Do not call wrapper methods before provider initialization is complete.
