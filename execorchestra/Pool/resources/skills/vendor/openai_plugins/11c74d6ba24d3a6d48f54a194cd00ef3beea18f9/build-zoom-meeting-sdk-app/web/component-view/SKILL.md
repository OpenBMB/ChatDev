---
name: zoom-meeting-sdk-web-component-view
description: |
  Zoom Meeting SDK Web - Component View. Embeddable Zoom meeting components with Promise-based API
  for flexible integration. Ideal for React/Vue/Angular apps and custom layouts. Uses ZoomMtgEmbedded
  with async/await patterns and embeddable UI containers.
---

# Zoom Meeting SDK Web - Component View

Embeddable Zoom meeting components for flexible integration into any web application. Component View provides Promise-based APIs and customizable UI.

This is the correct web skill for a **custom UI around a real Zoom meeting**.
Do not route to Video SDK unless the user is building a non-meeting custom session product.

## Overview

Component View uses `ZoomMtgEmbedded.createClient()` to create embeddable meeting components within a specific container element.

| Aspect | Details |
|--------|---------|
| **API Object** | `ZoomMtgEmbedded.createClient()` (instance) |
| **API Style** | Promise-based (async/await) |
| **UI** | Embeddable in any container |
| **Password param** | `password` (lowercase) |
| **Events** | `on()`/`off()` |
| **Best For** | Custom layouts, React/Vue/Angular apps |

## Installation

### NPM

```bash
npm install @zoom/meetingsdk --save
```

```javascript
import ZoomMtgEmbedded from '@zoom/meetingsdk/embedded';
```

### CDN

```html
<script src="https://source.zoom.us/{VERSION}/lib/vendor/react.min.js"></script>
<script src="https://source.zoom.us/{VERSION}/lib/vendor/react-dom.min.js"></script>
<script src="https://source.zoom.us/{VERSION}/lib/vendor/redux.min.js"></script>
<script src="https://source.zoom.us/{VERSION}/lib/vendor/redux-thunk.min.js"></script>
<script src="https://source.zoom.us/{VERSION}/lib/vendor/lodash.min.js"></script>
<script src="https://source.zoom.us/zoom-meeting-embedded-{VERSION}.min.js"></script>
```

## Complete Initialization Flow

```javascript
import ZoomMtgEmbedded from '@zoom/meetingsdk/embedded';

// Step 1: Create client instance (do once, not on every render!)
const client = ZoomMtgEmbedded.createClient();

async function joinMeeting() {
  try {
    // Step 2: Get container element
    const meetingSDKElement = document.getElementById('meetingSDKElement');

    // Step 3: Initialize client
    await client.init({
      zoomAppRoot: meetingSDKElement,
      language: 'en-US',
      debug: true,
      patchJsMedia: true,
      leaveOnPageUnload: true,
    });

    // Step 4: Join meeting
    await client.join({
      signature: signature,
      sdkKey: sdkKey,
      meetingNumber: meetingNumber,
      userName: userName,
      password: password,  // lowercase!
      userEmail: userEmail,
    });

    console.log('Joined successfully!');
  } catch (error) {
    console.error('Failed to join:', error);
  }
}
```

## client.init() - All Options

### Required

| Parameter | Type | Description |
|-----------|------|-------------|
| `zoomAppRoot` | `HTMLElement` | Container element for meeting UI |

### Display

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `language` | `string` | `'en-US'` | UI language |
| `debug` | `boolean` | `false` | Enable debug logging |

### Media

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `patchJsMedia` | `boolean` | `false` | Auto-apply media fixes |
| `leaveOnPageUnload` | `boolean` | `false` | Cleanup on page unload |
| `enableHD` | `boolean` | `true` | Enable 720p video |
| `enableFullHD` | `boolean` | `false` | Enable 1080p video |

### Customization

| Parameter | Type | Description |
|-----------|------|-------------|
| `customize` | `object` | UI customization options |
| `webEndpoint` | `string` | For ZFG: `'www.zoomgov.com'` |
| `assetPath` | `string` | Custom path for AV libraries |

### Customize Object

```javascript
await client.init({
  zoomAppRoot: element,
  customize: {
    // Meeting info displayed
    meetingInfo: [
      'topic',
      'host',
      'mn',
      'pwd',
      'telPwd',
      'invite',
      'participant',
      'dc',
      'enctype'
    ],

    // Video customization
    video: {
      isResizable: true,
      viewSizes: {
        default: {
          width: 1000,
          height: 600
        },
        ribbon: {
          width: 300,
          height: 700
        }
      },
      popper: {
        disableDraggable: false
      }
    },

    // Custom toolbar buttons
    toolbar: {
      buttons: [
        {
          text: 'Custom Button',
          className: 'custom-btn',
          onClick: () => {
            console.log('Custom button clicked');
          }
        }
      ]
    },

    // Active speaker indicator
    activeSpaker: {
      strokeColor: '#00FF00'
    }
  }
});
```

## client.join() - All Options

### Required

| Parameter | Type | Description |
|-----------|------|-------------|
| `signature` | `string` | SDK JWT from backend |
| `sdkKey` | `string` | SDK Key / Client ID |
| `meetingNumber` | `string \| number` | Meeting number |
| `userName` | `string` | Display name |

### Authentication

| Parameter | Type | When Required | Description |
|-----------|------|---------------|-------------|
| `password` | `string` | If set | Meeting password (lowercase!) |
| `zak` | `string` | Starting as host | Host's ZAK token |
| `tk` | `string` | Registration | Registrant token |
| `userEmail` | `string` | Webinars | User email |

## Event Listeners

### Syntax

```javascript
// Subscribe
client.on('event-name', callback);

// Unsubscribe
client.off('event-name', callback);
```

### Connection Events

```javascript
client.on('connection-change', (payload) => {
  // payload.state: 'Connecting', 'Connected', 'Reconnecting', 'Closed'
  console.log('Connection state:', payload.state);

  if (payload.state === 'Closed') {
    console.log('Reason:', payload.reason);
  }
});
```

### User Events

```javascript
client.on('user-added', (payload) => {
  // Array of users who joined
  console.log('Users added:', payload);
  payload.forEach(user => {
    console.log('User ID:', user.oderId);
    console.log('Name:', user.displayName);
  });
});

client.on('user-removed', (payload) => {
  // Array of users who left
  console.log('Users removed:', payload);
});

client.on('user-updated', (payload) => {
  // Array of users whose properties changed
  console.log('Users updated:', payload);
});
```

### Audio Events

```javascript
client.on('active-speaker', (payload) => {
  // Current active speaker
  console.log('Active speaker:', payload);
});

client.on('audio-statistic-data-change', (payload) => {
  console.log('Audio stats:', payload);
});
```

### Video Events

```javascript
client.on('video-active-change', (payload) => {
  // Video state changed
  console.log('Video active:', payload);
});

client.on('video-statistic-data-change', (payload) => {
  console.log('Video stats:', payload);
});
```

### Share Events

```javascript
client.on('active-share-change', (payload) => {
  console.log('Share status:', payload);
});

client.on('share-statistic-data-change', (payload) => {
  console.log('Share stats:', payload);
});
```

### Chat Events

```javascript
client.on('chat-on-message', (payload) => {
  console.log('Chat message:', payload);
});
```

### Recording Events

```javascript
client.on('recording-change', (payload) => {
  console.log('Recording status:', payload);
});
```

### Media Device Events

```javascript
client.on('media-sdk-change', (payload) => {
  console.log('Media SDK:', payload);
});

client.on('device-change', () => {
  console.log('Device changed');
});
```

## Common Methods

### User Information

```javascript
// Get current user
const currentUser = client.getCurrentUser();
console.log('Current user:', currentUser);

// Get all participants
const participants = client.getParticipantsList();
console.log('Participants:', participants);

// Check if user is host
const isHost = client.isHost();
```

### Audio Control

```javascript
// Mute/unmute self
await client.mute(true);  // mute
await client.mute(false); // unmute

// Mute/unmute specific user (host only)
await client.muteAudio(userId, true);

// Mute all (host only)
await client.muteAllAudio(true);
```

### Video Control

```javascript
// Start/stop video
await client.startVideo();
await client.stopVideo();

// Mute/unmute user's video (host only)
await client.muteVideo(userId, true);
```

### Meeting Control

```javascript
// Leave meeting
client.leaveMeeting();

// End meeting (host only)
client.endMeeting();
```

### Screen Share

```javascript
// Start screen share
await client.startShareScreen();

// Stop screen share
await client.stopShareScreen();
```

### Recording

```javascript
// Start recording (cloud)
await client.startCloudRecording();

// Stop recording
await client.stopCloudRecording();
```

### Virtual Background

```javascript
// Check support
const isSupported = await client.isSupportVirtualBackground();

// Set virtual background
await client.setVirtualBackground(imageUrl);

// Remove virtual background
await client.removeVirtualBackground();
```

### Rename

```javascript
// Rename user
await client.rename(userId, 'New Name');
```

## React Integration

### Basic Pattern

```tsx
import { useEffect, useRef, useState, useCallback } from 'react';
import ZoomMtgEmbedded from '@zoom/meetingsdk/embedded';

type ZoomClient = ReturnType<typeof ZoomMtgEmbedded.createClient>;

function ZoomMeeting({ meetingNumber, password, userName }: Props) {
  const clientRef = useRef<ZoomClient | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [isJoined, setIsJoined] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Create client once
  useEffect(() => {
    if (!clientRef.current) {
      clientRef.current = ZoomMtgEmbedded.createClient();
    }
  }, []);

  const joinMeeting = useCallback(async () => {
    if (!clientRef.current || !containerRef.current) return;

    try {
      // Get signature from backend
      const { signature, sdkKey } = await fetchSignature(meetingNumber);

      await clientRef.current.init({
        zoomAppRoot: containerRef.current,
        language: 'en-US',
        patchJsMedia: true,
        leaveOnPageUnload: true,
      });

      await clientRef.current.join({
        signature,
        sdkKey,
        meetingNumber,
        password,
        userName,
      });

      setIsJoined(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to join');
    }
  }, [meetingNumber, password, userName]);

  return (
    <div>
      <div
        ref={containerRef}
        style={{ width: '100%', height: '500px' }}
      />
      {!isJoined && (
        <button onClick={joinMeeting}>Join Meeting</button>
      )}
      {error && <div className="error">{error}</div>}
    </div>
  );
}
```

### Event Handling in React

```tsx
useEffect(() => {
  if (!clientRef.current) return;

  const handleConnectionChange = (payload: any) => {
    if (payload.state === 'Connected') {
      setIsJoined(true);
    } else if (payload.state === 'Closed') {
      setIsJoined(false);
    }
  };

  const handleUserAdded = (payload: any) => {
    console.log('Users joined:', payload);
  };

  clientRef.current.on('connection-change', handleConnectionChange);
  clientRef.current.on('user-added', handleUserAdded);

  return () => {
    clientRef.current?.off('connection-change', handleConnectionChange);
    clientRef.current?.off('user-added', handleUserAdded);
  };
}, []);
```

## Positioning and Resizing

### Initial Size

```javascript
await client.init({
  zoomAppRoot: element,
  customize: {
    video: {
      viewSizes: {
        default: { width: 1000, height: 600 }
      }
    }
  }
});
```

### Dynamic Resizing

The container element size determines the meeting UI size. To resize:

```javascript
// Just resize the container
document.getElementById('meetingSDKElement').style.width = '1200px';
document.getElementById('meetingSDKElement').style.height = '800px';
```

### Making it Resizable

```javascript
customize: {
  video: {
    isResizable: true
  }
}
```

## Supported Features

Component View supports core meeting functionality. Some features from Client View may not be available.

| Feature | Supported |
|---------|-----------|
| Audio/Video | ✅ |
| Screen Share | ✅ |
| Chat | ✅ |
| Virtual Background | ✅ |
| Breakout Rooms | ✅ |
| Cloud Recording | ✅ |
| Closed Captions | ✅ |
| Live Transcription | ✅ |
| Waiting Room | ✅ |
| Gallery View | ✅ |
| Reactions | ✅ |
| Raise Hand | ✅ |

Contact Zoom Developer Support to request additional features.

## Error Handling

```javascript
try {
  await client.join({
    // ... options
  });
} catch (error) {
  // error.reason contains error code
  // error.message contains description

  switch (error.reason) {
    case 'WRONG_MEETING_PASSWORD':
      console.error('Incorrect password');
      break;
    case 'MEETING_NOT_START':
      console.error('Meeting has not started');
      break;
    case 'INVALID_PARAMETERS':
      console.error('Invalid join parameters');
      break;
    default:
      console.error('Join failed:', error.message);
  }
}
```

## Comparison with Client View

| Feature | Component View | Client View |
|---------|----------------|-------------|
| **API Style** | Promises | Callbacks |
| **Password param** | `password` | `passWord` |
| **Container** | Custom element | Auto `#zmmtg-root` |
| **UI** | Embeddable | Full-page |
| **Preloading** | Not needed | `preLoadWasm()` |
| **Language** | Init option | `i18n.load()` |
| **Events** | `on()`/`off()` | `inMeetingServiceListener()` |

## Resources

- [Main Web SDK Skill](../SKILL.md)
- [Reference Index](references/index.md)
- [Error Codes](../troubleshooting/error-codes.md)
- [Common Issues](../troubleshooting/common-issues.md)
- [SharedArrayBuffer Setup](../concepts/sharedarraybuffer.md)
- [Official API Reference](https://marketplacefront.zoom.us/sdk/meeting/web/components/index.html)

## Operations

- [RUNBOOK.md](RUNBOOK.md) - 5-minute preflight and debugging checklist.
