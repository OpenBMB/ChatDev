---
name: zoom-meeting-sdk-linux
description: "Zoom Meeting SDK for Linux - C++ headless meeting bots with raw audio/video access, transcription, recording, and AI integration for server-side automation"
---

# Zoom Meeting SDK - Linux Development

Expert guidance for building headless meeting bots with the Zoom Meeting SDK on Linux. This SDK enables server-side meeting participation, raw media capture, transcription, and AI-powered meeting automation.

## How to Build a Meeting Bot That Automatically Joins and Records

Use this skill when the requirement is:
- visible bot joins a real Zoom meeting
- the bot records raw media itself
- or the bot triggers a Zoom-managed cloud-recording workflow after join

Skill chain:
- primary: `meeting-sdk/linux`
- add `zoom-rest-api` for OBF/ZAK lookup, scheduling, or cloud-recording settings
- add `zoom-webhooks` when post-meeting cloud recording retrieval is required

Minimal raw-recording flow:

```cpp
JoinParam join_param;
join_param.userType = SDK_UT_WITHOUT_LOGIN;
auto& params = join_param.param.withoutloginuserJoin;
params.meetingNumber = meeting_number;
params.userName = "Recording Bot";
params.psw = meeting_password.c_str();
params.app_privilege_token = obf_token.c_str();

SDKError join_err = meeting_service->Join(join_param);
if (join_err != SDKERR_SUCCESS) {
    throw std::runtime_error("join_failed");
}

// In MEETING_STATUS_INMEETING callback:
auto* record_ctrl = meeting_service->GetMeetingRecordingController();
if (!record_ctrl) {
    throw std::runtime_error("recording_controller_unavailable");
}

if (record_ctrl->CanStartRawRecording() != SDKERR_SUCCESS) {
    throw std::runtime_error("raw_recording_not_permitted");
}

SDKError record_err = record_ctrl->StartRawRecording();
if (record_err != SDKERR_SUCCESS) {
    throw std::runtime_error("start_raw_recording_failed");
}

GetAudioRawdataHelper()->subscribe(new MyAudioDelegate());
```

Use **raw recording** when the bot must own PCM/YUV media or feed an AI pipeline directly.
Use **cloud recording + webhooks** when the requirement is Zoom-managed MP4/M4A/transcript assets after the meeting.

**Official Documentation**: https://developers.zoom.us/docs/meeting-sdk/linux/
**API Reference**: https://marketplacefront.zoom.us/sdk/meeting/linux/
**Sample Repository (Raw Recording)**: https://github.com/zoom/meetingsdk-linux-raw-recording-sample
**Sample Repository (Headless)**: https://github.com/zoom/meetingsdk-headless-linux-sample

## Quick Links

**New to Meeting SDK Linux? Follow this path:**

1. **[linux.md](linux.md)** - Quick start guide with complete workflow
2. **[concepts/high-level-scenarios.md](concepts/high-level-scenarios.md)** - Production bot architectures
3. **[meeting-sdk-bot.md](meeting-sdk-bot.md)** - Resilient bot with retry logic
4. **[references/linux-reference.md](references/linux-reference.md)** - Dependencies, Docker, CMake

**Common Use Cases:**
- **Transcription Bot** → [high-level-scenarios.md#scenario-1-transcription-bot](concepts/high-level-scenarios.md)
- **Recording Bot** → [high-level-scenarios.md#scenario-2-recording-bot](concepts/high-level-scenarios.md)
- **AI Meeting Assistant** → [high-level-scenarios.md#scenario-3-ai-meeting-assistant](concepts/high-level-scenarios.md)
- **Quality Monitoring** → [high-level-scenarios.md#scenario-4-monitoring-quality-bot](concepts/high-level-scenarios.md)
- **Auto-Join + Recording Bot** → [meeting-sdk-bot.md](meeting-sdk-bot.md) for raw recording orchestration, retry, and cloud-recording handoff

**Having issues?**
- Docker audio issues → [references/linux-reference.md#pulseaudio-setup](references/linux-reference.md)
- Raw recording permission denied → [meeting-sdk-bot.md#raw-recording-permission-denied](meeting-sdk-bot.md)
- Build errors → [references/linux-reference.md#troubleshooting](references/linux-reference.md)

## Routing Rule for Bots

If the user asks to build a bot that **automatically joins a Zoom meeting and records it**, start with
[meeting-sdk-bot.md](meeting-sdk-bot.md).

- Use **Meeting SDK Linux** for the visible participant, join flow, and raw recording control.
- Chain **zoom-rest-api** when the bot must fetch OBF/ZAK tokens, schedule meetings, or enable account-side recording settings.
- Chain **zoom-webhooks** when the requirement is Zoom cloud recording retrieval after meeting end.

## SDK Overview

The Zoom Meeting SDK for Linux is a **C++ library optimized for headless server environments**:
- **Headless Operation**: No GUI required, perfect for Docker/cloud
- **Raw Data Access**: YUV420 video, PCM audio at 32kHz
- **GLib Event Loop**: Async event handling for callbacks
- **Docker-Ready**: Pre-configured Dockerfiles for CentOS/Ubuntu
- **PulseAudio Integration**: Virtual audio devices for headless environments

### Key Differences from Video SDK

| Feature | Meeting SDK (Linux) | Video SDK |
|---------|-------------------|-----------|
| **Primary Use** | Join existing meetings as bot | Host custom video sessions |
| **Visibility** | Visible participant | Session participant |
| **UI** | Headless (no UI) | Optional custom UI |
| **Authentication** | JWT + OBF/ZAK for external meetings | JWT only |
| **Recording Control** | `StartRawRecording()` required | Direct raw data access |
| **Platform** | Linux only | Windows, macOS, iOS, Android |

## Prerequisites

### System Requirements
- **OS**: Ubuntu 22+, CentOS 8/9, Oracle Linux 8
- **Architecture**: x86_64
- **Compiler**: gcc/g++ with C++11 support
- **Build Tools**: cmake 3.16+

### Development Dependencies
```bash
# Ubuntu
apt-get install -y build-essential cmake \
    libx11-xcb1 libxcb-xfixes0 libxcb-shape0 libxcb-shm0 \
    libxcb-randr0 libxcb-image0 libxcb-keysyms1 libxcb-xtest0 \
    libglib2.0-dev libcurl4-openssl-dev pulseaudio

# CentOS
yum install -y cmake gcc gcc-c++ \
    libxcb-devel xcb-util-image xcb-util-keysyms \
    glib2-devel libcurl-devel pulseaudio
```

### Required Credentials
1. **Zoom Meeting SDK App** (Client ID & Secret) → [Create at Marketplace](https://marketplace.zoom.us/)
2. **JWT Token** → Generate from Client ID/Secret
3. **For External Meetings**: OBF token OR ZAK token → [Get via REST API](../references/bot-authentication.md)
4. **For Raw Recording**: Meeting Recording Token (optional) → [Get via API](https://developers.zoom.us/docs/meeting-sdk/apis/#operation/meetingLocalRecordingJoinToken)

## Quick Start

### 1. Download & Extract SDK

```bash
# Download from https://marketplace.zoom.us/
tar xzf zoom-meeting-sdk-linux_x86_64-{version}.tar

# Organize files
mkdir -p demo/include/h demo/lib/zoom_meeting_sdk
cp -r h/* demo/include/h/
cp lib*.so demo/lib/zoom_meeting_sdk/
cp -r qt_libs demo/lib/zoom_meeting_sdk/
cp translation.json demo/lib/zoom_meeting_sdk/json/

# Create required symlink
cd demo/lib/zoom_meeting_sdk && ln -s libmeetingsdk.so libmeetingsdk.so.1
```

### 2. Initialize & Auth

```cpp
#include "zoom_sdk.h"

USING_ZOOM_SDK_NAMESPACE

// Initialize SDK
InitParam init_params;
init_params.strWebDomain = "https://zoom.us";
init_params.enableLogByDefault = true;
init_params.rawdataOpts.audioRawDataMemoryMode = ZoomSDKRawDataMemoryModeHeap;
InitSDK(init_params);

// Authenticate with JWT
AuthContext auth_ctx;
auth_ctx.jwt_token = your_jwt_token;
CreateAuthService(&auth_service);
auth_service->SDKAuth(auth_ctx);
```

### 3. Join Meeting

```cpp
// In onAuthenticationReturn callback
void onAuthenticationReturn(AuthResult ret) {
    if (ret == AUTHRET_SUCCESS) {
        JoinParam join_param;
        join_param.userType = SDK_UT_WITHOUT_LOGIN;

        auto& params = join_param.param.withoutloginuserJoin;
        params.meetingNumber = 1234567890;
        params.userName = "Bot";
        params.psw = "password";
        params.isVideoOff = true;
        params.isAudioOff = false;

        meeting_service->Join(join_param);
    }
}
```

### 4. Access Raw Data

```cpp
// In onMeetingStatusChanged callback
void onMeetingStatusChanged(MeetingStatus status, int iResult) {
    if (status == MEETING_STATUS_INMEETING) {
        auto* record_ctrl = meeting_service->GetMeetingRecordingController();

        // Start raw recording (enables raw data access)
        if (record_ctrl->CanStartRawRecording() == SDKERR_SUCCESS) {
            record_ctrl->StartRawRecording();

            // Subscribe to audio
            auto* audio_helper = GetAudioRawdataHelper();
            audio_helper->subscribe(new MyAudioDelegate());

            // Subscribe to video
            IZoomSDKRenderer* video_renderer;
            createRenderer(&video_renderer, new MyVideoDelegate());
            video_renderer->setRawDataResolution(ZoomSDKResolution_720P);
            video_renderer->subscribe(user_id, RAW_DATA_TYPE_VIDEO);
        }
    }
}
```

## Key Features

| Feature | Description |
|---------|-------------|
| **Headless Operation** | No GUI, perfect for Docker/server deployments |
| **Raw Audio (PCM)** | Capture mixed or per-user audio at 32kHz |
| **Raw Video (YUV420)** | Capture video frames in contiguous planar format |
| **GLib Event Loop** | Async callback handling |
| **Docker Support** | Pre-built Dockerfiles for CentOS/Ubuntu |
| **PulseAudio Virtual Devices** | Audio in headless environments |
| **Breakout Rooms** | Programmatic breakout room management |
| **Chat** | Send/receive in-meeting chat |
| **Recording Control** | Local, cloud, and raw recording |

## Critical Gotchas & Best Practices

### ⚠️ CRITICAL: PulseAudio for Docker/Headless

**The #1 issue for raw audio in Docker:**

Raw audio requires PulseAudio and a config file, even in headless environments.

**Solution**:
```bash
# Install PulseAudio
apt-get install -y pulseaudio pulseaudio-utils

# Create config file
mkdir -p ~/.config
cat > ~/.config/zoomus.conf << EOF
[General]
system.audio.type=default
EOF

# Start PulseAudio with virtual devices
pulseaudio --start --exit-idle-time=-1
pactl load-module module-null-sink sink_name=virtual_speaker
pactl load-module module-null-sink sink_name=virtual_mic
```

See: [references/linux-reference.md#pulseaudio-setup](references/linux-reference.md)

### Raw Recording Permission Required

Unlike Video SDK, Meeting SDK requires explicit permission to access raw data:

```cpp
// MUST call StartRawRecording() first
auto* record_ctrl = meeting_service->GetMeetingRecordingController();

SDKError can_record = record_ctrl->CanStartRawRecording();
if (can_record == SDKERR_SUCCESS) {
    record_ctrl->StartRawRecording();
    // NOW you can subscribe to audio/video
} else {
    // Need: host/co-host status OR recording token
}
```

**Ways to get permission**:
1. Bot is host/co-host
2. Host grants recording permission
3. Use `recording_token` parameter (get via [REST API](https://developers.zoom.us/docs/meeting-sdk/apis/#operation/meetingLocalRecordingJoinToken))
4. Use `app_privilege_token` (OBF) when joining

### GLib Main Loop Required

SDK callbacks execute via GLib event loop:

```cpp
#include <glib.h>

// Setup main loop
GMainLoop* loop = g_main_loop_new(NULL, FALSE);

// Add timeout for periodic tasks
g_timeout_add_seconds(10, check_meeting_status, NULL);

// Run loop (blocks until quit)
g_main_loop_run(loop);
```

**Without GLib loop**: Callbacks never fire, join hangs indefinitely.

### Heap Memory Mode Recommended

Always use heap mode for raw data to avoid stack overflow with large frames:

```cpp
init_params.rawdataOpts.videoRawDataMemoryMode = ZoomSDKRawDataMemoryModeHeap;
init_params.rawdataOpts.shareRawDataMemoryMode = ZoomSDKRawDataMemoryModeHeap;
init_params.rawdataOpts.audioRawDataMemoryMode = ZoomSDKRawDataMemoryModeHeap;
```

### Thread Safety

SDK callbacks execute on SDK threads:
- Don't perform heavy operations in callbacks
- Don't call `CleanUPSDK()` from within callbacks
- Use thread-safe queues for data passing
- Use mutexes for shared state

## Production Architectures

### Transcription Bot

**See**: [concepts/high-level-scenarios.md#scenario-1](concepts/high-level-scenarios.md)

```
Join Meeting → StartRawRecording → Subscribe Audio →
Stream to AssemblyAI/Whisper → Generate Real-time Transcript
```

### Recording Bot

**See**: [concepts/high-level-scenarios.md#scenario-2](concepts/high-level-scenarios.md)

```
Join Meeting → StartRawRecording → Subscribe Audio+Video →
Write YUV+PCM → FFmpeg Merge → Upload to Storage
```

### AI Meeting Assistant

**See**: [concepts/high-level-scenarios.md#scenario-3](concepts/high-level-scenarios.md)

```
Join Meeting → Real-time Transcription → AI Analysis →
Extract Action Items → Generate Summary
```

## Sample Applications

**Official Repositories**:

| Sample | Description | Link |
|--------|-------------|------|
| **Raw Recording Sample** | Traditional C++ approach with config.txt | [GitHub](https://github.com/zoom/meetingsdk-linux-raw-recording-sample) |
| **Headless Sample** | Modern TOML-based with CLI, Docker Compose | [GitHub](https://github.com/zoom/meetingsdk-headless-linux-sample) |

**What Each Demonstrates**:

- **Raw Recording Sample**: Complete raw data workflow, PulseAudio setup, Docker multi-distro support
- **Headless Sample**: AssemblyAI integration, LLM analysis, production-ready config management

## Documentation Library

### Core Concepts
- **[linux.md](linux.md)** - Quick start & core workflow
- **[concepts/high-level-scenarios.md](concepts/high-level-scenarios.md)** - Production bot architectures
- **[meeting-sdk-bot.md](meeting-sdk-bot.md)** - Resilient bot with retry logic

### Platform Reference
- **[references/linux-reference.md](references/linux-reference.md)** - Dependencies, CMake, Docker, troubleshooting

### Authentication
- **[../references/authorization.md](../references/authorization.md)** - SDK JWT generation
- **[../references/bot-authentication.md](../references/bot-authentication.md)** - Bot token types (ZAK, OBF, JWT)

### Advanced Features
- **[../references/breakout-rooms.md](../references/breakout-rooms.md)** - Programmatic breakout rooms
- **[../references/ai-companion.md](../references/ai-companion.md)** - AI Companion controls

## Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| **No audio in Docker** | Missing PulseAudio config | Create `~/.config/zoomus.conf` |
| **Raw recording denied** | No permission | Use host/co-host OR recording token |
| **Callbacks not firing** | Missing GLib main loop | Add `g_main_loop_run()` |
| **Build errors (XCB)** | Missing X11 libraries | Install libxcb packages |
| **Segfault on auth** | OpenSSL version mismatch | Install libssl1.1 |

**Complete troubleshooting**: [references/linux-reference.md#troubleshooting](references/linux-reference.md)

## Resources

- **Official Docs**: https://developers.zoom.us/docs/meeting-sdk/linux/
- **API Reference**: https://marketplacefront.zoom.us/sdk/meeting/linux/
- **Dev Forum**: https://devforum.zoom.us/
- **GitHub Samples**:
  - https://github.com/zoom/meetingsdk-linux-raw-recording-sample
  - https://github.com/zoom/meetingsdk-headless-linux-sample

---

**Need help?** Start with [linux.md](linux.md) for quick start, then explore [high-level-scenarios.md](concepts/high-level-scenarios.md) for production patterns.

## Operations

- [RUNBOOK.md](RUNBOOK.md) - 5-minute preflight and debugging checklist.
