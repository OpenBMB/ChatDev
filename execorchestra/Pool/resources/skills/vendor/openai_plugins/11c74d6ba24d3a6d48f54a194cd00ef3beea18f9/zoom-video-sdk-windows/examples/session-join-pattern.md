# Session Join Pattern

Complete working code for initializing the SDK and joining a session.

## Overview

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  InitSDK    │───►│  AddListener│───►│ JoinSession │───►│ onSessionJoin│
│             │    │  (delegate) │    │  (JWT)      │    │  callback   │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

---

## Complete Working Code

### main.cpp

```cpp
#include <windows.h>
#include <cstdint>
#include <iostream>
#include <fstream>
#include <string>
#include <thread>
#include <chrono>

// SDK headers
#include "zoom_video_sdk_api.h"
#include "zoom_video_sdk_interface.h"
#include "zoom_video_sdk_delegate_interface.h"

// JSON parsing (optional - for config file)
#include <json/json.h>

USING_ZOOM_VIDEO_SDK_NAMESPACE

// Global state
IZoomVideoSDK* g_sdk = nullptr;
bool g_inSession = false;
bool g_exit = false;

// Configuration
std::wstring g_jwt;
std::wstring g_sessionName;
std::wstring g_sessionPassword;
std::wstring g_userName;

//─────────────────────────────────────────────────────────────────────────────
// DELEGATE IMPLEMENTATION
//─────────────────────────────────────────────────────────────────────────────

class MyDelegate : public IZoomVideoSDKDelegate {
public:
    // === SESSION LIFECYCLE ===

    void onSessionJoin() override {
        std::cout << "[EVENT] Session joined successfully!" << std::endl;
        g_inSession = true;

        // Connect audio
        IZoomVideoSDKAudioHelper* audioHelper = g_sdk->getAudioHelper();
        if (audioHelper) {
            audioHelper->startAudio();
            std::cout << "[ACTION] Audio connected" << std::endl;
        }

        // Start video
        IZoomVideoSDKVideoHelper* videoHelper = g_sdk->getVideoHelper();
        if (videoHelper) {
            videoHelper->startVideo();
            std::cout << "[ACTION] Video started" << std::endl;
        }
    }

    void onSessionLeave() override {
        std::cout << "[EVENT] Session left" << std::endl;
        g_inSession = false;
        g_exit = true;
    }

    void onError(ZoomVideoSDKErrors errorCode, int detailErrorCode) override {
        std::cout << "[ERROR] Code: " << errorCode
                  << ", Detail: " << detailErrorCode << std::endl;
    }

    // === USER EVENTS ===

    void onUserJoin(IZoomVideoSDKUserHelper* helper,
                    IVideoSDKVector<IZoomVideoSDKUser*>* userList) override {
        for (int i = 0; i < userList->GetCount(); i++) {
            IZoomVideoSDKUser* user = userList->GetItem(i);
            std::wcout << L"[EVENT] User joined: " << user->getUserName() << std::endl;
        }
    }

    void onUserLeave(IZoomVideoSDKUserHelper* helper,
                     IVideoSDKVector<IZoomVideoSDKUser*>* userList) override {
        for (int i = 0; i < userList->GetCount(); i++) {
            IZoomVideoSDKUser* user = userList->GetItem(i);
            std::wcout << L"[EVENT] User left: " << user->getUserName() << std::endl;
        }
    }

    void onUserVideoStatusChanged(IZoomVideoSDKVideoHelper* helper,
                                  IVideoSDKVector<IZoomVideoSDKUser*>* userList) override {
        for (int i = 0; i < userList->GetCount(); i++) {
            IZoomVideoSDKUser* user = userList->GetItem(i);
            bool isOn = user->GetVideoPipe()->getVideoStatus().isOn;
            std::wcout << L"[EVENT] Video " << (isOn ? L"ON" : L"OFF")
                       << L": " << user->getUserName() << std::endl;
        }
    }

    void onUserAudioStatusChanged(IZoomVideoSDKAudioHelper* helper,
                                  IVideoSDKVector<IZoomVideoSDKUser*>* userList) override {
        for (int i = 0; i < userList->GetCount(); i++) {
            IZoomVideoSDKUser* user = userList->GetItem(i);
            bool isMuted = user->getAudioStatus().isMuted;
            std::wcout << L"[EVENT] Audio " << (isMuted ? L"muted" : L"unmuted")
                       << L": " << user->getUserName() << std::endl;
        }
    }

    // === CHAT ===

    void onChatNewMessageNotify(IZoomVideoSDKChatHelper* helper,
                                IZoomVideoSDKChatMessage* msg) override {
        std::wcout << L"[CHAT] " << msg->getSendUser()->getUserName()
                   << L": " << msg->getContent() << std::endl;
    }

    // === REQUIRED EMPTY IMPLEMENTATIONS ===
    // (All pure virtual methods must be implemented)

    void onSessionLeave(ZoomVideoSDKSessionLeaveReason reason) override {}
    void onSessionNeedPassword(IZoomVideoSDKPasswordHandler* handler) override {}
    void onSessionPasswordWrong(IZoomVideoSDKPasswordHandler* handler) override {}
    void onUserHostChanged(IZoomVideoSDKUserHelper* helper, IZoomVideoSDKUser* user) override {}
    void onUserManagerChanged(IZoomVideoSDKUser* user) override {}
    void onUserNameChanged(IZoomVideoSDKUser* user) override {}
    void onUserActiveAudioChanged(IZoomVideoSDKAudioHelper* helper, IVideoSDKVector<IZoomVideoSDKUser*>* list) override {}
    void onMixedAudioRawDataReceived(AudioRawData* data) override {}
    void onOneWayAudioRawDataReceived(AudioRawData* data, IZoomVideoSDKUser* user) override {}
    void onSharedAudioRawDataReceived(AudioRawData* data) override {}
    void onUserShareStatusChanged(IZoomVideoSDKShareHelper* helper, IZoomVideoSDKUser* user, IZoomVideoSDKShareAction* action) override {}
    void onShareContentChanged(IZoomVideoSDKShareHelper* helper, IZoomVideoSDKUser* user, IZoomVideoSDKShareAction* action) override {}
    void onFailedToStartShare(IZoomVideoSDKShareHelper* helper, IZoomVideoSDKUser* user) override {}
    void onShareContentSizeChanged(IZoomVideoSDKShareHelper* helper, IZoomVideoSDKUser* user, IZoomVideoSDKShareAction* action) override {}
    void onLiveStreamStatusChanged(IZoomVideoSDKLiveStreamHelper* helper, ZoomVideoSDKLiveStreamStatus status) override {}
    void onChatMsgDeleteNotification(IZoomVideoSDKChatHelper* helper, const zchar_t* msgID, ZoomVideoSDKChatMessageDeleteType type) override {}
    void onChatPrivilegeChanged(IZoomVideoSDKChatHelper* helper, ZoomVideoSDKChatPrivilegeType privilege) override {}
    void onLiveTranscriptionStatus(ZoomVideoSDKLiveTranscriptionStatus status) override {}
    void onLiveTranscriptionMsgInfoReceived(ILiveTranscriptionMessageInfo* info) override {}
    void onOriginalLanguageMsgReceived(ILiveTranscriptionMessageInfo* info) override {}
    void onLiveTranscriptionMsgError(ILiveTranscriptionLanguage* spoken, ILiveTranscriptionLanguage* transcript) override {}
    void onProxyDetectComplete() override {}
    void onProxySettingNotification(IZoomVideoSDKProxySettingHandler* handler) override {}
    void onSSLCertVerifiedFailNotification(IZoomVideoSDKSSLCertificateInfo* info) override {}
    void onUserVideoNetworkStatusChanged(ZoomVideoSDKNetworkStatus status, IZoomVideoSDKUser* user) override {}
    void onCallCRCDeviceStatusChanged(ZoomVideoSDKCRCCallStatus status) override {}
    void onVideoCanvasSubscribeFail(ZoomVideoSDKSubscribeFailReason reason, IZoomVideoSDKUser* user, void* handle) override {}
    void onShareCanvasSubscribeFail(IZoomVideoSDKUser* user, void* handle, IZoomVideoSDKShareAction* action) override {}
    void onAnnotationHelperCleanUp(IZoomVideoSDKAnnotationHelper* helper) override {}
    void onAnnotationPrivilegeChange(IZoomVideoSDKUser* user, IZoomVideoSDKShareAction* action) override {}
    void onAnnotationHelperActived(void* handle) override {}
    void onSendFileStatus(IZoomVideoSDKSendFile* file, const FileTransferStatus& status) override {}
    void onReceiveFileStatus(IZoomVideoSDKReceiveFile* file, const FileTransferStatus& status) override {}
    void onInviteByPhoneStatus(PhoneStatus status, PhoneFailedReason reason) override {}
    void onCalloutJoinSuccess(IZoomVideoSDKUser* user, const zchar_t* phoneNumber) override {}
    void onCameraControlRequestResult(IZoomVideoSDKUser* user, bool approved) override {}
    void onCameraControlRequestReceived(IZoomVideoSDKUser* user, ZoomVideoSDKCameraControlRequestType type, IZoomVideoSDKCameraControlRequestHandler* handler) override {}
    void onCommandReceived(IZoomVideoSDKUser* sender, const zchar_t* cmd) override {}
    void onCommandChannelConnectResult(bool success) override {}
    void onCloudRecordingStatus(RecordingStatus status, IZoomVideoSDKRecordingConsentHandler* handler) override {}
    void onHostAskUnmute() override {}
    void onUserRecordingConsent(IZoomVideoSDKUser* user) override {}
    void onMultiCameraStreamStatusChanged(ZoomVideoSDKMultiCameraStreamStatus status, IZoomVideoSDKUser* user, IZoomVideoSDKRawDataPipe* pipe) override {}
    void onMicSpeakerVolumeChanged(unsigned int micVol, unsigned int speakerVol) override {}
    void onAudioDeviceStatusChanged(ZoomVideoSDKAudioDeviceType type, ZoomVideoSDKAudioDeviceStatus status) override {}
    void onTestMicStatusChanged(ZoomVideoSDK_TESTMIC_STATUS status) override {}
    void onSelectedAudioDeviceChanged() override {}
    void onCameraListChanged() override {}
    void onSpotlightVideoChanged(IZoomVideoSDKVideoHelper* helper, IVideoSDKVector<IZoomVideoSDKUser*>* list) override {}
    void onVideoAlphaChannelStatusChanged(bool isOn) override {}
    void onRemoteControlStatus(IZoomVideoSDKUser* user, IZoomVideoSDKShareAction* action, ZoomVideoSDKRemoteControlStatus status) override {}
    void onRemoteControlRequestReceived(IZoomVideoSDKUser* user, IZoomVideoSDKShareAction* action, IZoomVideoSDKRemoteControlRequestHandler* handler) override {}
    void onRemoteControlServiceInstallResult(bool success) override {}
    void onBindIncomingLiveStreamResponse(bool success, const zchar_t* streamKeyID) override {}
    void onUnbindIncomingLiveStreamResponse(bool success, const zchar_t* streamKeyID) override {}
    void onIncomingLiveStreamStatusResponse(bool success, IVideoSDKVector<IncomingLiveStreamStatus>* list) override {}
    void onStartIncomingLiveStreamResponse(bool success, const zchar_t* streamKeyID) override {}
    void onStopIncomingLiveStreamResponse(bool success, const zchar_t* streamKeyID) override {}
    void onUserWhiteboardShareStatusChanged(IZoomVideoSDKUser* user, IZoomVideoSDKWhiteboardHelper* helper) override {}
};

//─────────────────────────────────────────────────────────────────────────────
// CONFIGURATION
//─────────────────────────────────────────────────────────────────────────────

bool LoadConfig(const std::string& filename) {
    std::ifstream file(filename);
    if (!file.is_open()) {
        std::cerr << "Cannot open " << filename << std::endl;
        return false;
    }

    Json::Value config;
    file >> config;

    std::string jwt = config["jwt"].asString();
    std::string sessionName = config["session_name"].asString();
    std::string password = config.get("password", "").asString();
    std::string userName = config.get("user_name", "Bot").asString();

    g_jwt = std::wstring(jwt.begin(), jwt.end());
    g_sessionName = std::wstring(sessionName.begin(), sessionName.end());
    g_sessionPassword = std::wstring(password.begin(), password.end());
    g_userName = std::wstring(userName.begin(), userName.end());

    return true;
}

//─────────────────────────────────────────────────────────────────────────────
// SDK OPERATIONS
//─────────────────────────────────────────────────────────────────────────────

bool InitializeSDK() {
    g_sdk = CreateZoomVideoSDKObj();
    if (!g_sdk) {
        std::cerr << "Failed to create SDK object" << std::endl;
        return false;
    }

    ZoomVideoSDKInitParams params;
    params.domain = L"https://zoom.us";
    params.enableLog = true;
    params.logFilePrefix = L"zoom_video_sdk";
    params.videoRawDataMemoryMode = ZoomVideoSDKRawDataMemoryModeHeap;
    params.shareRawDataMemoryMode = ZoomVideoSDKRawDataMemoryModeHeap;
    params.audioRawDataMemoryMode = ZoomVideoSDKRawDataMemoryModeHeap;

    ZoomVideoSDKErrors err = g_sdk->initialize(params);
    if (err != ZoomVideoSDKErrors_Success) {
        std::cerr << "SDK initialize failed: " << err << std::endl;
        return false;
    }

    std::cout << "SDK initialized successfully" << std::endl;
    return true;
}

bool JoinSession() {
    // Register delegate BEFORE joining
    g_sdk->addListener(new MyDelegate());

    ZoomVideoSDKSessionContext context;
    context.sessionName = g_sessionName.c_str();
    context.userName = g_userName.c_str();
    context.token = g_jwt.c_str();
    context.sessionPassword = g_sessionPassword.c_str();

    // IMPORTANT: Connect audio in onSessionJoin callback
    context.audioOption.connect = false;
    context.audioOption.mute = true;
    context.videoOption.localVideoOn = false;

    IZoomVideoSDKSession* session = g_sdk->joinSession(context);
    if (!session) {
        std::cerr << "joinSession returned null" << std::endl;
        return false;
    }

    std::cout << "Join session initiated..." << std::endl;
    return true;
}

void Cleanup() {
    if (g_sdk) {
        if (g_inSession) {
            g_sdk->leaveSession(false);
        }
        g_sdk->cleanup();
        DestroyZoomVideoSDKObj();
        g_sdk = nullptr;
    }
}

//─────────────────────────────────────────────────────────────────────────────
// MAIN
//─────────────────────────────────────────────────────────────────────────────

int main() {
    // Initialize COM (required for some SDK features)
    CoInitialize(NULL);

    // Load configuration
    if (!LoadConfig("config.json")) {
        return 1;
    }

    // Initialize SDK
    if (!InitializeSDK()) {
        return 1;
    }

    // Join session
    if (!JoinSession()) {
        Cleanup();
        return 1;
    }

    // ═══════════════════════════════════════════════════════════════════════
    // CRITICAL: Windows message loop
    // Without this, callbacks will NEVER fire!
    // ═══════════════════════════════════════════════════════════════════════
    std::cout << "Running message loop (Ctrl+C to exit)..." << std::endl;

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
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }

    // Cleanup
    Cleanup();
    CoUninitialize();

    std::cout << "Exited cleanly" << std::endl;
    return 0;
}
```

### config.json

```json
{
  "jwt": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "session_name": "my-session",
  "password": "",
  "user_name": "Bot"
}
```

---

## Key Points

### 1. Register Delegate BEFORE Joining

```cpp
// CORRECT
g_sdk->addListener(new MyDelegate());
g_sdk->joinSession(context);

// WRONG - callbacks will be missed
g_sdk->joinSession(context);
g_sdk->addListener(new MyDelegate());  // Too late!
```

### 2. Set audioOption.connect = false

```cpp
context.audioOption.connect = false;  // Connect in onSessionJoin
context.audioOption.mute = true;
```

Then connect audio in the callback:

```cpp
void onSessionJoin() override {
    g_sdk->getAudioHelper()->startAudio();
}
```

### 3. Windows Message Loop is MANDATORY

```cpp
// This is NOT optional!
while (!g_exit) {
    MSG msg;
    while (PeekMessage(&msg, NULL, 0, 0, PM_REMOVE)) {
        TranslateMessage(&msg);
        DispatchMessage(&msg);
    }
    Sleep(10);
}
```

### 4. Implement ALL Delegate Methods

The `IZoomVideoSDKDelegate` interface has 80+ pure virtual methods. **All must be implemented**, even if empty.

---

## Related Documentation

- [Windows Message Loop](../troubleshooting/windows-message-loop.md) - Why message loop is critical
- [Delegate Methods](../references/delegate-methods.md) - All 80+ callback methods
- [Video Rendering](video-rendering.md) - Subscribe to video after join
- [SDK Architecture Pattern](../concepts/sdk-architecture-pattern.md) - Universal pattern

---

**TL;DR**: Initialize → Add delegate → Join with `audioOption.connect = false` → Run message loop → Connect audio in `onSessionJoin`.
