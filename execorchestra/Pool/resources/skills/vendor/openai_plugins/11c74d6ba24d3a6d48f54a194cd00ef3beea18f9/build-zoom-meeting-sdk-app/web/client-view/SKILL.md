---
name: zoom-meeting-sdk-web-client-view
description: |
  Zoom Meeting SDK Web - Client View. Full-page Zoom meeting experience with the familiar Zoom interface.
  Uses ZoomMtg global singleton with callback-based API. Ideal for quick integration with minimal
  customization. Provides the same UI as Zoom Web Client.
---

# Zoom Meeting SDK Web - Client View

Full-page Zoom meeting experience embedded in your web application. Client View provides the familiar Zoom interface with minimal customization needed.

## Overview

Client View uses the `ZoomMtg` global singleton to render a full-page meeting experience identical to the Zoom Web Client.

| Aspect | Details |
|--------|---------|
| **API Object** | `ZoomMtg` (global singleton) |
| **API Style** | Callback-based |
| **UI** | Full-page takeover |
| **Password param** | `passWord` (capital W) |
| **Events** | `inMeetingServiceListener()` |
| **Best For** | Quick integration, standard Zoom UI |

## Installation

### NPM

```bash
npm install @zoom/meetingsdk --save
```

```javascript
import { ZoomMtg } from '@zoom/meetingsdk';
```

### CDN

```html
<script src="https://source.zoom.us/{VERSION}/lib/vendor/react.min.js"></script>
<script src="https://source.zoom.us/{VERSION}/lib/vendor/react-dom.min.js"></script>
<script src="https://source.zoom.us/{VERSION}/lib/vendor/redux.min.js"></script>
<script src="https://source.zoom.us/{VERSION}/lib/vendor/redux-thunk.min.js"></script>
<script src="https://source.zoom.us/{VERSION}/lib/vendor/lodash.min.js"></script>
<script src="https://source.zoom.us/zoom-meeting-{VERSION}.min.js"></script>
```

## Complete Initialization Flow

```javascript
// Step 1: Check browser compatibility
console.log('Requirements:', ZoomMtg.checkSystemRequirements());

// Step 2: Set CDN path (optional - for China or custom hosting)
// ZoomMtg.setZoomJSLib('https://source.zoom.us/{VERSION}/lib', '/av');

// Step 3: Preload WebAssembly modules
ZoomMtg.preLoadWasm();
ZoomMtg.prepareWebSDK();

// Step 4: Load language resources
ZoomMtg.i18n.load('en-US');
ZoomMtg.i18n.onLoad(() => {

  // Step 5: Initialize SDK
  ZoomMtg.init({
    leaveUrl: '/meeting-ended',
    patchJsMedia: true,
    disableCORP: !window.crossOriginIsolated,
    success: () => {
      console.log('SDK initialized');

      // Step 6: Join meeting
      const joinPayload = {
        signature: signature,
        meetingNumber: meetingNumber,
        userName: userName,
        passWord: passWord,
        success: (res) => {
          console.log('Joined meeting');

          // Step 7: Post-join operations
          ZoomMtg.getAttendeeslist({});
          ZoomMtg.getCurrentUser({
            success: (res) => console.log('Current user:', res.result.currentUser)
          });
        },
        error: (err) => console.error('Join failed:', err)
      };

      // IMPORTANT: only include optional fields when they have real values
      // Passing undefined for some optional fields can cause runtime join errors
      if (userEmail) joinPayload.userEmail = userEmail;
      if (tk) joinPayload.tk = tk;
      if (zak) joinPayload.zak = zak;

      ZoomMtg.join(joinPayload);
    },
    error: (err) => console.error('Init failed:', err)
  });
});
```

## ZoomMtg.init() - All Options

### Required

| Parameter | Type | Description |
|-----------|------|-------------|
| `leaveUrl` | `string` | URL to redirect after leaving meeting |

### UI Customization

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `showMeetingHeader` | `boolean` | `true` | Show meeting number and topic |
| `disableInvite` | `boolean` | `false` | Hide invite button |
| `disableCallOut` | `boolean` | `false` | Hide call out option |
| `disableRecord` | `boolean` | `false` | Hide record button |
| `disableJoinAudio` | `boolean` | `false` | Hide join audio option |
| `disablePreview` | `boolean` | `false` | Skip audio/video preview |
| `audioPanelAlwaysOpen` | `boolean` | `false` | Keep audio panel open |
| `showPureSharingContent` | `boolean` | `false` | Prevent overlays on shared content |
| `videoHeader` | `boolean` | `true` | Show video tile header |
| `isLockBottom` | `boolean` | `true` | Show/hide footer |
| `videoDrag` | `boolean` | `true` | Enable drag video tiles |
| `sharingMode` | `string` | `'both'` | `'both'` or `'fit'` |
| `screenShare` | `boolean` | `true` | Enable browser URL sharing |
| `hideShareAudioOption` | `boolean` | `false` | Hide "Share tab audio" checkbox |
| `disablePictureInPicture` | `boolean` | `false` | Disable PiP mode |
| `disableZoomLogo` | `boolean` | `false` | Remove Zoom logo (deprecated) |
| `defaultView` | `string` | `'speaker'` | `'gallery'`, `'speaker'`, `'multiSpeaker'` |

### Feature Toggles

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `isSupportAV` | `boolean` | `true` | Enable audio/video |
| `isSupportChat` | `boolean` | `true` | Enable in-meeting chat |
| `isSupportQA` | `boolean` | `true` | Enable webinar Q&A |
| `isSupportCC` | `boolean` | `true` | Enable closed captions |
| `isSupportPolling` | `boolean` | `true` | Enable polling |
| `isSupportBreakout` | `boolean` | `true` | Enable breakout rooms |
| `isSupportNonverbal` | `boolean` | `true` | Enable nonverbal feedback |
| `isSupportSimulive` | `boolean` | `false` | Enable Simulive |
| `disableVoIP` | `boolean` | `false` | Disable VoIP |
| `disableReport` | `boolean` | `false` | Disable report feature |

### Video Quality

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enableHD` | `boolean` | `true` (≥2.8.0) | Enable 720p video |
| `enableFullHD` | `boolean` | `false` | Enable 1080p for webinar attendees |

### Advanced

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `debug` | `boolean` | `false` | Enable debug logging |
| `patchJsMedia` | `boolean` | `false` | Auto-apply media fixes |
| `disableCORP` | `boolean` | `false` | Disable web isolation |
| `helper` | `string` | `''` | Path to helper.html |
| `externalLinkPage` | `string` | - | Page for external links |
| `webEndpoint` | `string` | - | For ZFG environments |
| `leaveOnPageUnload` | `boolean` | `false` | Auto cleanup on page close |
| `isShowJoiningErrorDialog` | `boolean` | `true` | Show error dialog on join failure |
| `meetingInfo` | `Array<string>` | `[...]` | Meeting info to display |
| `inviteUrlFormat` | `string` | `''` | Custom invite URL format |
| `loginWindow` | `object` | `{width: 400, height: 380}` | Login popup size |

### Callbacks

| Parameter | Type | Description |
|-----------|------|-------------|
| `success` | `Function` | Called on successful init |
| `error` | `Function` | Called on init failure |

## ZoomMtg.join() - All Options

### Required

| Parameter | Type | Description |
|-----------|------|-------------|
| `signature` | `string` | SDK JWT from backend (v5.0+: must include appKey prefix) |
| `meetingNumber` | `string \| number` | Meeting or webinar number |
| `userName` | `string` | Display name |
| `passWord` | `string` | Meeting password (capital W!) |

### Authentication

| Parameter | Type | When Required | Description |
|-----------|------|---------------|-------------|
| `zak` | `string` | Starting as host | Host's Zoom Access Key |
| `tk` | `string` | Registration required | Registrant token |
| `userEmail` | `string` | Webinars | User email |
| `obfToken` | `string` | March 2026+ | App Privilege Token |

### Optional

| Parameter | Type | Description |
|-----------|------|-------------|
| `customerKey` | `string` | Custom ID (max 36 chars) |
| `recordingToken` | `string` | Local recording permission |

### Callbacks

| Parameter | Type | Description |
|-----------|------|-------------|
| `success` | `Function` | Called on successful join |
| `error` | `Function` | Called on join failure |

## Event Listeners

### User Events

```javascript
ZoomMtg.inMeetingServiceListener('onUserJoin', (data) => {
  console.log('User joined:', data);
  // { userId, userName, ... }
});

ZoomMtg.inMeetingServiceListener('onUserLeave', (data) => {
  console.log('User left:', data);
  // Reason codes:
  // 0: OTHER
  // 1: HOST_ENDED_MEETING
  // 2: SELF_LEAVE_FROM_IN_MEETING
  // 3: SELF_LEAVE_FROM_WAITING_ROOM
  // 4: SELF_LEAVE_FROM_WAITING_FOR_HOST_START
  // 5: MEETING_TRANSFER
  // 6: KICK_OUT_FROM_MEETING
  // 7: KICK_OUT_FROM_WAITING_ROOM
  // 8: LEAVE_FROM_DISCLAIMER
});

ZoomMtg.inMeetingServiceListener('onUserUpdate', (data) => {
  console.log('User updated:', data);
});

ZoomMtg.inMeetingServiceListener('onUserIsInWaitingRoom', (data) => {
  console.log('User in waiting room:', data);
});
```

### Meeting Status

```javascript
ZoomMtg.inMeetingServiceListener('onMeetingStatus', (data) => {
  // status: 1=connecting, 2=connected, 3=disconnected, 4=reconnecting
  console.log('Status:', data.status);
});
```

### Audio/Video Events

```javascript
ZoomMtg.inMeetingServiceListener('onActiveSpeaker', (data) => {
  // [{userId, userName}]
  console.log('Active speaker:', data);
});

ZoomMtg.inMeetingServiceListener('onNetworkQualityChange', (data) => {
  // {level: 0-5, userId, type: 'uplink'}
  // 0-1=bad, 2=normal, 3-5=good
  console.log('Network quality:', data);
});

ZoomMtg.inMeetingServiceListener('onAudioQos', (data) => {
  console.log('Audio QoS:', data);
});

ZoomMtg.inMeetingServiceListener('onVideoQos', (data) => {
  console.log('Video QoS:', data);
});
```

### Chat & Communication

```javascript
ZoomMtg.inMeetingServiceListener('onReceiveChatMsg', (data) => {
  console.log('Chat message:', data);
});

ZoomMtg.inMeetingServiceListener('onReceiveTranscriptionMsg', (data) => {
  console.log('Transcription:', data);
});

ZoomMtg.inMeetingServiceListener('onReceiveTranslateMsg', (data) => {
  console.log('Translation:', data);
});
```

### Recording & Sharing

```javascript
ZoomMtg.inMeetingServiceListener('onRecordingChange', (data) => {
  console.log('Recording status:', data);
});

ZoomMtg.inMeetingServiceListener('onShareContentChange', (data) => {
  console.log('Share content:', data);
});

ZoomMtg.inMeetingServiceListener('receiveSharingChannelReady', (data) => {
  console.log('Sharing channel ready:', data);
});
```

### Breakout Rooms

```javascript
ZoomMtg.inMeetingServiceListener('onRoomStatusChange', (data) => {
  // status: 2=InProgress, 3=Closing, 4=Closed
  console.log('Breakout room status:', data);
});
```

### Other Events

```javascript
ZoomMtg.inMeetingServiceListener('onJoinSpeed', (data) => {
  console.log('Join metrics:', data);
});

ZoomMtg.inMeetingServiceListener('onVbStatusChange', (data) => {
  console.log('Virtual background status:', data);
});

ZoomMtg.inMeetingServiceListener('onFocusModeStatusChange', (data) => {
  console.log('Focus mode:', data);
});

ZoomMtg.inMeetingServiceListener('onPictureInPicture', (data) => {
  console.log('PiP status:', data);
});

ZoomMtg.inMeetingServiceListener('onClaimStatus', (data) => {
  console.log('Host claim status:', data);
});
```

## Common Methods

### Meeting Info

```javascript
// Get current user
ZoomMtg.getCurrentUser({
  success: (res) => console.log(res.result.currentUser)
});

// Get all attendees
ZoomMtg.getAttendeeslist({});

// Get meeting info
ZoomMtg.getCurrentMeetingInfo({
  success: (res) => console.log(res)
});

// Get SDK version
ZoomMtg.getWebSDKVersion({
  success: (version) => console.log(version)
});
```

### Audio/Video Control

```javascript
// Mute/unmute specific user
ZoomMtg.mute({ userId, mute: true });

// Mute/unmute all
ZoomMtg.muteAll({ muteAll: true });

// Stop incoming audio
ZoomMtg.stopIncomingAudio({ stop: true });

// Mirror video
ZoomMtg.mirrorVideo({ mirror: true });
```

### Chat

```javascript
// Send chat message
ZoomMtg.sendChat({
  message: 'Hello!',
  userId: 0  // 0 = everyone
});
```

### Meeting Control

```javascript
// Leave meeting
ZoomMtg.leaveMeeting({});

// End meeting (host only)
ZoomMtg.endMeeting({});

// Lock meeting
ZoomMtg.lockMeeting({ lock: true });
```

### Host Controls

```javascript
// Make host
ZoomMtg.makeHost({ userId });

// Make co-host
ZoomMtg.makeCoHost({ userId });

// Remove co-host
ZoomMtg.withdrawCoHost({ userId });

// Remove participant
ZoomMtg.expel({ userId });

// Put on hold
ZoomMtg.putOnHold({ userId, bHold: true });

// Claim host with host key
ZoomMtg.claimHostWithHostKey({ hostKey: '123456' });

// Reclaim host
ZoomMtg.reclaimHost({});

// Admit all from waiting room
ZoomMtg.admitAll({});
```

### Raise Hand

```javascript
// Raise hand
ZoomMtg.raiseHand({ userId });

// Lower hand
ZoomMtg.lowerHand({ oderId });

// Lower all hands
ZoomMtg.lowerAllHands({});
```

### Spotlight & Pin

```javascript
// Spotlight video
ZoomMtg.operateSpotlight({ oderId, action: 'add' }); // or 'remove'

// Pin video
ZoomMtg.operatePin({ oderId, action: 'add' }); // or 'remove'

// Allow multi-pin
ZoomMtg.allowMultiPin({ allow: true });
```

### Screen Share

```javascript
// Start screen share
ZoomMtg.startScreenShare({});

// Share specific source (Electron)
ZoomMtg.shareSource({ source });
```

### Recording

```javascript
// Start/stop recording
ZoomMtg.record({ record: true }); // or false

// Show/hide record button
ZoomMtg.showRecordFunction({ show: true });
```

### Breakout Rooms

```javascript
// Create breakout room
ZoomMtg.createBreakoutRoom({
  rooms: [{ name: 'Room 1' }, { name: 'Room 2' }]
});

// Open breakout rooms
ZoomMtg.openBreakoutRooms({});

// Close breakout rooms
ZoomMtg.closeBreakoutRooms({});

// Join breakout room
ZoomMtg.joinBreakoutRoom({ roomId });

// Leave breakout room
ZoomMtg.leaveBreakoutRoom({});

// Move user to breakout room
ZoomMtg.moveUserToBreakoutRoom({ oderId, roomId });

// Get breakout room status
ZoomMtg.getBreakoutRoomStatus({
  success: (res) => console.log(res)
});
```

### Virtual Background

```javascript
// Check support
ZoomMtg.isSupportVirtualBackground({
  success: (data) => console.log(data.result.isSupport)
});

// Set virtual background
ZoomMtg.setVirtualBackground({ imageUrl: '...' });

// Get VB status
ZoomMtg.getVirtualBackgroundStatus({
  success: (data) => console.log(data)
});

// Lock virtual background (host)
ZoomMtg.lockVirtualBackground({ lock: true });
```

### UI Control

```javascript
// Show/hide meeting header
ZoomMtg.showMeetingHeader({ show: true });

// Show/hide invite button
ZoomMtg.showInviteFunction({ show: true });

// Show/hide join audio button
ZoomMtg.showJoinAudioFunction({ show: true });

// Show/hide callout button
ZoomMtg.showCalloutFunction({ show: true });

// Re-render with new options
ZoomMtg.reRender({ lang: 'de-DE' });
```

### Language

```javascript
// Load language
ZoomMtg.i18n.load('de-DE');

// Reload language
ZoomMtg.i18n.reload('de-DE');

// Get current language
ZoomMtg.i18n.getCurrentLang();

// Get all translations
ZoomMtg.i18n.getAll();
```

## Rate Limits

| Method | Limit |
|--------|-------|
| `join()` | 10 seconds |
| `callOut()` | 10 seconds |
| `mute()` | 1 second |
| `muteAll()` | 5 seconds |

## DOM Elements

The SDK automatically adds these elements:
- `#zmmtg-root` - Main meeting container
- `#aria-notify-area` - Accessibility announcements

Do NOT manually create or remove these.

### SPA (React/Next) Overlay Gotcha

If you "join" but see a blank/black area or your app shell instead of the meeting UI, the Zoom UI can be rendering **behind** your app layout. Ensure `#zmmtg-root` occupies the viewport and is above other fixed elements:

```css
#zmmtg-root {
  position: fixed !important;
  inset: 0 !important;
  z-index: 9999 !important;
}
```

### Join Payload Sanitization Gotcha

If `ZoomMtg.join()` succeeds partially but the screen turns black and console shows errors like `Cannot read properties of undefined (reading 'toString')`, sanitize optional fields before calling join.

Do not pass optional keys with `undefined` values (`userEmail`, `tk`, `zak`, etc.). Build a payload and only attach those keys when they are non-empty strings.

Also prefer `defaultView: 'speaker'` during `ZoomMtg.init()` unless you have SharedArrayBuffer/gallery-view prerequisites fully configured.

## Resources

- [Main Web SDK Skill](../SKILL.md)
- [Reference Index](references/index.md)
- [Error Codes](../troubleshooting/error-codes.md)
- [Common Issues](../troubleshooting/common-issues.md)
- [SharedArrayBuffer Setup](../concepts/sharedarraybuffer.md)
- [Official API Reference](https://marketplacefront.zoom.us/sdk/meeting/web/index.html)

## Operations

- [RUNBOOK.md](RUNBOOK.md) - 5-minute preflight and debugging checklist.
