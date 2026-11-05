# High-Level Scenarios for Meeting SDK Linux

This guide covers common bot architectures and patterns that remain stable across SDK versions, with flexible approaches to handle API changes.

## Scenario 1: Transcription Bot

**Goal**: Join meetings to transcribe conversations in real-time.

### Architecture

```
┌─────────────┐    ┌──────────────┐    ┌─────────────────┐    ┌──────────────┐
│   Meeting   │───►│  Meeting SDK │───►│  Audio Stream   │───►│ Transcription│
│   Starts    │    │  Join + Auth │    │  (PCM 32kHz)    │    │   Service    │
└─────────────┘    └──────────────┘    └─────────────────┘    └──────────────┘
                           │                      │                     │
                           ▼                      ▼                     ▼
                   ┌──────────────┐    ┌─────────────────┐    ┌──────────────┐
                   │ StartRaw     │    │ onMixedAudio    │    │  Store       │
                   │ Recording    │    │ RawDataReceived │    │  Transcript  │
                   └──────────────┘    └─────────────────┘    └──────────────┘
```

### Core Pattern (Version-Flexible)

```cpp
// STEP 1: Initialize (stable across versions)
InitParam init_params;
init_params.strWebDomain = "https://zoom.us";
init_params.enableLogByDefault = true;
init_params.rawdataOpts.audioRawDataMemoryMode = ZoomSDKRawDataMemoryModeHeap;
InitSDK(init_params);

// STEP 2: Authenticate (JWT token - stable)
AuthContext auth_ctx;
auth_ctx.jwt_token = getJWTToken();  // Generate from SDK credentials
CreateAuthService(&auth_service);
auth_service->SDKAuth(auth_ctx);

// STEP 3: Join meeting (flexible - check SDK version for exact field names)
JoinParam join_param;
join_param.userType = SDK_UT_WITHOUT_LOGIN;
auto& params = join_param.param.withoutloginuserJoin;
params.meetingNumber = meeting_number;
params.userName = "Transcription Bot";
params.psw = meeting_password;

// Version-flexible: Check if these fields exist in your SDK version
// params.app_privilege_token = obf_token;  // v5.15+
// params.onBehalfToken = obf_token;        // Some versions
// params.userZAK = zak_token;              // Alternative

meeting_service->Join(join_param);

// STEP 4: In onMeetingStatusChanged callback
if (status == MEETING_STATUS_INMEETING) {
    // Get recording controller (pattern stable)
    auto* record_ctrl = meeting_service->GetMeetingRecordingController();

    // Start raw recording (enables raw data access)
    if (record_ctrl->CanStartRawRecording() == SDKERR_SUCCESS) {
        record_ctrl->StartRawRecording();
    }

    // Subscribe to audio
    auto* audio_helper = GetAudioRawdataHelper();
    audio_helper->subscribe(new TranscriptionAudioDelegate());
}

// STEP 5: Process audio
class TranscriptionAudioDelegate : public IZoomSDKAudioRawDataDelegate {
    void onMixedAudioRawDataReceived(AudioRawData* data) override {
        // Send PCM data to transcription service
        sendToTranscriptionAPI(data->GetBuffer(), data->GetBufferLen());
    }
};
```

### Version Handling Strategy

**Flexible field access**:
```cpp
// Define a macro to check field existence at compile time
#ifdef HAS_APP_PRIVILEGE_TOKEN
    params.app_privilege_token = token;
#elif defined(HAS_ON_BEHALF_TOKEN)
    params.onBehalfToken = token;
#else
    params.userZAK = token;
#endif
```

**Runtime capability detection**:
```cpp
SDKError canRecord = record_ctrl->CanStartRawRecording();
if (canRecord != SDKERR_SUCCESS) {
    // Fallback: Try local recording
    if (record_ctrl->CanStartRecording(true) == SDKERR_SUCCESS) {
        record_ctrl->StartRecording(time, path);
    }
}
```

### Key Resilience Patterns

1. **Always check CanXXX() before calling XXX()**
2. **Have fallback authentication methods** (OBF → ZAK → password-only)
3. **Detect capabilities**, don't assume
4. **Use error codes** to adapt behavior

---

## Scenario 2: Recording Bot (Video + Audio)

**Goal**: Record meetings with synchronized audio and video.

### Architecture

```
┌──────────────┐    ┌─────────────────┐    ┌──────────────┐
│ Join Meeting │───►│ StartRawRecording│───►│ Subscribe    │
│              │    │                  │    │ Audio+Video  │
└──────────────┘    └─────────────────┘    └──────────────┘
                                                    │
                         ┌──────────────────────────┴─────────────────┐
                         ▼                                            ▼
                  ┌──────────────┐                           ┌──────────────┐
                  │ Write YUV420 │                           │ Write PCM    │
                  │ video.yuv    │                           │ audio.pcm    │
                  └──────────────┘                           └──────────────┘
                         │                                            │
                         └──────────────────────────────────────────┬─┘
                                                                     ▼
                                                            ┌──────────────┐
                                                            │ FFmpeg Merge │
                                                            │   output.mp4 │
                                                            └──────────────┘
```

### Core Pattern

```cpp
// After joining and starting raw recording...

// Video subscription
class VideoRecorderDelegate : public IZoomSDKRendererDelegate {
    std::ofstream videoFile;

    void onRawDataFrameReceived(YUVRawDataI420* data) override {
        int width = data->GetStreamWidth();
        int height = data->GetStreamHeight();

        // YUV420 format: Y + U + V planes (contiguous)
        videoFile.write(data->GetYBuffer(), width * height);
        videoFile.write(data->GetUBuffer(), (width/2) * (height/2));
        videoFile.write(data->GetVBuffer(), (width/2) * (height/2));
    }
};

IZoomSDKRenderer* video_renderer;
createRenderer(&video_renderer, new VideoRecorderDelegate());
video_renderer->setRawDataResolution(ZoomSDKResolution_720P);
video_renderer->subscribe(user_id, RAW_DATA_TYPE_VIDEO);

// Audio subscription
class AudioRecorderDelegate : public IZoomSDKAudioRawDataDelegate {
    std::ofstream audioFile;

    void onMixedAudioRawDataReceived(AudioRawData* data) override {
        audioFile.write((char*)data->GetBuffer(), data->GetBufferLen());
    }
};

auto* audio_helper = GetAudioRawdataHelper();
audio_helper->subscribe(new AudioRecorderDelegate());

// Post-processing with FFmpeg
system("ffmpeg -video_size 1280x720 -pixel_format yuv420p -f rawvideo -i video.yuv "
       "-f s16le -ar 32000 -ac 1 -i audio.pcm "
       "-c:v libx264 -c:a aac -shortest output.mp4");
```

### Handling Resolution Changes

**Flexible resolution selection** (adapt to SDK version):
```cpp
// Try highest resolution available, fall back gracefully
ZoomSDKResolution resolutions[] = {
    ZoomSDKResolution_1080P,
    ZoomSDKResolution_720P,
    ZoomSDKResolution_360P
};

for (auto res : resolutions) {
    SDKError err = video_renderer->setRawDataResolution(res);
    if (err == SDKERR_SUCCESS) {
        std::cout << "Using resolution: " << res << std::endl;
        break;
    }
}
```

---

## Scenario 3: AI Meeting Assistant

**Goal**: Real-time meeting analysis with AI (sentiment, action items, summaries).

### Architecture

```
┌──────────────┐    ┌─────────────────┐    ┌──────────────┐    ┌──────────────┐
│ Audio Stream │───►│  Transcription  │───►│ AI Analysis  │───►│   Actions    │
│  (Real-time) │    │  (AssemblyAI)   │    │    (LLM)     │    │  Identified  │
└──────────────┘    └─────────────────┘    └──────────────┘    └──────────────┘
                             │                      │                    │
                             ▼                      ▼                    ▼
                    ┌─────────────────┐   ┌─────────────────┐  ┌──────────────┐
                    │  Speaker         │   │  Sentiment      │  │  Generate    │
                    │  Diarization     │   │  Analysis       │  │  Summary     │
                    └─────────────────┘   └─────────────────┘  └──────────────┘
```

### Core Pattern

```cpp
// Real-time streaming transcription
class AIAssistantAudioDelegate : public IZoomSDKAudioRawDataDelegate {
    WebSocketClient transcription_ws;  // AssemblyAI WebSocket
    AIClient ai_client;                 // LLM provider

    void onMixedAudioRawDataReceived(AudioRawData* data) override {
        // Stream audio to real-time transcription
        transcription_ws.send_audio(data->GetBuffer(), data->GetBufferLen());
    }
};

// Process transcription results
void onTranscriptReceived(const std::string& text, const std::string& speaker) {
    // Accumulate context
    meeting_context += speaker + ": " + text + "\n";

    // Every 30 seconds, analyze with AI
    if (should_analyze()) {
        std::string analysis = ai_client.analyze(meeting_context, {
            "extract_action_items",
            "detect_decisions",
            "identify_blockers"
        });

        // Store results
        meeting_insights.push_back(analysis);
    }
}

// Post-meeting summary
void onMeetingEnded() {
    std::string summary = ai_client.summarize(meeting_context, meeting_insights);
    save_to_database(meeting_id, summary);
    send_email_summary(participants, summary);
}
```

### Version Flexibility: Chat Integration

Some SDK versions support in-meeting chat:
```cpp
// Try to send AI insights to meeting chat
auto* chat_ctrl = meeting_service->GetMeetingChatController();
if (chat_ctrl) {
    // Check if available
    if (chat_ctrl->CanSendChat()) {
        chat_ctrl->SendChatTo("AI detected action item: ...");
    }
}
```

---

## Scenario 4: Monitoring & Quality Bot

**Goal**: Monitor meeting quality metrics and alert on issues.

### Core Pattern

```cpp
// Get service quality info
auto* meeting_info = meeting_service->GetMeetingInfo();

// Polling loop (GLib timeout)
gboolean check_quality(gpointer data) {
    // Audio stats
    auto* audio_stats = meeting_info->GetAudioStatistics();
    if (audio_stats) {
        int jitter = audio_stats->jitter;
        int packet_loss = audio_stats->packet_loss_percent;

        if (packet_loss > 5) {
            alert("High packet loss: " + std::to_string(packet_loss) + "%");
        }
    }

    // Video stats
    auto* video_stats = meeting_info->GetVideoStatistics();
    if (video_stats) {
        int fps = video_stats->fps;
        int resolution_width = video_stats->width;

        if (fps < 15) {
            alert("Low FPS: " + std::to_string(fps));
        }
    }

    return TRUE;  // Continue polling
}

// Setup polling
g_timeout_add_seconds(10, check_quality, nullptr);
```

---

## Version Migration Guide

### When SDK Updates

1. **Read release notes** for breaking changes
2. **Check header files** for actual method signatures
3. **Test compilation** with `-Werror=deprecated`
4. **Update authentication** if new token types added
5. **Verify raw data flow** still works

### Common Breaking Changes

| Change Type | Example | Mitigation |
|-------------|---------|------------|
| Struct field rename | `withoutloginuserJoin` → `withoutLoginUserJoin` | Use `#ifdef` or update |
| Method signature change | `subscribe(user_id)` → `subscribe(user_id, type)` | Check return codes |
| Enum value rename | `SDKERR_NORECORDINGINPROCESS` → `SDKERR_NO_RECORDING_IN_PROCESS` | Map old → new |
| New required field | `app_privilege_token` becomes mandatory | Add to config |

### Testing Strategy

```cpp
// Version detection at compile time
#if ZOOM_SDK_VERSION >= 51500  // v5.15.0
    #define USE_OBF_TOKEN
#endif

// Runtime capability testing
bool test_raw_recording() {
    auto* ctrl = meeting_service->GetMeetingRecordingController();
    return ctrl && ctrl->CanStartRawRecording() == SDKERR_SUCCESS;
}
```

---

## Docker Deployment Patterns

### Multi-Stage Build (Version-Flexible)

```dockerfile
FROM ubuntu:22.04 AS builder

# Install dependencies (stable)
RUN apt-get update && apt-get install -y \
    build-essential cmake \
    libx11-xcb1 libxcb-xfixes0 libxcb-shape0 \
    libglib2.0-dev libcurl4-openssl-dev

# Copy SDK (any version)
COPY zoom-meeting-sdk-linux_*.tar.gz /tmp/
RUN cd /tmp && tar xzf zoom-meeting-sdk-linux_*.tar.gz

# Build app
COPY . /app
WORKDIR /app
RUN cmake -B build && cd build && make

# Runtime stage
FROM ubuntu:22.04
COPY --from=builder /app/build/meetingBot /usr/local/bin/
COPY --from=builder /tmp/lib*.so /usr/local/lib/

# PulseAudio setup (required for raw audio)
RUN apt-get update && apt-get install -y pulseaudio && \
    mkdir -p ~/.config && \
    echo "[General]\nsystem.audio.type=default" > ~/.config/zoomus.conf

CMD ["meetingBot"]
```

---

## Summary: Resilient Bot Checklist

✅ **Always check capabilities** before calling methods
✅ **Use heap memory mode** for raw data
✅ **Handle authentication fallbacks** (OBF → ZAK → password)
✅ **Detect SDK version** at compile/runtime
✅ **Test with actual SDK headers**, not documentation examples
✅ **Setup PulseAudio** for Docker/headless environments
✅ **Parse error codes** to adapt behavior
✅ **Keep authentication tokens fresh** (regenerate before expiry)
✅ **Log everything** for debugging version-specific issues
