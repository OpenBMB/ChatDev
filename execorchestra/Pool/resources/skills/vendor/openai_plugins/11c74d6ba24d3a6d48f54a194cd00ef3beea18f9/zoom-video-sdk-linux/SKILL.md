---
name: zoom-video-sdk-linux
description: "Zoom Video SDK for Linux - C++ headless bots, raw audio/video capture/injection, Qt/GTK integration, Docker support"
---

# Zoom Video SDK - Linux Development

Expert guidance for developing with the Zoom Video SDK on Linux. Build headless bots, raw media capture/injection applications, and custom UI integrations with Qt/GTK.

**Official Documentation**: https://developers.zoom.us/docs/video-sdk/linux/
**API Reference**: https://marketplacefront.zoom.us/sdk/custom/linux/
**Sample Repository**: https://github.com/zoom/videosdk-linux-raw-recording-sample

## Quick Links

**New to Video SDK? Follow this path:**

1. **[SDK Architecture Pattern](concepts/sdk-architecture-pattern.md)** - Universal 3-step pattern for ANY feature
2. **[Session Join Pattern](examples/session-join-pattern.md)** - Complete working code to join a session
3. **[Raw Data vs Canvas](concepts/raw-data-vs-canvas.md)** - **CRITICAL**: Linux has NO Canvas API - raw data ONLY
4. **[Raw Video Capture](examples/raw-video-capture.md)** - Capture and process YUV420 frames

**Reference:**
- **[Singleton Hierarchy](concepts/singleton-hierarchy.md)** - 5-level SDK navigation map
- **[API Reference](references/linux-reference.md)** - Complete API documentation
- **[Qt/GTK Integration](examples/qt-gtk-integration.md)** - UI framework patterns
- **[Troubleshooting](troubleshooting/common-issues.md)** - Quick diagnostics
- **[SKILL.md](SKILL.md)** - Complete documentation navigation

**Having issues?**
- PulseAudio setup → [PulseAudio Guide](troubleshooting/pulseaudio-setup.md)
- Qt dependencies → [Qt Dependencies](troubleshooting/qt-dependencies.md)
- Build errors → [Build Errors Guide](troubleshooting/build-errors.md)

## Key Differences from Windows/macOS

| Feature | Linux | Windows/Mac |
|---------|-------|-------------|
| **Canvas API** | ❌ Not available | ✅ Available |
| **Raw Data Pipe** | ✅ **ONLY option** | ✅ Available |
| **UI Integration** | Qt, GTK, SDL2, OpenGL | Win32/WinForms/WPF, Cocoa |
| **Headless Support** | ✅ Excellent (Docker) | Limited |
| **Audio** | PulseAudio required | Native |
| **Virtual Devices** | ✅ Required for headless | Optional |

## SDK Overview

The Zoom Video SDK for Linux is a C++ library optimized for:
- **Headless Bots**: Docker/WSL support, no display required
- **Raw Data Access**: Capture YUV420 video, PCM audio
- **Raw Data Injection**: Virtual camera/mic for custom media
- **Screen Sharing**: Capture or inject share data
- **Cloud Recording**: Record sessions to Zoom cloud
- **Live Streaming**: Stream to RTMP endpoints
- **Live Transcription**: Real-time speech-to-text
- **Qt/GTK Integration**: Full UI framework support

## Prerequisites

### System Requirements

- **OS**: Ubuntu 20.04+, Debian 11+, or compatible
- **Architecture**: x64 (recommended), ARM64
- **Compiler**: GCC 9+, Clang 10+
- **CMake**: 3.14 or later
- **Qt5**: Bundled with SDK (do NOT install system Qt5)

### Dependencies

```bash
sudo apt update
sudo apt install -y build-essential gcc cmake libglib2.0-dev liblzma-dev \
    libxcb-image0 libxcb-keysyms1 libxcb-xfixes0 libxcb-xkb1 libxcb-shape0 \
    libxcb-shm0 libxcb-randr0 libxcb-xtest0 libgbm1 libxtst6 libgl1 libnss3 \
    libasound2 libpulse0

# For headless Linux
sudo apt install -y pulseaudio

# PulseAudio configuration (CRITICAL for audio)
mkdir -p ~/.config
echo "[General]" > ~/.config/zoomus.conf
echo "system.audio.type=default" >> ~/.config/zoomus.conf

# Log directory
mkdir -p ~/.zoom/logs
```

## Quick Start

```cpp
#include "zoom_video_sdk_api.h"
#include "zoom_video_sdk_interface.h"
#include "zoom_video_sdk_delegate_interface.h"

USING_ZOOM_VIDEO_SDK_NAMESPACE

// 1. Create SDK
IZoomVideoSDK* sdk = CreateZoomVideoSDKObj();

// 2. Initialize
ZoomVideoSDKInitParams init_params;
init_params.domain = "https://zoom.us";
init_params.enableLog = true;
init_params.logFilePrefix = "bot";
init_params.videoRawDataMemoryMode = ZoomVideoSDKRawDataMemoryModeHeap;
init_params.shareRawDataMemoryMode = ZoomVideoSDKRawDataMemoryModeHeap;
init_params.audioRawDataMemoryMode = ZoomVideoSDKRawDataMemoryModeHeap;

sdk->initialize(init_params);

// 3. Add delegate
sdk->addListener(myDelegate);

// 4. Join session
ZoomVideoSDKSessionContext ctx;
ctx.sessionName = "my-session";
ctx.userName = "Linux Bot";
ctx.token = "jwt-token";
ctx.audioOption.connect = true;
ctx.audioOption.mute = false;
ctx.videoOption.localVideoOn = false;

// For headless: Virtual audio speaker
ctx.virtualAudioSpeaker = new VirtualSpeaker();

IZoomVideoSDKSession* session = sdk->joinSession(ctx);
```

See **[Session Join Pattern](examples/session-join-pattern.md)** for complete code.

## Key Features

| Feature | Linux Support | Guide |
|---------|---------------|-------|
| **Session Management** | ✅ Full | [Session Join](examples/session-join-pattern.md) |
| **Raw Video (YUV420)** | ✅ ONLY rendering option | [Raw Video](examples/raw-video-capture.md) |
| **Raw Audio (PCM)** | ✅ Full | [Raw Audio](examples/raw-audio-capture.md) |
| **Virtual Camera/Mic** | ✅ Full | [Virtual Devices](examples/virtual-audio-video.md) |
| **Cloud Recording** | ✅ Full | [Recording](examples/cloud-recording.md) |
| **Live Streaming** | ✅ Full | [Live Stream](examples/live-streaming.md) |
| **Live Transcription** | ✅ Full | [Transcription](examples/transcription.md) |
| **Command Channel** | ✅ Full | [Commands](examples/command-channel.md) |
| **Chat** | ✅ Full | [Chat](examples/chat.md) |
| **Qt Integration** | ✅ Recommended | [Qt/GTK](examples/qt-gtk-integration.md) |
| **GTK Integration** | ✅ Supported | [Qt/GTK](examples/qt-gtk-integration.md) |
| **Docker/Headless** | ✅ Excellent | [Virtual Devices](examples/virtual-audio-video.md) |

## Critical Gotchas

### ⚠️ CRITICAL #1: No Canvas API on Linux

**Problem**: Linux SDK does NOT have Canvas API like Windows/Mac.

**Solution**: You MUST use Raw Data Pipe and implement your own rendering.

See: **[Raw Data vs Canvas](concepts/raw-data-vs-canvas.md)**

### ⚠️ CRITICAL #2: PulseAudio Required for Audio

**Problem**: SDK requires PulseAudio for raw audio functions.

**Solution**:
```bash
sudo apt install -y pulseaudio
mkdir -p ~/.config
echo "[General]" > ~/.config/zoomus.conf
echo "system.audio.type=default" >> ~/.config/zoomus.conf
```

See: **[PulseAudio Setup](troubleshooting/pulseaudio-setup.md)**

### ⚠️ CRITICAL #3: Qt5 Dependencies

**Problem**: SDK requires Qt5 libraries (bundled, NOT system Qt5).

**Solution**:
```bash
# Copy from SDK package
cp -r samples/qt_libs/Qt/lib/* lib/zoom_video_sdk/

# Create symlinks
cd lib/zoom_video_sdk
for lib in libQt5*.so.5; do ln -sf $lib ${lib%.5}; done
```

See: **[Qt Dependencies](troubleshooting/qt-dependencies.md)**

### ⚠️ CRITICAL #4: Heap Memory Mode

Always use heap mode for raw data:

```cpp
init_params.videoRawDataMemoryMode = ZoomVideoSDKRawDataMemoryModeHeap;
init_params.shareRawDataMemoryMode = ZoomVideoSDKRawDataMemoryModeHeap;
init_params.audioRawDataMemoryMode = ZoomVideoSDKRawDataMemoryModeHeap;
```

### ⚠️ CRITICAL #5: Virtual Audio for Headless

**Problem**: Docker/headless environments have no audio devices.

**Solution**: Use virtual audio speaker and mic.

```cpp
session_context.virtualAudioSpeaker = new VirtualSpeaker();
session_context.virtualAudioMic = new VirtualMic();
```

See: **[Virtual Audio/Video](examples/virtual-audio-video.md)**

## Sample Repositories

### Official Samples

| Repository | Description |
|-----------|-------------|
| **[raw-recording-sample](https://github.com/zoom/videosdk-linux-raw-recording-sample)** | Raw audio/video capture |
| **[qt-quickstart](https://github.com/tanchunsiong/videosdk-linux-qt-quickstart)** | Qt6 UI integration |
| **[gtk-quickstart](https://github.com/tanchunsiong/videosdk-linux-gtk-quickstart)** | GTK3 UI integration |

### Sample Architecture

```
Headless Bot (Docker):
┌──────────────────────────────────┐
│  Virtual Audio Speaker/Mic       │
├──────────────────────────────────┤
│  Raw Data Processing             │
│  - YUV420 → File/Stream


## Merged from video-sdk/linux/SKILL.md

# Zoom Video SDK Linux - Complete Documentation Index

## Quick Start Path

**If you're new to the SDK, follow this order:**

1. **Read the architecture pattern** → [concepts/sdk-architecture-pattern.md](concepts/sdk-architecture-pattern.md)
   - Universal formula: Singleton → Delegate → Subscribe
   - Once you understand this, you can implement any feature

2. **Understand Linux specifics** → [concepts/raw-data-vs-canvas.md](concepts/raw-data-vs-canvas.md)
   - **CRITICAL**: Linux has NO Canvas API - raw data ONLY

3. **Implement session join** → [examples/session-join-pattern.md](examples/session-join-pattern.md)
   - Complete working JWT + session join code

4. **Setup environment** → [troubleshooting/pulseaudio-setup.md](troubleshooting/pulseaudio-setup.md)
   - PulseAudio configuration (required for audio)
   - [troubleshooting/qt-dependencies.md](troubleshooting/qt-dependencies.md)
   - Qt5 library setup (bundled with SDK)

5. **Implement features** → Choose from examples below

---

## Documentation Structure

```
video-sdk/linux/
├── SKILL.md                          # Main skill overview
├── SKILL.md                          # This file - navigation guide
├── linux.md                          # Platform summary
│
├── concepts/                         # Core architectural patterns
│   ├── sdk-architecture-pattern.md  # Universal formula for ANY feature
│   ├── singleton-hierarchy.md       # 5-level navigation guide
│   └── raw-data-vs-canvas.md        # Linux-specific: raw data ONLY
│
├── examples/                         # Complete working code
│   ├── session-join-pattern.md      # JWT auth + session join
│   └── command-channel.md           # Command channel with threading
│
├── troubleshooting/                  # Problem solving guides
│   ├── pulseaudio-setup.md          # Audio configuration
│   ├── qt-dependencies.md           # Qt5 library setup
│   ├── build-errors.md              # Common build issues
│   └── common-issues.md             # Quick diagnostic workflow
│
└── references/                       # Reference documentation
    └── linux-reference.md           # API hierarchy, methods, error codes
```

---

## By Use Case

### I want to build a headless bot
1. [SDK Architecture Pattern](concepts/sdk-architecture-pattern.md) - Understand the pattern
2. [Session Join Pattern](examples/session-join-pattern.md) - Join sessions
3. [PulseAudio Setup](troubleshooting/pulseaudio-setup.md) - Configure audio
4. [Raw Data vs Canvas](concepts/raw-data-vs-canvas.md) - Understand Linux differences

### I'm getting build errors
1. [Build Errors Guide](troubleshooting/build-errors.md) - SDK build issues
2. [Qt Dependencies](troubleshooting/qt-dependencies.md) - Qt5 setup
3. [Common Issues](troubleshooting/common-issues.md) - Quick diagnostics

### I'm getting runtime errors
1. [PulseAudio Setup](troubleshooting/pulseaudio-setup.md) - Audio not working
2. [Qt Dependencies](troubleshooting/qt-dependencies.md) - Library not found
3. [Common Issues](troubleshooting/common-issues.md) - Error code tables

### I want to use command channel
1. [Command Channel](examples/command-channel.md) - Send/receive commands
2. [Common Issues](troubleshooting/common-issues.md) - Threading requirements

### I want to implement a specific feature
1. [SDK Architecture Pattern](concepts/sdk-architecture-pattern.md) - **START HERE!**
2. [Singleton Hierarchy](concepts/singleton-hierarchy.md) - Navigate to the feature
3. [API Reference](references/linux-reference.md) - Method signatures

---

## Most Critical Documents

### 1. SDK Architecture Pattern (MASTER DOCUMENT)
**[concepts/sdk-architecture-pattern.md](concepts/sdk-architecture-pattern.md)**

The universal 3-step pattern:
1. Get singleton (SDK, helpers, session, users)
2. Implement delegate (event callbacks)
3. Subscribe and use

### 2. Raw Data vs Canvas (LINUX-SPECIFIC)
**[concepts/raw-data-vs-canvas.md](concepts/raw-data-vs-canvas.md)**

**CRITICAL**: Unlike Windows/Mac, Linux SDK has NO Canvas API. You MUST use raw data pipe.

### 3. PulseAudio Setup (MOST COMMON ISSUE)
**[troubleshooting/pulseaudio-setup.md](troubleshooting/pulseaudio-setup.md)**

Audio requires PulseAudio configuration.

### 4. Qt Dependencies
**[troubleshooting/qt-dependencies.md](troubleshooting/qt-dependencies.md)**

SDK requires bundled Qt5 libraries, NOT system Qt5.

---

## Key Learnings

### Critical Discoveries:

1. **Linux has NO Canvas API**
   - Windows/Mac have Canvas API for SDK-rendered video
   - Linux MUST use Raw Data Pipe
   - See: [Raw Data vs Canvas](concepts/raw-data-vs-canvas.md)

2. **PulseAudio is MANDATORY**
   - SDK requires PulseAudio for raw audio
   - Must configure ~/.config/zoomus.conf
   - See: [PulseAudio Setup](troubleshooting/pulseaudio-setup.md)

3. **Use Bundled Qt5, NOT System Qt5**
   - SDK includes specific Qt5 versions
   - Copy from samples/qt_libs/
   - See: [Qt Dependencies](troubleshooting/qt-dependencies.md)

4. **Helpers Control YOUR Streams Only**
   - `videoHelper->startVideo()` starts YOUR camera
   - To see others, subscribe to their VideoPipe
   - See: [Singleton Hierarchy](concepts/singleton-hierarchy.md)

5. **Virtual Devices for Headless**
   - Docker/headless needs virtual audio speaker/mic
   - Set before joining session
   - See: [Session Join Pattern](examples/session-join-pattern.md)

6. **Always Use Heap Memory Mode**
   ```cpp
   init_params.videoRawDataMemoryMode = ZoomVideoSDKRawDataMemoryModeHeap;
   ```

7. **GLib Main Loop Required**
   - while/sleep loops don't dispatch SDK events
   - Must use g_main_loop_run()
   - See: [Common Issues](troubleshooting/common-issues.md)

8. **All SDK Calls Must Be on Main Thread**
   - Background thread SDK calls return error 2 (Internal_Error)
   - Use g_idle_add() to schedule on GLib main thread
   - See: [Command Channel](examples/command-channel.md)

9. **Command Channel is Session-Scoped**
   - Does NOT span across different sessions
   - Both sender and receiver must be in the same session
   - See: [Command Channel](examples/command-channel.md)

---

## Sample Repositories

- **[raw-recording-sample](https://github.com/zoom/videosdk-linux-raw-recording-sample)** - Official raw data sample
- **[qt-quickstart](https://github.com/tanchunsiong/videosdk-linux-qt-quickstart)** - Qt6 UI integration
- **[gtk-quickstart](https://github.com/tanchunsiong/videosdk-linux-gtk-quickstart)** - GTK3 UI integration

---

## Quick Reference

### "My code won't compile"
→ [Build Errors Guide](troubleshooting/build-errors.md)

### "Audio not working"
→ [PulseAudio Setup](troubleshooting/pulseaudio-setup.md)

### "Library not found"
→ [Qt Dependencies](troubleshooting/qt-dependencies.md)

### "How do I implement [feature]?"
→ [SDK Architecture Pattern](concepts/sdk-architecture-pattern.md)

### "What error code means what?"
→ [Common Issues](troubleshooting/common-issues.md)

---

## Document Version

Based on **Zoom Video SDK for Linux v2.x**

---

**Happy coding!**

Remember: The [SDK Architecture Pattern](concepts/sdk-architecture-pattern.md) is your key to unlocking the entire SDK. Read it first!

## Operations

- [RUNBOOK.md](RUNBOOK.md) - 5-minute preflight and debugging checklist.
