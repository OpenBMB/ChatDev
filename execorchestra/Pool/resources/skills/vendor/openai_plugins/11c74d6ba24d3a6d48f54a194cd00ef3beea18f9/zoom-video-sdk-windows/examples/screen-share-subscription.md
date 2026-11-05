# Screen Share Subscription - Complete Guide

## Overview

Screen share subscription in the Zoom Video SDK is **fundamentally different** from video subscription. This guide explains why and provides complete working code for both Canvas API and Raw Data approaches.

## Why Screen Share is Different from Video

| Aspect | Video | Screen Share |
|--------|-------|--------------|
| **Streams per user** | One video stream | Multiple share streams possible (multi-share) |
| **Access method** | `user->GetVideoCanvas()` | `IZoomVideoSDKShareAction*` from callback |
| **Subscription timing** | `onUserVideoStatusChanged` | `onUserShareStatusChanged` |
| **Key object** | `IZoomVideoSDKUser*` | `IZoomVideoSDKShareAction*` |

**The critical difference**: A user can have multiple active share actions simultaneously (e.g., sharing screen + sharing a whiteboard). The `IZoomVideoSDKShareAction` object in the callback represents a specific share stream.

## The Wrong Way (Common Mistake)

```cpp
// WRONG - This won't work for remote screen shares!
IZoomVideoSDKUser* sharingUser = ...;
IZoomVideoSDKCanvas* shareCanvas = sharingUser->GetShareCanvas();
shareCanvas->subscribeWithView(hwnd, aspect);  // May fail or show nothing!
```

**Why it fails**: `GetShareCanvas()` on the user object doesn't give you access to the active share stream. You MUST use the `IZoomVideoSDKShareAction*` provided in the callback.

## The Correct Way

### Canvas API (Recommended)

The Canvas API lets the SDK render the shared screen directly to your window handle.

```cpp
class MyDelegate : public IZoomVideoSDKDelegate {
private:
    HWND shareWindow_;
    std::map<IZoomVideoSDKShareAction*, bool> activeShares_;

public:
    MyDelegate(HWND shareWnd) : shareWindow_(shareWnd) {}

    void onUserShareStatusChanged(
        IZoomVideoSDKShareHelper* pShareHelper,
        IZoomVideoSDKUser* pUser,
        IZoomVideoSDKShareAction* pShareAction) override
    {
        if (!pShareAction) return;

        ZoomVideoSDKShareStatus status = pShareAction->getShareStatus();
        ZoomVideoSDKShareType type = pShareAction->getShareType();

        // Get user name for logging
        const zchar_t* userName = pUser ? pUser->getUserName() : L"Unknown";

        switch (status) {
            case ZoomVideoSDKShareStatus_Start:
            case ZoomVideoSDKShareStatus_Resume:
                SubscribeToShare(pShareAction, userName);
                break;

            case ZoomVideoSDKShareStatus_Pause:
                // Share is paused - you may want to show a "Paused" overlay
                // The subscription remains active
                break;

            case ZoomVideoSDKShareStatus_Stop:
                UnsubscribeFromShare(pShareAction, userName);
                break;
        }
    }

private:
    void SubscribeToShare(IZoomVideoSDKShareAction* pShareAction,
                          const zchar_t* userName)
    {
        // Prevent duplicate subscriptions
        if (activeShares_.find(pShareAction) != activeShares_.end()) {
            return;
        }

        // Get the share canvas from the ShareAction (NOT from the user!)
        IZoomVideoSDKCanvas* shareCanvas = pShareAction->getShareCanvas();
        if (!shareCanvas) {
            // Error: Share canvas not available
            return;
        }

        // Subscribe with Canvas API
        ZoomVideoSDKErrors ret = shareCanvas->subscribeWithView(
            shareWindow_,
            ZoomVideoSDKVideoAspect_Original  // Show full content, letterbox if needed
        );

        if (ret == ZoomVideoSDKErrors_Success) {
            activeShares_[pShareAction] = true;
            // Successfully subscribed to share from [userName]
        } else {
            // Failed to subscribe: error code [ret]
        }
    }

    void UnsubscribeFromShare(IZoomVideoSDKShareAction* pShareAction,
                              const zchar_t* userName)
    {
        auto it = activeShares_.find(pShareAction);
        if (it == activeShares_.end()) {
            return;  // Not subscribed
        }

        IZoomVideoSDKCanvas* shareCanvas = pShareAction->getShareCanvas();
        if (shareCanvas) {
            shareCanvas->unSubscribeWithView(shareWindow_);
        }

        activeShares_.erase(it);
        // Unsubscribed from share
    }
};
```

### Raw Data Pipe (Advanced)

Use Raw Data when you need to process the shared screen frames yourself (recording, effects, computer vision).

```cpp
class ShareRawDataDelegate : public IZoomVideoSDKRawDataPipeDelegate {
private:
    std::function<void(YUVRawDataI420*)> frameCallback_;

public:
    ShareRawDataDelegate(std::function<void(YUVRawDataI420*)> callback)
        : frameCallback_(callback) {}

    void onRawDataFrameReceived(YUVRawDataI420* data) override {
        if (!data) return;

        int width = data->GetStreamWidth();
        int height = data->GetStreamHeight();

        // Share frames can be large (1080p, 4K)
        // Process efficiently or queue for async processing

        if (frameCallback_) {
            frameCallback_(data);
        }
    }

    void onRawDataStatusChanged(RawDataStatus status) override {
        switch (status) {
            case RawData_On:
                // Share raw data stream started
                break;
            case RawData_Off:
                // Share raw data stream stopped
                break;
        }
    }
};

class MyDelegate : public IZoomVideoSDKDelegate {
private:
    std::map<IZoomVideoSDKShareAction*, ShareRawDataDelegate*> shareDataDelegates_;

public:
    void onUserShareStatusChanged(
        IZoomVideoSDKShareHelper* pShareHelper,
        IZoomVideoSDKUser* pUser,
        IZoomVideoSDKShareAction* pShareAction) override
    {
        if (!pShareAction) return;

        ZoomVideoSDKShareStatus status = pShareAction->getShareStatus();

        if (status == ZoomVideoSDKShareStatus_Start ||
            status == ZoomVideoSDKShareStatus_Resume)
        {
            SubscribeToShareRawData(pShareAction);
        }
        else if (status == ZoomVideoSDKShareStatus_Stop)
        {
            UnsubscribeFromShareRawData(pShareAction);
        }
    }

private:
    void SubscribeToShareRawData(IZoomVideoSDKShareAction* pShareAction) {
        if (shareDataDelegates_.find(pShareAction) != shareDataDelegates_.end()) {
            return;  // Already subscribed
        }

        // Get the raw data pipe from ShareAction
        IZoomVideoSDKRawDataPipe* sharePipe = pShareAction->getSharePipe();
        if (!sharePipe) {
            return;
        }

        // Create delegate to receive frames
        auto* delegate = new ShareRawDataDelegate([](YUVRawDataI420* frame) {
            // Process share frame here
            // Example: save to file, apply effects, send to encoder
            ProcessShareFrame(frame);
        });

        // Subscribe with desired resolution
        ZoomVideoSDKErrors ret = sharePipe->subscribe(
            ZoomVideoSDKResolution_1080P,  // Request high quality for screen share
            delegate
        );

        if (ret == ZoomVideoSDKErrors_Success) {
            shareDataDelegates_[pShareAction] = delegate;
        } else {
            delete delegate;
        }
    }

    void UnsubscribeFromShareRawData(IZoomVideoSDKShareAction* pShareAction) {
        auto it = shareDataDelegates_.find(pShareAction);
        if (it == shareDataDelegates_.end()) {
            return;
        }

        IZoomVideoSDKRawDataPipe* sharePipe = pShareAction->getSharePipe();
        if (sharePipe) {
            sharePipe->unSubscribe(it->second);
        }

        delete it->second;
        shareDataDelegates_.erase(it);
    }

    static void ProcessShareFrame(YUVRawDataI420* frame) {
        // Your frame processing logic
        // Note: This runs on SDK thread - don't block!
    }
};
```

## Complete Working Example

Here's a complete example showing screen share subscription with proper lifecycle management:

```cpp
#include <windows.h>
#include <map>
#include "zoom_video_sdk_api.h"
#include "zoom_video_sdk_interface.h"
#include "zoom_video_sdk_delegate_interface.h"

USING_ZOOM_VIDEO_SDK_NAMESPACE

class ScreenShareManager : public IZoomVideoSDKDelegate {
private:
    IZoomVideoSDK* sdk_;
    HWND mainShareWindow_;

    // Track active share subscriptions
    struct ShareSubscription {
        IZoomVideoSDKShareAction* action;
        IZoomVideoSDKUser* user;
        ZoomVideoSDKShareType type;
        bool isSubscribed;
    };
    std::vector<ShareSubscription> activeSubscriptions_;

public:
    ScreenShareManager(IZoomVideoSDK* sdk, HWND shareWindow)
        : sdk_(sdk), mainShareWindow_(shareWindow) {}

    // ==========================================
    // IZoomVideoSDKDelegate - Share Events
    // ==========================================

    void onUserShareStatusChanged(
        IZoomVideoSDKShareHelper* pShareHelper,
        IZoomVideoSDKUser* pUser,
        IZoomVideoSDKShareAction* pShareAction) override
    {
        if (!pShareAction || !pUser) return;

        ZoomVideoSDKShareStatus status = pShareAction->getShareStatus();
        ZoomVideoSDKShareType type = pShareAction->getShareType();
        const zchar_t* userName = pUser->getUserName();

        // Check if this is our own share
        IZoomVideoSDKSession* session = sdk_->getSessionInfo();
        IZoomVideoSDKUser* myself = session ? session->getMyself() : nullptr;
        bool isMyShare = (pUser == myself);

        switch (status) {
            case ZoomVideoSDKShareStatus_Start:
                HandleShareStart(pShareAction, pUser, type, isMyShare);
                break;

            case ZoomVideoSDKShareStatus_Resume:
                HandleShareResume(pShareAction, pUser);
                break;

            case ZoomVideoSDKShareStatus_Pause:
                HandleSharePause(pShareAction, pUser);
                break;

            case ZoomVideoSDKShareStatus_Stop:
                HandleShareStop(pShareAction, pUser);
                break;
        }
    }

private:
    void HandleShareStart(IZoomVideoSDKShareAction* action,
                          IZoomVideoSDKUser* user,
                          ZoomVideoSDKShareType type,
                          bool isMyShare)
    {
        // Don't subscribe to our own share (we're sending it)
        if (isMyShare) {
            return;
        }

        // Get share canvas from the action
        IZoomVideoSDKCanvas* shareCanvas = action->getShareCanvas();
        if (!shareCanvas) {
            return;
        }

        // Choose aspect based on share type
        ZoomVideoSDKVideoAspect aspect = ZoomVideoSDKVideoAspect_Original;
        if (type == ZoomVideoSDKShareType_Camera) {
            // Camera share might benefit from pan-and-scan
            aspect = ZoomVideoSDKVideoAspect_PanAndScan;
        }

        // Subscribe to the share
        ZoomVideoSDKErrors ret = shareCanvas->subscribeWithView(
            mainShareWindow_,
            aspect
        );

        if (ret == ZoomVideoSDKErrors_Success) {
            ShareSubscription sub = {action, user, type, true};
            activeSubscriptions_.push_back(sub);
        }
    }

    void HandleShareResume(IZoomVideoSDKShareAction* action,
                           IZoomVideoSDKUser* user)
    {
        // Check if we need to re-subscribe
        auto* sub = FindSubscription(action);
        if (sub && !sub->isSubscribed) {
            IZoomVideoSDKCanvas* canvas = action->getShareCanvas();
            if (canvas) {
                canvas->subscribeWithView(mainShareWindow_,
                    ZoomVideoSDKVideoAspect_Original);
                sub->isSubscribed = true;
            }
        }
    }

    void HandleSharePause(IZoomVideoSDKShareAction* action,
                          IZoomVideoSDKUser* user)
    {
        // Optionally show a "Share Paused" UI overlay
        // The canvas subscription remains active
        auto* sub = FindSubscription(action);
        if (sub) {
            // You could trigger UI update here
        }
    }

    void HandleShareStop(IZoomVideoSDKShareAction* action,
                         IZoomVideoSDKUser* user)
    {
        auto* sub = FindSubscription(action);
        if (!sub) return;

        // Unsubscribe from canvas
        IZoomVideoSDKCanvas* canvas = action->getShareCanvas();
        if (canvas && sub->isSubscribed) {
            canvas->unSubscribeWithView(mainShareWindow_);
        }

        // Remove from tracking
        RemoveSubscription(action);

        // Clear the share window or show placeholder
        InvalidateRect(mainShareWindow_, NULL, TRUE);
    }

    ShareSubscription* FindSubscription(IZoomVideoSDKShareAction* action) {
        for (auto& sub : activeSubscriptions_) {
            if (sub.action == action) {
                return &sub;
            }
        }
        return nullptr;
    }

    void RemoveSubscription(IZoomVideoSDKShareAction* action) {
        activeSubscriptions_.erase(
            std::remove_if(activeSubscriptions_.begin(),
                           activeSubscriptions_.end(),
                           [action](const ShareSubscription& s) {
                               return s.action == action;
                           }),
            activeSubscriptions_.end()
        );
    }

public:
    // Cleanup all subscriptions (call on session leave)
    void CleanupAllShares() {
        for (auto& sub : activeSubscriptions_) {
            if (sub.isSubscribed && sub.action) {
                IZoomVideoSDKCanvas* canvas = sub.action->getShareCanvas();
                if (canvas) {
                    canvas->unSubscribeWithView(mainShareWindow_);
                }
            }
        }
        activeSubscriptions_.clear();
    }

    // ==========================================
    // Implement remaining IZoomVideoSDKDelegate methods as empty
    // (required but not shown for brevity)
    // ==========================================
    void onSessionJoin() override {}
    void onSessionLeave() override { CleanupAllShares(); }
    void onError(ZoomVideoSDKErrors errorCode) override {}
    void onUserJoin(IZoomVideoSDKUserHelper*, IVideoSDKVector<IZoomVideoSDKUser*>*) override {}
    void onUserLeave(IZoomVideoSDKUserHelper*, IVideoSDKVector<IZoomVideoSDKUser*>*) override {}
    void onUserVideoStatusChanged(IZoomVideoSDKVideoHelper*, IVideoSDKVector<IZoomVideoSDKUser*>*) override {}
    void onUserAudioStatusChanged(IZoomVideoSDKAudioHelper*, IVideoSDKVector<IZoomVideoSDKUser*>*) override {}
    // ... implement all other required callbacks as empty
};
```

## Share Types

The `IZoomVideoSDKShareAction::getShareType()` returns:

| Type | Description |
|------|-------------|
| `ZoomVideoSDKShareType_Normal` | Desktop/window share |
| `ZoomVideoSDKShareType_Camera` | Camera share (second camera) |

## Share Status Flow

```
User starts sharing
       │
       ▼
onUserShareStatusChanged (status = Start)
       │
       ├──► Subscribe to share canvas
       │
       ▼
[Share is active and visible]
       │
       ├──► User pauses share
       │         │
       │         ▼
       │    onUserShareStatusChanged (status = Pause)
       │         │
       │         ├──► Show "paused" UI (optional)
       │         │
       │         ▼
       │    [Share paused]
       │         │
       │         ├──► User resumes share
       │         │         │
       │         │         ▼
       │         │    onUserShareStatusChanged (status = Resume)
       │         │         │
       │         │         └──► Re-subscribe if needed
       │         │
       ▼         ▼
[Share continues...]
       │
       ▼
User stops sharing
       │
       ▼
onUserShareStatusChanged (status = Stop)
       │
       ├──► Unsubscribe from canvas
       ├──► Clear share window
       └──► Remove from tracking
```

## Best Practices

### 1. Always Use ShareAction from Callback

```cpp
// CORRECT
void onUserShareStatusChanged(..., IZoomVideoSDKShareAction* pShareAction) {
    pShareAction->getShareCanvas()->subscribeWithView(...);
}

// WRONG
user->GetShareCanvas()->subscribeWithView(...);
```

### 2. Track Subscriptions for Cleanup

```cpp
std::map<IZoomVideoSDKShareAction*, bool> subscribedShares_;

// Subscribe
subscribedShares_[pShareAction] = true;

// On session leave - cleanup all
for (auto& pair : subscribedShares_) {
    // Unsubscribe each
}
```

### 3. Don't Subscribe to Your Own Share

```cpp
IZoomVideoSDKUser* myself = session->getMyself();
if (pUser == myself) {
    return;  // Don't subscribe to our own share
}
```

### 4. Handle All Share Statuses

```cpp
switch (status) {
    case ZoomVideoSDKShareStatus_Start:   // New share started
    case ZoomVideoSDKShareStatus_Resume:  // Paused share resumed
    case ZoomVideoSDKShareStatus_Pause:   // Share temporarily paused
    case ZoomVideoSDKShareStatus_Stop:    // Share ended
}
```

### 5. Use Appropriate Aspect Ratio

```cpp
// For screen share - show all content
ZoomVideoSDKVideoAspect_Original  // Letterbox, no crop

// For camera share - fill window
ZoomVideoSDKVideoAspect_PanAndScan  // May crop edges
```

## Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Share not visible | Using `user->GetShareCanvas()` | Use `pShareAction->getShareCanvas()` from callback |
| Multiple shares not handled | Not tracking by ShareAction | Use map keyed by `IZoomVideoSDKShareAction*` |
| Share doesn't update | Not handling Resume status | Subscribe on both Start and Resume |
| Crash on session leave | Not unsubscribing | Call `unSubscribeWithView` before cleanup |
| Can see own share | Not filtering self | Check `pUser == session->getMyself()` |

## Related Documentation

- **[Video Rendering](video-rendering.md)** - Video subscription (different pattern)
- **[SDK Architecture Pattern](../concepts/sdk-architecture-pattern.md)** - Universal pattern
- **[Singleton Hierarchy](../concepts/singleton-hierarchy.md)** - SDK navigation
- **[Delegate Methods](../references/delegate-methods.md)** - All callback methods

---

**Key Takeaway**: Always get the share canvas from `IZoomVideoSDKShareAction*` in the callback, never from the user object directly.
