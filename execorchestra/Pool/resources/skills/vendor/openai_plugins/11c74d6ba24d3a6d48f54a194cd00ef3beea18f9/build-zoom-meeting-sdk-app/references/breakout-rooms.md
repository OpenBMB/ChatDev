# Breakout Rooms

Programmatically manage breakout rooms in Zoom meetings across all platforms.

## Overview

Breakout rooms allow hosts to split meeting participants into smaller groups. This guide covers SDK APIs for creating, managing, and controlling breakout rooms.

## Platform Support

| Platform | Support Level | Notes |
|----------|---------------|-------|
| **Web SDK** | Full | Complete API |
| **iOS SDK** | Full | Creator + Admin helpers |
| **Android SDK** | Full | Creator + Admin helpers |
| **Windows SDK** | Full | Controller interface |
| **macOS SDK** | Full | Controller interface |
| **Linux SDK** | Limited | Basic functionality only |
| **Video SDK** | Different | Uses "Subsessions" - not native breakout rooms |

**Important:** Video SDK does NOT have native breakout rooms. It uses a "Subsessions" concept requiring manual session management.

## REST API: Pre-assigned Rooms

Create meetings with pre-assigned breakout rooms:

```bash
POST /v2/users/{userId}/meetings
```

```json
{
  "topic": "Team Workshop",
  "type": 2,
  "settings": {
    "breakout_room": {
      "enable": true,
      "rooms": [
        {
          "name": "Team Alpha",
          "participants": ["user1@example.com", "user2@example.com"]
        },
        {
          "name": "Team Beta",
          "participants": ["user3@example.com", "user4@example.com"]
        }
      ]
    }
  }
}
```

**Limitation:** Pre-assigned rooms are NOT auto-opened. The host must manually open breakout rooms when the meeting starts. There is NO REST API to auto-open rooms.

---

## Web SDK Implementation

### Create Breakout Rooms

```javascript
// Create 5 rooms with auto-generated names (Room 1, Room 2, etc.)
ZoomMtg.BreakoutRoom.createBreakoutRoom({
  data: 5,
  success: (response) => console.log('Rooms created:', response),
  error: (error) => console.error('Error:', error)
});

// Create named rooms
ZoomMtg.BreakoutRoom.createBreakoutRoom({
  data: [
    { name: 'Engineering' },
    { name: 'Design' },
    { name: 'Product' }
  ],
  success: (response) => console.log('Rooms created:', response),
  error: (error) => console.error('Error:', error)
});
```

### Get Breakout Rooms

```javascript
ZoomMtg.BreakoutRoom.getBreakoutRooms({
  success: (response) => {
    const rooms = response.result.rooms;
    rooms.forEach(room => {
      console.log(`Room ID: ${room.boId}, Name: ${room.name}`);
    });
  },
  error: (error) => console.error('Error:', error)
});
```

### Assign Participants

```javascript
// Get unassigned attendees first
ZoomMtg.BreakoutRoom.getUnassignedAttendeeList({
  success: (response) => {
    const unassigned = response.result.unassignedAttendeeList;
    console.log('Unassigned:', unassigned);
  }
});

// Assign user to a room
ZoomMtg.BreakoutRoom.assignUserToBreakoutRoom({
  targetRoomId: 'room-id-here',
  userId: 12345678,
  success: (response) => console.log('Assigned:', response),
  error: (error) => console.error('Error:', error)
});
```

### Move Participants Between Rooms

```javascript
ZoomMtg.BreakoutRoom.moveUserToBreakoutRoom({
  targetRoomId: 'destination-room-id',
  userId: 12345678,
  success: (response) => console.log('Moved:', response),
  error: (error) => console.error('Error:', error)
});
```

### Open Breakout Rooms

```javascript
ZoomMtg.BreakoutRoom.openBreakoutRooms({
  options: {
    isAutoJoinRoom: false,              // Let participants choose
    isBackToMainSessionEnabled: true,   // Allow returning to main
    isTimerEnabled: true,               // Enable countdown
    timerDuration: 1800,                // 30 minutes (seconds)
    needCountDown: true,                // Show countdown
    waitSeconds: 60                     // Wait before auto-join
  },
  success: (response) => console.log('Rooms opened:', response),
  error: (error) => console.error('Error:', error)
});
```

### Close Breakout Rooms

```javascript
ZoomMtg.BreakoutRoom.closeBreakoutRooms({
  success: (response) => console.log('Rooms closed:', response),
  error: (error) => console.error('Error:', error)
});
```

### Broadcast Message

```javascript
ZoomMtg.BreakoutRoom.broadcast({
  message: 'Please return to the main room in 2 minutes',
  success: (response) => console.log('Broadcast sent:', response),
  error: (error) => console.error('Error:', error)
});
```

### Check User Status

```javascript
// Get current user's breakout room
ZoomMtg.BreakoutRoom.getCurrentBreakoutRoom({
  success: (response) => {
    const { roomId, name, attendeeStatus } = response.result;
    console.log(`Current room: ${name}, Status: ${attendeeStatus}`);
  }
});

// attendeeStatus values:
// 1: UNASSIGNED - Not assigned to any room
// 2: ASSIGNED_NOT_JOIN - Assigned but hasn't joined yet
// 3: IN_BO - Currently in breakout room
```

---

## iOS SDK Implementation

### Get Helpers

```objc
#import <MobileRTC/MobileRTC.h>

// Get meeting service
MobileRTCMeetingService *meetingService = [[MobileRTC sharedRTC] getMeetingService];

// Get breakout room creator (for creating rooms)
MobileRTCBOCreator *boCreator = [meetingService getCreatorHelper];

// Get breakout room admin (for managing rooms)
MobileRTCBOAdmin *boAdmin = [meetingService getAdminHelper];
```

### Create Rooms

```objc
// Create 3 breakout rooms
[boCreator createBreakoutRoom:3 completion:^(NSError *error) {
    if (error) {
        NSLog(@"Error: %@", error.localizedDescription);
    } else {
        NSLog(@"Rooms created");
    }
}];

// Create room with specific name
[boCreator createBreakoutRoomWithName:@"Engineering" completion:^(NSError *error) {
    // Handle result
}];
```

### Manage Rooms

```objc
// Open all rooms
[boAdmin openAllRoomsCompletion:^(NSError *error) {
    if (!error) {
        NSLog(@"Rooms opened");
    }
}];

// Assign user to room
[boAdmin assignUser:userId toRoom:roomId completion:^(NSError *error) {
    if (!error) {
        NSLog(@"User assigned");
    }
}];

// Close all rooms
[boAdmin closeAllRoomsCompletion:^(NSError *error) {
    if (!error) {
        NSLog(@"Rooms closed");
    }
}];
```

### Event Handling

```objc
@interface MyDelegate : NSObject <MobileRTCMeetingServiceDelegate>
@end

@implementation MyDelegate

- (void)onMeetingBreakoutRoomStatusChanged:(MobileRTCBreakoutRoomStatus)status {
    switch (status) {
        case MobileRTCBreakoutRoomStatusNotStarted:
            NSLog(@"Breakout rooms not started");
            break;
        case MobileRTCBreakoutRoomStatusStarted:
            NSLog(@"Breakout rooms started");
            break;
        case MobileRTCBreakoutRoomStatusClosed:
            NSLog(@"Breakout rooms closed");
            break;
    }
}

@end
```

---

## Android SDK Implementation

### Get Helpers

```kotlin
import us.zoom.sdk.ZoomSDK

val zoomSDK = ZoomSDK.getInstance()
val meetingService = zoomSDK.meetingService
val boController = meetingService?.inMeetingBreakoutRoomController

// Get creator (for creating rooms)
val creator = boController?.getCreatorHelper()

// Get admin (for managing rooms)
val admin = boController?.getAdminHelper()
```

### Create Rooms

```kotlin
// Create breakout rooms
val error = creator?.createBreakoutRoom(5)  // Create 5 rooms
if (error == SDKError.SDKERR_SUCCESS) {
    Log.d("Breakout", "Rooms created")
}

// Create room with name
creator?.createBreakoutRoomWithName("Engineering")
```

### Manage Rooms

```kotlin
// Open all rooms
admin?.openAllRooms()

// Assign user to room
admin?.assignUser(userId, roomId)

// Move user between rooms
admin?.assignUser(userId, newRoomId)  // Removes from old room

// Broadcast message
admin?.broadcastToAll("Please return in 2 minutes")

// Close all rooms
admin?.closeAllRooms()
```

---

## Windows/macOS SDK Implementation

### Windows (C++)

```cpp
#include "meeting_breakout_rooms_interface.h"

class MyBreakoutRoomsEvent : public IMeetingBreakoutRoomsEvent {
public:
    void OnBreakoutRoomsStartedNotification(const wchar_t* stBID) override {
        // Handle breakout rooms started
        wprintf(L"Breakout rooms started: %s\n", stBID);
    }
};

// Get controller
IMeetingBreakoutRoomsController* pController =
    pMeetingService->GetBreakoutRoomsController(nullptr);

// Set event handler
pController->SetEvent(new MyBreakoutRoomsEvent());

// Get list of rooms
IList<IBreakoutRoomsInfo*>* pRoomList = pController->GetBreakoutRoomsInfoList();
for (int i = 0; i < pRoomList->GetItemCount(); ++i) {
    IBreakoutRoomsInfo* pRoom = pRoomList->GetItem(i);
    wprintf(L"Room: %s (ID: %s)\n",
            pRoom->GetBreakoutRoomName(),
            pRoom->GetBID());
}

// Join a breakout room
pController->JoinBreakoutRoom(L"room-id");

// Leave breakout room
pController->LeaveBreakoutRoom();
```

### macOS (Objective-C)

```objc
#import <ZoomSDK/ZoomSDK.h>

// Get controller
ZoomSDKBreakoutRoomsController *boController =
    [[ZoomSDK sharedSDK] getMeetingService] getBreakoutRoomsController];

// Join breakout room
[boController requestJoinBreakoutRoom:@"room-id"];

// Leave breakout room
[boController requestLeaveBreakoutRoom];

// Close all rooms (host only)
[boController requestCloseAllBreakoutRooms];
```

---

## Permissions

### Host/Co-Host Restrictions

| Action | Host | Co-Host | Participant |
|--------|------|---------|-------------|
| Create breakout rooms | ✅ | ✅ | ❌ |
| Open breakout rooms | ✅ | ✅ | ❌ |
| Close breakout rooms | ✅ | ✅ | ❌ |
| Assign participants | ✅ | ✅ | ❌ |
| Move participants | ✅ | ❌ | ❌ |
| Broadcast messages | ✅ | ✅ | ❌ |
| Join any room | ✅ | ✅* | ❌ |

*Co-hosts can only join rooms assigned by host.

---

## Limitations

### Capacity Limits

| Account Type | Max Rooms | Max Participants |
|--------------|-----------|------------------|
| Standard | 50 rooms | 500 total |
| Large Meeting Add-on | 100 rooms | 1,000 total |

### Recording Limitations

- **Cloud Recording**: Only records the **main session**
- **Local Recording**: Records only the room the recorder is in
- **Host cannot record** breakout rooms they're not in

### Cannot Auto-Open Pre-Assigned Rooms

**Critical:** There is NO API to auto-open pre-assigned breakout rooms. The host MUST manually open rooms when the meeting starts.

### Session Timeout

If no participant remains in the main session during breakout rooms, the main session may close after timeout. Ensure at least one participant (host or bot) stays in main session.

---

## Best Practices

### 1. Check Support Before Creating

```javascript
ZoomMtg.BreakoutRoom.getBreakoutRoomOptions({
  success: (response) => {
    if (response.result.isSupportBreakoutRoom) {
      // Proceed to create rooms
    }
  }
});
```

### 2. Handle User Status

```javascript
// Check before assigning
ZoomMtg.BreakoutRoom.getUserStatus({
  userId: userId,
  success: (response) => {
    const { attendeeStatus } = response.result;
    if (attendeeStatus === 3) {  // IN_BO
      // User already in a room - move instead of assign
    }
  }
});
```

### 3. Error Handling

```javascript
function handleBreakoutError(error) {
  switch (error.method) {
    case 'createBreakoutRoom':
      if (error.errorMessage.includes('not support')) {
        alert('Breakout rooms not enabled for this meeting');
      }
      break;
    case 'assignUserToBreakoutRoom':
      if (error.errorMessage.includes('not host')) {
        alert('Only host/co-host can assign participants');
      }
      break;
  }
}
```

---

## Video SDK Note

Video SDK does **NOT** have native breakout rooms. Instead, use "Subsessions":

1. Create separate Video SDK sessions
2. Move participants between sessions programmatically
3. Implement your own room management logic

See: https://developers.zoom.us/blog/build-breakout-rooms-for-video-sdk/

---

## Resources

- **Web SDK Docs**: https://developers.zoom.us/docs/meeting-sdk/web/
- **iOS SDK Docs**: https://developers.zoom.us/docs/meeting-sdk/ios/
- **Android SDK Docs**: https://developers.zoom.us/docs/meeting-sdk/android/
- **REST API - Meetings**: https://developers.zoom.us/docs/api/rest/reference/zoom-api/methods/#tag/Meetings
- **Developer Forum**: https://devforum.zoom.us/
