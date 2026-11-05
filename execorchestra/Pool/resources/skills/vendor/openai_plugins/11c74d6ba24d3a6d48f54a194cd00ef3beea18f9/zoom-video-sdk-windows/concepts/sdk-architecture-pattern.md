# SDK Architecture Pattern

## The Universal Formula

The Zoom Video SDK follows a **perfectly consistent architecture**. Every feature works the same way:

```
┌─────────────────────────────────────────────────────────────────┐
│                    UNIVERSAL 3-STEP PATTERN                     │
├─────────────────────────────────────────────────────────────────┤
│  1. GET SINGLETON    →  SDK, helpers, session, users            │
│  2. IMPLEMENT DELEGATE →  Event callbacks (IZoomVideoSDKDelegate)│
│  3. SUBSCRIBE & USE   →  Call methods, receive events           │
└─────────────────────────────────────────────────────────────────┘
```

**Once you understand this pattern, you can implement ANY feature.**

---

## Step 1: Get Singleton

The SDK is a tree of singleton objects. You navigate to what you need:

```cpp
// Root singleton
IZoomVideoSDK* sdk = CreateZoomVideoSDKObj();

// Level 1: Helpers (control YOUR streams)
IZoomVideoSDKVideoHelper* videoHelper = sdk->getVideoHelper();
IZoomVideoSDKAudioHelper* audioHelper = sdk->getAudioHelper();
IZoomVideoSDKShareHelper* shareHelper = sdk->getShareHelper();
IZoomVideoSDKChatHelper* chatHelper = sdk->getChatHelper();

// Level 2: Session
IZoomVideoSDKSession* session = sdk->getSessionInfo();

// Level 3: Users
IZoomVideoSDKUser* myself = session->getMyself();
IVideoSDKVector<IZoomVideoSDKUser*>* remoteUsers = session->getRemoteUsers();

// Level 4: Canvas/Pipe (per user)
IZoomVideoSDKCanvas* canvas = user->GetVideoCanvas();
IZoomVideoSDKRawDataPipe* pipe = user->GetVideoPipe();
```

**Key insight**: You don't construct these objects. You navigate to them.

---

## Step 2: Implement Delegate

The SDK uses **observer pattern** for events. Implement `IZoomVideoSDKDelegate`:

```cpp
class MyDelegate : public IZoomVideoSDKDelegate {
public:
    // Session lifecycle
    void onSessionJoin() override {
        std::cout << "Joined session!" << std::endl;
        // Safe to start video, subscribe to users, etc.
    }

    void onSessionLeave() override {
        std::cout << "Left session" << std::endl;
    }

    // User events
    void onUserJoin(IZoomVideoSDKUserHelper* helper,
                    IVideoSDKVector<IZoomVideoSDKUser*>* userList) override {
        // New users joined - but don't subscribe to video yet!
    }

    void onUserVideoStatusChanged(IZoomVideoSDKVideoHelper* helper,
                                  IVideoSDKVector<IZoomVideoSDKUser*>* userList) override {
        // NOW subscribe to video - it's ready
        for (int i = 0; i < userList->GetCount(); i++) {
            IZoomVideoSDKUser* user = userList->GetItem(i);
            if (user->GetVideoPipe()->getVideoStatus().isOn) {
                user->GetVideoCanvas()->subscribeWithView(hwnd, aspect, resolution);
            }
        }
    }

    // Chat events
    void onChatNewMessageNotify(IZoomVideoSDKChatHelper* helper,
                                IZoomVideoSDKChatMessage* msg) override {
        std::wcout << L"Chat: " << msg->getContent() << std::endl;
    }

    // Share events
    void onUserShareStatusChanged(IZoomVideoSDKShareHelper* helper,
                                  IZoomVideoSDKUser* user,
                                  IZoomVideoSDKShareAction* shareAction) override {
        // Subscribe to remote user's screen share
        shareAction->subscribeWithView(shareHwnd, ZoomVideoSDKVideoAspect_Original);
    }

    // ... 80+ more callbacks (implement as empty if not needed)
    void onError(ZoomVideoSDKErrors errorCode, int detailErrorCode) override {}
    void onUserLeave(IZoomVideoSDKUserHelper*, IVideoSDKVector<IZoomVideoSDKUser*>*) override {}
    // etc.
};
```

**Key insight**: All 80+ methods must be implemented (even if empty).

---

## Step 3: Subscribe & Use

Register your delegate and call methods:

```cpp
// Register delegate BEFORE joining
sdk->addListener(new MyDelegate());

// Initialize
ZoomVideoSDKInitParams initParams;
initParams.domain = L"https://zoom.us";
initParams.videoRawDataMemoryMode = ZoomVideoSDKRawDataMemoryModeHeap;
sdk->initialize(initParams);

// Join session
ZoomVideoSDKSessionContext context;
context.sessionName = L"my-session";
context.userName = L"Bot";
context.token = L"your-jwt-token";
context.audioOption.connect = false;  // Connect audio in onSessionJoin
sdk->joinSession(context);

// In onSessionJoin callback:
void onSessionJoin() override {
    // Start audio
    sdk->getAudioHelper()->startAudio();

    // Start video
    sdk->getVideoHelper()->startVideo();

    // Subscribe to self video
    IZoomVideoSDKUser* myself = sdk->getSessionInfo()->getMyself();
    myself->GetVideoCanvas()->subscribeWithView(selfHwnd, aspect, resolution);
}
```

---

## Pattern Applied to Every Feature

### Audio

```cpp
// Get singleton
IZoomVideoSDKAudioHelper* audioHelper = sdk->getAudioHelper();

// Use
audioHelper->startAudio();
audioHelper->muteAudio(user);
audioHelper->unmuteAudio(user);

// Events arrive in delegate
void onUserAudioStatusChanged(...) override { }
```

### Video

```cpp
// Get singleton
IZoomVideoSDKVideoHelper* videoHelper = sdk->getVideoHelper();

// Use
videoHelper->startVideo();
videoHelper->stopVideo();
videoHelper->switchCamera(deviceId);

// Subscribe to user's video
user->GetVideoCanvas()->subscribeWithView(hwnd, aspect, resolution);

// Events arrive in delegate
void onUserVideoStatusChanged(...) override { }
```

### Chat

```cpp
// Get singleton
IZoomVideoSDKChatHelper* chatHelper = sdk->getChatHelper();

// Use
chatHelper->sendChatToAll(L"Hello everyone!");
chatHelper->sendChatToUser(user, L"Private message");

// Events arrive in delegate
void onChatNewMessageNotify(...) override { }
```

### Screen Share

```cpp
// Get singleton
IZoomVideoSDKShareHelper* shareHelper = sdk->getShareHelper();

// Use (start YOUR share)
shareHelper->startShareScreen(monitorId);
shareHelper->stopShare();

// Subscribe to REMOTE share (in callback)
void onUserShareStatusChanged(..., IZoomVideoSDKShareAction* shareAction) override {
    shareAction->subscribeWithView(hwnd, aspect);
}
```

### Command Channel

```cpp
// Get singleton
IZoomVideoSDKCmdChannel* cmdChannel = sdk->getCmdChannel();

// Use
cmdChannel->sendCommandToAll(L"custom-data");
cmdChannel->sendCommand(user, L"private-data");

// Events arrive in delegate
void onCommandReceived(IZoomVideoSDKUser* sender, const zchar_t* cmd) override { }
```

---

## Why This Pattern Works

| Aspect | Design Choice | Benefit |
|--------|---------------|---------|
| **Singletons** | One instance per feature | No object lifecycle management |
| **Observer** | Delegate callbacks | Decoupled, event-driven code |
| **Navigation** | Tree structure | Predictable access patterns |
| **Consistency** | Same pattern everywhere | Learn once, apply everywhere |

---

## Common Mistakes

### Mistake 1: Subscribing Too Early

```cpp
// WRONG - video not ready
void onUserJoin(...) {
    user->GetVideoCanvas()->subscribeWithView(hwnd, ...);  // Error!
}

// CORRECT - wait for video status
void onUserVideoStatusChanged(...) {
    if (user->GetVideoPipe()->getVideoStatus().isOn) {
        user->GetVideoCanvas()->subscribeWithView(hwnd, ...);
    }
}
```

### Mistake 2: Missing Message Loop

```cpp
// WRONG - callbacks never fire
sdk->joinSession(context);
while (true) { Sleep(100); }  // No message pump!

// CORRECT - process Windows messages
while (!done) {
    MSG msg;
    while (PeekMessage(&msg, NULL, 0, 0, PM_REMOVE)) {
        TranslateMessage(&msg);
        DispatchMessage(&msg);
    }
    Sleep(10);
}
```

### Mistake 3: Using Helpers for Remote Users

```cpp
// WRONG - helpers control YOUR streams only
sdk->getVideoHelper()->startVideo();  // Starts YOUR camera
sdk->getVideoHelper()->stopVideo();   // Stops YOUR camera

// CORRECT - subscribe to remote users via their Canvas
remoteUser->GetVideoCanvas()->subscribeWithView(hwnd, ...);
```

---

## Related Documentation

- [Singleton Hierarchy](singleton-hierarchy.md) - Complete navigation tree
- [Canvas vs Raw Data](canvas-vs-raw-data.md) - Choose rendering approach
- [Delegate Methods](../references/delegate-methods.md) - All 80+ callbacks
- [Session Join Pattern](../examples/session-join-pattern.md) - Working code

---

**TL;DR**: Get singleton → Implement delegate → Subscribe & use. This works for every feature.
