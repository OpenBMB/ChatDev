---
name: video-sdk/linux
description: "Zoom Video SDK for Linux - C++ integration for video sessions, raw audio/video capture, screen sharing, recording, and real-time communication"
---

# Zoom Video SDK - Linux Development

Expert guidance for developing with the Zoom Video SDK on Linux. This SDK enables headless video conferencing bots, raw media capture/injection, cloud recording, live streaming, and real-time transcription.

**Official Documentation**: https://developers.zoom.us/docs/video-sdk/linux/
**API Reference**: https://marketplacefront.zoom.us/sdk/custom/linux/
**Sample Repository**: https://github.com/zoom/videosdk-linux-raw-recording-sample

## SDK Overview

The Zoom Video SDK for Linux is a C++ library that provides:
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

## Project Structure

```
project/
├── CMakeLists.txt
├── config.json              # Session credentials
├── src/
│   ├── main.cpp
├── include/
│   └── zoom_video_sdk/      # SDK headers
│       ├── zoom_video_sdk_api.h
│       ├── zoom_video_sdk_interface.h
│       ├── zoom_video_sdk_delegate_interface.h
│       ├── zoom_video_sdk_def.h
│       └── helpers/         # Feature-specific interfaces
│           ├── zoom_video_sdk_audio_helper_interface.h
│           ├── zoom_video_sdk_audio_send_rawdata_interface.h  # Virtual audio
│           ├── zoom_video_sdk_video_helper_interface.h
│           ├── zoom_video_sdk_video_source_helper_interface.h # Video injection
│           └── zoom_video_sdk_user_helper_interface.h
├── lib/
│   └── zoom_video_sdk/      # SDK + Qt5 libraries
│       ├── libvideosdk.so   # Main SDK (from SDK tarball)
│       ├── libcml.so        # Required
│       ├── libmpg123.so     # Audio codec
│       ├── cpthost          # Host binary
│       ├── libQt5Core.so.5  # Qt5 dependencies (from sdk samples/qt_libs)
│       ├── libQt5Gui.so.5
│       ├── libQt5Network.so.5
│       ├── libQt5Qml.so.5
│       └── libQt5Quick.so.5
└── bin/                     # Build output
```

**CRITICAL**: SDK requires Qt5 libraries. Copy from SDK samples (`qt_libs/Qt/lib/`) and create symlinks:
```bash
cd lib/zoom_video_sdk
ln -sf libQt5Core.so.5 libQt5Core.so
ln -sf libQt5Gui.so.5 libQt5Gui.so
# ... repeat for all Qt5 libs
```

## Prerequisites

```bash
# System dependencies
sudo apt update
sudo apt install -y build-essential gcc cmake
sudo apt install -y libglib2.0-dev liblzma-dev libxcb-image0 libxcb-keysyms1 \
    libxcb-xfixes0 libxcb-xkb1 libxcb-shape0 libxcb-shm0 libxcb-randr0 \
    libxcb-xtest0 libgbm1 libxtst6 libgl1 libnss3 libasound2 libpulse0

# Qt5 is bundled with SDK - do NOT install system Qt5
# Copy Qt5 libs from SDK samples/qt_libs/Qt/lib/ to your lib directory

# For headless Linux (no soundcard)
sudo apt install -y pulseaudio
# OR use virtual audio speaker/mic in code (recommended)

# Create log directory
mkdir -p ~/.zoom/logs
```

## CMakeLists.txt Template

```cmake
cmake_minimum_required(VERSION 3.14)
project(ZoomVideoSDKBot VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(PkgConfig REQUIRED)
pkg_check_modules(GLIB REQUIRED glib-2.0)

# CRITICAL: Include both paths for nested SDK headers
include_directories(
    ${CMAKE_SOURCE_DIR}/include
    ${CMAKE_SOURCE_DIR}/include/zoom_video_sdk  # For helpers/ relative includes
    ${GLIB_INCLUDE_DIRS}
)

link_directories(${CMAKE_SOURCE_DIR}/lib/zoom_video_sdk)

set(SOURCES src/main.cpp src/ZoomDelegate.cpp)

add_executable(${PROJECT_NAME} ${SOURCES})

target_link_libraries(${PROJECT_NAME}
    videosdk
    ${GLIB_LIBRARIES}
    pthread
    Qt5Core Qt5Gui Qt5Network Qt5Qml Qt5Quick
)

set_target_properties(${PROJECT_NAME} PROPERTIES
    BUILD_RPATH "${CMAKE_SOURCE_DIR}/lib/zoom_video_sdk"
    INSTALL_RPATH "${CMAKE_SOURCE_DIR}/lib/zoom_video_sdk"
    RUNTIME_OUTPUT_DIRECTORY ${CMAKE_SOURCE_DIR}/bin
)
```

## Configuration

**config.json** (place in bin/ directory):
```json
{
    "session_name": "your-session-name",
    "token": "your.jwt.token",
    "session_psw": "optional-password"
}
```

**JWT Generation**: Use Zoom Video SDK credentials from marketplace.zoom.us

## Core Implementation Pattern

### 1. SDK Initialization

```cpp
#include "zoom_video_sdk_api.h"
#include "zoom_video_sdk_interface.h"
#include "zoom_video_sdk_delegate_interface.h"

USING_ZOOM_VIDEO_SDK_NAMESPACE

IZoomVideoSDK* video_sdk_obj = CreateZoomVideoSDKObj();

ZoomVideoSDKInitParams init_params;
init_params.domain = "https://zoom.us";
init_params.enableLog = true;
init_params.logFilePrefix = "my_bot";
init_params.videoRawDataMemoryMode = ZoomVideoSDKRawDataMemoryModeHeap;
init_params.shareRawDataMemoryMode = ZoomVideoSDKRawDataMemoryModeHeap;
init_params.audioRawDataMemoryMode = ZoomVideoSDKRawDataMemoryModeHeap;
init_params.enableIndirectRawdata = false;

ZoomVideoSDKErrors err = video_sdk_obj->initialize(init_params);
```

### 2. Session Join

```cpp
ZoomVideoSDKSessionContext session_context;
session_context.sessionName = "session-name";
session_context.sessionPassword = "password";
session_context.userName = "Linux Bot";
session_context.token = "jwt-token";
session_context.sessionIdleTimeoutMins = 40; // 0 = never timeout
session_context.autoLoadMutliStream = true;
session_context.videoOption.localVideoOn = true;
session_context.audioOption.connect = true;
session_context.audioOption.mute = false;

// For headless Linux - use virtual audio
ZoomVideoSDKVirtualAudioSpeaker* vSpeaker = new ZoomVideoSDKVirtualAudioSpeaker();
session_context.virtualAudioSpeaker = vSpeaker;

IZoomVideoSDKSession* session = video_sdk_obj->joinSession(session_context);
```

### 3. Event Delegate

```cpp
class MyDelegate : public IZoomVideoSDKDelegate {
public:
    virtual void onSessionJoin() override {
        printf("Joined session!\n");
        // Start audio subscription
        IZoomVideoSDKAudioHelper* audioHelper = video_sdk_obj->getAudioHelper();
        if (audioHelper) {
            audioHelper->startAudio();
            audioHelper->subscribe();
        }
    }

    virtual void onSessionLeave() override {
        printf("Left session\n");
    }

    virtual void onError(ZoomVideoSDKErrors errorCode, int detailErrorCode) override {
        printf("Error: %d, Detail: %d\n", errorCode, detailErrorCode);
    }

    virtual void onUserJoin(IZoomVideoSDKUserHelper* pUserHelper,
                           IVideoSDKVector<IZoomVideoSDKUser*>* userList) override {
        int count = userList->GetCount();
        for (int i = 0; i < count; i++) {
            IZoomVideoSDKUser* user = userList->GetItem(i);
            // Subscribe to user's video
            user->GetVideoPipe()->subscribe(ZoomVideoSDKResolution_720P, videoDelegate);
        }
    }

    virtual void onMixedAudioRawDataReceived(AudioRawData* data_) override {
        // Handle mixed audio (all participants)
        char* buffer = data_->GetBuffer();
        unsigned int len = data_->GetBufferLen();
        unsigned int sampleRate = data_->GetSampleRate();
        // Process PCM audio
    }

    virtual void onOneWayAudioRawDataReceived(AudioRawData* data_,
                                              IZoomVideoSDKUser* pUser) override {
        // Handle individual user audio
    }
};

video_sdk_obj->addListener(new MyDelegate());
```

## IZoomVideoSDKDelegate - CRITICAL Notes

**WARNING**: `IZoomVideoSDKDelegate` has many pure virtual methods. ALL must be implemented.

**VERSION SENSITIVITY**: The delegate interface changes between SDK versions:
- New callbacks are added, old ones may be removed
- Method signatures may change
- **ALWAYS check `zoom_video_sdk_delegate_interface.h` when upgrading SDK versions**

### Required Includes for Full Class Definitions

**VERSION SENSITIVITY**: Forward declarations in `zoom_video_sdk_def.h` may change. Always verify which helper headers contain full class definitions.

```cpp
// zoom_video_sdk_def.h only forward-declares classes!
// Include helper headers for actual implementations:
#include "zoom_video_sdk/helpers/zoom_video_sdk_user_helper_interface.h"    // IZoomVideoSDKUser full definition
#include "zoom_video_sdk/helpers/zoom_video_sdk_audio_send_rawdata_interface.h"  // Virtual audio classes
#include "zoom_video_sdk/helpers/zoom_video_sdk_video_source_helper_interface.h" // Video source/sender
#include "zoom_video_sdk/zoom_video_sdk_chat_message_interface.h"  // IZoomVideoSDKChatMessage
```

### SDK 2.4.12 Method Signature Examples

**VERSION SENSITIVITY**: Method signatures change between SDK versions. These are examples from 2.4.12 - **always verify against current SDK headers**.

| Example Change | SDK 2.4.12 Signature |
|----------------|----------------------|
| `onSessionLeave()` | `onSessionLeave(ZoomVideoSDKSessionLeaveReason reason)` (both exist) |
| `onUserShareStatusChanged(...)` | Takes `IZoomVideoSDKShareAction*` instead of `ZoomVideoSDKShareStatus, ZoomVideoSDKShareType` |
| `message->getSenderUser()` | Now `message->getSendUser()` |
| `info->getSpeaker()` | Now `info->getSpeakerName()` (returns `const zchar_t*` directly) |
| `sender->send()` | Now `sender->Send()` (capital S) |
| `user->getVideoStatus()` | Now `user->GetVideoPipe()->getVideoStatus()` |

### Required Empty Stub Callbacks

**VERSION SENSITIVITY**: Callbacks are added/removed between SDK versions. Check `zoom_video_sdk_delegate_interface.h` for the complete current list.

Must implement ALL these (use empty `{}` for unused ones):
```cpp
virtual void onUserShareStatusChanged(IZoomVideoSDKShareHelper*, IZoomVideoSDKUser*, IZoomVideoSDKShareAction*) override {}
virtual void onShareContentChanged(IZoomVideoSDKShareHelper*, IZoomVideoSDKUser*, IZoomVideoSDKShareAction*) override {}
virtual void onFailedToStartShare(IZoomVideoSDKShareHelper*, IZoomVideoSDKUser*) override {}
virtual void onShareSettingChanged(ZoomVideoSDKShareSetting) override {}
virtual void onUserManagerChanged(IZoomVideoSDKUser*) override {}
virtual void onAudioLevelChanged(unsigned int, bool, IZoomVideoSDKUser*) override {}
virtual void onSpokenLanguageChanged(ILiveTranscriptionLanguage*) override {}
virtual void onChatPrivilegeChanged(IZoomVideoSDKChatHelper*, ZoomVideoSDKChatPrivilegeType) override {}
virtual void onSendFileStatus(IZoomVideoSDKSendFile*, const FileTransferStatus&) override {}
virtual void onReceiveFileStatus(IZoomVideoSDKReceiveFile*, const FileTransferStatus&) override {}
virtual void onShareNetworkStatusChanged(ZoomVideoSDKNetworkStatus, bool) override {}
virtual void onUserNetworkStatusChanged(ZoomVideoSDKDataType, ZoomVideoSDKNetworkStatus, IZoomVideoSDKUser*) override {}
virtual void onUserOverallNetworkStatusChanged(ZoomVideoSDKNetworkStatus, IZoomVideoSDKUser*) override {}
virtual void onAnnotationHelperCleanUp(IZoomVideoSDKAnnotationHelper*) override {}
virtual void onAnnotationPrivilegeChange(IZoomVideoSDKUser*, IZoomVideoSDKShareAction*) override {}
virtual void onAnnotationHelperActived(void*) override {}
virtual void onAnnotationToolTypeChanged(IZoomVideoSDKAnnotationHelper*, void*, ZoomVideoSDKAnnotationToolType) override {}
virtual void onVideoAlphaChannelStatusChanged(bool) override {}
virtual void onSpotlightVideoChanged(IZoomVideoSDKVideoHelper*, IVideoSDKVector<IZoomVideoSDKUser*>*) override {}
// ... and many more for live stream, subsession, broadcast, etc.
```

See `zoom_video_sdk_delegate_interface.h` for complete list (~90 methods).

### IZoomVideoSDKRawDataPipeDelegate Requirements

**VERSION SENSITIVITY**: Interface methods may be added/removed between SDK versions.

```cpp
class VideoDelegate : public IZoomVideoSDKRawDataPipeDelegate {
    virtual void onRawDataFrameReceived(YUVRawDataI420* data) override { /* handle */ }
    virtual void onRawDataStatusChanged(RawDataStatus status) override { /* handle */ }
    virtual void onShareCursorDataReceived(ZoomVideoSDKShareCursorData info) override {} // REQUIRED in 2.4.12
};
```

## Raw Data Capture

### Video Raw Data (YUV I420)

```cpp
class VideoEncoder : public IZoomVideoSDKRawDataPipeDelegate {
public:
    virtual void onRawDataFrameReceived(YUVRawDataI420* data) override {
        int width = data->GetStreamWidth();
        int height = data->GetStreamHeight();

        char* yBuffer = data->GetYBuffer();
        char* uBuffer = data->GetUBuffer();
        char* vBuffer = data->GetVBuffer();
        char* alphaBuffer = data->GetAlphaBuffer(); // Optional

        unsigned long long timestamp = data->GetTimeStamp();
        int rotation = data->GetRotation(); // 0, 90, 180, 270
        bool isLimited = data->IsLimitedI420();

        // Reference counting for async processing
        if (data->CanAddRef()) {
            data->AddRef();
            // Process in background thread
            data->Release();
        }
    }

    virtual void onRawDataStatusChanged(RawDataStatus status) override {
        // RawData_On or RawData_Off
    }
};

// Subscribe to user's video
user->GetVideoPipe()->subscribe(ZoomVideoSDKResolution_720P, new VideoEncoder());
```

### Audio Raw Data (PCM)

```cpp
// Subscribe to audio in onSessionJoin or onUserAudioStatusChanged
IZoomVideoSDKAudioHelper* audioHelper = video_sdk_obj->getAudioHelper();
audioHelper->subscribe();

// Receive in callbacks:
virtual void onMixedAudioRawDataReceived(AudioRawData* data_) override {
    char* buffer = data_->GetBuffer();       // PCM 16-bit
    unsigned int len = data_->GetBufferLen();
    unsigned int sampleRate = data_->GetSampleRate();
    unsigned int channels = data_->GetChannelNum();
    unsigned long long timestamp = data_->GetTimeStamp();
}

// Convert PCM to MP3:
// ffmpeg -f s16le -ar 32000 -i output.pcm output.mp3
```

## Raw Data Injection

### Virtual Audio Mic

```cpp
class MyAudioMic : public IZoomVideoSDKVirtualAudioMic {
public:
    virtual void onMicInitialize(IZoomVideoSDKAudioSender* sender) override {
        audio_sender_ = sender;
    }

    virtual void onMicStartSend() override {
        // Start sending audio frames
    }

    virtual void onMicStopSend() override {}
    virtual void onMicUninitialized() override { audio_sender_ = nullptr; }

    void SendAudio(char* data, unsigned int len, int sampleRate) {
        if (audio_sender_) {
            audio_sender_->Send(data, len, sampleRate);
        }
    }

private:
    IZoomVideoSDKAudioSender* audio_sender_ = nullptr;
};

// Set before joining
session_context.virtualAudioMic = new MyAudioMic();
session_context.audioOption.connect = true;
session_context.audioOption.mute = false;
```

### Virtual Video Source

```cpp
class MyVideoSource : public IZoomVideoSDKVideoSource {
public:
    virtual void onInitialize(IZoomVideoSDKVideoSender* sender,
                             IVideoSDKVector<VideoSourceCapability>* caps,
                             VideoSourceCapability& suggest) override {
        video_sender_ = sender;
    }

    virtual void onStartSend() override {
        // Start sending video frames
    }

    virtual void onStopSend() override {}
    virtual void onPropertyChange(...) override {}

    void SendFrame(char* y, char* u, char* v, int w, int h, int rotation) {
        if (video_sender_) {
            video_sender_->sendVideoFrame(y, u, v, w, h, 0, rotation);
        }
    }

private:
    IZoomVideoSDKVideoSender* video_sender_ = nullptr;
};

// Set before joining
session_context.externalVideoSource = new MyVideoSource();
```

## Helper Interfaces

### Audio Helper
```cpp
IZoomVideoSDKAudioHelper* audio = video_sdk_obj->getAudioHelper();
audio->startAudio();
audio->stopAudio();
audio->muteAudio(true);
audio->subscribe();    // For raw data callbacks
audio->unSubscribe();
```

### Video Helper
```cpp
IZoomVideoSDKVideoHelper* video = video_sdk_obj->getVideoHelper();
video->startVideo();
video->stopVideo();
video->rotateMyVideo(90);
IVideoSDKVector<IZoomVideoSDKCameraDevice*>* cameras = video->getCameraList();
```

### Share Helper
```cpp
IZoomVideoSDKShareHelper* share = video_sdk_obj->getShareHelper();
share->startShare();
share->startSharingExternalSource(shareSource);
share->stopShare();
bool isSharing = share->isSharingOut();
```

### Chat Helper
```cpp
IZoomVideoSDKChatHelper* chat = video_sdk_obj->getChatHelper();
chat->sendChatToAll("Hello!");
chat->sendChatToUser(user, "Private message");
```

### Recording Helper
```cpp
IZoomVideoSDKRecordingHelper* rec = video_sdk_obj->getRecordingHelper();
if (rec->canStartRecording() == ZoomVideoSDKErrors_Success) {
    rec->startCloudRecording();
}
```

### Live Stream Helper
```cpp
IZoomVideoSDKLiveStreamHelper* ls = video_sdk_obj->getLiveStreamHelper();
if (ls->canStartLiveStream() == ZoomVideoSDKErrors_Success) {
    ls->startLiveStream("rtmp://...", "stream-key", "broadcast-url");
}
```

### Live Transcription Helper

**Note**: The session host can start/stop live transcription via the SDK object. Participants receive transcription messages via callbacks.

```cpp
IZoomVideoSDKLiveTranscriptionHelper* ltt = video_sdk_obj->getLiveTranscriptionHelper();

// Check if transcription can be started (host privilege required)
if (ltt->canStartLiveTranscription()) {
    ltt->startLiveTranscription();
}

// Set spoken language (optional)
IVideoSDKVector<ILiveTranscriptionLanguage*>* languages = ltt->getAvailableSpokenLanguages();
if (languages && languages->GetCount() > 0) {
    ltt->setSpokenLanguage(languages->GetItem(0)->getLTTLanguageID());
}

// Receive transcription in callback:
virtual void onLiveTranscriptionMsgInfoReceived(ILiveTranscriptionMessageInfo* info) override {
    const char* speaker = info->getSpeakerName();
    const char* content = info->getMessageContent();
    printf("[%s]: %s\n", speaker, content);
}

// Monitor transcription status changes:
virtual void onLiveTranscriptionStatus(ZoomVideoSDKLiveTranscriptionStatus status) override {
    // ZoomVideoSDKLiveTranscription_Status_Start or _Stop
}
```

## CMakeLists.txt Template

```cmake
cmake_minimum_required(VERSION 3.10)
project(ZoomVideoSDKBot)

set(CMAKE_CXX_STANDARD 14)

find_package(PkgConfig REQUIRED)
pkg_check_modules(GLIB REQUIRED glib-2.0)

include_directories(
    ${CMAKE_SOURCE_DIR}/src/include
    ${GLIB_INCLUDE_DIRS}
)

link_directories(${CMAKE_SOURCE_DIR}/src/lib/zoom_video_sdk)

add_executable(${PROJECT_NAME}
    src/main.cpp
    src/ZoomVideoSDKRawDataPipeDelegate.cpp
    src/ZoomVideoSDKVirtualAudioMic.cpp
    src/ZoomVideoSDKVirtualAudioSpeaker.cpp
)

target_link_libraries(${PROJECT_NAME}
    videosdk
    ${GLIB_LIBRARIES}
    pthread
    z
    lzma
)
```

## Build & Run

```bash
cmake -B build
cd build && make

# Run from bin directory
cd bin
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:../src/lib/zoom_video_sdk
./ZoomVideoSDKBot
```

## Headless Linux (Docker/WSL)

```bash
# Install PulseAudio
sudo apt install -y pulseaudio
pulseaudio --start

# Create virtual devices
pactl load-module module-null-sink sink_name=virtual_speaker
pactl load-module module-null-source source_name=virtual_mic

# Configure
mkdir -p ~/.config
cat > ~/.config/zoomus.conf << EOF
[General]
system.audio.type=default
EOF
```

Or use `IZoomVideoSDKVirtualAudioSpeaker` and `IZoomVideoSDKVirtualAudioMic` interfaces.

## Thread Safety

- SDK callbacks are on SDK's internal threads
- Don't perform heavy operations in callbacks
- Use message queues for async processing
- Don't call `cleanup()` inside callbacks

```cpp
// Reference counting for async use
if (data->CanAddRef()) {
    data->AddRef();
    // Queue for processing
    data->Release(); // When done
}
```

## Custom UI Frameworks

For applications requiring a graphical user interface, use these quickstart templates:

### Qt Framework (Recommended)

**Repository**: https://github.com/tanchunsiong/videosdk-linux-qt-quickstart

```bash
# Prerequisites
sudo apt install -y qt6-base-dev qt6-tools-dev libasound2-dev cmake

# Build
cd videosdk-linux-qt-quickstart/src
mkdir build && cd build
export Qt6_DIR=/usr/lib/x86_64-linux-gnu/cmake/Qt6
cmake .. && make -j$(nproc)

# Run
./run_qt_demo.sh
```

**Features**:
- Qt6/Qt5 cross-platform GUI
- Video rendering with QPainter + QImage
- YUV-to-RGB conversion (ITU-R BT.601)
- ALSA audio playback
- Device selection (camera, mic, speaker)
- Session management UI

**Key Components**:
- `QtMainWindow` - Main window with controls
- `QtVideoWidget` - Video display widget
- `QtVideoRenderer` - Video rendering logic
- `QtPreviewVideoHandler` - Self video preview
- `QtRemoteVideoHandler` - Remote video streams

**Qt Platform Options**:
```bash
# Desktop
./run_qt_demo.sh

# Headless/Server
QT_QPA_PLATFORM=offscreen ./run_qt_demo.sh

# Wayland
QT_QPA_PLATFORM=wayland ./run_qt_demo.sh

# X11 with SSH forwarding
ssh -X user@host
export DISPLAY=:10.0
./run_qt_demo.sh
```

### GTK Framework

**Repository**: https://github.com/tanchunsiong/videosdk-linux-gtk-quickstart

```bash
# Prerequisites
sudo apt install -y libgtkmm-3.0-dev libsdl2-dev libasound2-dev libcurl4-openssl-dev cmake

# Build
cd videosdk-linux-gtk-quickstart/src
mkdir build && cd build
cmake .. && make

# Run
cd ../bin && ./SkeletonDemo
```

**Features**:
- GTKmm 3.0 native Linux GUI
- SDL2 + Cairo video rendering
- ALSA audio integration
- Device hot-swapping
- Separate self/remote video panels
- Chat system

**Key Components**:
- `VideoRenderer` - SDL2-based rendering engine
- `VideoDisplayBridge` - SDK to renderer connection
- `PreviewVideoHandler` - Camera preview
- `RemoteVideoRawDataHandler` - Remote participant video

**Architecture**:
```
┌─────────────────────────────────────────────────────────┐
│                  GTK User Interface                      │
├─────────────────────────────────────────────────────────┤
│  Session Controls │ Device Selection │ Video Controls   │
├─────────────────────────────────────────────────────────┤
│   Self Video      │   Status Area    │  Remote Video    │
│  (Left Panel)     │                  │  (Right Panel)   │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                 Video Processing Layer                   │
│  VideoRenderer ←→ VideoDisplayBridge ←→ Device Manager  │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                    Zoom Video SDK                        │
└─────────────────────────────────────────────────────────┘
```

### Comparison

| Feature | Qt | GTK |
|---------|----|----|
| Cross-platform | Yes (Windows, Mac, Linux) | Linux-focused |
| Video Rendering | QPainter + QImage | SDL2 + Cairo |
| Threading | Qt signals/slots | Glib main loop |
| Modern C++ | Better support | Good support |
| Performance | Slightly better | Good |
| Learning Curve | Moderate | Moderate |

**Choose Qt** for: Cross-platform apps, modern C++ features, better tooling
**Choose GTK** for: Native Linux look, lightweight, GNOME integration

## Runtime Setup

### Required Symlinks

```bash
cd lib/zoom_video_sdk

# SDK library versioned symlink
ln -sf libvideosdk.so libvideosdk.so.1

# Qt5 library symlinks (if using bundled Qt)
ln -sf libQt5Core.so.5 libQt5Core.so
ln -sf libQt5Gui.so.5 libQt5Gui.so
ln -sf libQt5Network.so.5 libQt5Network.so
ln -sf libQt5Qml.so.5 libQt5Qml.so
ln -sf libQt5Quick.so.5 libQt5Quick.so
```

### Output Directories

Create directories for raw data capture (relative to binary location):
```bash
mkdir -p bin/output/audio bin/output/video
```

### Raw File Playback

```bash
# Audio (PCM 16-bit, 32kHz, Mono)
ffplay -f s16le -ar 32000 -ac 1 output/audio/mixed_audio.pcm

# Video (YUV420P) - adjust resolution as needed
ffplay -f rawvideo -pixel_format yuv420p -video_size 640x360 output/video/video.yuv

# Convert audio to MP3
ffmpeg -f s16le -ar 32000 -ac 1 -i audio.pcm output.mp3

# Convert video to MP4
ffmpeg -f rawvideo -pixel_format yuv420p -video_size 640x360 -framerate 30 -i video.yuv -c:v libx264 output.mp4
```

## Error Codes

| Code | Name | Description |
|------|------|-------------|
| 0 | Success | Operation succeeded |
| 1001 | Auth_Error | Authentication failed |
| 1002 | Auth_Empty_Token | No token provided |
| 1003 | Auth_Wrong_Token | Invalid token |
| 1004 | Auth_Expired_Token | Token expired |
| 3001 | Session_Join_Failed | Failed to join |
| 3008 | Session_Need_Password | Password required |
| 3009 | Session_Password_Wrong | Wrong password |

## Reference Files



See `linux-reference.md` for complete API documentation.
