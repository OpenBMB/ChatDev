# Video Advanced Features: Level 3 Helpers

## Overview

The `IMeetingVideoController` provides three Level 3 sub-helpers for advanced video operations:

| Helper | Getter | Platform | Purpose |
|--------|--------|----------|---------|
| `IMeetingCameraHelper` | `GetMeetingCameraHelper(userid)` | Cross-platform | Remote PTZ camera control |
| `ISetVideoOrderHelper` | `GetSetVideoOrderHelper()` | Windows-only | Batch set video order in gallery |
| `ICameraController` | `GetMyCameraController()` | Windows-only | Control local camera device |

---

## Navigation Path

```
IMeetingService
  └─► GetMeetingVideoController()
        ├─► GetMeetingCameraHelper(userid)    // Remote camera PTZ control
        ├─► GetSetVideoOrderHelper()          // Gallery video order (Windows)
        └─► GetMyCameraController()           // Local camera device (Windows)
```

---

## 1. Remote Camera Control (IMeetingCameraHelper)

Control PTZ (Pan-Tilt-Zoom) cameras of remote participants who have granted permission.

### Get the Helper

```cpp
// Get video controller first
IMeetingVideoController* videoCtrl = meetingService->GetMeetingVideoController();
if (!videoCtrl) return;

// Get camera helper for specific user
unsigned int targetUserId = 12345;
IMeetingCameraHelper* cameraHelper = videoCtrl->GetMeetingCameraHelper(targetUserId);
if (!cameraHelper) {
    // User doesn't exist or doesn't have controllable camera
    return;
}
```

### Check Controllability

```cpp
// Check if we can control this user's camera
if (!cameraHelper->CanControlCamera()) {
    // Need to request control first
    SDKError err = cameraHelper->RequestControlRemoteCamera();
    if (err != SDKERR_SUCCESS) {
        // Request failed - user may not have PTZ camera
    }
    // Wait for callback to confirm permission granted
    return;
}
```

### Camera Movement Operations

```cpp
// All movement methods accept range 10-100 (default: 50)
// Higher = faster/larger movement

// Pan left/right
cameraHelper->TurnLeft(50);   // Pan left
cameraHelper->TurnRight(50);  // Pan right

// Tilt up/down
cameraHelper->TurnUp(50);     // Tilt up
cameraHelper->TurnDown(50);   // Tilt down

// Zoom in/out
cameraHelper->ZoomIn(50);     // Zoom in
cameraHelper->ZoomOut(50);    // Zoom out
```

### Release Control

```cpp
// When done controlling
cameraHelper->GiveUpControlRemoteCamera();
```

### Handle Camera Control Requests (Callback)

```cpp
class MyCameraEventHandler : public IMeetingVideoCtrlEvent {
public:
    void onCameraControlRequestReceived(
        unsigned int userId,
        CameraControlRequestType requestType,
        ICameraControlRequestHandler* pHandler) override
    {
        if (requestType == CameraControlRequestType_RequestControl) {
            // Someone wants to control our camera
            // Approve or decline
            pHandler->Approve();  // or pHandler->Decline();
        } else if (requestType == CameraControlRequestType_GiveUpControl) {
            // User released control of our camera
        }
    }

    void onCameraControlRequestResult(
        unsigned int userId,
        CameraControlRequestResult result) override
    {
        switch (result) {
            case CameraControlRequestResult_Approve:
                // Our request was approved - can now control camera
                break;
            case CameraControlRequestResult_Decline:
                // Our request was declined
                break;
            case CameraControlRequestResult_Revoke:
                // Our control was revoked
                break;
        }
    }

    // ... other callback implementations
};
```

---

## 2. Video Order Control (ISetVideoOrderHelper) - Windows Only

Batch-set the video order in gallery view. Useful for arranging participant videos in a specific layout.

### Get the Helper

```cpp
#if defined(WIN32)
IMeetingVideoController* videoCtrl = meetingService->GetMeetingVideoController();
if (!videoCtrl) return;

ISetVideoOrderHelper* orderHelper = videoCtrl->GetSetVideoOrderHelper();
if (!orderHelper) return;
#endif
```

### Set Video Order (Transaction Pattern)

```cpp
#if defined(WIN32)
// Step 1: Begin transaction (clears any previous prepared order)
SDKError err = orderHelper->SetVideoOrderTransactionBegin();
if (err != SDKERR_SUCCESS) return;

// Step 2: Add users to positions (0-based, max 49 positions)
// Position 0 = first slot in gallery
orderHelper->AddVideoToOrder(hostUserId, 0);      // Host at position 0
orderHelper->AddVideoToOrder(presenter1Id, 1);    // Presenter at position 1
orderHelper->AddVideoToOrder(presenter2Id, 2);    // Another presenter at position 2
// ... add more as needed

// Step 3: Commit the transaction
err = orderHelper->SetVideoOrderTransactionCommit();
if (err != SDKERR_SUCCESS) {
    // Commit failed
}
#endif
```

### Important Notes

- Maximum 49 users can be ordered
- If same position assigned to multiple users, only last one applies
- Must call `SetVideoOrderTransactionBegin()` before adding users
- Only host/co-host can set video order for all participants
- Use `EnableFollowHostVideoOrder()` to make participants follow host's order

### Follow Host Video Order

```cpp
// Check if feature is supported
if (videoCtrl->IsSupportFollowHostVideoOrder()) {
    // Enable following host's video order
    videoCtrl->EnableFollowHostVideoOrder(true);

    // Check if currently following
    bool isFollowing = videoCtrl->IsFollowHostVideoOrderOn();
}

// Get current video order list
IList<unsigned int>* orderList = videoCtrl->GetVideoOrderList();
if (orderList) {
    for (int i = 0; i < orderList->GetCount(); i++) {
        unsigned int userId = orderList->GetItem(i);
        // Process ordered user IDs
    }
}
```

---

## 3. Local Camera Control (ICameraController) - Windows Only

Control the local user's camera device settings.

### Get the Helper

```cpp
#if defined(WIN32)
IMeetingVideoController* videoCtrl = meetingService->GetMeetingVideoController();
if (!videoCtrl) return;

ICameraController* cameraCtrl = videoCtrl->GetMyCameraController();
if (!cameraCtrl) return;

// ICameraController provides device-level camera control
// (Interface details depend on SDK version - check headers)
#endif
```

---

## Video Order Callbacks

```cpp
class MyVideoEventHandler : public IMeetingVideoCtrlEvent {
public:
    void onHostVideoOrderUpdated(IList<unsigned int>* orderList) override {
        // Host changed the video order
        // Update UI to reflect new order
        if (orderList) {
            for (int i = 0; i < orderList->GetCount(); i++) {
                unsigned int userId = orderList->GetItem(i);
                // Reorder video tiles accordingly
            }
        }
    }

    void onLocalVideoOrderUpdated(IList<unsigned int>* localOrderList) override {
        // Local video order changed (user's personal arrangement)
    }

    void onFollowHostVideoOrderChanged(bool bFollow) override {
        // Following host video order setting changed
        if (bFollow) {
            // Now following host's order
        } else {
            // Using local order
        }
    }

    // ... other callback implementations
};
```

---

## Complete Example: Camera Control Flow

```cpp
class CameraControlManager : public IMeetingVideoCtrlEvent {
private:
    IMeetingVideoController* m_videoCtrl = nullptr;
    IMeetingCameraHelper* m_currentCameraHelper = nullptr;

public:
    void Initialize(IMeetingService* meetingService) {
        m_videoCtrl = meetingService->GetMeetingVideoController();
        if (m_videoCtrl) {
            m_videoCtrl->SetEvent(this);
        }
    }

    void RequestCameraControl(unsigned int targetUserId) {
        if (!m_videoCtrl) return;

        m_currentCameraHelper = m_videoCtrl->GetMeetingCameraHelper(targetUserId);
        if (!m_currentCameraHelper) {
            // User not found or no controllable camera
            return;
        }

        if (m_currentCameraHelper->CanControlCamera()) {
            // Already have control
            OnCameraControlGranted();
        } else {
            // Request control
            m_currentCameraHelper->RequestControlRemoteCamera();
        }
    }

    void OnCameraControlGranted() {
        // Now can control camera
        // Example: Center the camera
        m_currentCameraHelper->TurnLeft(30);
        m_currentCameraHelper->TurnUp(20);
    }

    void ReleaseCameraControl() {
        if (m_currentCameraHelper) {
            m_currentCameraHelper->GiveUpControlRemoteCamera();
            m_currentCameraHelper = nullptr;
        }
    }

    // IMeetingVideoCtrlEvent implementations
    void onCameraControlRequestResult(unsigned int userId,
                                      CameraControlRequestResult result) override {
        if (result == CameraControlRequestResult_Approve) {
            OnCameraControlGranted();
        } else {
            m_currentCameraHelper = nullptr;
        }
    }

    void onCameraControlRequestReceived(unsigned int userId,
                                        CameraControlRequestType requestType,
                                        ICameraControlRequestHandler* pHandler) override {
        // Auto-approve camera control requests
        if (requestType == CameraControlRequestType_RequestControl) {
            pHandler->Approve();
        }
    }

    // ... implement other required callbacks
    void onUserVideoStatusChange(unsigned int userId, VideoStatus status) override {}
    void onSpotlightedUserListChangeNotification(IList<unsigned int>* lst) override {}
    void onHostRequestStartVideo(IRequestStartVideoHandler* handler) override {}
    void onActiveSpeakerVideoUserChanged(unsigned int userid) override {}
    void onActiveVideoUserChanged(unsigned int userid) override {}
    void onHostVideoOrderUpdated(IList<unsigned int>* orderList) override {}
    void onLocalVideoOrderUpdated(IList<unsigned int>* localOrderList) override {}
    void onFollowHostVideoOrderChanged(bool bFollow) override {}
    void onUserVideoQualityChanged(VideoConnectionQuality quality, unsigned int userid) override {}
    void onVideoAlphaChannelStatusChanged(bool isAlphaModeOn) override {}
};
```

---

## Related Documentation

- [Singleton Hierarchy](../concepts/singleton-hierarchy.md) - Complete navigation map
- [SDK Architecture Pattern](../concepts/sdk-architecture-pattern.md) - Universal 3-step pattern
