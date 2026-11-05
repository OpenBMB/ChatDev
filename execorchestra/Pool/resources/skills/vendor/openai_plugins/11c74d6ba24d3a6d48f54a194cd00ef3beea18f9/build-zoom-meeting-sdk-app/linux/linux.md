# Zoom Meeting SDK (Linux)

Embed Zoom meeting capabilities into Linux applications for headless meeting bots and server-side integrations.

## Prerequisites

- Zoom app with Meeting SDK credentials (Client ID & Secret)
- Docker (recommended) or Linux environment (Ubuntu 22+, CentOS 8/9)
- C++ development toolchain (cmake, gcc, g++)
- GLib 2.0, libcurl, pthread

> **Need help with authentication?** See the **[zoom-oauth](../../oauth/SKILL.md)** skill for JWT token generation.

## Overview

The Linux SDK is a **C++ native SDK** designed for:
- **Headless meeting bots** - Join meetings without UI
- **Raw media access** - Capture/send audio/video streams
- **Server-side automation** - Scalable meeting integrations

## Quick Start

### 1. Download Linux SDK

Download from [Zoom Marketplace](https://marketplace.zoom.us/):
- Extract `zoom-meeting-sdk-linux_x86_64-{version}.tar`

### 2. Setup Project Structure

```
your-project/
  demo/
    include/h/          # SDK headers
    lib/zoom_meeting_sdk/
      libmeetingsdk.so
      libmeetingsdk.so.1  # symlink
      qt_libs/
      json/translations.json
    meeting_sdk_demo.cpp
    CMakeLists.txt
    config.txt
```

Copy SDK files:
```bash
cp -r h/* demo/include/h/
cp lib*.so demo/lib/zoom_meeting_sdk/
cp -r qt_libs demo/lib/zoom_meeting_sdk/
cp translation.json demo/lib/zoom_meeting_sdk/json/

# Create required symlink
cd demo/lib/zoom_meeting_sdk/
ln -s libmeetingsdk.so libmeetingsdk.so.1
```

### 3. Configure Credentials

Create `config.txt`:
```
meeting_number: "1234567890"
token: "YOUR_JWT_TOKEN"
meeting_password: "password123"
recording_token: ""
GetVideoRawData: "true"
GetAudioRawData: "true"
SendVideoRawData: "false"
SendAudioRawData: "false"
```

### 4. Build & Run

```bash
cd demo
cmake -B build
cd build
make
cd ../bin
./meetingSDKDemo
```

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

## Code Examples

### 1. Initialize SDK

```cpp
#include "zoom_sdk.h"

USING_ZOOM_SDK_NAMESPACE

void InitMeetingSDK() {
    SDKError err(SDKERR_SUCCESS);
    InitParam initParam;

    initParam.strWebDomain = "https://zoom.us";
    initParam.strSupportUrl = "https://zoom.us";
    initParam.emLanguageID = LANGUAGE_English;
    initParam.enableLogByDefault = true;
    initParam.enableGenerateDump = true;

    err = InitSDK(initParam);
    if (err != SDKERR_SUCCESS) {
        std::cerr << "Init meetingSdk:error" << std::endl;
    }
}
```

### 2. Authenticate with JWT

```cpp
#include "auth_service_interface.h"

IAuthService* m_pAuthService;

void OnAuthenticationComplete() {
    JoinMeeting();  // Called on successful auth
}

void AuthMeetingSDK() {
    CreateAuthService(&m_pAuthService);

    m_pAuthService->SetEvent(
        new AuthServiceEventListener(&OnAuthenticationComplete)
    );

    AuthContext param;
    param.jwt_token = token.c_str();  // Your JWT token
    m_pAuthService->SDKAuth(param);
}
```

### 3. Join Meeting

```cpp
#include "meeting_service_interface.h"

IMeetingService* m_pMeetingService;
ISettingService* m_pSettingService;

void JoinMeeting() {
    CreateMeetingService(&m_pMeetingService);
    CreateSettingService(&m_pSettingService);

    // Set event listeners
    m_pMeetingService->SetEvent(
        new MeetingServiceEventListener(&onMeetingJoined, &onMeetingEnds, &onInMeeting)
    );

    // Prepare join parameters
    JoinParam joinParam;
    joinParam.userType = SDK_UT_WITHOUT_LOGIN;

    JoinParam4WithoutLogin& params = joinParam.param.withoutloginuserJoin;
    params.meetingNumber = std::stoull(meeting_number);
    params.userName = "BotUser";
    params.psw = meeting_password.c_str();
    params.isVideoOff = false;
    params.isAudioOff = false;

    m_pMeetingService->Join(joinParam);
}
```

### 4. Subscribe to Raw Video

```cpp
#include "rawdata/rawdata_renderer_interface.h"
#include "rawdata/zoom_rawdata_api.h"

class ZoomSDKRenderer : public IZoomSDKRendererDelegate {
public:
    void onRawDataFrameReceived(YUVRawDataI420* data) override {
        // YUV420 (I420) format - contiguous planar data (no strides)
        int width = data->GetStreamWidth();
        int height = data->GetStreamHeight();

        // Y plane: width * height bytes
        outputFile.write(data->GetYBuffer(), width * height);
        // U plane: (width/2) * (height/2) bytes
        outputFile.write(data->GetUBuffer(), (width / 2) * (height / 2));
        // V plane: (width/2) * (height/2) bytes
        outputFile.write(data->GetVBuffer(), (width / 2) * (height / 2));
    }

    void onRawDataStatusChanged(RawDataStatus status) override {}
    void onRendererBeDestroyed() override {}
};

// Subscribe after joining
IZoomSDKRenderer* videoHelper;
ZoomSDKRenderer* videoSource = new ZoomSDKRenderer();

createRenderer(&videoHelper, videoSource);
videoHelper->setRawDataResolution(ZoomSDKResolution_720P);
videoHelper->subscribe(userID, RAW_DATA_TYPE_VIDEO);
```

### 5. Subscribe to Raw Audio

```cpp
#include "rawdata/rawdata_audio_helper_interface.h"

class ZoomSDKAudioRawData : public IZoomSDKAudioRawDataDelegate {
public:
    void onMixedAudioRawDataReceived(AudioRawData* data) override {
        // Process PCM audio (mixed from all participants)
        pcmFile.write((char*)data->GetBuffer(), data->GetBufferLen());
    }

    void onOneWayAudioRawDataReceived(AudioRawData* data, uint32_t node_id) override {
        // Process audio from specific participant
    }
};

// Subscribe after joining
IZoomSDKAudioRawDataHelper* audioHelper = GetAudioRawdataHelper();
audioHelper->subscribe(new ZoomSDKAudioRawData());
```

### 6. GLib Main Loop

```cpp
#include <glib.h>

GMainLoop* loop;

gboolean timeout_callback(gpointer data) {
    return TRUE;  // Keep running
}

int main(int argc, char* argv[]) {
    InitMeetingSDK();
    AuthMeetingSDK();

    loop = g_main_loop_new(NULL, FALSE);
    g_timeout_add(1000, timeout_callback, loop);
    g_main_loop_run(loop);

    return 0;
}
```

## Available Examples

| Example | Description |
|---------|-------------|
| **SkeletonExample** | Minimal join meeting - start here |
| **GetRawVideoAndAudioExample** | Subscribe to raw audio/video streams |
| **GetRawVideoAndAudioAPIExample** | API-based raw data access |
| **SendRawVideoAndAudioExample** | Send custom video/audio as virtual camera/mic |
| **ChatExample** | In-meeting chat functionality |
| **BreakoutExample** | Breakout room management |
| **AllInOneExample** | Complete demo with all features |
| **SendRawVideoAndAudioWithRTMSExample** | Raw data with RTMS integration |

## Detailed References

### High-Level Guides
- **[concepts/high-level-scenarios.md](concepts/high-level-scenarios.md)** - Production bot architectures (transcription, recording, AI assistant)
- **[meeting-sdk-bot.md](meeting-sdk-bot.md)** - Resilient bot pattern with retry logic

### Platform Guide
- **[references/linux-reference.md](references/linux-reference.md)** - Dependencies, Docker setup, troubleshooting

### Authentication
- **[../references/authorization.md](../references/authorization.md)** - SDK JWT generation
- **[../references/bot-authentication.md](../references/bot-authentication.md)** - Bot token types (ZAK, OBF, JWT)

### Features
- **[../references/breakout-rooms.md](../references/breakout-rooms.md)** - Programmatic breakout room management
- **[../references/ai-companion.md](../references/ai-companion.md)** - AI Companion controls

## Sample Repositories

| Repository | Description |
|------------|-------------|
| [meetingsdk-headless-linux-sample](https://github.com/zoom/meetingsdk-headless-linux-sample) | Official headless bot with Docker |
| [meetingsdk-linux-raw-recording-sample](https://github.com/zoom/meetingsdk-linux-raw-recording-sample) | Raw audio/video access |

## Playing Raw Video/Audio Files

Raw YUV/PCM files have no headers - you must specify format explicitly.

### Play Raw YUV Video
```bash
ffplay -video_size 640x360 -pixel_format yuv420p -f rawvideo video.yuv
```

### Convert YUV to MP4
```bash
ffmpeg -video_size 640x360 -pixel_format yuv420p -f rawvideo -i video.yuv -c:v libx264 output.mp4
```

### Play Raw PCM Audio
```bash
ffplay -f s16le -ar 32000 -ac 1 audio.pcm
```

### Convert PCM to WAV
```bash
ffmpeg -f s16le -ar 32000 -ac 1 -i audio.pcm output.wav
```

### Combine Video + Audio
```bash
ffmpeg -video_size 640x360 -pixel_format yuv420p -f rawvideo -i video.yuv \
       -f s16le -ar 32000 -ac 1 -i audio.pcm \
       -c:v libx264 -c:a aac -shortest output.mp4
```

**Key flags:**
| Flag | Description |
|------|-------------|
| `-video_size WxH` | Frame dimensions (check output filename) |
| `-pixel_format yuv420p` | I420/YUV420 planar format |
| `-f rawvideo` | Raw video input (no container) |
| `-f s16le` | Signed 16-bit little-endian PCM |
| `-ar 32000` | Sample rate (Zoom uses 32kHz) |
| `-ac 1` | Mono (use `-ac 2` for stereo) |

## Compilation Tips

> **Note**: These are general patterns - specific methods/types may vary by SDK version.

### Event Listener Interfaces
SDK event listener interfaces (`IMeetingServiceEvent`, `IMeetingParticipantsCtrlEvent`, etc.) have **many pure virtual methods**. You must implement ALL of them, even with empty bodies, or you'll get "invalid new-expression of abstract class type" errors. Always check the SDK headers for the complete list.

### Include Order Issues
Some SDK headers don't include their own dependencies. If you encounter undefined type errors (like `AudioType` or `time_t`), try:
- Adding standard library includes (`<ctime>`, `<cstdint>`) before SDK headers
- Including related SDK headers in dependency order
- Checking which header defines the missing type

### Method Signature Mismatches
Reference samples may have outdated method names. Always verify against the actual SDK header files - they are the authoritative source.

## Authentication Requirements (2026 Update)

> **Important**: Beginning **March 2, 2026**, apps joining meetings outside their account must be authorized.

Use one of:
- **App Privilege Token (OBF)** - Recommended for bots (`app_privilege_token` in JoinParam)
- **ZAK Token** - Zoom Access Key (`userZAK` in JoinParam)
- **On Behalf Token** - For specific use cases (`onBehalfToken` in JoinParam)

## Resources

- **Official docs**: https://developers.zoom.us/docs/meeting-sdk/linux/
- **API Reference**: https://marketplacefront.zoom.us/sdk/meeting/linux/index.html
- **Developer forum**: https://devforum.zoom.us/
- **SDK download**: https://marketplace.zoom.us/
