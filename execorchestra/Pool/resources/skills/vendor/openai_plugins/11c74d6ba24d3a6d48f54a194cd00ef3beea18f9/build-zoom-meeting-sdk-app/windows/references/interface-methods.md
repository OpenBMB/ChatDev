# Virtual Method Implementation Guide

## Overview

The Zoom SDK requires implementing ALL pure virtual methods from interface classes, even platform-specific ones. Missing even a single method results in abstract class errors at compile time.

This guide shows how to find required methods and implement them correctly.

---

## Critical Rules

1. **Implement ALL pure virtual methods** - No exceptions
2. **Include WIN32-conditional methods** - They're required even though they're in `#if defined(WIN32)` blocks
3. **SDK version matters** - Different versions have different required methods
4. **Use exact signatures** - Parameter names can differ, but types and order must match exactly

---

## How to Find Required Methods

### Method 1: Grep the SDK Headers

```bash
# Find all pure virtual methods (ending with = 0)
grep "= 0" SDK/x64/h/*.h

# Find methods in specific interface
grep "= 0" SDK/x64/h/auth_service_interface.h
grep "= 0" SDK/x64/h/meeting_service_interface.h
```

### Method 2: Read Compiler Errors

When you forget to implement a method, the compiler tells you:

```
error C2259: 'AuthServiceEventListener': cannot instantiate abstract class
note: see declaration of 'AuthServiceEventListener'
note: due to following members:
'void IAuthServiceEvent::onNotificationServiceStatus(SDKNotificationServiceStatus,SDKNotificationServiceError)':
  is abstract at auth_service_interface.h(256)
```

This tells you:
- **Method name**: `onNotificationServiceStatus`
- **Parameters**: `SDKNotificationServiceStatus status, SDKNotificationServiceError error`
- **Location**: Line 256 in `auth_service_interface.h`

### Method 3: Read the Header Files Manually

Open the interface header and look for methods marked with `= 0`:

```cpp
class IAuthServiceEvent {
public:
    virtual ~IAuthServiceEvent() {}
    virtual void onAuthenticationReturn(AuthResult ret) = 0;  // <-- REQUIRED (= 0)
    virtual void onLogout() = 0;  // <-- REQUIRED (= 0)
};
```

---

## Complete Method Lists

### IAuthServiceEvent (6 methods required)

**File**: `SDK/x64/h/auth_service_interface.h` (lines 217-258)

```cpp
class AuthServiceEventListener : public IAuthServiceEvent {
public:
    // Method 1: Authentication result (JWT token validation)
    void onAuthenticationReturn(AuthResult ret) override;

    // Method 2: Login result with fail reason (for user login, not JWT)
    void onLoginReturnWithReason(LOGINSTATUS ret, IAccountInfo* pAccountInfo, LoginFailReason reason) override;

    // Method 3: Logout notification
    void onLogout() override;

    // Method 4: Zoom identity expired (need to regenerate token)
    void onZoomIdentityExpired() override;

    // Method 5: Zoom auth identity expiring soon (10 minutes warning)
    void onZoomAuthIdentityExpired() override;

    // Method 6: WIN32 ONLY - Notification service status
#if defined(WIN32)
    void onNotificationServiceStatus(SDKNotificationServiceStatus status, SDKNotificationServiceError error) override;
#endif
};
```

**Important notes**:
- Methods 1-5 are cross-platform
- Method 6 is Windows-only but **MUST** be implemented on Windows
- For JWT auth, only `onAuthenticationReturn` fires; others are for user login

---

### IMeetingServiceEvent (9 methods required)

**File**: `SDK/x64/h/meeting_service_interface.h` (lines 830-897)

```cpp
class MeetingServiceEventListener : public IMeetingServiceEvent {
public:
    // Method 1: Meeting status changed (joined, ended, failed, etc.)
    void onMeetingStatusChanged(MeetingStatus status, int iResult) override;

    // Method 2: Meeting statistics warning (network issues, etc.)
    void onMeetingStatisticsWarningNotification(StatisticsWarningType type) override;

    // Method 3: Meeting parameters (right before meeting starts)
    void onMeetingParameterNotification(const MeetingParameter* meeting_param) override;

    // Method 4: Participants activities suspended
    void onSuspendParticipantsActivities() override;

    // Method 5: AI Companion status changed
    void onAICompanionActiveChangeNotice(bool bActive) override;

    // Method 6: Meeting topic changed
    void onMeetingTopicChanged(const zchar_t* sTopic) override;

    // Method 7: Meeting at capacity, provides livestream URL
    void onMeetingFullToWatchLiveStream(const zchar_t* sLiveStreamUrl) override;

    // Method 8: User network quality changed
    void onUserNetworkStatusChanged(MeetingComponentType type, ConnectionQuality level, unsigned int userId, bool uplink) override;

    // Method 9: WIN32 ONLY - App signal panel updated
#if defined(WIN32)
    void onAppSignalPanelUpdated(IMeetingAppSignalHandler* pHandler) override;
#endif
};
```

**Important notes**:
- Methods 1-8 are cross-platform
- Method 9 is Windows-only but **MUST** be implemented on Windows
- Most apps only care about method 1 (`onMeetingStatusChanged`)

---

## Implementation Patterns

### Minimal Implementation (Empty Stubs)

If you don't need a method's functionality, implement it as an empty stub:

```cpp
void AuthServiceEventListener::onLogout() {
    // We're not using user login, so this never fires
    // Empty implementation is fine
}

void MeetingServiceEventListener::onAICompanionActiveChangeNotice(bool bActive) {
    // We don't care about AI Companion status
    // Empty implementation is fine
}
```

### Logging Implementation (Recommended for Debugging)

Add basic logging to see when callbacks fire:

```cpp
void AuthServiceEventListener::onZoomIdentityExpired() {
    std::cout << "[AUTH] Zoom identity expired! Need to regenerate JWT token." << std::endl;
}

void MeetingServiceEventListener::onMeetingStatisticsWarningNotification(StatisticsWarningType type) {
    std::cout << "[MEETING] Statistics warning: " << static_cast<int>(type) << std::endl;
}
```

### Full Implementation (For Important Callbacks)

```cpp
void MeetingServiceEventListener::onMeetingStatusChanged(MeetingStatus status, int iResult) {
    switch (status) {
        case MEETING_STATUS_IDLE:
            std::cout << "[MEETING] Status: IDLE" << std::endl;
            break;
        case MEETING_STATUS_CONNECTING:
            std::cout << "[MEETING] Status: CONNECTING" << std::endl;
            break;
        case MEETING_STATUS_INMEETING:
            std::cout << "[MEETING] Status: IN MEETING" << std::endl;
            if (onInMeetingCallback) {
                onInMeetingCallback();  // Trigger custom logic
            }
            break;
        case MEETING_STATUS_ENDED:
            std::cout << "[MEETING] Status: ENDED (Reason: " << iResult << ")" << std::endl;
            if (onMeetingEnded) {
                onMeetingEnded();  // Trigger custom logic
            }
            break;
        case MEETING_STATUS_FAILED:
            std::cout << "[MEETING] Status: FAILED (Error: " << iResult << ")" << std::endl;
            break;
        default:
            std::cout << "[MEETING] Status: UNKNOWN (" << status << ")" << std::endl;
            break;
    }
}
```

---

## Complete Header/Source File Template

### Header File (AuthServiceEventListener.h)

```cpp
#pragma once
#include <windows.h>
#include <cstdint>
#include <auth_service_interface.h>
#include <iostream>

using namespace ZOOM_SDK_NAMESPACE;

class AuthServiceEventListener : public IAuthServiceEvent {
public:
    // Constructor with callback
    AuthServiceEventListener(void (*onComplete)());

    // All 6 required methods
    void onAuthenticationReturn(AuthResult ret) override;
    void onLoginReturnWithReason(LOGINSTATUS ret, IAccountInfo* info, LoginFailReason reason) override;
    void onLogout() override;
    void onZoomIdentityExpired() override;
    void onZoomAuthIdentityExpired() override;
#if defined(WIN32)
    void onNotificationServiceStatus(SDKNotificationServiceStatus status, SDKNotificationServiceError error) override;
#endif

private:
    void (*onAuthComplete)();
};
```

### Source File (AuthServiceEventListener.cpp)

```cpp
#include "AuthServiceEventListener.h"

AuthServiceEventListener::AuthServiceEventListener(void (*onComplete)())
    : onAuthComplete(onComplete) {}

void AuthServiceEventListener::onAuthenticationReturn(AuthResult ret) {
    if (ret == AUTHRET_SUCCESS) {
        std::cout << "[AUTH] Authentication successful!" << std::endl;
        if (onAuthComplete) {
            onAuthComplete();
        }
    } else {
        std::cout << "[AUTH] Authentication failed: " << ret << std::endl;
    }
}

void AuthServiceEventListener::onLoginReturnWithReason(LOGINSTATUS ret, IAccountInfo* info, LoginFailReason reason) {
    std::cout << "[AUTH] Login return (not used for JWT): " << ret << std::endl;
}

void AuthServiceEventListener::onLogout() {
    std::cout << "[AUTH] Logout" << std::endl;
}

void AuthServiceEventListener::onZoomIdentityExpired() {
    std::cout << "[AUTH] Zoom identity expired!" << std::endl;
}

void AuthServiceEventListener::onZoomAuthIdentityExpired() {
    std::cout << "[AUTH] Zoom auth identity expiring soon!" << std::endl;
}

#if defined(WIN32)
void AuthServiceEventListener::onNotificationServiceStatus(SDKNotificationServiceStatus status, SDKNotificationServiceError error) {
    std::cout << "[AUTH] Notification service status: " << status << ", error: " << error << std::endl;
}
#endif
```

---

## Troubleshooting

### Error: "Cannot instantiate abstract class"

**Cause**: You're missing one or more pure virtual method implementations.

**Solution**:
1. Read the compiler error carefully - it lists the missing methods
2. Look up the method signature in the SDK header file
3. Add the method to both your .h and .cpp files
4. Use `override` keyword to catch signature mismatches

**Example error**:
```
error C2259: 'AuthServiceEventListener': cannot instantiate abstract class
note: due to following members:
'void IAuthServiceEvent::onNotificationServiceStatus(...)': is abstract
```

**Fix**: Add the missing method:
```cpp
// In .h file
#if defined(WIN32)
void onNotificationServiceStatus(SDKNotificationServiceStatus status, SDKNotificationServiceError error) override;
#endif

// In .cpp file
#if defined(WIN32)
void AuthServiceEventListener::onNotificationServiceStatus(SDKNotificationServiceStatus status, SDKNotificationServiceError error) {
    // Empty implementation is fine if you don't need this
}
#endif
```

### Error: "No suitable user-defined conversion"

**Cause**: Method signature doesn't match exactly (wrong parameter types, missing const, etc.).

**Solution**: Copy the signature EXACTLY from the SDK header file, including:
- `const` qualifiers
- Pointer vs reference (`*` vs `&`)
- Parameter order
- Return type

### WIN32 Methods Not Compiling

**Cause**: Forgot `#if defined(WIN32)` wrapper.

**Solution**: Wrap WIN32-only methods in both .h and .cpp files:
```cpp
#if defined(WIN32)
void onNotificationServiceStatus(...) override;
#endif
```

---

---

## Custom UI Interfaces

These interfaces are required when using Custom UI mode (`ENABLE_CUSTOMIZED_UI_FLAG`).

### ICustomizedUIMgrEvent (3 methods required)

**File**: `SDK/x64/h/customized_ui/customized_ui_mgr.h`

```cpp
class CustomUIMgrEventListener : public ICustomizedUIMgrEvent {
public:
    // Method 1: Video container destroyed by SDK (e.g., meeting ended)
    void onVideoContainerDestroyed(ICustomizedVideoContainer* pContainer) override;

    // Method 2: Share render destroyed by SDK
    void onShareRenderDestroyed(ICustomizedShareRender* pRender) override;

    // Method 3: Immersive container destroyed by SDK
    void onImmersiveContainerDestroyed() override;
};
```

**Important notes**:
- These fire when the SDK destroys containers on its own (e.g., meeting ends)
- You MUST null out your pointers in these callbacks to avoid dangling references
- All 3 are always required

---

### ICustomizedVideoContainerEvent (6 methods required)

**File**: `SDK/x64/h/customized_ui/customized_video_container.h`

```cpp
class VideoContainerEventListener : public ICustomizedVideoContainerEvent {
public:
    // Method 1: User changed for a video render element
    void onRenderUserChanged(IVideoRenderElement* pElement, unsigned int userid) override;

    // Method 2: Data type changed (video, avatar, screen name)
    void onRenderDataTypeChanged(IVideoRenderElement* pElement, VideoRenderDataType dataType) override;

    // Method 3: Layout notification — container resized, recompute element positions
    void onLayoutNotification(RECT wnd_client_rect) override;

    // Method 4: A video render element was destroyed
    void onVideoRenderElementDestroyed(IVideoRenderElement* pElement) override;

    // Method 5: Window messages from SDK child HWND (mouse, keyboard)
    void onWindowMsgNotification(UINT uMsg, WPARAM wParam, LPARAM lParam) override;

    // Method 6: Video subscription failed for an element
    void onSubscribeUserFail(ZoomSDKVideoSubscribeFailReason fail_reason, IVideoRenderElement* pElement) override;
};
```

**Important notes**:
- `onLayoutNotification` is where you re-layout video elements after container resize
- `onWindowMsgNotification` forwards input from SDK's child HWND (see [Custom UI Architecture](../concepts/custom-ui-architecture.md))
- `VideoRenderDataType` values: `VideoRenderData_Video`, `VideoRenderData_Avatar`, `VideoRenderData_ScreenName`
- `ZoomSDKVideoSubscribeFailReason` values: `ViewOnly`, `NotInMeeting`, `HasSubscribe1080POr720`, `HasSubscribeTwo720P`, `HasSubscribeExceededLimit`, `TooFrequentCall`

---

### ICustomizedShareRenderEvent (3 methods required)

**File**: `SDK/x64/h/customized_ui/customized_share_render.h`

```cpp
class ShareRenderEventListener : public ICustomizedShareRenderEvent {
public:
    // Method 1: Started receiving shared content
    void onSharingContentStartReceiving() override;

    // Method 2: Share source changed or sharing closed
    void onSharingSourceNotification(unsigned int nShareSourceID) override;

    // Method 3: Window messages from share render's child HWND
    void onWindowMsgNotification(UINT uMsg, WPARAM wParam, LPARAM lParam) override;
};
```

**Important notes**:
- When `onSharingSourceNotification` fires with a new ID, call `SetShareSourceID(nShareSourceID)` and `Show()`
- When sharing stops, `nShareSourceID` will be 0 — call `Hide()`

---

### Quick Reference: Custom UI Method Counts

| Interface | Methods | File |
|-----------|---------|------|
| `ICustomizedUIMgrEvent` | 3 | `customized_ui/customized_ui_mgr.h` |
| `ICustomizedVideoContainerEvent` | 6 | `customized_ui/customized_video_container.h` |
| `ICustomizedShareRenderEvent` | 3 | `customized_ui/customized_share_render.h` |
| `ICustomizedImmersiveContainerEvent` | 1 | `customized_ui/customized_immersive_container.h` |
| **Total Custom UI methods** | **13** | |

---

## SDK Version Differences

Different SDK versions may have different required methods. This guide is for **SDK v6.7.2.26830**.

If you're using a different version:
1. Run `grep "= 0" SDK/x64/h/auth_service_interface.h` to see your version's methods
2. Run `grep "= 0" SDK/x64/h/meeting_service_interface.h`
3. Compare against this guide to identify new or removed methods

---

## Quick Reference Commands

```bash
# List all pure virtual methods in SDK
grep "= 0" SDK/x64/h/*.h

# Count methods per interface
grep -c "= 0" SDK/x64/h/auth_service_interface.h      # Should be 6
grep -c "= 0" SDK/x64/h/meeting_service_interface.h   # Should be 9

# Find method signature
grep -A 5 "onAuthenticationReturn" SDK/x64/h/auth_service_interface.h

# Verify your implementation has all methods
grep "override" src/AuthServiceEventListener.h        # Should match SDK count
```

---

## Related Documentation

- [Build Errors Guide](../troubleshooting/build-errors.md) - Header dependency issues
- [Authentication Pattern](../examples/authentication-pattern.md) - Using IAuthServiceEvent
- [Windows Reference](windows-reference.md) - General SDK setup

---

**Last Updated**: Based on Zoom Windows Meeting SDK v6.7.2.26830
