# Windows Message Loop

## The #1 Cause of "Callbacks Don't Fire"

If your SDK callbacks aren't firing (onSessionJoin, onUserJoin, etc.), you're almost certainly missing the Windows message loop.

```
┌─────────────────────────────────────────────────────────────────┐
│  SYMPTOM                        │  CAUSE                        │
├─────────────────────────────────────────────────────────────────┤
│  joinSession() returns success  │                               │
│  but onSessionJoin() never      │  Missing Windows message loop │
│  fires                          │                               │
└─────────────────────────────────────────────────────────────────┘
```

---

## Why It's Required

The Zoom Video SDK uses **Windows messaging** to dispatch callbacks. When an event occurs (user joins, video starts, etc.), the SDK posts a message to your thread's message queue. If you never process those messages, the callbacks never fire.

```
SDK Event Occurs
      ↓
SDK posts message to your thread's queue
      ↓
Your message loop calls PeekMessage/GetMessage
      ↓
Message is dispatched
      ↓
Your callback fires
```

**Without the message loop, step 3 never happens.**

---

## The Fix

### Console Application (No GUI)

```cpp
int main() {
    // Initialize SDK
    IZoomVideoSDK* sdk = CreateZoomVideoSDKObj();
    sdk->initialize(params);
    sdk->addListener(new MyDelegate());
    sdk->joinSession(context);

    // ═══════════════════════════════════════════════════════════════
    // CRITICAL: Windows message loop
    // ═══════════════════════════════════════════════════════════════
    bool running = true;
    while (running) {
        MSG msg;
        while (PeekMessage(&msg, NULL, 0, 0, PM_REMOVE)) {
            if (msg.message == WM_QUIT) {
                running = false;
                break;
            }
            TranslateMessage(&msg);
            DispatchMessage(&msg);
        }

        // Small sleep to avoid 100% CPU
        Sleep(10);
    }

    // Cleanup
    sdk->leaveSession(false);
    sdk->cleanup();

    return 0;
}
```

### GUI Application (WinMain)

GUI applications using standard WinMain already have a message loop, but make sure it's running:

```cpp
int WINAPI WinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance,
                   LPSTR lpCmdLine, int nCmdShow) {
    // Create window, initialize SDK, etc.

    // Standard message loop
    MSG msg;
    while (GetMessage(&msg, NULL, 0, 0)) {
        TranslateMessage(&msg);
        DispatchMessage(&msg);
    }

    return (int)msg.wParam;
}
```

---

## Common Mistakes

### Mistake 1: No Message Loop At All

```cpp
// WRONG - callbacks will never fire
int main() {
    sdk->joinSession(context);

    // Waiting forever, but callbacks never fire
    while (!g_joined) {
        Sleep(100);  // No message processing!
    }
}
```

### Mistake 2: Message Loop in Wrong Thread

```cpp
// WRONG - SDK callbacks are tied to the thread that called joinSession
void WorkerThread() {
    sdk->joinSession(context);  // Callbacks tied to this thread
}

int main() {
    std::thread worker(WorkerThread);

    // Message loop on main thread won't help worker thread's callbacks
    MSG msg;
    while (GetMessage(&msg, NULL, 0, 0)) {
        TranslateMessage(&msg);
        DispatchMessage(&msg);
    }
}
```

**Fix**: Run message loop on the same thread that calls SDK methods.

### Mistake 3: Blocking the Message Loop

```cpp
// WRONG - blocking call prevents message processing
void onSessionJoin() override {
    // This blocks the message loop!
    std::this_thread::sleep_for(std::chrono::seconds(10));

    // Or this:
    while (waiting) { }  // Infinite loop blocks everything
}
```

**Fix**: Keep callbacks fast. Use async/threading for long operations.

---

## Diagnostic Checklist

If callbacks aren't firing:

1. **Is there a message loop?**
   - Look for `PeekMessage` or `GetMessage` in your code
   - Must be on the same thread that calls `joinSession()`

2. **Is the message loop running?**
   - Add logging: `std::cout << "Processing messages..." << std::endl;`
   - Should print continuously

3. **Is the delegate registered?**
   - `sdk->addListener(delegate)` must be called BEFORE `joinSession()`

4. **Are all delegate methods implemented?**
   - Missing pure virtual methods = compile error
   - Wrong signature = callback not called

5. **Is the SDK initialized?**
   - Check return value of `initialize()`

---

## Minimal Working Example

```cpp
#include <windows.h>
#include <iostream>
#include "zoom_video_sdk_api.h"
#include "zoom_video_sdk_interface.h"
#include "zoom_video_sdk_delegate_interface.h"

USING_ZOOM_VIDEO_SDK_NAMESPACE

bool g_joined = false;

class TestDelegate : public IZoomVideoSDKDelegate {
public:
    void onSessionJoin() override {
        std::cout << "*** onSessionJoin fired! ***" << std::endl;
        g_joined = true;
    }

    void onError(ZoomVideoSDKErrors err, int detail) override {
        std::cout << "*** onError: " << err << " ***" << std::endl;
    }

    // ... implement all other methods as empty
};

int main() {
    IZoomVideoSDK* sdk = CreateZoomVideoSDKObj();

    ZoomVideoSDKInitParams params;
    params.domain = L"https://zoom.us";
    sdk->initialize(params);

    sdk->addListener(new TestDelegate());

    ZoomVideoSDKSessionContext ctx;
    ctx.sessionName = L"test";
    ctx.userName = L"Bot";
    ctx.token = L"your-jwt";
    ctx.audioOption.connect = false;

    sdk->joinSession(ctx);

    std::cout << "Starting message loop..." << std::endl;

    // THE CRITICAL PART
    while (!g_joined) {
        MSG msg;
        while (PeekMessage(&msg, NULL, 0, 0, PM_REMOVE)) {
            TranslateMessage(&msg);
            DispatchMessage(&msg);
        }
        Sleep(10);
    }

    std::cout << "Joined! Exiting..." << std::endl;

    sdk->leaveSession(false);
    sdk->cleanup();

    return 0;
}
```

---

## Related Documentation

- [Session Join Pattern](../examples/session-join-pattern.md) - Complete working code
- [Common Issues](common-issues.md) - Other troubleshooting
- [SDK Architecture Pattern](../concepts/sdk-architecture-pattern.md) - Event-driven design

---

**TL;DR**: Add `PeekMessage`/`TranslateMessage`/`DispatchMessage` loop on the same thread that calls `joinSession()`. This is NOT optional.
