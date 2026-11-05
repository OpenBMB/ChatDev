# Windows Message Loop Requirement

## Critical Issue: SDK Callbacks Not Firing

### The Problem

**Symptom**: Authentication times out, callbacks never execute
```
[AUTH] Calling SDKAuth...
[AUTH] Waiting for callback...
[Still waiting after 30 seconds...]
ERROR: Authentication timeout
```

**Root Cause**: The Zoom Windows SDK uses the **Windows message pump** to dispatch callbacks. Without processing Windows messages, callbacks are queued but never delivered.

---

## Why This Happens

The SDK uses COM/Windows messaging for asynchronous operations:

1. **SDK Thread**: Receives response from Zoom servers
2. **Posts Windows Message**: To application's message queue
3. **Application Must Process**: Via `GetMessage()` or `PeekMessage()`
4. **Message Dispatched**: Callback function finally invoked

**Without message processing**: Messages queue up → Never dispatched → Callbacks never fire → Timeout

---

## The Solution

### Pattern 1: Non-Blocking with PeekMessage() (Recommended)

Use when you need to check conditions or implement timeouts:

```cpp
bool WaitForAuthentication() {
    auto startTime = std::chrono::steady_clock::now();

    while (!g_authenticated && !g_exit) {
        // CRITICAL: Process Windows messages for SDK callbacks!
        MSG msg;
        while (PeekMessage(&msg, NULL, 0, 0, PM_REMOVE)) {
            TranslateMessage(&msg);
            DispatchMessage(&msg);
        }

        // Check timeout
        auto elapsed = std::chrono::duration_cast<std::chrono::seconds>(
            std::chrono::steady_clock::now() - startTime).count();
        if (elapsed >= 30) {
            return false; // Timeout
        }

        // Small sleep to avoid CPU spinning
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }

    return g_authenticated;
}
```

### Pattern 2: Blocking with GetMessage()

Use for main application loop:

```cpp
int main() {
    // ... initialize SDK, authenticate, join meeting ...

    // Main message loop
    MSG msg;
    while (GetMessage(&msg, nullptr, 0, 0)) {
        if (msg.message == WM_QUIT) {
            break;
        }
        TranslateMessage(&msg);
        DispatchMessage(&msg);
    }

    // Cleanup
    CleanUPSDK();
    return 0;
}
```

### Pattern 3: Hybrid Approach (Our Solution)

Combines non-blocking message processing with custom exit conditions:

```cpp
// During authentication wait
while (!g_authenticated && !g_exit) {
    MSG msg;
    while (PeekMessage(&msg, NULL, 0, 0, PM_REMOVE)) {
        TranslateMessage(&msg);
        DispatchMessage(&msg);
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(100));
}

// Main application loop
while (!g_exit) {
    MSG msg;
    while (PeekMessage(&msg, NULL, 0, 0, PM_REMOVE)) {
        if (msg.message == WM_QUIT) {
            g_exit = true;
            break;
        }
        TranslateMessage(&msg);
        DispatchMessage(&msg);
    }

    // Do other work here
    ProcessVideoFrames();

    std::this_thread::sleep_for(std::chrono::milliseconds(100));
}
```

---

## Common Mistakes

### ❌ Wrong: Just Sleeping

```cpp
// This will NEVER work - callbacks never dispatched!
while (!g_authenticated) {
    std::this_thread::sleep_for(std::chrono::seconds(1));
}
```

### ❌ Wrong: Using std::condition_variable Without Messages

```cpp
// Callbacks won't fire - no message processing!
std::unique_lock<std::mutex> lock(mutex);
cv.wait(lock, []{ return g_authenticated; });
```

### ✅ Correct: Message Loop with Condition Check

```cpp
while (!g_authenticated) {
    MSG msg;
    while (PeekMessage(&msg, NULL, 0, 0, PM_REMOVE)) {
        TranslateMessage(&msg);
        DispatchMessage(&msg);
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(100));
}
```

---

## Where Message Processing is Required

You MUST process Windows messages in these scenarios:

### 1. Authentication
```cpp
authService->SDKAuth(authContext);

// MUST process messages while waiting
while (!authenticated) {
    ProcessMessages();
}
```

### 2. Joining Meeting
```cpp
meetingService->Join(joinParam);

// MUST process messages while waiting
while (meetingStatus != IN_MEETING) {
    ProcessMessages();
}
```

### 3. Main Application Loop
```cpp
// MUST continuously process messages
while (!exit) {
    ProcessMessages();
}
```

### 4. Waiting for Any SDK Callback
Any time you're waiting for:
- `onAuthenticationReturn()`
- `onMeetingStatusChanged()`
- `onRawDataFrameReceived()`
- Any other SDK callback

You MUST be processing Windows messages!

---

## Debugging Tips

### How to Tell if Message Loop is Missing

**Symptoms**:
- Callbacks never fire
- Timeouts after 10-30 seconds
- No error messages from SDK
- Debug output shows "waiting..." but nothing happens

**Quick Test**:
Add logging in your callback:
```cpp
void onAuthenticationReturn(AuthResult ret) {
    std::cout << "CALLBACK FIRED!" << std::endl;  // Does this ever print?
}
```

If you never see "CALLBACK FIRED!", you're not processing messages.

### Debug Helper Function

```cpp
void ProcessMessagesWithDebug() {
    MSG msg;
    int messageCount = 0;
    while (PeekMessage(&msg, NULL, 0, 0, PM_REMOVE)) {
        messageCount++;
        TranslateMessage(&msg);
        DispatchMessage(&msg);
    }
    if (messageCount > 0) {
        std::cout << "Processed " << messageCount << " messages" << std::endl;
    }
}
```

---

## PeekMessage vs GetMessage

| Feature | PeekMessage | GetMessage |
|---------|-------------|------------|
| **Blocking** | No | Yes |
| **Returns if no messages** | Immediately | Waits |
| **Good for** | Timeouts, conditions | Main message loop |
| **CPU Usage** | Can spin (add sleep) | Efficient |
| **Flexibility** | High | Low |

### When to Use Each

**PeekMessage**:
- When waiting for SDK callbacks with timeout
- When you need to check other conditions
- When combining with other work

**GetMessage**:
- Main application message loop
- When you want efficient CPU usage
- Standard Windows application pattern

---

## Complete Example

```cpp
#include <windows.h>
#include <zoom_sdk.h>
#include <auth_service_interface.h>
#include <iostream>
#include <chrono>
#include <thread>

using namespace ZOOM_SDK_NAMESPACE;

bool g_authenticated = false;
bool g_exit = false;

class MyAuthListener : public IAuthServiceEvent {
public:
    void onAuthenticationReturn(AuthResult ret) override {
        std::cout << "Auth callback received!" << std::endl;
        if (ret == AUTHRET_SUCCESS) {
            g_authenticated = true;
        }
    }
    // ... other required methods ...
};

bool AuthenticateWithMessageLoop(IAuthService* authService, const wchar_t* jwt) {
    authService->SetEvent(new MyAuthListener());

    AuthContext context;
    context.jwt_token = jwt;

    if (authService->SDKAuth(context) != SDKERR_SUCCESS) {
        return false;
    }

    // Wait for callback with message processing
    auto startTime = std::chrono::steady_clock::now();
    while (!g_authenticated && !g_exit) {
        // Process Windows messages - CRITICAL!
        MSG msg;
        while (PeekMessage(&msg, NULL, 0, 0, PM_REMOVE)) {
            TranslateMessage(&msg);
            DispatchMessage(&msg);
        }

        // Check timeout (30 seconds)
        auto elapsed = std::chrono::duration_cast<std::chrono::seconds>(
            std::chrono::steady_clock::now() - startTime).count();
        if (elapsed >= 30) {
            std::cerr << "Authentication timeout" << std::endl;
            return false;
        }

        // Small sleep to avoid CPU spinning
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }

    return g_authenticated;
}

int main() {
    // Initialize SDK
    InitParam initParam;
    initParam.strWebDomain = L"https://zoom.us";
    InitSDK(initParam);

    // Create auth service
    IAuthService* authService = nullptr;
    CreateAuthService(&authService);

    // Authenticate with message loop
    if (!AuthenticateWithMessageLoop(authService, L"your-jwt-token")) {
        std::cerr << "Authentication failed" << std::endl;
        return 1;
    }

    std::cout << "Authenticated successfully!" << std::endl;

    // Main application loop with message processing
    while (!g_exit) {
        MSG msg;
        while (PeekMessage(&msg, NULL, 0, 0, PM_REMOVE)) {
            if (msg.message == WM_QUIT) {
                g_exit = true;
                break;
            }
            TranslateMessage(&msg);
            DispatchMessage(&msg);
        }

        // Do other work
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }

    // Cleanup
    CleanUPSDK();
    return 0;
}
```

---

## Why SDK Documentation Doesn't Mention This

1. **Assumed knowledge**: Windows developers are expected to know about message pumps
2. **Sample code uses it**: But in different patterns that might not be obvious
3. **Not explicitly required**: Works fine if you already have a message loop
4. **Platform-specific**: Only affects Windows SDK

---

## Key Takeaways

1. **Always process Windows messages** when waiting for SDK callbacks
2. **Use PeekMessage()** for non-blocking with timeout
3. **Use GetMessage()** for main application loop
4. **Add sleep** to avoid CPU spinning with PeekMessage()
5. **Test callbacks** to verify message loop is working
6. **This is not optional** - SDK will not work without it

---

## Related Issues

- **Authentication timeout**: Usually caused by missing message loop
- **Meeting join timeout**: Same issue
- **No video frames**: Check message loop in main application loop
- **Callbacks delayed**: Ensure message processing is frequent enough

---

## See Also

- [Authentication Flow Pattern](../examples/authentication-pattern.md)
- [Common Build Errors](build-errors.md)
- [SDK Initialization](../SKILL.md#initialization)
