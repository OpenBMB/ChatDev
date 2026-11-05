# Session Join Pattern - Complete Working Example

## Overview

This guide provides a complete, working example of joining a Zoom Video SDK session on Linux, including JWT generation, session configuration, event handling, and cleanup.

## Prerequisites

```bash
# System dependencies
sudo apt update
sudo apt install -y build-essential gcc cmake libglib2.0-dev liblzma-dev \
    libxcb-image0 libxcb-keysyms1 libxcb-xfixes0 libxcb-xkb1 libxcb-shape0 \
    libxcb-shm0 libxcb-randr0 libxcb-xtest0 libgbm1 libxtst6 libgl1 libnss3 \
    libasound2 libpulse0

# For headless Linux
sudo apt install -y pulseaudio
mkdir -p ~/.config
echo "[General]" > ~/.config/zoomus.conf
echo "system.audio.type=default" >> ~/.config/zoomus.conf

# Create log directory
mkdir -p ~/.zoom/logs
```

## JWT Token Generation

**CRITICAL**: You need a JWT token to join sessions. Generate from your SDK credentials.

### Using Python

```python
import jwt
import time

def generate_video_sdk_jwt(sdk_key, sdk_secret, session_name, role_type=1, session_key="", user_identity=""):
    iat = int(time.time()) - 30
    exp = iat + 60 * 60 * 2  # 2 hours

    payload = {
        "app_key": sdk_key,
        "iat": iat,
        "exp": exp,
        "tpc": session_name,
        "role_type": role_type,  # 0=participant, 1=host
    }

    if session_key:
        payload["session_key"] = session_key
    if user_identity:
        payload["user_identity"] = user_identity

    token = jwt.encode(payload, sdk_secret, algorithm="HS256")
    return token

# Usage
SDK_KEY = "YOUR_SDK_KEY"
SDK_SECRET = "YOUR_SDK_SECRET"
SESSION_NAME = "my-test-session"

jwt_token = generate_video_sdk_jwt(SDK_KEY, SDK_SECRET, SESSION_NAME, role_type=1)
print(f"JWT Token: {jwt_token}")
```

### Using Node.js

```javascript
const jwt = require('jsonwebtoken');

function generateVideoSDKJWT(sdkKey, sdkSecret, sessionName, roleType = 1) {
    const iat = Math.floor(Date.now() / 1000) - 30;
    const exp = iat + 60 * 60 * 2; // 2 hours

    const payload = {
        app_key: sdkKey,
        iat: iat,
        exp: exp,
        tpc: sessionName,
        role_type: roleType // 0=participant, 1=host
    };

    return jwt.sign(payload, sdkSecret);
}

const SDK_KEY = "YOUR_SDK_KEY";
const SDK_SECRET = "YOUR_SDK_SECRET";
const SESSION_NAME = "my-test-session";

const jwtToken = generateVideoSDKJWT(SDK_KEY, SDK_SECRET, SESSION_NAME, 1);
console.log(`JWT Token: ${jwtToken}`);
```

## Complete C++ Implementation

### Header File: BotDelegate.h

```cpp
#ifndef BOT_DELEGATE_H
#define BOT_DELEGATE_H

#include "zoom_video_sdk_api.h"
#include "zoom_video_sdk_interface.h"
#include "zoom_video_sdk_delegate_interface.h"
#include <stdio.h>
#include <atomic>

USING_ZOOM_VIDEO_SDK_NAMESPACE

class BotDelegate : public IZoomVideoSDKDelegate {
public:
    BotDelegate() : running_(true) {}

    bool isRunning() const { return running_; }
    void stop() { running_ = false; }

    // Session events
    virtual void onSessionJoin() override;
    virtual void onSessionLeave() override;
    virtual void onError(ZoomVideoSDKErrors errorCode, int detailErrorCode) override;

    // User events
    virtual void onUserJoin(IZoomVideoSDKUserHelper* pUserHelper,
                           IVideoSDKVector<IZoomVideoSDKUser*>* userList) override;
    virtual void onUserLeave(IZoomVideoSDKUserHelper* pUserHelper,
                            IVideoSDKVector<IZoomVideoSDKUser*>* userList) override;
    virtual void onUserVideoStatusChanged(IZoomVideoSDKVideoHelper* pVideoHelper,
                                         IVideoSDKVector<IZoomVideoSDKUser*>* userList) override;
    virtual void onUserAudioStatusChanged(IZoomVideoSDKAudioHelper* pAudioHelper,
                                         IVideoSDKVector<IZoomVideoSDKUser*>* userList) override;

    // Password events
    virtual void onSessionNeedPassword(IZoomVideoSDKPasswordHandler* handler) override;
    virtual void onSessionPasswordWrong(IZoomVideoSDKPasswordHandler* handler) override;

    // Host/manager events
    virtual void onUserHostChanged(IZoomVideoSDKUserHelper* pUserHelper,
                                  IZoomVideoSDKUser* pUser) override;
    virtual void onUserManagerChanged(IZoomVideoSDKUser* pUser) override;
    virtual void onUserNameChanged(IZoomVideoSDKUser* pUser) override;

    // Audio raw data (optional)
    virtual void onMixedAudioRawDataReceived(AudioRawData* data_) override;
    virtual void onOneWayAudioRawDataReceived(AudioRawData* data_,
                                             IZoomVideoSDKUser* pUser) override;

    // Minimal stubs for required callbacks
    virtual void onUserShareStatusChanged(IZoomVideoSDKShareHelper*, IZoomVideoSDKUser*,
                                         IZoomVideoSDKShareAction*) override {}
    virtual void onLiveStreamStatusChanged(IZoomVideoSDKLiveStreamHelper*,
                                          ZoomVideoSDKLiveStreamStatus) override {}
    virtual void onCloudRecordingStatus(RecordingStatus, IZoomVideoSDKRecordingConsentHandler*) override {}
    virtual void onHostAskUnmute() override {}
    virtual void onUserActiveAudioChanged(IZoomVideoSDKAudioHelper*, IVideoSDKVector<IZoomVideoSDKUser*>*) override {}
    virtual void onSessionNeedPassword(IZoomVideoSDKPasswordHandler*) override {}
    virtual void onSessionPasswordWrong(IZoomVideoSDKPasswordHandler*) override {}
    virtual void onMixedAudioRawDataReceived(AudioRawData*) override {}
    virtual void onOneWayAudioRawDataReceived(AudioRawData*, IZoomVideoSDKUser*) override {}
    virtual void onShareAudioRawDataReceived(AudioRawData*) override {}
    virtual void onUserRecordingConsent(IZoomVideoSDKUser*) override {}
    virtual void onCommandReceived(IZoomVideoSDKUser*, const zchar_t*) override {}
    virtual void onCommandChannelConnectResult(bool) override {}
    virtual void onChatNewMessageNotify(IZoomVideoSDKChatHelper*, IZoomVideoSDKChatMessage*) override {}
    virtual void onChatMsgDeleteNotification(IZoomVideoSDKChatHelper*, const zchar_t*,
                                            ZoomVideoSDKChatMessageDeleteType) override {}
    virtual void onShareContentChanged(IZoomVideoSDKShareHelper*, IZoomVideoSDKUser*,
                                      IZoomVideoSDKShareAction*) override {}
    virtual void onLiveTranscriptionStatus(ZoomVideoSDKLiveTranscriptionStatus) override {}
    virtual void onLiveTranscriptionMsgReceived(const zchar_t*, IZoomVideoSDKUser*,
                                               ZoomVideoSDKLiveTranscriptionOperationType) override {}
    virtual void onLiveTranscriptionMsgInfoReceived(ILiveTranscriptionMessageInfo*) override {}
    virtual void onLiveTranscriptionMsgError(ILiveTranscriptionLanguage*,
                                            ILiveTranscriptionLanguage*) override {}
    virtual void onOriginalLanguageMsgReceived(ILiveTranscriptionMessageInfo*) override {}
    virtual void onInviteByPhoneStatus(PhoneStatus, PhoneFailedReason) override {}
    virtual void onCalloutJoinSuccess(IZoomVideoSDKUser*, const zchar_t*) override {}
    virtual void onCameraControlRequestResult(IZoomVideoSDKUser*, bool) override {}
    virtual void onCameraControlRequestReceived(IZoomVideoSDKUser*, ZoomVideoSDKCameraControlRequestType,
                                               IZoomVideoSDKCameraControlRequestHandler*) override {}
    virtual void onProxyDetectComplete() override {}
    virtual void onProxySettingNotification(IZoomVideoSDKProxySettingHandler*) override {}
    virtual void onSSLCertVerifiedFailNotification(IZoomVideoSDKSSLCertificateInfo*) override {}
    virtual void onVideoAlphaChannelStatusChanged(bool) override {}
    virtual void onMultiCameraStreamStatusChanged(ZoomVideoSDKMultiCameraStreamStatus,
                                                 IZoomVideoSDKUser*, IZoomVideoSDKRawDataPipe*) override {}
    virtual void onUserVideoNetworkStatusChanged(ZoomVideoSDKNetworkStatus, IZoomVideoSDKUser*) override {}
    virtual void onChatPrivilegeChanged(IZoomVideoSDKChatHelper*, ZoomVideoSDKChatPrivilegeType) override {}
    virtual void onVideoCanvasSubscribeFail(ZoomVideoSDKSubscribeFailReason, IZoomVideoSDKUser*, void*) override {}
    virtual void onShareCanvasSubscribeFail(ZoomVideoSDKSubscribeFailReason, IZoomVideoSDKUser*, void*) override {}

private:
    std::atomic<bool> running_;
};

#endif // BOT_DELEGATE_H
```

### Implementation File: BotDelegate.cpp

```cpp
#include "BotDelegate.h"

void BotDelegate::onSessionJoin() {
    printf("[EVENT] Session joined successfully!\n");

    // Get session info
    IZoomVideoSDKSession* session = video_sdk_obj->getSessionInfo();
    if (session) {
        printf("  Session Name: %s\n", session->getSessionName());
        printf("  Session ID: %s\n", session->getSessionID());

        // Get myself
        IZoomVideoSDKUser* myself = session->getMyself();
        if (myself) {
            printf("  My Name: %s\n", myself->getUserName());
            printf("  Is Host: %s\n", myself->isHost() ? "Yes" : "No");
        }
    }

    // Start audio
    IZoomVideoSDKAudioHelper* audio = video_sdk_obj->getAudioHelper();
    if (audio) {
        ZoomVideoSDKErrors err = audio->startAudio();
        if (err == ZoomVideoSDKErrors_Success) {
            printf("  Audio started\n");

            // Subscribe to raw audio (optional)
            audio->subscribe();
        } else {
            printf("  Failed to start audio: %d\n", err);
        }
    }
}

void BotDelegate::onSessionLeave() {
    printf("[EVENT] Session left\n");
    running_ = false;
}

void BotDelegate::onError(ZoomVideoSDKErrors errorCode, int detailErrorCode) {
    printf("[ERROR] Error occurred: %d, Detail: %d\n", errorCode, detailErrorCode);

    // Common errors
    switch (errorCode) {
        case ZoomVideoSDKErrors_Auth_Error:
            printf("  Authentication failed - check JWT token\n");
            break;
        case ZoomVideoSDKErrors_Auth_Wrong_Key_or_Secret:
            printf("  Wrong SDK key or secret\n");
            break;
        case ZoomVideoSDKErrors_Session_Join_Failed:
            printf("  Failed to join session\n");
            break;
        case ZoomVideoSDKErrors_Session_Need_Password:
            printf("  Session requires password\n");
            break;
        case ZoomVideoSDKErrors_Session_Password_Wrong:
            printf("  Wrong session password\n");
            break;
        default:
            break;
    }
}

void BotDelegate::onUserJoin(IZoomVideoSDKUserHelper* pUserHelper,
                            IVideoSDKVector<IZoomVideoSDKUser*>* userList) {
    if (!userList) return;

    int count = userList->GetCount();
    printf("[EVENT] %d user(s) joined\n", count);

    for (int i = 0; i < count; i++) {
        IZoomVideoSDKUser* user = userList->GetItem(i);
        if (user) {
            printf("  User: %s\n", user->getUserName());
        }
    }
}

void BotDelegate::onUserLeave(IZoomVideoSDKUserHelper* pUserHelper,
                             IVideoSDKVector<IZoomVideoSDKUser*>* userList) {
    if (!userList) return;

    int count = userList->GetCount();
    printf("[EVENT] %d user(s) left\n", count);

    for (int i = 0; i < count; i++) {
        IZoomVideoSDKUser* user = userList->GetItem(i);
        if (user) {
            printf("  User: %s\n", user->getUserName());
        }
    }
}

void BotDelegate::onUserVideoStatusChanged(IZoomVideoSDKVideoHelper* pVideoHelper,
                                          IVideoSDKVector<IZoomVideoSDKUser*>* userList) {
    if (!userList) return;

    int count = userList->GetCount();
    for (int i = 0; i < count; i++) {
        IZoomVideoSDKUser* user = userList->GetItem(i);
        if (user) {
            printf("[EVENT] Video status changed for: %s\n", user->getUserName());
            // Subscribe to video here if needed
        }
    }
}

void BotDelegate::onUserAudioStatusChanged(IZoomVideoSDKAudioHelper* pAudioHelper,
                                          IVideoSDKVector<IZoomVideoSDKUser*>* userList) {
    if (!userList) return;

    int count = userList->GetCount();
    for (int i = 0; i < count; i++) {
        IZoomVideoSDKUser* user = userList->GetItem(i);
        if (user) {
            IZoomVideoSDKAudioStatus* audioStatus = user->getAudioStatus();
            if (audioStatus) {
                printf("[EVENT] Audio status for %s: Muted=%s\n",
                      user->getUserName(),
                      audioStatus->isMuted() ? "Yes" : "No");
            }
        }
    }
}

void BotDelegate::onSessionNeedPassword(IZoomVideoSDKPasswordHandler* handler) {
    printf("[EVENT] Session requires password\n");
    // Provide password if available
    // handler->inputSessionPassword("password");
    // Or leave without password
    // handler->leaveSessionIgnorePassword();
}

void BotDelegate::onSessionPasswordWrong(IZoomVideoSDKPasswordHandler* handler) {
    printf("[EVENT] Wrong session password\n");
    // Retry with correct password or leave
    // handler->inputSessionPassword("correct-password");
    // handler->leaveSessionIgnorePassword();
}

void BotDelegate::onUserHostChanged(IZoomVideoSDKUserHelper* pUserHelper,
                                   IZoomVideoSDKUser* pUser) {
    if (pUser) {
        printf("[EVENT] Host changed to: %s\n", pUser->getUserName());
    }
}

void BotDelegate::onUserManagerChanged(IZoomVideoSDKUser* pUser) {
    if (pUser) {
        printf("[EVENT] Manager changed: %s (Is Manager: %s)\n",
              pUser->getUserName(),
              pUser->isManager() ? "Yes" : "No");
    }
}

void BotDelegate::onUserNameChanged(IZoomVideoSDKUser* pUser) {
    if (pUser) {
        printf("[EVENT] User name changed to: %s\n", pUser->getUserName());
    }
}

void BotDelegate::onMixedAudioRawDataReceived(AudioRawData* data_) {
    // Process mixed audio (all participants)
    // char* buffer = data_->GetBuffer();
    // unsigned int len = data_->GetBufferLen();
    // unsigned int sampleRate = data_->GetSampleRate();
}

void BotDelegate::onOneWayAudioRawDataReceived(AudioRawData* data_,
                                              IZoomVideoSDKUser* pUser) {
    // Process per-user audio
    // if (pUser) {
    //     printf("Audio from: %s\n", pUser->getUserName());
    // }
}
```

### Main File: main.cpp

**IMPORTANT**: The SDK internally uses Qt/GLib for event dispatching. You MUST use a GLib main loop — a `while (running) { sleep(); }` loop will NOT dispatch SDK events, and callbacks like `onSessionJoin` will never fire. See [Common Issues](../troubleshooting/common-issues.md) for details.

```cpp
#include "BotDelegate.h"
#include <glib.h>
#include <thread>
#include <chrono>
#include <signal.h>

IZoomVideoSDK* video_sdk_obj = nullptr;
BotDelegate* delegate = nullptr;
static GMainLoop* g_loop = nullptr;

// GLib timeout callback - checks if bot should stop
static gboolean glib_timeout_callback(gpointer data) {
    BotDelegate* del = static_cast<BotDelegate*>(data);
    if (!del->isRunning()) {
        g_main_loop_quit(g_loop);
        return FALSE;  // Remove this timeout source
    }
    return TRUE;  // Keep checking
}

void signalHandler(int signum) {
    printf("\nReceived signal %d, cleaning up...\n", signum);
    if (delegate) {
        delegate->stop();
    }
    if (g_loop) {
        g_main_loop_quit(g_loop);
    }
}

int main(int argc, char* argv[]) {
    // Check arguments
    if (argc < 4) {
        printf("Usage: %s <session_name> <user_name> <jwt_token> [session_password]\n", argv[0]);
        return 1;
    }

    const char* sessionName = argv[1];
    const char* userName = argv[2];
    const char* jwtToken = argv[3];
    const char* sessionPassword = (argc >= 5) ? argv[4] : "";

    // Setup signal handlers
    signal(SIGINT, signalHandler);
    signal(SIGTERM, signalHandler);

    printf("Zoom Video SDK Bot\n");
    printf("==================\n");
    printf("Session: %s\n", sessionName);
    printf("User: %s\n", userName);
    printf("\n");

    // 1. Create SDK object
    video_sdk_obj = CreateZoomVideoSDKObj();
    if (!video_sdk_obj) {
        printf("Failed to create SDK object\n");
        return 1;
    }

    // 2. Initialize SDK
    ZoomVideoSDKInitParams init_params;
    init_params.domain = "https://zoom.us";
    init_params.enableLog = true;
    init_params.logFilePrefix = "bot";
    init_params.videoRawDataMemoryMode = ZoomVideoSDKRawDataMemoryModeHeap;
    init_params.shareRawDataMemoryMode = ZoomVideoSDKRawDataMemoryModeHeap;
    init_params.audioRawDataMemoryMode = ZoomVideoSDKRawDataMemoryModeHeap;
    init_params.enableIndirectRawdata = false;

    ZoomVideoSDKErrors err = video_sdk_obj->initialize(init_params);
    if (err != ZoomVideoSDKErrors_Success) {
        printf("Failed to initialize SDK: %d\n", err);
        DestroyZoomVideoSDKObj();
        return 1;
    }

    printf("SDK initialized\n");

    // 3. Add delegate
    delegate = new BotDelegate();
    video_sdk_obj->addListener(delegate);

    // 4. Configure session context
    ZoomVideoSDKSessionContext session_context;
    session_context.sessionName = sessionName;
    session_context.sessionPassword = sessionPassword;
    session_context.userName = userName;
    session_context.token = jwtToken;
    session_context.sessionIdleTimeoutMins = 40;
    session_context.autoLoadMutliStream = true;
    session_context.videoOption.localVideoOn = false;  // Headless bot
    session_context.audioOption.connect = true;
    session_context.audioOption.mute = false;

    // For headless Linux: Virtual audio speaker
    // Uncomment if you have implemented VirtualSpeaker class
    // session_context.virtualAudioSpeaker = new VirtualSpeaker();

    // 5. Join session
    printf("Joining session...\n");
    IZoomVideoSDKSession* session = video_sdk_obj->joinSession(session_context);

    if (!session) {
        printf("Failed to join session\n");
        video_sdk_obj->cleanup();
        DestroyZoomVideoSDKObj();
        delete delegate;
        return 1;
    }

    // 6. GLib main loop - REQUIRED for SDK event dispatching
    // A while/sleep loop does NOT work — SDK callbacks will never fire without GLib.
    printf("Bot is running. Press Ctrl+C to exit.\n\n");

    g_loop = g_main_loop_new(NULL, FALSE);
    g_timeout_add(100, glib_timeout_callback, delegate);
    g_main_loop_run(g_loop);  // Blocks here, SDK events dispatch on this thread
    g_main_loop_unref(g_loop);

    // 7. Cleanup
    printf("\nCleaning up...\n");

    if (video_sdk_obj->isInSession()) {
        video_sdk_obj->leaveSession(false);

        // Wait a bit for leave to complete
        std::this_thread::sleep_for(std::chrono::milliseconds(500));
    }

    video_sdk_obj->cleanup();
    DestroyZoomVideoSDKObj();

    delete delegate;

    printf("Goodbye!\n");
    return 0;
}
```

## CMakeLists.txt

```cmake
cmake_minimum_required(VERSION 3.14)
project(ZoomVideoSDKBot VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(PkgConfig REQUIRED)
pkg_check_modules(GLIB REQUIRED glib-2.0)

# SDK paths
include_directories(
    ${CMAKE_SOURCE_DIR}/include
    ${CMAKE_SOURCE_DIR}/include/zoom_video_sdk
    ${GLIB_INCLUDE_DIRS}
)

link_directories(${CMAKE_SOURCE_DIR}/lib/zoom_video_sdk)

# Source files
set(SOURCES
    src/main.cpp
    src/BotDelegate.cpp
)

add_executable(${PROJECT_NAME} ${SOURCES})

target_link_libraries(${PROJECT_NAME}
    videosdk
    ${GLIB_LIBRARIES}
    pthread
)

set_target_properties(${PROJECT_NAME} PROPERTIES
    BUILD_RPATH "${CMAKE_SOURCE_DIR}/lib/zoom_video_sdk"
    INSTALL_RPATH "${CMAKE_SOURCE_DIR}/lib/zoom_video_sdk"
    RUNTIME_OUTPUT_DIRECTORY ${CMAKE_SOURCE_DIR}/bin
)
```

## Build and Run

```bash
# 1. Extract SDK
tar -xf zoom-video-sdk-linux_x86_64.tar.xz
cd zoom-video-sdk-linux_x86_64

# 2. Copy Qt5 libraries and create symlinks
cp -r samples/qt_libs/Qt/lib/* lib/
cd lib
for lib in libQt5*.so.5; do
    ln -sf $lib ${lib%.5}
done
cd ..

# 3. Build
mkdir build && cd build
cmake ..
make

# 4. Generate JWT token (use Python script above)
JWT_TOKEN="your.jwt.token.here"

# 5. Run
cd ../bin
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:../lib/zoom_video_sdk
./ZoomVideoSDKBot "test-session" "Linux Bot" "$JWT_TOKEN"
```

## Testing

```bash
# Test with password
./ZoomVideoSDKBot "test-session" "Bot" "$JWT_TOKEN" "password123"

# Test as host (role_type=1 in JWT)
./ZoomVideoSDKBot "host-session" "Host Bot" "$HOST_JWT_TOKEN"

# Test as participant (role_type=0 in JWT)
./ZoomVideoSDKBot "join-session" "Participant Bot" "$PARTICIPANT_JWT_TOKEN"
```

## Common Issues

### Issue: Callbacks not firing

**Solution**: You MUST use a GLib main loop (`g_main_loop_run`). A `while/sleep` loop does not dispatch SDK events. See the main.cpp example above and [Common Issues](../troubleshooting/common-issues.md).

### Issue: "Failed to join session"

**Causes**:
1. Invalid JWT token
2. Session name doesn't match JWT `tpc` claim
3. Wrong SDK credentials
4. Expired token

**Solution**: Verify JWT payload and regenerate token.

### Issue: "Auth failed"

**Solution**: Check SDK_KEY and SDK_SECRET in JWT generation.

### Issue: No audio on headless Linux

**Solution**: Use virtual audio speaker:
```cpp
session_context.virtualAudioSpeaker = new VirtualSpeaker();
```

---

## See Also

- **[SDK Architecture Pattern](../concepts/sdk-architecture-pattern.md)** - Universal pattern
- **[Raw Audio Capture](raw-audio-capture.md)** - Capture audio
- **[Raw Video Capture](raw-video-capture.md)** - Capture video
- **[Virtual Audio/Video](virtual-audio-video.md)** - Custom media injection
- **[Command Channel](command-channel.md)** - Custom command messaging with threading
