# SDK Architecture Pattern - Universal Formula

## The 3-Step Pattern for ANY Feature

**Once you understand this pattern, you can implement ANY Zoom Video SDK feature**. The SDK follows a consistent architectural pattern across all features.

### Pattern Overview

```
1. Get Singleton/Helper → 2. Implement Delegate → 3. Subscribe & Use
```

This pattern applies to:
- Video subscription
- Audio processing
- Screen sharing
- Raw data capture
- Raw data injection (virtual devices)
- Recording
- Live streaming
- Transcription
- Commands
- Chat

---

## Step 1: Get Singleton/Helper

The SDK uses a singleton hierarchy to access features:

```cpp
// Main SDK singleton
IZoomVideoSDK* video_sdk_obj = CreateZoomVideoSDKObj();

// Get helpers for specific features
IZoomVideoSDKAudioHelper* audio = video_sdk_obj->getAudioHelper();
IZoomVideoSDKVideoHelper* video = video_sdk_obj->getVideoHelper();
IZoomVideoSDKShareHelper* share = video_sdk_obj->getShareHelper();
IZoomVideoSDKChatHelper* chat = video_sdk_obj->getChatHelper();
IZoomVideoSDKRecordingHelper* rec = video_sdk_obj->getRecordingHelper();
IZoomVideoSDKLiveStreamHelper* stream = video_sdk_obj->getLiveStreamHelper();
IZoomVideoSDKLiveTranscriptionHelper* transcription = video_sdk_obj->getLiveTranscriptionHelper();
```

**Key Insight**: Helpers control YOUR streams/actions. To receive others' data, you subscribe to their pipes/canvas.

---

## Step 2: Implement Delegate

The SDK communicates via callbacks. You implement delegate interfaces to receive events.

### Main Event Delegate

```cpp
class MyDelegate : public IZoomVideoSDKDelegate {
public:
    // Session events
    virtual void onSessionJoin() override { /* Session joined */ }
    virtual void onSessionLeave() override { /* Session left */ }
    virtual void onError(ZoomVideoSDKErrors errorCode, int detailErrorCode) override { /* Error occurred */ }

    // User events
    virtual void onUserJoin(IZoomVideoSDKUserHelper*, IVideoSDKVector<IZoomVideoSDKUser*>*) override { /* Users joined */ }
    virtual void onUserLeave(IZoomVideoSDKUserHelper*, IVideoSDKVector<IZoomVideoSDKUser*>*) override { /* Users left */ }

    // Video events
    virtual void onUserVideoStatusChanged(IZoomVideoSDKVideoHelper*, IVideoSDKVector<IZoomVideoSDKUser*>*) override { /* Video status changed */ }

    // Audio events
    virtual void onUserAudioStatusChanged(IZoomVideoSDKAudioHelper*, IVideoSDKVector<IZoomVideoSDKUser*>*) override { /* Audio status changed */ }
    virtual void onMixedAudioRawDataReceived(AudioRawData* data_) override { /* Mixed audio data */ }
    virtual void onOneWayAudioRawDataReceived(AudioRawData* data_, IZoomVideoSDKUser* pUser) override { /* Per-user audio */ }

    // Share events
    virtual void onUserShareStatusChanged(IZoomVideoSDKShareHelper*, IZoomVideoSDKUser*, IZoomVideoSDKShareAction*) override { /* Share status changed */ }

    // ... many more callbacks (see linux-reference.md for complete list)
};

// Register delegate
video_sdk_obj->addListener(new MyDelegate());
```

### Raw Data Delegates

For raw video/share data:

```cpp
class VideoDelegate : public IZoomVideoSDKRawDataPipeDelegate {
public:
    virtual void onRawDataFrameReceived(YUVRawDataI420* data) override {
        // Process YUV420 frame
        int width = data->GetStreamWidth();
        int height = data->GetStreamHeight();
        char* yBuffer = data->GetYBuffer();
        char* uBuffer = data->GetUBuffer();
        char* vBuffer = data->GetVBuffer();
    }

    virtual void onRawDataStatusChanged(RawDataStatus status) override {
        // Video on/off
    }
};
```

For virtual audio mic:

```cpp
class VirtualMic : public IZoomVideoSDKVirtualAudioMic {
public:
    virtual void onMicInitialize(IZoomVideoSDKAudioSender* sender) override {
        audio_sender_ = sender;  // Store for sending
    }

    virtual void onMicStartSend() override {
        // Start sending audio frames
    }

    virtual void onMicStopSend() override { /* Stop sending */ }
    virtual void onMicUninitialized() override { audio_sender_ = nullptr; }

private:
    IZoomVideoSDKAudioSender* audio_sender_ = nullptr;
};
```

For virtual video source:

```cpp
class VirtualVideo : public IZoomVideoSDKVideoSource {
public:
    virtual void onInitialize(IZoomVideoSDKVideoSender* sender,
                             IVideoSDKVector<VideoSourceCapability>* caps,
                             VideoSourceCapability& suggest) override {
        video_sender_ = sender;  // Store for sending
    }

    virtual void onStartSend() override {
        // Start sending video frames
    }

    virtual void onStopSend() override { /* Stop sending */ }
    virtual void onPropertyChange(...) override { /* Resolution changed */ }
    virtual void onUninitialized() override { video_sender_ = nullptr; }

private:
    IZoomVideoSDKVideoSender* video_sender_ = nullptr;
};
```

---

## Step 3: Subscribe & Use

### Pattern A: Control YOUR streams (via Helpers)

```cpp
// Start YOUR audio
IZoomVideoSDKAudioHelper* audio = video_sdk_obj->getAudioHelper();
audio->startAudio();
audio->muteAudio(true);

// Start YOUR video
IZoomVideoSDKVideoHelper* video = video_sdk_obj->getVideoHelper();
video->startVideo();
video->stopVideo();

// Start YOUR screen share
IZoomVideoSDKShareHelper* share = video_sdk_obj->getShareHelper();
share->startShare();
share->stopShare();
```

### Pattern B: Receive data from OTHERS (via Pipes)

```cpp
// Subscribe to remote user's video
IZoomVideoSDKUser* user = /* get from onUserJoin */;
IZoomVideoSDKRawDataPipe* pipe = user->GetVideoPipe();
pipe->subscribe(ZoomVideoSDKResolution_720P, videoDelegate);

// Subscribe to remote user's share
IZoomVideoSDKRawDataPipe* sharePipe = user->GetSharePipe();
sharePipe->subscribe(ZoomVideoSDKResolution_720P, shareDelegate);
```

### Pattern C: Inject custom data (via Virtual Devices)

```cpp
// Set virtual mic BEFORE joining
session_context.virtualAudioMic = new VirtualMic();
session_context.audioOption.connect = true;
session_context.audioOption.mute = false;

// Set virtual video source BEFORE joining
session_context.externalVideoSource = new VirtualVideo();

// Join session
video_sdk_obj->joinSession(session_context);

// Send data in onStartSend callbacks
// For audio: audio_sender_->Send(data, len, sampleRate);
// For video: video_sender_->sendVideoFrame(y, u, v, w, h, 0, rotation);
```

---

## Common Patterns

### Pattern: Session Join

```cpp
// 1. Get SDK singleton
IZoomVideoSDK* sdk = CreateZoomVideoSDKObj();

// 2. Implement delegate
sdk->addListener(new MyDelegate());

// 3. Configure and join
ZoomVideoSDKSessionContext ctx;
ctx.sessionName = "my-session";
ctx.userName = "Linux Bot";
ctx.token = "jwt-token";
ctx.audioOption.connect = true;
ctx.audioOption.mute = false;
ctx.videoOption.localVideoOn = false;

// For headless: add virtual speaker
ctx.virtualAudioSpeaker = new VirtualSpeaker();

IZoomVideoSDKSession* session = sdk->joinSession(ctx);
```

### Pattern: Raw Video Capture

```cpp
// 1. Create delegate
class VideoCapture : public IZoomVideoSDKRawDataPipeDelegate {
    void onRawDataFrameReceived(YUVRawDataI420* data) override {
        // Save to file or process
    }
};

// 2. In onUserJoin or onUserVideoStatusChanged
IZoomVideoSDKUser* user = /* from callback */;
IZoomVideoSDKRawDataPipe* pipe = user->GetVideoPipe();
pipe->subscribe(ZoomVideoSDKResolution_720P, new VideoCapture());
```

### Pattern: Virtual Audio Injection

```cpp
// 1. Implement virtual mic
class MyMic : public IZoomVideoSDKVirtualAudioMic {
    IZoomVideoSDKAudioSender* sender_;

    void onMicInitialize(IZoomVideoSDKAudioSender* sender) override {
        sender_ = sender;
    }

    void onMicStartSend() override {
        // Load PCM audio and send
        char* audioData = LoadPCMAudio();
        sender_->Send(audioData, length, 32000);
    }
};

// 2. Set before joining
session_context.virtualAudioMic = new MyMic();
```

### Pattern: Cloud Recording

```cpp
// 1. Get recording helper
IZoomVideoSDKRecordingHelper* rec = sdk->getRecordingHelper();

// 2. Check permissions
if (rec->canStartRecording() == ZoomVideoSDKErrors_Success) {
    // 3. Start recording
    rec->startCloudRecording();
}

// Listen in delegate
void onCloudRecordingStatus(RecordingStatus status,
                            IZoomVideoSDKRecordingConsentHandler* handler) override {
    if (status == Recording_Start) {
        printf("Recording started\n");
    }
}
```

---

## Linux-Specific Patterns

### Pattern: Headless Linux (Docker/WSL)

**Problem**: No physical audio devices.

**Solution**: Use virtual audio speaker and mic.

```cpp
// Virtual speaker for receiving audio
class MySpeaker : public IZoomVideoSDKVirtualAudioSpeaker {
    void onVirtualSpeakerMixedAudioReceived(AudioRawData* data) override {
        // Process or discard audio
    }

    void onVirtualSpeakerOneWayAudioReceived(AudioRawData* data, IZoomVideoSDKUser* user) override {
        // Per-user audio
    }

    void onVirtualSpeakerSharedAudioReceived(AudioRawData* data) override {
        // Share audio
    }
};

// Virtual mic for sending audio
class MyMic : public IZoomVideoSDKVirtualAudioMic {
    IZoomVideoSDKAudioSender* sender_;

    void onMicInitialize(IZoomVideoSDKAudioSender* sender) override {
        sender_ = sender;
    }

    void onMicStartSend() override {
        // Send PCM audio
    }

    void onMicStopSend() override {}
    void onMicUninitialized() override { sender_ = nullptr; }
};

// Apply before joining
session_context.virtualAudioSpeaker = new MySpeaker();
session_context.virtualAudioMic = new MyMic();
session_context.audioOption.connect = true;
```

### Pattern: Qt/GTK UI Integration

**Qt Pattern**:
```cpp
// Use Qt signals/slots with SDK callbacks
class QtVideoRenderer : public QWidget, public IZoomVideoSDKRawDataPipeDelegate {
    Q_OBJECT
signals:
    void frameReceived(QImage frame);

public:
    void onRawDataFrameReceived(YUVRawDataI420* data) override {
        // Convert YUV to RGB
        QImage img = ConvertYUVToRGB(data);

        // Emit signal (thread-safe)
        emit frameReceived(img);
    }
};

// In Qt widget
connect(renderer, &QtVideoRenderer::frameReceived,
        this, [this](QImage img) {
    // Update UI on main thread
    videoLabel->setPixmap(QPixmap::fromImage(img));
});
```

**GTK Pattern**:
```cpp
// Use Glib main loop for thread safety
class GtkVideoRenderer : public IZoomVideoSDKRawDataPipeDelegate {
    void onRawDataFrameReceived(YUVRawDataI420* data) override {
        // Marshal to main thread
        g_idle_add([](gpointer user_data) {
            YUVRawDataI420* data = (YUVRawDataI420*)user_data;
            // Update GTK UI safely
            return G_SOURCE_REMOVE;
        }, data);
    }
};
```

---

## Key Insights

### 1. Helpers vs Pipes

| Component | Purpose | Example |
|-----------|---------|---------|
| **Helpers** | Control YOUR streams | `videoHelper->startVideo()` starts YOUR camera |
| **Pipes** | Receive OTHERS' streams | `user->GetVideoPipe()->subscribe()` receives their video |

### 2. Virtual Devices for Injection

To send custom audio/video, use virtual devices:
- `IZoomVideoSDKVirtualAudioMic` - Send custom audio
- `IZoomVideoSDKVirtualAudioSpeaker` - Receive audio (headless)
- `IZoomVideoSDKVideoSource` - Send custom video
- `IZoomVideoSDKShareSource` - Send custom share

Set these **before** joining session.

### 3. Memory Modes

Always use heap mode for raw data:
```cpp
init_params.videoRawDataMemoryMode = ZoomVideoSDKRawDataMemoryModeHeap;
init_params.shareRawDataMemoryMode = ZoomVideoSDKRawDataMemoryModeHeap;
init_params.audioRawDataMemoryMode = ZoomVideoSDKRawDataMemoryModeHeap;
```

### 4. Qt5 Dependencies

SDK requires Qt5 libraries (bundled in SDK package):
- Copy from SDK `samples/qt_libs/Qt/lib/`
- Create symlinks for versioned libraries
- See [Qt Dependencies Guide](../troubleshooting/qt-dependencies.md)

### 5. PulseAudio for Audio

Linux requires PulseAudio for raw audio features:
```bash
sudo apt install -y pulseaudio
mkdir -p ~/.config
echo "[General]" > ~/.config/zoomus.conf
echo "system.audio.type=default" >> ~/.config/zoomus.conf
```

---

## Complete Example

```cpp
#include "zoom_video_sdk_api.h"
#include "zoom_video_sdk_interface.h"
#include "zoom_video_sdk_delegate_interface.h"

USING_ZOOM_VIDEO_SDK_NAMESPACE

class BotDelegate : public IZoomVideoSDKDelegate {
    void onSessionJoin() override {
        printf("Joined session!\n");

        // Start audio
        IZoomVideoSDKAudioHelper* audio = video_sdk_obj->getAudioHelper();
        audio->startAudio();
        audio->subscribe();  // For raw audio callbacks
    }

    void onUserJoin(IZoomVideoSDKUserHelper*, IVideoSDKVector<IZoomVideoSDKUser*>* users) override {
        for (int i = 0; i < users->GetCount(); i++) {
            IZoomVideoSDKUser* user = users->GetItem(i);

            // Subscribe to video
            IZoomVideoSDKRawDataPipe* pipe = user->GetVideoPipe();
            pipe->subscribe(ZoomVideoSDKResolution_720P, videoDelegate);
        }
    }

    void onMixedAudioRawDataReceived(AudioRawData* data) override {
        // Process audio
        char* buffer = data->GetBuffer();
        unsigned int len = data->GetBufferLen();
        unsigned int sampleRate = data->GetSampleRate();
    }

    // ... implement all other required callbacks
};

int main() {
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
    sdk->addListener(new BotDelegate());

    // 4. Join session
    ZoomVideoSDKSessionContext ctx;
    ctx.sessionName = "my-session";
    ctx.userName = "Linux Bot";
    ctx.token = "jwt-token";
    ctx.audioOption.connect = true;
    ctx.audioOption.mute = false;
    ctx.videoOption.localVideoOn = false;

    // For headless
    ctx.virtualAudioSpeaker = new VirtualSpeaker();

    IZoomVideoSDKSession* session = sdk->joinSession(ctx);

    // Keep running
    while (running) {
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }

    // Cleanup
    sdk->leaveSession(false);
    sdk->cleanup();
    DestroyZoomVideoSDKObj();

    return 0;
}
```

---

## Next Steps

- **[Singleton Hierarchy](singleton-hierarchy.md)** - Navigate the 5-level SDK structure
- **[Session Join Pattern](../examples/session-join-pattern.md)** - Complete working session join
- **[Raw Video Capture](../examples/raw-video-capture.md)** - Capture YUV420 frames
- **[Raw Audio Capture](../examples/raw-audio-capture.md)** - Capture PCM audio
- **[Virtual Audio/Video](../examples/virtual-audio-video.md)** - Inject custom media
