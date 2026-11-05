---
name: zoom-video-sdk-windows
description: "Zoom Video SDK for Windows - C++ integration for video sessions, raw audio/video capture, screen sharing, recording, and real-time communication"
---

# Zoom Video SDK - Windows Development

Expert guidance for developing with the Zoom Video SDK on Windows. This SDK enables custom video applications, raw media capture/injection, cloud recording, live streaming, and real-time transcription on Windows platforms.

**Official Documentation**: https://developers.zoom.us/docs/video-sdk/windows/
**API Reference**: https://marketplacefront.zoom.us/sdk/custom/windows/
**Sample Repository**: https://github.com/zoom/videosdk-windows-rawdata-sample

## Quick Links

**New to Video SDK? Follow this path:**

1. **[SDK Architecture Pattern](concepts/sdk-architecture-pattern.md)** - Universal 3-step pattern for ANY feature
2. **[Session Join Pattern](examples/session-join-pattern.md)** - Complete working code to join a session
3. **[Windows Message Loop](troubleshooting/windows-message-loop.md)** - **CRITICAL**: Fix callbacks not firing
4. **[Video Rendering](examples/video-rendering.md)** - Display video with Canvas API

**Reference:**
- **[Singleton Hierarchy](concepts/singleton-hierarchy.md)** - 5-level SDK navigation map
- **[API Reference](references/windows-reference.md)** - Methods, error codes, timing rules
- **[Delegate Methods](references/delegate-methods.md)** - All 80+ callback methods
- **[Sample Applications](references/samples.md)** - Official samples guide
- **[windows.md](windows.md)** - Secondary overview doc (pointer-style)
- **[SKILL.md](SKILL.md)** - Complete documentation navigation

**Having issues?**
- Callbacks not firing → [Windows Message Loop](troubleshooting/windows-message-loop.md)
- Build errors → [Build Errors Guide](troubleshooting/build-errors.md)
- Video subscribe fails → [Video Rendering](examples/video-rendering.md) (subscribe in `onUserVideoStatusChanged`)
- Quick diagnostics → [Common Issues](troubleshooting/common-issues.md)

**Building a Custom UI?**
- [Canvas vs Raw Data](concepts/canvas-vs-raw-data.md) - Choose your rendering approach
- [Raw Video Capture](examples/raw-video-capture.md) - YUV420 frame processing

## SDK Overview

The Zoom Video SDK for Windows is a C++ library that provides:
- **Session Management**: Join/leave video SDK sessions
- **Raw Data Access**: Capture raw audio/video frames (YUV420, PCM)
- **Raw Data Injection**: Send custom audio/video into sessions
- **Screen Sharing**: Share screens or inject custom share sources
- **Cloud Recording**: Record sessions to Zoom cloud
- **Live Streaming**: Stream to RTMP endpoints (YouTube, etc.)
- **Chat & Commands**: In-session messaging and command channels
- **Live Transcription**: Real-time speech-to-text
- **Subsessions**: Breakout room support
- **Whiteboard**: Collaborative whiteboard features
- **Annotations**: Screen share annotations
- **C# Integration**: C++/CLI wrapper for .NET applications

## Prerequisites

### System Requirements

- **OS**: Windows 10 (1903 or later) or Windows 11
- **Architecture**: x64 (recommended), x86, or ARM64
- **Visual Studio**: 2019 or 2022 (Community, Professional, or Enterprise)
- **Windows SDK**: 10.0.19041.0 or later
- **.NET Framework**: 4.8 or later (for C# applications)

### Visual Studio Workloads

Install these workloads via Visual Studio Installer:

1. **Desktop development with C++**
   - MSVC v142 or v143 compiler
   - Windows 10/11 SDK
   - C++ CMake tools (optional)

2. **.NET desktop development** (for C# applications)
   - .NET Framework 4.8 targeting pack
   - C++/CLI support

## Quick Start

### C++ Application

```cpp
#include <windows.h>
#include "zoom_video_sdk_api.h"
#include "zoom_video_sdk_interface.h"
#include "zoom_video_sdk_delegate_interface.h"

USING_ZOOM_VIDEO_SDK_NAMESPACE

// 1. Create SDK object
IZoomVideoSDK* video_sdk_obj = CreateZoomVideoSDKObj();

// 2. Initialize
ZoomVideoSDKInitParams init_params;
init_params.domain = L"https://zoom.us";
init_params.enableLog = true;
init_params.logFilePrefix = L"zoom_win_video";
init_params.videoRawDataMemoryMode = ZoomVideoSDKRawDataMemoryModeHeap;
init_params.shareRawDataMemoryMode = ZoomVideoSDKRawDataMemoryModeHeap;
init_params.audioRawDataMemoryMode = ZoomVideoSDKRawDataMemoryModeHeap;

ZoomVideoSDKErrors err = video_sdk_obj->initialize(init_params);

// 3. Add event listener
video_sdk_obj->addListener(myDelegate);

// 4. Join session (IMPORTANT: set audioOption.connect = false)
ZoomVideoSDKSessionContext session_context;
session_context.sessionName = L"my-session";
session_context.userName = L"Windows User";
session_context.token = L"your-jwt-token";
session_context.videoOption.localVideoOn = false;
session_context.audioOption.connect = false;  // Connect audio after join
session_context.audioOption.mute = true;

IZoomVideoSDKSession* session = video_sdk_obj->joinSession(session_context);

// 5. CRITICAL: Add Windows message pump for callbacks to work
bool running = true;
while (running) {
    // Process Windows messages (required for SDK callbacks)
    MSG msg;
    while (PeekMessage(&msg, NULL, 0, 0, PM_REMOVE)) {
        TranslateMessage(&msg);
        DispatchMessage(&msg);
    }

    // Your application logic here
    Sleep(10);
}
```

### C# Application

```csharp
using ZoomVideoSDK;

var sdkManager = new ZoomSDKManager();
sdkManager.Initialize();
sdkManager.JoinSession("my-session", "jwt-token", "User Name", "");
```

## Key Features

| Feature | Description |
|---------|-------------|
| **Session Management** | Join, leave, and manage video sessions |
| **Raw Video (YUV I420)** | Capture and inject raw video frames |
| **Raw Audio (PCM)** | Capture and inject raw audio data |
| **Screen Sharing** | Share screens or custom content |
| **Cloud Recording** | Record sessions to Zoom cloud |
| **Live Streaming** | Stream to RTMP endpoints |
| **Chat** | Send/receive chat messages |
| **Command Channel** | Custom command messaging |
| **Live Transcription** | Real-time speech-to-text |
| **C# Support** | Full .NET Framework integration |

## Sample Applications

**Official Repository**: https://github.com/zoom/videosdk-windows-rawdata-sample

| Sample | Description |
|--------|-------------|
| VSDK_SkeletonDemo | Minimal session join - **start here** |
| VSDK_getRawVideo | Capture YUV420 video frames |
| VSDK_getRawAudio | Capture PCM audio |
| VSDK_sendRawVideo | Inject custom video (virtual camera) |
| VSDK_sendRawAudio | Inject custom audio (virtual mic) |
| VSDK_CloudRecording | Cloud recording control |
| VSDK_CommandChannel | Custom command messaging |
| VSDK_TranscriptionAndTranslation | Live captions |

**See complete guide**: [Sample Applications Reference](references/samples.md)

## Critical Gotchas and Best Practices

### ⚠️ CRITICAL: Windows Message Pump Required

**The #1 issue that causes session joins to hang with no callbacks:**

All Windows applications using the Zoom SDK **MUST** process Windows messages. The SDK uses Windows messages to deliver callbacks like `onSessionJoin()`, `onError()`, etc.

**Problem**: Without a message pump, `joinSession()` appears to succeed but callbacks never fire.

**Solution**: Add this to your main loop:

```cpp
while (running) {
    // REQUIRED: Process Windows messages
    MSG msg;
    while (PeekMessage(&msg, NULL, 0, 0, PM_REMOVE)) {
        TranslateMessage(&msg);
        DispatchMessage(&msg);
    }

    // Your application logic
    Sleep(10);
}
```

**Applies to**:
- Console applications (no automatic message pump)
- Custom main loops
- Applications that don't use standard WinMain/WndProc

**GUI applications** using WinMain with standard message loop already have this.

### Audio Connection Strategy

**Best Practice**: Set `audioOption.connect = false` when joining, then connect audio in the `onSessionJoin()` callback.

```cpp
// During join
session_context.audioOption.connect = false;  // Don't connect yet
session_context.audioOption.mute = true;

// In onSessionJoin() callback
void onSessionJoin() override {
    IZoomVideoSDKAudioHelper* audioHelper = video_sdk_obj->getAudioHelper();
    if (audioHelper) {
        audioHelper->startAudio();  // Connect now
    }
}
```

**Why**: This pattern is used in all official Zoom samples. It separates session join from audio initialization for better reliability and error handling.

### All Delegate Callbacks Must Be Implemented

The `IZoomVideoSDKDelegate` interface has 70+ pure virtual methods. **ALL must be implemented**, even if empty:

```cpp
// Required even if you don't use them
void onProxyDetectComplete() override {}
void onUserWhiteboardShareStatusChanged(IZoomVideoSDKUser*, IZoomVideoSDKWhiteboardHelper*) override {}
// ... etc
```

**Tip**: Check the SDK version's `zoom_video_sdk_delegate_interface.h` for the complete list. The interface changes between SDK versions.

### Memory Mode for Raw Data

Always use heap mode for raw data memory:

```cpp
init_params.videoRawDataMemoryMode = ZoomVideoSDKRawDataMemoryModeHeap;
init_params.shareRawDataMemoryMode = ZoomVideoSDKRawDataMemoryModeHeap;
init_params.audioRawDataMemoryMode = ZoomVideoSDKRawDataMemoryModeHeap;
```

Stack mode can cause issues with large video frames.

### Thread Safety

SDK callbacks execute on SDK threads, not your main thread:
- Don't perform heavy operations in callbacks
- Don't call `cleanup()` from within callbacks
- Use thread-safe queues for passing data to UI thread
- Use mutexes when accessing shared state

### Consult Official Samples First

When SDK behavior is unexpected, **always check the official samples** before troubleshooting:

**Local samples**:
- `C:\tempsdk\Zoom_VideoSDK_Windows_RawDataDemos\VSDK_SkeletonDemo\` (simplest)
- `C:\tempsdk\sdksamples\zoom-video-sdk-windows-2.4.12\Sample-Libs\x64\demo\`

Official samples show correct patterns for:
- Message pump implementation ✓
- Audio connection strategy ✓
- Error handling ✓
- Memory management ✓

## Video Rendering - Two Approaches

The Zoom SDK provides **two different ways** to render video. Choose based on your needs.

### 🎯 Canvas API (Recommended for Most Use Cases)

**Best for**: Standard applications, clean video quality, ease of implementation

The SDK renders video directly to your HWND. **No YUV conversion needed**.

```cpp
// Subscribe to a user's video with Canvas API
IZoomVideoSDKCanvas* canvas = user->GetVideoCanvas();
if (canvas) {
    ZoomVideoSDKErrors ret = canvas->subscribeWithView(
        hwnd,                                    // Your window handle
        ZoomVideoSDKVideoAspect_PanAndScan,     // Fit to window, may crop
        ZoomVideoSDKResolution_Auto              // Let SDK choose best resolution
    );

    if (ret == ZoomVideoSDKErrors_Success) {
        // SDK is now rendering directly to your window!
    }
}

// Unsubscribe when done
canvas->unSubscribeWithView(hwnd);
```

**Advantages**:
- ✅ **Best quality** - SDK uses optimized, hardware-accelerated rendering
- ✅ **No artifacts** - Professional video quality
- ✅ **Simple code** - 3 lines to subscribe
- ✅ **Better performance** - No CPU-intensive YUV conversion
- ✅ **Automatic scaling** - SDK handles window resizing
- ✅ **Aspect ratio** - Built-in aspect ratio handling

**Example from official .NET sample**:
```cpp
// Self video preview
IZoomVideoSDKCanvas* canvas = myself->GetVideoCanvas();
canvas->subscribeWithView(selfVideoHwnd, aspect, resolution);

// Remote user video
IZoomVideoSDKCanvas* remoteCanvas = remoteUser->GetVideoCanvas();
remoteCanvas->subscribeWithView(remoteVideoHwnd, aspect, resolution);
```

**Video Aspect Options**:
- `ZoomVideoSDKVideoAspect_Original` - Letterbox/pillarbox, no cropping
- `ZoomVideoSDKVideoAspect_FullFilled` - Fill window, may crop edges
- `ZoomVideoSDKVideoAspect_PanAndScan` - Smart crop to fill window
- `ZoomVideoSDKVideoAspect_LetterBox` - Show full video with black bars

**Resolution Options**:
- `ZoomVideoSDKResolution_90P`
- `ZoomVideoSDKResolution_180P`
- `ZoomVideoSDKResolution_360P` - Good balance
- `ZoomVideoSDKResolution_720P` - HD quality
- `ZoomVideoSDKResolution_1080P`
- `ZoomVideoSDKResolution_Auto` - Let SDK decide (recommended)

### 🔧 Raw Data Pipe (Advanced Use Cases)

**Best for**: Custom video processing, effects, recording, computer vision

You receive raw YUV420 frames and handle rendering yourself.

```cpp
// 1. Create a delegate to receive frames
class VideoRenderer : public IZoomVideoSDKRawDataPipeDelegate {
public:
    void onRawDataFrameReceived(YUVRawDataI420* data) override {
        int width = data->GetStreamWidth();
        int height = data->GetStreamHeight();

        char* yBuffer = data->GetYBuffer();
        char* uBuffer = data->GetUBuffer();
        char* vBuffer = data->GetVBuffer();

        // Convert YUV420 to RGB and render
        ConvertYUVToRGB(yBuffer, uBuffer, vBuffer, width, height);
        RenderToWindow(rgbBuffer, width, height);
    }

    void onRawDataStatusChanged(RawDataStatus status) override {
        // Handle video on/off
    }
};

// 2. Subscribe to raw data
IZoomVideoSDKRawDataPipe* pipe = user->GetVideoPipe();
VideoRenderer* renderer = new VideoRenderer();
pipe->subscribe(ZoomVideoSDKResolution_720P, renderer);
```

**YUV420 to RGB Conversion** (ITU-R BT.601):
```cpp
void ConvertYUV420ToRGB(char* yBuffer, char* uBuffer, char* vBuffer,
                        int width, int height) {
    for (int y = 0; y < height; y++) {
        for (int x = 0; x < width; x++) {
            int yIndex = y * width + x;
            int uvIndex = (y / 2) * (width / 2) + (x / 2);

            int Y = (unsigned char)yBuffer[yIndex];
            int U = (unsigned char)uBuffer[uvIndex];
            int V = (unsigned char)vBuffer[uvIndex];

            // YUV to RGB conversion
            int C = Y - 16;
            int D = U - 128;
            int E = V - 128;

            int R = (298 * C + 409 * E + 128) >> 8;
            int G = (298 * C - 100 * D - 208 * E + 128) >> 8;
            int B = (298 * C + 516 * D + 128) >> 8;

            // Clamp to [0, 255]
            R = (R < 0) ? 0 : (R > 255) ? 255 : R;
            G = (G < 0) ? 0 : (G > 255) ? 255 : G;
            B = (B < 0) ? 0 : (B > 255) ? 255 : B;

            // Store RGB (BGR format for Windows)
            rgbBuffer[yIndex * 3 + 0] = (unsigned char)B;
            rgbBuffer[yIndex * 3 + 1] = (unsigned char)G;
            rgbBuffer[yIndex * 3 + 2] = (unsigned char)R;
        }
    }
}
```

**Render with GDI**:
```cpp
void RenderToWindow(unsigned char* rgbBuffer, int width, int height) {
    HDC hdc = GetDC(hwnd);

    BITMAPINFO bmi = {};
    bmi.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
    bmi.bmiHeader.biWidth = width;
    bmi.bmiHeader.biHeight = -height;  // Negative for top-down
    bmi.bmiHeader.biPlanes = 1;
    bmi.bmiHeader.biBitCount = 24;     // 24-bit RGB
    bmi.bmiHeader.biCompression = BI_RGB;

    RECT rect;
    GetClientRect(hwnd, &rect);

    StretchDIBits(hdc,
        0, 0, rect.right, rect.bottom,  // Destination
        0, 0, width, height,              // Source
        rgbBuffer, &bmi,
        DIB_RGB_COLORS, SRCCOPY);

    ReleaseDC(hwnd, hdc);
}
```

**Disadvantages**:
- ⚠️ **CPU intensive** - YUV conversion can cause frame drops
- ⚠️ **Artifacts** - Manual rendering may show tearing/artifacts
- ⚠️ **Complex** - More code to maintain
- ⚠️ **Performance** - Slower than Canvas API

**Use Raw Data When**:
- Adding video filters/effects
- Recording to custom formats
- Computer vision processing
- Custom compositing
- Streaming to non-standard outputs

### Self Video vs Remote Users

**Self Video** (your own camera):

**Option A: Canvas API**
```cpp
IZoomVideoSDKSession* session = sdk->getSessionInfo();
IZoomVideoSDKUser* myself = session->getMyself();
IZoomVideoSDKCanvas* canvas = myself->GetVideoCanvas();
canvas->subscribeWithView(selfVideoHwnd, aspect, resolution);
```

**Option B: Video Preview** (for self only)
```cpp
IZoomVideoSDKVideoHelper* videoHelper = sdk->getVideoHelper();
videoHelper->startVideo();  // Start transmission

// For preview rendering
videoHelper->startVideoCanvasPreview(selfVideoHwnd, aspect, resolution);
```

**Remote Users** (other participants):

**Canvas API** (recommended):
```cpp
// In onUserJoin callback
void onUserJoin(IZoomVideoSDKUserHelper*, IVideoSDKVector<IZoomVideoSDKUser*>* userList) {
    for (int i = 0; i < userList->GetCount(); i++) {
        IZoomVideoSDKUser* user = userList->GetItem(i);
        IZoomVideoSDKCanvas* canvas = user->GetVideoCanvas();
        canvas->subscribeWithView(userVideoHwnd, aspect, resolution);
    }
}
```

### Event-Driven Subscription Pattern

⚠️ **CRITICAL**: Video subscription must be **event-driven** and **manual**.

**Key Events**:

1. **`onSessionJoin`** - Subscribe to self video
2. **`onUserJoin`** - Subscribe to new remote users
3. **`onUserVideoStatusChanged`** - Re-subscribe when video turns on/off
4. **`onUserLeave`** - Unsubscribe and cleanup

**Complete Pattern**:

```cpp
class MainFrame : public IZoomVideoSDKDelegate {
private:
    std::map<IZoomVideoSDKUser*, IZoomVideoSDKCanvas*> subscribedUsers_;
    HWND videoWindow_;

public:
    void onSessionJoin() override {
        // Start your own video
        IZoomVideoSDKVideoHelper* videoHelper = sdk->getVideoHelper();
        videoHelper->startVideo();

        // Subscribe to self video
        IZoomVideoSDKUser* myself = sdk->getSessionInfo()->getMyself();
        SubscribeToUser(myself);
    }

    void onUserJoin(IZoomVideoSDKUserHelper*,
                    IVideoSDKVector<IZoomVideoSDKUser*>* userList) override {
        // Get current user to exclude self
        IZoomVideoSDKUser* myself = sdk->getSessionInfo()->getMyself();

        for (int i = 0; i < userList->GetCount(); i++) {
            IZoomVideoSDKUser* user = userList->GetItem(i);

            // IMPORTANT: Only subscribe to REMOTE users!
            if (user != myself) {
                SubscribeToUser(user);
            }
        }
    }

    void onUserVideoStatusChanged(IZoomVideoSDKVideoHelper*,
                                  IVideoSDKVector<IZoomVideoSDKUser*>* userList) override {
        IZoomVideoSDKUser* myself = sdk->getSessionInfo()->getMyself();

        for (int i = 0; i < userList->GetCount(); i++) {
            IZoomVideoSDKUser* user = userList->GetItem(i);
            if (user != myself) {
                // Re-subscribe when video status changes
                SubscribeToUser(user);
            }
        }
    }

    void onUserLeave(IZoomVideoSDKUserHelper*,
                    IVideoSDKVector<IZoomVideoSDKUser*>* userList) override {
        for (int i = 0; i < userList->GetCount(); i++) {
            IZoomVideoSDKUser* user = userList->GetItem(i);
            UnsubscribeFromUser(user);
        }
    }

    void onSessionLeave() override {
        // Cleanup all subscriptions
        for (auto& pair : subscribedUsers_) {
            IZoomVideoSDKCanvas* canvas = pair.second;
            if (canvas) {
                canvas->unSubscribeWithView(videoWindow_);
            }
        }
        subscribedUsers_.clear();
    }

private:
    void SubscribeToUser(IZoomVideoSDKUser* user) {
        if (!user || subscribedUsers_.find(user) != subscribedUsers_.end())
            return;

        IZoomVideoSDKCanvas* canvas = user->GetVideoCanvas();
        if (canvas) {
            ZoomVideoSDKErrors ret = canvas->subscribeWithView(
                videoWindow_,
                ZoomVideoSDKVideoAspect_PanAndScan,
                ZoomVideoSDKResolution_Auto
            );

            if (ret == ZoomVideoSDKErrors_Success) {
                subscribedUsers_[user] = canvas;
            }
        }
    }

    void UnsubscribeFromUser(IZoomVideoSDKUser* user) {
        auto it = subscribedUsers_.find(user);
        if (it != subscribedUsers_.end()) {
            IZoomVideoSDKCanvas* canvas = it->second;
            if (canvas) {
                canvas->unSubscribeWithView(videoWindow_);
            }
            subscribedUsers_.erase(it);
        }
    }
};
```

**Key Points**:
- ✅ Subscribe in response to events (onUserJoin, onUserVideoStatusChanged)
- ✅ Always exclude current user from remote subscriptions
- ✅ Unsubscribe on onUserLeave
- ✅ Clean up all subscriptions on onSessionLeave
- ✅ Track subscriptions in a map for lifecycle management

### ⚠️ Screen Share Subscription (DIFFERENT from Video!)

**CRITICAL**: Screen share subscription uses `IZoomVideoSDKShareAction` from the callback, NOT `user->GetShareCanvas()`!

```cpp
// WRONG - This won't work for remote screen shares!
user->GetShareCanvas()->subscribeWithView(hwnd, ...);

// CORRECT - Use IZoomVideoSDKShareAction from onUserShareStatusChanged callback
void onUserShareStatusChanged(IZoomVideoSDKShareHelper* pShareHelper,
                               IZoomVideoSDKUser* pUser,
                               IZoomVideoSDKShareAction* pShareAction) {
    if (!pShareAction) return;

    ZoomVideoSDKShareStatus status = pShareAction->getShareStatus();

    if (status == ZoomVideoSDKShareStatus_Start ||
        status == ZoomVideoSDKShareStatus_Resume) {
        // Subscribe to the share using Canvas API
        IZoomVideoSDKCanvas* shareCanvas = pShareAction->getShareCanvas();
        if (shareCanvas) {
            shareCanvas->subscribeWithView(shareWindow_,
                ZoomVideoSDKVideoAspect_Original);
        }
    }
    else if (status == ZoomVideoSDKShareStatus_Stop) {
        // Unsubscribe when share stops
        IZoomVideoSDKCanvas* shareCanvas = pShareAction->getShareCanvas();
        if (shareCanvas) {
            shareCanvas->unSubscribeWithView(shareWindow_);
        }
    }
}
```

**Why is share different from video?**
- **Video**: Each user has one video stream → use `user->GetVideoCanvas()`
- **Share**: A user can have multiple share actions (multi-share) → use `IZoomVideoSDKShareAction*` from callback
- The `IZoomVideoSDKShareAction` object represents a specific share stream and contains the share status, type, and rendering interfaces

**See also**: [Screen Share Subscription Example](examples/screen-share-subscription.md)

### Multi-User Video Layout

For multiple participants, you need **one HWND per user**:

```cpp
// Create separate windows/panels for each user
HWND selfVideoWindow = CreateWindow(...);   // Your video
HWND user1Window = CreateWindow(...);       // User 1's video
HWND user2Window = CreateWindow(...);       // User 2's video

// Subscribe each user to their own window
myself->GetVideoCanvas()->subscribeWithView(selfVideoWindow, ...);
user1->GetVideoCanvas()->subscribeWithView(user1Window, ...);
user2->GetVideoCanvas()->subscribeWithView(user2Window, ...);
```

**Layout Strategies**:
- Grid layout (2x2, 3x3)
- Gallery view (scrollable)
- Active speaker (large) + thumbnails
- Picture-in-picture

### Common Video Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Video not showing | Not calling `startVideo()` | Call `videoHelper->startVideo()` in `onSessionJoin` |
| Artifacts/tearing | Using Raw Data Pipe | Switch to Canvas API |
| Poor performance | YUV conversion on UI thread | Use Canvas API or move conversion to worker thread |
| Video freezes | Not processing Windows messages | Add message pump to main loop |
| Can't see self | Subscribing to wrong user | Use `session->getMyself()` for self video |
| Seeing self in remote list | Not excluding self | Check `if (user != myself)` before subscribing |

## Complete Documentation Library

This skill includes comprehensive guides organized by category:

### Core Concepts (Start Here!)
- **[SDK Architecture Pattern](concepts/sdk-architecture-pattern.md)** - Universal 3-step pattern for ANY feature
- **[Singleton Hierarchy](concepts/singleton-hierarchy.md)** - 5-level navigation guide
- **[Canvas vs Raw Data](concepts/canvas-vs-raw-data.md)** - Choose your rendering approach

### Complete Examples
- **[Session Join Pattern](examples/session-join-pattern.md)** - JWT auth + session join with full code
- **[Video Rendering](examples/video-rendering.md)** - Canvas API video display
- **[Screen Share Subscription](examples/screen-share-subscription.md)** - View remote screen shares (DIFFERENT from video!)
- **[Raw Video Capture](examples/raw-video-capture.md)** - YUV420 frame capture
- **[Raw Audio Capture](examples/raw-audio-capture.md)** - PCM audio capture
- **[Send Raw Video](examples/send-raw-video.md)** - Virtual camera (inject custom video)
- **[Send Raw Audio](examples/send-raw-audio.md)** - Virtual mic (inject custom audio)
- **[Cloud Recording](examples/cloud-recording.md)** - Cloud recording control
- **[Command Channel](examples/command-channel.md)** - Custom command messaging
- **[Transcription](examples/transcription.md)** - Live transcription/captions

### UI Framework Integration
- **[Win32 Native](examples/dotnet-winforms/guide.md#option-1-win32-native-c---direct-sdk)** - Direct SDK usage with Canvas API (best performance)
- **[WinForms (.NET)](examples/dotnet-winforms/guide.md#option-2-winforms-c--ccli-wrapper)** - C++/CLI wrapper + Raw Data Pipe
- **[WPF (.NET)](examples/dotnet-winforms/guide.md#option-3-wpf-c--ccli-wrapper)** - C++/CLI wrapper + BitmapSource conversion
- **[Production Quality Guidelines](examples/dotnet-winforms/guide.md#production-quality-review)** - Checklist and common issues

### C++/CLI Wrapper Patterns (Wrapping ANY Native Library)
- **[Complete Guide](examples/dotnet-winforms/guide.md#ccli-wrapper-patterns-for-net-integration)** - 8 patterns for native→.NET interop
- **[Pattern 1: Basic Structure](examples/dotnet-winforms/guide.md#pattern-1-basic-wrapper-structure)** - Project setup, class layout
- **[Pattern 2: void* Pointers](examples/dotnet-winforms/guide.md#pattern-2-opaque-void-pointers)** - Hide native types
- **[Pattern 3: gcroot Callbacks](examples/dotnet-winforms/guide.md#pattern-3-gcrootT-for-nativemanaged-callbacks)** - Native→Managed events
- **[Pattern 4: IDisposable](examples/dotnet-winforms/guide.md#pattern-4-destructor--finalizer-idisposable)** - Cleanup pattern
- **[Pattern 5: Strings](examples/dotnet-winforms/guide.md#pattern-5-string-conversion)** - String^ ↔ wstring/string
- **[Pattern 6: Arrays](examples/dotnet-winforms/guide.md#pattern-6-arraybuffer-conversion)** - pin_ptr, Marshal::Copy
- **[Pattern 7: Threading](examples/dotnet-winforms/guide.md#pattern-7-thread-marshaling-native-thread--ui-thread)** - UI thread dispatch
- **[Pattern 8: LockBits](examples/dotnet-winforms/guide.md#pattern-8-lockbits-for-fast-image-manipulation)** - Fast image conversion
- **[Common Errors](examples/dotnet-winforms/guide.md#common-wrapper-errors)** - Troubleshooting

### Troubleshooting
- **[Windows Message Loop](troubleshooting/windows-message-loop.md)** - **CRITICAL**: Why callbacks don't fire
- **[Build Errors](troubleshooting/build-errors.md)** - SDK header dependency fixes
- **[Common Issues](troubleshooting/common-issues.md)** - Quick diagnostics & error codes

### References
- **[API Reference](references/windows-reference.md)** - 5-level API hierarchy, methods, error codes
- **[Delegate Methods](references/delegate-methods.md)** - All 80+ callback methods
- **[SKILL.md](SKILL.md)** - Complete navigation guide

### Most Critical Issues (From Real Debugging)

1. **Callbacks not firing** → Missing Windows message loop (99% of issues)
   - See: [Windows Message Loop Guide](troubleshooting/windows-message-loop.md)

2. **Video subscribe returns error 2** → Subscribing too early
   - See: [Video Rendering](examples/video-rendering.md) - Subscribe in `onUserVideoStatusChanged`

3. **Abstract class errors** → Missing virtual method implementations
   - See: [Delegate Methods](references/delegate-methods.md)

### Key Insight

**Once you learn the 3-step pattern, you can implement ANY feature:**
1. Get singleton → 2. Implement delegate → 3. Subscribe & use

See: [SDK Architecture Pattern](concepts/sdk-architecture-pattern.md)

## Resources

- **Official Docs**: https://developers.zoom.us/docs/video-sdk/windows/
- **API Reference**: https://marketplacefront.zoom.us/sdk/custom/windows/
- **Dev Forum**: https://devforum.zoom.us/
- **GitHub Samples**: https://github.com/zoom/videosdk-windows-rawdata-sample
- **Working Sample**: `C:\tempsdk\zoom-video-sdk-windows-sample\` (complete implementation)

---

**Need help?** Start with [SKILL.md](SKILL.md) for complete navigation.


## Merged from video-sdk/windows/SKILL.md

# Zoom Video SDK Windows - Complete Documentation Index

## Quick Start Path

**If you're new to the SDK, follow this order:**

0. **Overview** → [windows.md](windows.md)
1. **Read the architecture pattern** → [concepts/sdk-architecture-pattern.md](concepts/sdk-architecture-pattern.md)
   - Universal formula: Singleton → Delegate → Subscribe
   - Once you understand this, you can implement any feature

2. **Fix build errors** → [troubleshooting/build-errors.md](troubleshooting/build-errors.md)
   - SDK header dependencies
   - Required include order

3. **Implement session join** → [examples/session-join-pattern.md](examples/session-join-pattern.md)
   - Complete working JWT + session join code

4. **Fix callback issues** → [troubleshooting/windows-message-loop.md](troubleshooting/windows-message-loop.md)
   - **CRITICAL**: Why callbacks don't fire without Windows message loop

5. **Implement video** → [examples/video-rendering.md](examples/video-rendering.md)
   - Canvas API (SDK-rendered) vs Raw Data Pipe

6. **Troubleshoot any issues** → [troubleshooting/common-issues.md](troubleshooting/common-issues.md)
   - Quick diagnostic checklist
   - Error code tables

---

## Documentation Structure

```
video-sdk/windows/
├── SKILL.md                           # Main skill overview
├── SKILL.md                           # This file - navigation guide
├── windows.md                          # Secondary overview doc (pointer-style)
│
├── concepts/                          # Core architectural patterns
│   ├── sdk-architecture-pattern.md   # Universal formula for ANY feature
│   ├── singleton-hierarchy.md        # 5-level navigation guide
│   └── canvas-vs-raw-data.md         # SDK-rendered vs self-rendered choice
│
├── examples/                          # Complete working code
│   ├── session-join-pattern.md       # JWT auth + session join
│   ├── video-rendering.md            # Canvas API video display
│   ├── screen-share-subscription.md  # View remote screen shares
│   ├── raw-video-capture.md          # YUV420 raw frame capture
│   ├── raw-audio-capture.md          # PCM audio capture
│   ├── send-raw-video.md             # Virtual camera (inject video)
│   ├── send-raw-audio.md             # Virtual mic (inject audio)
│   ├── cloud-recording.md            # Cloud recording control
│   ├── command-channel.md            # Custom command messaging
│   ├── transcription.md              # Live transcription/captions
│   └── dotnet-winforms/              # UI Framework integration
│       └── README.md                 # Win32, WinForms, WPF patterns
│                                     # C++/CLI wrapper patterns
│                                     # Production quality guidelines
│
├── troubleshooting/                   # Problem solving guides
│   ├── windows-message-loop.md       # CRITICAL - Why callbacks fail
│   ├── build-errors.md               # Header dependency fixes
│   └── common-issues.md              # Quick diagnostic workflow
│
└── references/                        # Reference documentation
    ├── windows-reference.md           # API hierarchy, methods, error codes
    ├── delegate-methods.md            # All 80+ callback methods
    └── samples.md                     # Official samples guide
```

---

## By Use Case

### I want to build a video app
1. [SDK Architecture Pattern](concepts/sdk-architecture-pattern.md) - Understand the pattern
2. [Session Join Pattern](examples/session-join-pattern.md) - Join sessions
3. [Video Rendering](examples/video-rendering.md) - Display video
4. [Windows Message Loop](troubleshooting/windows-message-loop.md) - Fix callback issues

### I'm getting build errors
1. [Build Errors Guide](troubleshooting/build-errors.md) - SDK header dependencies
2. [Delegate Methods](references/delegate-methods.md) - Abstract class errors
3. [Common Issues](troubleshooting/common-issues.md) - Linker errors

### I'm getting runtime errors
1. [Windows Message Loop](troubleshooting/windows-message-loop.md) - Callbacks not firing
2. [Common Issues](troubleshooting/common-issues.md) - Error code tables

### I want to view screen shares
1. [Screen Share Subscription](examples/screen-share-subscription.md) - **DIFFERENT from video!**
2. [SDK Architecture Pattern](concepts/sdk-architecture-pattern.md) - Event-driven pattern
3. [Video Rendering](examples/video-rendering.md) - Compare with video subscription

### I want to capture raw video/audio
1. [Canvas vs Raw Data](concepts/canvas-vs-raw-data.md) - Choose your approach
2. [Raw Video Capture](examples/raw-video-capture.md) - YUV420 frame capture
3. [Raw Audio Capture](examples/raw-audio-capture.md) - PCM audio capture
4. [SDK Architecture Pattern](concepts/sdk-architecture-pattern.md) - Subscription pattern

### I want to send custom video/audio (virtual camera/mic)
1. [Send Raw Video](examples/send-raw-video.md) - Inject custom video frames
2. [Send Raw Audio](examples/send-raw-audio.md) - Inject custom audio
3. [SDK Architecture Pattern](concepts/sdk-architecture-pattern.md) - External source pattern

### I want to record sessions
1. [Cloud Recording](examples/cloud-recording.md) - Start/stop cloud recording
2. [API Reference](references/windows-reference.md) - Recording helper methods

### I want to use live transcription
1. [Transcription](examples/transcription.md) - Enable live captions
2. [Delegate Methods](references/delegate-methods.md) - Transcription callbacks

### I want custom messaging between participants
1. [Command Channel](examples/command-channel.md) - Send custom commands
2. [API Reference](references/windows-reference.md) - Command channel methods

### I want to build a Win32 native app
1. [Win32 Integration](examples/dotnet-winforms/guide.md#option-1-win32-native-c---direct-sdk) - Direct SDK + Canvas API
2. [Video Rendering](examples/video-rendering.md) - Canvas API patterns
3. [Production Guidelines](examples/dotnet-winforms/guide.md#production-quality-review) - Best practices

### I want to build a WinForms (.NET) app
1. [WinForms Integration](examples/dotnet-winforms/guide.md#option-2-winforms-c--ccli-wrapper) - C++/CLI wrapper + Raw Data
2. [C++/CLI Patterns](examples/dotnet-winforms/guide.md#ccli-wrapper-patterns-for-net-integration) - gcroot, Finalizer, LockBits
3. [Production Guidelines](examples/dotnet-winforms/guide.md#production-quality-review) - IDisposable, thread safety

### I want to build a WPF (.NET) app
1. [WPF Integration](examples/dotnet-winforms/guide.md#option-3-wpf-c--ccli-wrapper) - C++/CLI + BitmapSource
2. [Bitmap Conversion](examples/dotnet-winforms/guide.md#2-bitmap--bitmapsource-conversion) - Freeze(), Dispatcher
3. [Production Guidelines](examples/dotnet-winforms/guide.md#production-quality-review) - Performance optimization

### I want to use C# / .NET Framework (general)
1. [.NET Integration Overview](examples/dotnet-winforms/guide.md) - **Complete C++/CLI wrapper guide**
2. [Raw Video Capture](examples/raw-video-capture.md) - YUV→RGB conversion patterns
3. [Session Join Pattern](examples/session-join-pattern.md) - SDK initialization flow

### I want to wrap ANY native C++ library for .NET
1. [C++/CLI Wrapper Patterns](examples/dotnet-winforms/guide.md#ccli-wrapper-patterns-for-net-integration) - **Complete 8-pattern guide**
2. [Pattern 1: Basic Structure](examples/dotnet-winforms/guide.md#pattern-1-basic-wrapper-structure) - Project setup + class layout
3. [Pattern 3: gcroot Callbacks](examples/dotnet-winforms/guide.md#pattern-3-gcrootT-for-nativemanaged-callbacks) - Native→Managed events
4. [Pattern 4: IDisposable](examples/dotnet-winforms/guide.md#pattern-4-destructor--finalizer-idisposable) - Cleanup pattern
5. [Common Errors](examples/dotnet-winforms/guide.md#common-wrapper-errors) - Troubleshooting

### I want to implement a specific feature
1. [SDK Architecture Pattern](concepts/sdk-architecture-pattern.md) - **START HERE!**
2. [Singleton Hierarchy](concepts/singleton-hierarchy.md) - Navigate to the feature
3. [API Reference](references/windows-reference.md) - Method signatures

---

## Most Critical Documents

### 1. SDK Architecture Pattern (MASTER DOCUMENT)
**[concepts/sdk-architecture-pattern.md](concepts/sdk-architecture-pattern.md)**

The universal 3-step pattern:
1. Get singleton (SDK, helpers, session, users)
2. Implement delegate (event callbacks)
3. Subscribe and use

### 2. Windows Message Loop (MOST COMMON ISSUE)
**[troubleshooting/windows-message-loop.md](troubleshooting/windows-message-loop.md)**

99% of "callbacks not firing" issues are caused by missing Windows message loop.

### 3. Singleton Hierarchy (NAVIGATION MAP)
**[concepts/singleton-hierarchy.md](concepts/singleton-hierarchy.md)**

5-level deep navigation showing how to reach every feature.

---

## Key Learnings

### Critical Discoveries:

1. **Windows Message Loop is MANDATORY**
   - SDK uses Windows message pump for callbacks
   - Without it, callbacks are queued but never fire
   - See: [Windows Message Loop Guide](troubleshooting/windows-message-loop.md)

2. **Subscribe in onUserVideoStatusChanged, NOT onUserJoin**
   - Video may not be ready when user joins
   - Wait for video status change callback
   - See: [Video Rendering](examples/video-rendering.md)

3. **Two Rendering Paths**
   - Canvas API: SDK renders to your HWND (recommended)
   - Raw Data Pipe: You receive YUV frames (advanced)
   - See: [Canvas vs Raw Data](concepts/canvas-vs-raw-data.md)

4. **Helpers Control YOUR Streams Only**
   - `videoHelper->startVideo()` starts YOUR camera
   - To see others, subscribe to their Canvas/Pipe
   - See: [Singleton Hierarchy](concepts/singleton-hierarchy.md)

5. **UI Framework Integration Differs by Platform**
   - **Win32**: Direct SDK, Canvas API (SDK renders to HWND) - best performance
   - **WinForms**: C++/CLI wrapper, Raw Data Pipe, YUV→Bitmap, InvokeRequired
   - **WPF**: Same wrapper + Bitmap→BitmapSource, Dispatcher, Freeze()
   - See: [UI Framework Integration](examples/dotnet-winforms/guide.md)

6. **C++/CLI Wrapper Patterns (for ANY native library → .NET)**
   - `void*` pointers - hide native types from managed headers
   - `gcroot<T^>` - prevent GC from collecting managed references in native code
   - Finalizer + Destructor - `~Class()` and `!Class()` for IDisposable cleanup
   - `pin_ptr` + `Marshal::Copy` - array/buffer conversion
   - `LockBits` - 100x faster than SetPixel for image manipulation
   - Thread marshaling - InvokeRequired (WinForms) / Dispatcher (WPF)
   - See: [C++/CLI Wrapper Guide](examples/dotnet-winforms/guide.md#ccli-wrapper-patterns-for-net-integration)

7. **Audio Connection Timing**
   - Set `audioOption.connect = false` during join
   - Call `startAudio()` in `onSessionJoin` callback
   - See: [Production Guidelines](examples/dotnet-winforms/guide.md#production-quality-review)

---

## Quick Reference

### "My code won't compile"
→ [Build Errors Guide](troubleshooting/build-errors.md)

### "Callbacks never fire"
→ [Windows Message Loop](troubleshooting/windows-message-loop.md)

### "Video subscription returns error 2"
→ [Video Rendering](examples/video-rendering.md) - Subscribe in onUserVideoStatusChanged

### "Abstract class error"
→ [Delegate Methods](references/delegate-methods.md)

### "How do I implement [feature]?"
→ [SDK Architecture Pattern](concepts/sdk-architecture-pattern.md)

### "How do I navigate to [controller]?"
→ [Singleton Hierarchy](concepts/singleton-hierarchy.md)

### "What error code means what?"
→ [Common Issues](troubleshooting/common-issues.md)

---

## Document Version

Based on **Zoom Video SDK for Windows v2.x**

---

**Happy coding!**

Remember: The [SDK Architecture Pattern](concepts/sdk-architecture-pattern.md) is your key to unlocking the entire SDK. Read it first!

## Operations

- [RUNBOOK.md](RUNBOOK.md) - 5-minute preflight and debugging checklist.
