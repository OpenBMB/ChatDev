---
name: zoom-meeting-sdk-windows
description: |
  Zoom Meeting SDK for Windows - Native C++ SDK for embedding Zoom meetings into Windows desktop
  applications. Supports custom UI architecture with raw video/audio data, headless bots, and deep
  integration with meeting features. Includes SDK architecture patterns and Windows message loop handling.
---

# Zoom Meeting SDK (Windows)

Embed Zoom meeting capabilities into Windows desktop applications for native C++ integrations and headless bots.

## New to Zoom SDK? Start Here!

**The fastest way to master the SDK:**

1. **[SDK Architecture Pattern](concepts/sdk-architecture-pattern.md)** - Learn the universal pattern that works for ALL 35+ features
2. **[Authentication Pattern](examples/authentication-pattern.md)** - Get a working bot joining meetings
3. **[Windows Message Loop](troubleshooting/windows-message-loop.md)** - Fix the #1 reason callbacks don't fire

**Building a Custom UI?**
- [Custom UI Architecture](concepts/custom-ui-architecture.md) - How SDK rendering actually works (child HWNDs, D3D, etc.)
- [Custom UI Video Rendering Example](examples/custom-ui-video-rendering.md) - Complete working code
- [SDK-Rendered vs Self-Rendered](concepts/custom-ui-vs-raw-data.md) - Choose the right approach
- [Custom UI Interface Methods](references/interface-methods.md) - All 13 required virtual methods

**Having issues?**
- Build errors → [Build Errors Guide](troubleshooting/build-errors.md)
- Callbacks not firing → [Windows Message Loop](troubleshooting/windows-message-loop.md)
- Quick diagnostics → [Common Issues](troubleshooting/common-issues.md)
- Performance / service quality → [service-quality.md](examples/service-quality.md)
- Deployment notes → [deployment.md](references/deployment.md)
- MSBuild from git bash → [Build Errors Guide](troubleshooting/build-errors.md#msbuild-command-pattern)
- Complete navigation → [SKILL.md](SKILL.md)

## Prerequisites

- Zoom app with Meeting SDK credentials (Client ID & Secret)
- Visual Studio 2019/2022 or later
- Windows 10 or later
- C++ development environment
- vcpkg for dependency management

> **Need help with authentication?** See the **[zoom-oauth](../../oauth/SKILL.md)** skill for JWT token generation.

## Project Preferences & Learnings

> **IMPORTANT**: These are hard-won preferences from real project experience. Follow these when creating new projects.

### Do NOT use CMake — Use native Visual Studio `.vcxproj`

**Always create a native Visual Studio `.sln` + `.vcxproj` project**, not a CMake project. Reasons:
- More standard and familiar for Windows C++ developers
- Developers can double-click the `.sln` to open in Visual Studio immediately
- Project settings (include dirs, lib dirs, preprocessor defines) are easier to see and edit in the VS Property Pages UI
- No extra CMake tooling or configuration step required
- Friendlier and easier for developers to understand and maintain

### `config.json` must be visible in Solution Explorer

The `config.json` file (containing `sdk_jwt`, `meeting_number`, `passcode`) must be:
1. **Included in the `.vcxproj`** as a `<None>` item with `<CopyToOutputDirectory>PreserveNewest</CopyToOutputDirectory>`
2. **Placed in a "Config" filter** in the `.vcxproj.filters` file so it appears under a "Config" folder in Solution Explorer
3. **Easily editable** by developers directly from Solution Explorer — they should never have to hunt for it in File Explorer

Example `.vcxproj` entry:
```xml
<ItemGroup>
  <None Include="config.json">
    <CopyToOutputDirectory>PreserveNewest</CopyToOutputDirectory>
  </None>
</ItemGroup>
```

Example `.vcxproj.filters` entry:
```xml
<ItemGroup>
  <Filter Include="Config">
    <UniqueIdentifier>{GUID-HERE}</UniqueIdentifier>
  </Filter>
</ItemGroup>
<ItemGroup>
  <None Include="config.json">
    <Filter>Config</Filter>
  </None>
</ItemGroup>
```

## Overview

The Windows SDK is a **C++ native SDK** designed for:
- **Desktop applications** - Native Windows apps with full UI control
- **Headless bots** - Join meetings without UI
- **Raw media access** - Capture/send audio/video streams
- **Local recording** - Record meetings locally or to cloud

### Key Architectural Insight

The SDK follows a **universal 3-step pattern** for every feature:
1. **Get controller** (singleton): `meetingService->Get[Feature]Controller()`
2. **Implement event listener**: `class MyListener : public I[Feature]Event { ... }`
3. **Register and use**: `controller->SetEvent(listener)` then call methods

**This works for ALL features**: audio, video, chat, recording, participants, screen sharing, breakout rooms, webinars, Q&A, polling, whiteboard, and 20+ more!

Learn more: **[SDK Architecture Pattern Guide](concepts/sdk-architecture-pattern.md)**

## Quick Start

### 1. Download Windows SDK

Download from [Zoom Marketplace](https://marketplace.zoom.us/):
- Extract `zoom-meeting-sdk-windows_x86_64-{version}.zip`

### 2. Setup Project Structure

```
your-project/
  YourApp/
    SDK/
      x64/
        bin/          # DLL files and dependencies
        h/            # Header files
        lib/          # sdk.lib
      x86/
        bin/
        h/
        lib/
    YourApp.cpp
    YourApp.vcxproj
    config.json
```

Copy SDK files:
```cmd
xcopy /E /I sdk-package\x64 your-project\YourApp\SDK\x64\
xcopy /E /I sdk-package\x86 your-project\YourApp\SDK\x86\
```

### 3. Install Dependencies (vcpkg)

```powershell
# Install vcpkg
git clone https://github.com/Microsoft/vcpkg.git C:\vcpkg
cd C:\vcpkg
.\bootstrap-vcpkg.bat
.\vcpkg integrate install

# Install dependencies
.\vcpkg install jsoncpp:x64-windows
.\vcpkg install curl:x64-windows
```

### 4. Configure Visual Studio Project

**Project Properties → C/C++ → General → Additional Include Directories:**
```
$(SolutionDir)SDK\$(PlatformTarget)\h
C:\vcpkg\packages\jsoncpp_x64-windows\include
C:\vcpkg\packages\curl_x64-windows\include
```

**Project Properties → Linker → General → Additional Library Directories:**
```
$(SolutionDir)SDK\$(PlatformTarget)\lib
```

**Project Properties → Linker → Input → Additional Dependencies:**
```
sdk.lib
```

**Post-Build Event** (Copy DLLs to output):
```cmd
xcopy /Y /D "$(SolutionDir)SDK\$(PlatformTarget)\bin\*.*" "$(OutDir)"
```

### 5. Configure Credentials

Create `config.json`:
```json
{
  "sdk_jwt": "YOUR_JWT_TOKEN",
  "meeting_number": "1234567890",
  "passcode": "password123",
  "zak": ""
}
```

### 6. Build & Run

- Open solution in Visual Studio
- Select x64 or x86 configuration
- Press F5 to build and run

## Core Workflow

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  InitSDK    │───►│  AuthSDK    │───►│ JoinMeeting │───►│ Raw Data    │
│             │    │  (JWT)      │    │             │    │ Subscribe   │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
                         │                   │
                         ▼                   ▼
                   OnAuthComplete      onInMeeting
                     callback           callback
```

**⚠️ CRITICAL**: Add Windows message loop or callbacks won't fire!
```cpp
while (!done) {
    MSG msg;
    while (PeekMessage(&msg, NULL, 0, 0, PM_REMOVE)) {
        TranslateMessage(&msg);
        DispatchMessage(&msg);
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(100));
}
```
See: [Windows Message Loop Guide](troubleshooting/windows-message-loop.md)

## Code Examples

> **💡 Pro Tip**: These are minimal examples. For complete, tested code see:
> - [Authentication Pattern](examples/authentication-pattern.md) - Full auth workflow
> - [Raw Video Capture](examples/raw-video-capture.md) - Complete video capture
> - [SDK Architecture Pattern](concepts/sdk-architecture-pattern.md) - Implement any feature

### Important: Include Order

**CRITICAL**: Include headers in this exact order or you'll get build errors:

```cpp
#include <windows.h>      // MUST be first
#include <cstdint>         // MUST be second (SDK headers use uint32_t)
// ... other standard headers ...
#include <zoom_sdk.h>
#include <meeting_service_components/meeting_audio_interface.h>  // BEFORE participants!
#include <meeting_service_components/meeting_participants_ctrl_interface.h>
```

See: [Build Errors Guide](troubleshooting/build-errors.md) for all dependency fixes.

### 1. Initialize SDK

```cpp
#include <windows.h>
#include <cstdint>
#include <zoom_sdk.h>

using namespace ZOOM_SDK_NAMESPACE;

bool InitMeetingSDK() {
    InitParam initParam;
    initParam.strWebDomain = L"https://zoom.us";
    initParam.strSupportUrl = L"https://zoom.us";
    initParam.emLanguageID = LANGUAGE_English;
    initParam.enableLogByDefault = true;
    initParam.enableGenerateDump = true;

    SDKError err = InitSDK(initParam);
    if (err != SDKERR_SUCCESS) {
        std::wcout << L"InitSDK failed: " << err << std::endl;
        return false;
    }
    return true;
}
```

### 2. Authenticate with JWT

```cpp
#include <windows.h>
#include <cstdint>
#include <auth_service_interface.h>
#include "AuthServiceEventListener.h"

IAuthService* authService = nullptr;

void OnAuthenticationComplete() {
    std::cout << "Authentication successful!" << std::endl;
    JoinMeeting();  // Proceed to join meeting
}

bool AuthenticateSDK(const std::wstring& jwtToken) {
    CreateAuthService(&authService);
    if (!authService) return false;

    // Set event listener BEFORE calling SDKAuth
    authService->SetEvent(new AuthServiceEventListener(&OnAuthenticationComplete));

    // Authenticate with JWT
    AuthContext authContext;
    authContext.jwt_token = jwtToken.c_str();

    SDKError err = authService->SDKAuth(authContext);
    if (err != SDKERR_SUCCESS) {
        std::wcout << L"SDKAuth failed: " << err << std::endl;
        return false;
    }

    // CRITICAL: Add message loop or callback won't fire!
    // See complete example: examples/authentication-pattern.md

    return true;
}
```

**AuthServiceEventListener.h:**
```cpp
#include <windows.h>
#include <cstdint>
#include <auth_service_interface.h>
#include <iostream>

using namespace ZOOM_SDK_NAMESPACE;

class AuthServiceEventListener : public IAuthServiceEvent {
public:
    AuthServiceEventListener(void (*onComplete)())
        : onAuthComplete(onComplete) {}

    void onAuthenticationReturn(AuthResult ret) override {
        if (ret == AUTHRET_SUCCESS && onAuthComplete) {
            onAuthComplete();
        } else {
            std::cout << "Auth failed: " << ret << std::endl;
        }
    }

    // Must implement ALL pure virtual methods (6 total)
    void onLoginReturnWithReason(LOGINSTATUS ret, IAccountInfo* info, LoginFailReason reason) override {}
    void onLogout() override {}
    void onZoomIdentityExpired() override {}
    void onZoomAuthIdentityExpired() override {}
#if defined(WIN32)
    void onNotificationServiceStatus(SDKNotificationServiceStatus status, SDKNotificationServiceError error) override {}
#endif

private:
    void (*onAuthComplete)();
};
```

**See complete working code**: [Authentication Pattern Guide](examples/authentication-pattern.md)

### 3. Join Meeting

```cpp
#include <meeting_service_interface.h>
#include "MeetingServiceEventListener.h"

IMeetingService* meetingService = nullptr;

void OnMeetingJoined() {
    std::cout << "Joining meeting..." << std::endl;
}

void OnInMeeting() {
    std::cout << "In meeting now!" << std::endl;
    // Start raw data capture here
}

void OnMeetingEnds() {
    std::cout << "Meeting ended" << std::endl;
}

bool JoinMeeting(UINT64 meetingNumber, const std::wstring& password) {
    CreateMeetingService(&meetingService);
    if (!meetingService) return false;

    // Set event listener
    meetingService->SetEvent(
        new MeetingServiceEventListener(&OnMeetingJoined, &OnMeetingEnds, &OnInMeeting)
    );

    // Prepare join parameters
    JoinParam joinParam;
    joinParam.userType = SDK_UT_WITHOUT_LOGIN;

    JoinParam4WithoutLogin& params = joinParam.param.withoutloginuserJoin;
    params.meetingNumber = meetingNumber;
    params.userName = L"Bot User";
    params.psw = password.c_str();
    params.isVideoOff = false;
    params.isAudioOff = false;

    SDKError err = meetingService->Join(joinParam);
    if (err != SDKERR_SUCCESS) {
        std::wcout << L"Join failed: " << err << std::endl;
        return false;
    }
    return true;
}
```

**MeetingServiceEventListener.h:**
```cpp
#include <windows.h>
#include <cstdint>
#include <meeting_service_interface.h>
#include <iostream>

using namespace ZOOM_SDK_NAMESPACE;

class MeetingServiceEventListener : public IMeetingServiceEvent {
public:
    MeetingServiceEventListener(
        void (*onJoined)(),
        void (*onEnded)(),
        void (*onInMeeting)()
    ) : onMeetingJoined(onJoined),
        onMeetingEnded(onEnded),
        onInMeetingCallback(onInMeeting) {}

    void onMeetingStatusChanged(MeetingStatus status, int iResult) override {
        if (status == MEETING_STATUS_CONNECTING) {
            if (onMeetingJoined) onMeetingJoined();
        }
        else if (status == MEETING_STATUS_INMEETING) {
            if (onInMeetingCallback) onInMeetingCallback();
        }
        else if (status == MEETING_STATUS_ENDED) {
            if (onMeetingEnded) onMeetingEnded();
        }
    }

    // Must implement ALL pure virtual methods (9 total)
    void onMeetingStatisticsWarningNotification(StatisticsWarningType type) override {}
    void onMeetingParameterNotification(const MeetingParameter* param) override {}
    void onSuspendParticipantsActivities() override {}
    void onAICompanionActiveChangeNotice(bool isActive) override {}
    void onMeetingTopicChanged(const zchar_t* sTopic) override {}
    void onMeetingFullToWatchLiveStream(const zchar_t* sLiveStreamUrl) override {}
    void onUserNetworkStatusChanged(MeetingComponentType type, ConnectionQuality level, unsigned int userId, bool uplink) override {}
#if defined(WIN32)
    void onAppSignalPanelUpdated(IMeetingAppSignalHandler* pHandler) override {}
#endif

private:
    void (*onMeetingJoined)();
    void (*onMeetingEnded)();
    void (*onInMeetingCallback)();
};
```

**See all required methods**: [Interface Methods Guide](references/interface-methods.md)

### 4. Subscribe to Raw Video

```cpp
#include <windows.h>
#include <cstdint>
#include <rawdata/zoom_rawdata_api.h>
#include <rawdata/rawdata_renderer_interface.h>
#include <zoom_sdk_raw_data_def.h>  // REQUIRED for YUVRawDataI420
#include "ZoomSDKRendererDelegate.h"

IZoomSDKRenderer* videoHelper = nullptr;
ZoomSDKRendererDelegate* videoSource = new ZoomSDKRendererDelegate();

bool StartVideoCapture(uint32_t userId) {
    // STEP 1: Start raw recording FIRST (required!)
    IMeetingRecordingController* recordCtrl =
        meetingService->GetMeetingRecordingController();

    SDKError canStart = recordCtrl->CanStartRawRecording();
    if (canStart != SDKERR_SUCCESS) {
        std::cout << "Cannot start recording: " << canStart << std::endl;
        return false;
    }

    recordCtrl->StartRawRecording();

    // Wait for recording to initialize
    std::this_thread::sleep_for(std::chrono::milliseconds(500));

    // STEP 2: Create renderer
    SDKError err = createRenderer(&videoHelper, videoSource);
    if (err != SDKERR_SUCCESS || !videoHelper) {
        std::cout << "createRenderer failed: " << err << std::endl;
        return false;
    }

    // STEP 3: Set resolution and subscribe
    videoHelper->setRawDataResolution(ZoomSDKResolution_720P);
    err = videoHelper->subscribe(userId, RAW_DATA_TYPE_VIDEO);
    if (err != SDKERR_SUCCESS) {
        std::cout << "Subscribe failed: " << err << std::endl;
        return false;
    }

    std::cout << "Video capture started! Frames arrive in onRawDataFrameReceived()" << std::endl;
    return true;
}
```

**ZoomSDKRendererDelegate.h:**
```cpp
#include <windows.h>
#include <cstdint>
#include <rawdata/rawdata_renderer_interface.h>
#include <zoom_sdk_raw_data_def.h>
#include <fstream>
#include <iostream>

using namespace ZOOM_SDK_NAMESPACE;

class ZoomSDKRendererDelegate : public IZoomSDKRendererDelegate {
public:
    void onRawDataFrameReceived(YUVRawDataI420* data) override {
        if (!data) return;

        // YUV420 (I420) format: Y plane + U plane + V plane
        int width = data->GetStreamWidth();
        int height = data->GetStreamHeight();

        // Calculate buffer sizes
        // Y = full resolution, U/V = quarter resolution each
        size_t ySize = width * height;
        size_t uvSize = ySize / 4;  // (width/2) * (height/2)

        // Total size: width * height * 1.5 bytes

        // Save to file (playback: ffplay -f rawvideo -pixel_format yuv420p -video_size 1280x720 output.yuv)
        std::ofstream outputFile("output.yuv", std::ios::binary | std::ios::app);
        outputFile.write(data->GetYBuffer(), ySize);    // Brightness
        outputFile.write(data->GetUBuffer(), uvSize);   // Blue-difference
        outputFile.write(data->GetVBuffer(), uvSize);   // Red-difference
        outputFile.close();
    }

    void onRawDataStatusChanged(RawDataStatus status) override {
        std::cout << "Raw data status: " << status << std::endl;
    }

    void onRendererBeDestroyed() override {
        std::cout << "Renderer destroyed" << std::endl;
    }
};
```

**Complete video capture guide**: [Raw Video Capture Guide](examples/raw-video-capture.md)

### 5. Subscribe to Raw Audio

```cpp
#include <rawdata/rawdata_audio_helper_interface.h>

class ZoomSDKAudioRawDataDelegate : public IZoomSDKAudioRawDataDelegate {
public:
    void onMixedAudioRawDataReceived(AudioRawData* data) override {
        // Process PCM audio (mixed from all participants)
        std::ofstream pcmFile("audio.pcm", std::ios::binary | std::ios::app);
        pcmFile.write((char*)data->GetBuffer(), data->GetBufferLen());
        pcmFile.close();
    }

    void onOneWayAudioRawDataReceived(AudioRawData* data, uint32_t node_id) override {
        // Process audio from specific participant
    }
};

// Subscribe to audio
IZoomSDKAudioRawDataHelper* audioHelper = GetAudioRawdataHelper();
audioHelper->subscribe(new ZoomSDKAudioRawDataDelegate());
```

### 6. Main Message Loop (CRITICAL!)

**⚠️ WITHOUT THIS, CALLBACKS WON'T FIRE!**

```cpp
#include <windows.h>
#include <thread>
#include <chrono>

int main() {
    // Initialize COM
    CoInitialize(NULL);

    // Load config and initialize
    LoadConfig();
    InitMeetingSDK();
    AuthenticateSDK(sdk_jwt);

    // CRITICAL: Windows message loop for SDK callbacks
    // SDK uses Windows message pump to dispatch callbacks
    // Without this, callbacks are queued but NEVER fire!
    MSG msg;
    while (!g_exit) {
        // Process all pending Windows messages
        while (PeekMessage(&msg, NULL, 0, 0, PM_REMOVE)) {
            if (msg.message == WM_QUIT) {
                g_exit = true;
                break;
            }
            TranslateMessage(&msg);
            DispatchMessage(&msg);
        }

        // Small sleep to avoid busy-waiting
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }

    // Cleanup
    CleanSDK();
    CoUninitialize();

    return 0;
}
```

**Why message loop is critical**: The SDK uses Windows COM/messaging for async callbacks. Without `PeekMessage()`, the SDK queues messages but they're never retrieved/dispatched, so callbacks never execute.

**Symptoms without message loop**:
- Authentication timeout (even with valid JWT)
- Meeting join timeout
- No callback events fire
- Appears like network/auth issue but it's a message loop issue

**See detailed explanation**: [Windows Message Loop Guide](troubleshooting/windows-message-loop.md)

## Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| **Callbacks don't fire / Auth timeout** | Add Windows message loop → [Guide](troubleshooting/windows-message-loop.md) |
| **`uint32_t` / `AudioType` errors** | Fix include order → [Guide](troubleshooting/build-errors.md) |
| **Abstract class error** | Implement all virtual methods → [Guide](references/interface-methods.md) |
| **How to implement [feature]?** | Follow universal pattern → [Guide](concepts/sdk-architecture-pattern.md) |
| **Authentication fails** | Check JWT token & error codes → [Guide](troubleshooting/common-issues.md) |
| **No video frames received** | Call StartRawRecording() first → [Guide](examples/raw-video-capture.md) |

**Complete troubleshooting**: [Common Issues Guide](troubleshooting/common-issues.md)

## How to Implement Any Feature

The SDK has **35+ feature controllers** (audio, video, chat, recording, participants, screen sharing, breakout rooms, webinars, Q&A, polling, whiteboard, captions, AI companion, etc.).

**Universal pattern that works for ALL features:**

1. **Get the controller** (singleton):
   ```cpp
   IMeetingAudioController* audioCtrl = meetingService->GetMeetingAudioController();
   IMeetingChatController* chatCtrl = meetingService->GetMeetingChatController();
   // ... 33 more controllers available
   ```

2. **Implement event listener** (observer pattern):
   ```cpp
   class MyAudioListener : public IMeetingAudioCtrlEvent {
       void onUserAudioStatusChange(IList<IUserAudioStatus*>* lst) override {
           // React to audio events
       }
       // ... implement all required methods
   };
   ```

3. **Register and use**:
   ```cpp
   audioCtrl->SetEvent(new MyAudioListener());
   audioCtrl->MuteAudio(userId, true);  // Use feature
   ```

**Complete guide with examples**: [SDK Architecture Pattern](concepts/sdk-architecture-pattern.md)

## Available Examples

| Example | Description |
|---------|-------------|
| **SkeletonDemo** | Minimal join meeting - start here |
| **GetVideoRawData** | Subscribe to raw video streams |
| **GetAudioRawData** | Subscribe to raw audio streams |
| **SendVideoRawData** | Send custom video as virtual camera |
| **SendAudioRawData** | Send custom audio as virtual mic |
| **GetShareRawData** | Capture screen share content |
| **LocalRecording** | Local MP4 recording |
| **ChatDemo** | In-meeting chat functionality |
| **CaptionDemo** | Closed caption/live transcription |
| **BreakoutDemo** | Breakout room management |

## Detailed References

### 🎯 Core Concepts (START HERE!)
- **[concepts/sdk-architecture-pattern.md](concepts/sdk-architecture-pattern.md)** - **Universal pattern for implementing ANY feature** - Understanding this unlocks the entire SDK!

### 📚 Complete Examples
- **[examples/authentication-pattern.md](examples/authentication-pattern.md)** - Complete working authentication with JWT tokens
- **[examples/raw-video-capture.md](examples/raw-video-capture.md)** - YUV420 video capture with detailed format explanation

### 🔧 Troubleshooting Guides
- **[troubleshooting/windows-message-loop.md](troubleshooting/windows-message-loop.md)** - **Why callbacks don't fire** (MOST CRITICAL!)
- **[troubleshooting/build-errors.md](troubleshooting/build-errors.md)** - SDK header dependency issues and fixes
- **[troubleshooting/common-issues.md](troubleshooting/common-issues.md)** - Quick diagnostic workflow and error code tables

### 📖 References
- **[references/interface-methods.md](references/interface-methods.md)** - How to implement ALL required virtual methods
- **[references/windows-reference.md](references/windows-reference.md)** - Dependencies, Visual Studio setup
- **[../references/authorization.md](../references/authorization.md)** - SDK JWT generation
- **[../references/bot-authentication.md](../references/bot-authentication.md)** - Bot token types (ZAK, OBF, JWT)

### 🎨 Feature-Specific Guides
- **[../references/breakout-rooms.md](../references/breakout-rooms.md)** - Programmatic breakout room management
- **[../references/ai-companion.md](../references/ai-companion.md)** - AI Companion controls

## Sample Repositories

| Repository | Description |
|------------|-------------|
| [meetingsdk-windows-raw-recording-sample](https://github.com/zoom/meetingsdk-windows-raw-recording-sample) | Official raw data capture samples |
| [meetingsdk-windows-local-recording-sample](https://github.com/zoom/meetingsdk-windows-local-recording-container-sample) | Local recording with Docker |

## Playing Raw Video/Audio Files

Raw YUV/PCM files have no headers - you must specify format explicitly.

### Play Raw YUV Video
```cmd
ffplay -video_size 1280x720 -pixel_format yuv420p -f rawvideo output.yuv
```

### Convert YUV to MP4
```cmd
ffmpeg -video_size 1280x720 -pixel_format yuv420p -f rawvideo -i output.yuv -c:v libx264 output.mp4
```

### Play Raw PCM Audio
```cmd
ffplay -f s16le -ar 32000 -ac 1 audio.pcm
```

### Convert PCM to WAV
```cmd
ffmpeg -f s16le -ar 32000 -ac 1 -i audio.pcm output.wav
```

### Combine Video + Audio
```cmd
ffmpeg -video_size 1280x720 -pixel_format yuv420p -f rawvideo -i output.yuv ^
       -f s16le -ar 32000 -ac 1 -i audio.pcm ^
       -c:v libx264 -c:a aac -shortest output.mp4
```

**Key flags:**
| Flag | Description |
|------|-------------|
| `-video_size WxH` | Frame dimensions (e.g., 1280x720) |
| `-pixel_format yuv420p` | I420/YUV420 planar format |
| `-f rawvideo` | Raw video input (no container) |
| `-f s16le` | Signed 16-bit little-endian PCM |
| `-ar 32000` | Sample rate (Zoom uses 32kHz) |
| `-ac 1` | Mono (use `-ac 2` for stereo) |

## Authentication Requirements (2026 Update)

> **Important**: Beginning **March 2, 2026**, apps joining meetings outside their account must be authorized.

Use one of:
- **App Privilege Token (OBF)** - Recommended for bots (`app_privilege_token` in JoinParam)
- **ZAK Token** - Zoom Access Key (`userZAK` in JoinParam)
- **On Behalf Token** - For specific use cases (`onBehalfToken` in JoinParam)

## 📖 Complete Documentation Library

This skill includes comprehensive guides created from real-world debugging:

### 🎯 Start Here
- **[SDK Architecture Pattern](concepts/sdk-architecture-pattern.md)** - Master document: Universal pattern for ANY feature
- **[SKILL.md](SKILL.md)** - Complete navigation guide

### 📚 By Category

**Core Concepts:**
- [SDK Architecture Pattern](concepts/sdk-architecture-pattern.md) - How every feature works (singleton + observer pattern)

**Complete Examples:**
- [Authentication Pattern](examples/authentication-pattern.md) - Working JWT auth with all code
- [Raw Video Capture](examples/raw-video-capture.md) - YUV420 video capture explained

**Troubleshooting:**
- [Windows Message Loop](troubleshooting/windows-message-loop.md) - **CRITICAL**: Why callbacks don't fire
- [Build Errors](troubleshooting/build-errors.md) - SDK header dependency fixes
- [Common Issues](troubleshooting/common-issues.md) - Quick diagnostics & error codes

**References:**
- [Interface Methods](references/interface-methods.md) - All required virtual methods (6 auth + 9 meeting)
- [Windows Reference](references/windows-reference.md) - Platform setup
- [Authorization](../references/authorization.md) - JWT generation
- [Bot Authentication](../references/bot-authentication.md) - Bot token types
- [Breakout Rooms](../references/breakout-rooms.md) - Breakout room API
- [AI Companion](../references/ai-companion.md) - AI features

### 🚨 Most Critical Issues (From Real Debugging)

1. **Callbacks not firing** → Missing Windows message loop (99% of issues)
   - See: [Windows Message Loop Guide](troubleshooting/windows-message-loop.md)

2. **Build errors** → SDK header dependencies (`uint32_t`, `AudioType`, etc.)
   - See: [Build Errors Guide](troubleshooting/build-errors.md)

3. **Abstract class errors** → Missing virtual method implementations
   - See: [Interface Methods Guide](references/interface-methods.md)

### 💡 Key Insight

**Once you learn the 3-step pattern, you can implement ANY of the 35+ features:**
1. Get controller → 2. Implement event listener → 3. Register and use

See: [SDK Architecture Pattern](concepts/sdk-architecture-pattern.md)

## Official Resources

- **Official docs**: https://developers.zoom.us/docs/meeting-sdk/windows/
- **API Reference**: https://marketplacefront.zoom.us/sdk/meeting/windows/annotated.html
- **Developer forum**: https://devforum.zoom.us/
- **SDK download**: https://marketplace.zoom.us/

---

**Documentation Version**: Based on Zoom Windows Meeting SDK v6.7.2.26830

**Need help?** Start with [SKILL.md](SKILL.md) for complete navigation.


## Merged from meeting-sdk/windows/SKILL.md

# Zoom Windows Meeting SDK - Complete Documentation Index

## 🚀 Quick Start Path

**If you're new to the SDK, follow this order:**

1. **Read the architecture pattern** → [concepts/sdk-architecture-pattern.md](concepts/sdk-architecture-pattern.md)
   - This teaches you the universal formula that applies to ALL features
   - Once you understand this, you can implement any feature by reading the `.h` files

2. **Fix build errors** → [troubleshooting/build-errors.md](troubleshooting/build-errors.md)
   - SDK header dependencies issues
   - Required include order

3. **Implement authentication** → [examples/authentication-pattern.md](examples/authentication-pattern.md)
   - Complete working JWT authentication code

4. **Fix callback issues** → [troubleshooting/windows-message-loop.md](troubleshooting/windows-message-loop.md)
   - **CRITICAL**: Why callbacks don't fire without Windows message loop
   - This was the hardest issue to diagnose!

5. **Implement virtual methods** → [references/interface-methods.md](references/interface-methods.md)
   - Complete lists of all required methods
   - How to avoid abstract class errors

6. **Capture video (optional)** → [examples/raw-video-capture.md](examples/raw-video-capture.md)
   - YUV420 format explained
   - Complete raw data capture workflow

7. **Troubleshoot any issues** → [troubleshooting/common-issues.md](troubleshooting/common-issues.md)
   - Quick diagnostic checklist
   - Error code tables
   - "If you see X, do Y" reference

---

## 📂 Documentation Structure

```
meeting-sdk/windows/
├── SKILL.md                           # Main skill overview
├── SKILL.md                           # This file - navigation guide
│
├── concepts/                          # Core architectural patterns
│   ├── sdk-architecture-pattern.md   # THE MOST IMPORTANT DOC
│   │                                  # Universal formula for ANY feature
│   ├── singleton-hierarchy.md        # Navigation guide for SDK services
│   │                                  # 4-level deep service tree, when/how
│   ├── custom-ui-architecture.md     # How Custom UI rendering works
│   │                                  # Child HWNDs, D3D, layout, events
│   └── custom-ui-vs-raw-data.md      # SDK-rendered vs self-rendered
│                                      # Decision guide for Custom UI approach
│
├── examples/                          # Complete working code
│   ├── authentication-pattern.md     # JWT auth with full code
│   ├── raw-video-capture.md          # Video capture with YUV420 details
│   │                                  # Recording vs Streaming, permissions
│   ├── custom-ui-video-rendering.md  # Custom UI with video container
│   │                                  # Active speaker + gallery layout
│   ├── breakout-rooms.md             # Complete breakout room guide
│   │                                  # 5 roles, create/manage/join
│   ├── chat.md                       # Send/receive chat messages
│   │                                  # Rich text, threading, file transfer
│   ├── captions-transcription.md     # Live transcription & closed captions
│   │                                  # Multi-language translation
│   ├── local-recording.md            # Local MP4 recording
│   │                                  # Permission flow, encoder monitoring
│   ├── share-raw-data-capture.md     # Screen share raw data capture
│   │                                  # YUV420 frames from shared content
│   └── send-raw-data.md              # Virtual camera/mic/share
│                                      # Send custom video/audio/share
│
├── troubleshooting/                   # Problem solving guides
│   ├── windows-message-loop.md       # CRITICAL - Why callbacks fail
│   ├── build-errors.md               # Header dependency fixes + MSBuild
│   └── common-issues.md              # Quick diagnostic workflow
│
└── references/                        # Reference documentation
    ├── interface-methods.md           # Required virtual methods
    │                                  # Auth(6) + Meeting(9) + CustomUI(13)
    ├── windows-reference.md           # Platform setup
    ├── authorization.md               # JWT generation
    ├── bot-authentication.md          # Bot token types
    ├── breakout-rooms.md              # Breakout room features
    └── ai-companion.md                # AI Companion features
```

---

## 🎯 By Use Case

### I want to build a meeting bot
1. [SDK Architecture Pattern](concepts/sdk-architecture-pattern.md) - Understand the pattern
2. [Authentication Pattern](examples/authentication-pattern.md) - Join meetings
3. [Windows Message Loop](troubleshooting/windows-message-loop.md) - Fix callback issues
4. [Interface Methods](references/interface-methods.md) - Implement callbacks

### I'm getting build errors
1. [Build Errors Guide](troubleshooting/build-errors.md) - SDK header dependencies
2. [Interface Methods](references/interface-methods.md) - Abstract class errors
3. [Common Issues](troubleshooting/common-issues.md) - Linker errors

### I'm getting runtime errors
1. [Windows Message Loop](troubleshooting/windows-message-loop.md) - Callbacks not firing
2. [Authentication Pattern](examples/authentication-pattern.md) - Auth timeout
3. [Common Issues](troubleshooting/common-issues.md) - Error code tables

### I want to build a Custom UI meeting app
1. [Custom UI Architecture](concepts/custom-ui-architecture.md) - How SDK rendering works
2. [SDK-Rendered vs Self-Rendered](concepts/custom-ui-vs-raw-data.md) - Choose your approach
3. [Custom UI Video Rendering](examples/custom-ui-video-rendering.md) - Complete working code
4. [Interface Methods](references/interface-methods.md) - 13 Custom UI virtual methods
5. [Build Errors Guide](troubleshooting/build-errors.md) - MSBuild from git bash

### I want to capture video/audio
1. [Raw Video Capture](examples/raw-video-capture.md) - Complete video workflow
   - Recording vs Streaming approaches
   - Permission requirements (host, OAuth tokens)
   - Audio PCM capture
2. [Share Raw Data Capture](examples/share-raw-data-capture.md) - Screen share capture
   - Subscribe to RAW_DATA_TYPE_SHARE
   - Handle dynamic resolution
3. [SDK Architecture Pattern](concepts/sdk-architecture-pattern.md) - Controller pattern
4. [Common Issues](troubleshooting/common-issues.md) - No frames received

### I want to use breakout rooms
1. [Breakout Rooms Guide](examples/breakout-rooms.md) - Complete breakout room workflow
   - 5 roles: Creator, Admin, Data, Assistant, Attendee
   - Create, configure, manage, join/leave rooms
2. [Common Issues](troubleshooting/common-issues.md) - Breakout room error codes

### I want to implement chat
1. [Chat Guide](examples/chat.md) - Send/receive messages
   - Rich text formatting (bold, italic, links)
   - Private messages and threading
   - File transfer events

### I want to use live transcription
1. [Captions & Transcription Guide](examples/captions-transcription.md) - Live transcription
   - Automatic speech-to-text
   - Multi-language translation
   - Manual closed captions (host feature)

### I want to record meetings
1. [Local Recording Guide](examples/local-recording.md) - Local MP4 recording
   - Permission request workflow
   - zTscoder.exe encoder monitoring
   - Gallery view vs active speaker

### I want to implement a specific feature
1. [SDK Architecture Pattern](concepts/sdk-architecture-pattern.md) - **START HERE!**
2. Find the controller in `SDK/x64/h/meeting_service_interface.h`
3. Find the header in `SDK/x64/h/meeting_service_components/`
4. Follow the universal pattern: Get controller → Implement listener → Use methods

### I want to understand the SDK architecture
1. [SDK Architecture Pattern](concepts/sdk-architecture-pattern.md) - Complete architecture overview
2. [Singleton Hierarchy](concepts/singleton-hierarchy.md) - Navigate the service tree (4 levels)
3. [Interface Methods](references/interface-methods.md) - Event listener pattern
4. [Authentication Pattern](examples/authentication-pattern.md) - Service pattern

---

## 🔥 Most Critical Documents

### 1. SDK Architecture Pattern (⭐ MASTER DOCUMENT)
**[concepts/sdk-architecture-pattern.md](concepts/sdk-architecture-pattern.md)**

This is THE most important document. It teaches the universal 3-step pattern:
1. Get controller (singleton pattern)
2. Implement event listener (observer pattern)
3. Register and use

Once you understand this pattern, you can implement **any of the 35+ features** by just reading the SDK headers.

**Key insight**: The Zoom SDK follows a perfectly consistent architecture. Every feature works the same way.

---

### 2. Windows Message Loop (⚠️ MOST COMMON ISSUE)
**[troubleshooting/windows-message-loop.md](troubleshooting/windows-message-loop.md)**

99% of "callbacks not firing" issues are caused by missing Windows message loop. This document explains:
- Why SDK requires `PeekMessage()` loop
- How to implement it correctly
- How to diagnose callback issues

**This was the hardest bug to find during development** (took ~2 hours).

---

### 3. Build Errors Guide
**[troubleshooting/build-errors.md](troubleshooting/build-errors.md)**

SDK headers have dependency bugs that cause build errors. This document provides:
- Required include order
- Missing `<cstdint>` fix
- Missing `AudioType` fix
- Missing `YUVRawDataI420` fix

---

## 📊 By Document Type

### Concepts (Why and How)
- [SDK Architecture Pattern](concepts/sdk-architecture-pattern.md) - Universal implementation pattern
- [Singleton Hierarchy](concepts/singleton-hierarchy.md) - Navigation guide for SDK services (4 levels deep)

### Examples (Complete Working Code)
- [Authentication Pattern](examples/authentication-pattern.md) - JWT authentication
- [Raw Video Capture](examples/raw-video-capture.md) - Video capture with YUV420, recording vs streaming
- [Custom UI Video Rendering](examples/custom-ui-video-rendering.md) - SDK-rendered video containers
- [Breakout Rooms](examples/breakout-rooms.md) - Create, manage, join breakout rooms
- [Chat](examples/chat.md) - Send/receive messages with rich formatting
- [Captions & Transcription](examples/captions-transcription.md) - Live transcription and closed captions
- [Local Recording](examples/local-recording.md) - Local MP4 recording with permission flow
- [Share Raw Data Capture](examples/share-raw-data-capture.md) - Screen share raw data capture
- [Send Raw Data](examples/send-raw-data.md) - Virtual camera, microphone, and share

### Troubleshooting (Problem Solving)
- [Windows Message Loop](troubleshooting/windows-message-loop.md) - Callback issues
- [Build Errors](troubleshooting/build-errors.md) - Compilation issues
- [Common Issues](troubleshooting/common-issues.md) - Quick diagnostics

### References (Lookup Information)
- [Interface Methods](references/interface-methods.md) - Required virtual methods
- [Windows Reference](references/windows-reference.md) - Platform setup
- [Authorization](../references/authorization.md) - JWT generation
- [Bot Authentication](../references/bot-authentication.md) - Bot tokens
- [Breakout Rooms](../references/breakout-rooms.md) - Breakout room API
- [AI Companion](../references/ai-companion.md) - AI features

---

## 💡 Key Learnings from Real Debugging

These documents were created from actual debugging of a non-functional Zoom SDK sample. Here are the key insights:

### Critical Discoveries:

1. **Windows Message Loop is MANDATORY** (not optional)
   - SDK uses Windows message pump for callbacks
   - Without it, callbacks are queued but never fire
   - Manifests as "authentication timeout" even with valid JWT
   - See: [Windows Message Loop Guide](troubleshooting/windows-message-loop.md)

2. **SDK Headers Have Dependency Bugs**
   - Missing `#include <cstdint>` in SDK headers
   - `meeting_participants_ctrl_interface.h` doesn't include `meeting_audio_interface.h`
   - `rawdata_renderer_interface.h` only forward-declares `YUVRawDataI420`
   - See: [Build Errors Guide](troubleshooting/build-errors.md)

3. **Include Order is CRITICAL**
   - `<windows.h>` must be FIRST
   - `<cstdint>` must be SECOND
   - Then SDK headers in specific order
   - See: [Build Errors Guide](troubleshooting/build-errors.md)

4. **ALL Virtual Methods Must Be Implemented**
   - Including WIN32-conditional methods
   - SDK v6.7.2 requires 6 auth methods + 9 meeting methods
   - Different versions have different requirements
   - See: [Interface Methods Guide](references/interface-methods.md)

5. **The Architecture is Beautifully Consistent**
   - Every feature follows the same 3-step pattern
   - Controllers are singletons
   - Event listeners use observer pattern
   - Once you learn the pattern, you can implement any feature
   - See: [SDK Architecture Pattern](concepts/sdk-architecture-pattern.md)

---

## 🎓 Learning Path by Skill Level

### Beginner (Never used Zoom SDK)
1. Read [SDK Architecture Pattern](concepts/sdk-architecture-pattern.md) to understand the overall design
2. Follow [Authentication Pattern](examples/authentication-pattern.md) to join your first meeting
3. Reference [Common Issues](troubleshooting/common-issues.md) when you hit problems

### Intermediate (Familiar with SDK basics)
1. Deep dive into [SDK Architecture Pattern](concepts/sdk-architecture-pattern.md) - implement multiple features
2. Learn [Raw Video Capture](examples/raw-video-capture.md) for media processing
3. Use [Interface Methods](references/interface-methods.md) as reference

### Advanced (Building production bots)
1. Study [SDK Architecture Pattern](concepts/sdk-architecture-pattern.md) - learn to implement ANY feature
2. Master [Windows Message Loop](troubleshooting/windows-message-loop.md) - understand async callback flow
3. Reference SDK headers directly using the universal pattern

---

## 🔍 How to Find What You Need

### "My code won't compile"
→ [Build Errors Guide](troubleshooting/build-errors.md)

### "Authentication times out"
→ [Windows Message Loop](troubleshooting/windows-message-loop.md)

### "Callbacks never fire"
→ [Windows Message Loop](troubleshooting/windows-message-loop.md)

### "Abstract class error"
→ [Interface Methods](references/interface-methods.md)

### "How do I implement [feature]?"
→ [SDK Architecture Pattern](concepts/sdk-architecture-pattern.md)

### "How do I join a meeting?"
→ [Authentication Pattern](examples/authentication-pattern.md)

### "How do I capture video?"
→ [Raw Video Capture](examples/raw-video-capture.md)

### "What error code means what?"
→ [Common Issues](troubleshooting/common-issues.md) - Comprehensive error code tables (SDKERR, AUTHRET, Login, BO, Phone, OBF)

### "How do I use breakout rooms?"
→ [Breakout Rooms Guide](examples/breakout-rooms.md)

### "How does the SDK work?"
→ [SDK Architecture Pattern](concepts/sdk-architecture-pattern.md)

### "How do I navigate to a specific controller/feature?"
→ [Singleton Hierarchy](concepts/singleton-hierarchy.md)

### "How do I send/receive chat messages?"
→ [Chat Guide](examples/chat.md)

### "How do I use live transcription?"
→ [Captions & Transcription Guide](examples/captions-transcription.md)

### "How do I record locally?"
→ [Local Recording Guide](examples/local-recording.md)

### "How do I capture screen share?"
→ [Share Raw Data Capture](examples/share-raw-data-capture.md)

---

## 📝 Document Version

All documents are based on **Zoom Windows Meeting SDK v6.7.2.26830**.

Different SDK versions may have:
- Different required callback methods
- Different error codes
- Different API behavior

If using a different version, use `grep "= 0" SDK/x64/h/*.h` to verify required methods.

---

Remember: The [SDK Architecture Pattern](concepts/sdk-architecture-pattern.md) is the fastest way to understand how the Windows Meeting SDK fits together. Read it first if you are debugging custom UI or event flow issues.

## Operations

- [RUNBOOK.md](RUNBOOK.md) - 5-minute preflight and debugging checklist.
