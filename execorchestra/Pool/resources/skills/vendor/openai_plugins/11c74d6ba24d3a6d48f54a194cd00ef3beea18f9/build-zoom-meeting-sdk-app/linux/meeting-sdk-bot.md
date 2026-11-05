# Meeting SDK Bot (Linux)

Build resilient meeting bots that join Zoom meetings as visible participants using the Meeting SDK.

## Overview

Meeting SDK bots join as real participants (visible in participant list) and can access raw audio/video data for recording, transcription, or AI processing.

**Use this approach when:**
- You need to be visible in the participant list
- You want to interact with meeting features (chat, reactions, etc.)
- You need local recording control
- You're processing your own meetings or have user consent

**Alternative:** See [rtms/examples/rtms-bot.md](../../rtms/examples/rtms-bot.md) for invisible, read-only access via RTMS.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    MEETING SDK BOT FLOW                              │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ 1. Pre-Join: REST API                                               │
│    └── Get meeting schedule (number, password, start time)          │
│    └── Get OBF token for user (bot joins "on behalf of" user)       │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 2. Join with Retry (OBF requires owner present)                     │
│    └── Retry with configurable interval until owner joins           │
│    └── Circuit breaker: Stop after N attempts                       │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 3. Start Raw Recording (Meeting SDK singleton)                      │
│    └── IMeetingRecordingController::StartRawRecording()             │
│    └── Subscribe to raw audio/video                                 │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 4. Process Media Streams                                            │
│    └── Audio: PCM data via IZoomSDKAudioRawDataDelegate             │
│    └── Video: YUV420 frames via IZoomSDKVideoRawDataDelegate        │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 5. Mid-Meeting: Connection Monitoring                               │
│    └── Detect disconnections → Exponential backoff retry            │
│    └── Stop after N reconnection attempts                           │
└─────────────────────────────────────────────────────────────────────┘
```

## Skills Required

| Skill | Purpose |
|-------|---------|
| **zoom-rest-api** | Get meeting schedule, retrieve OBF token |
| **zoom-meeting-sdk** (Linux) | Join meeting, control recording, access raw media |

## Choose the Recording Mode

| Goal | Primary path | Skills |
|------|--------------|--------|
| Bot writes its own audio/video files | `StartRawRecording()` + raw audio/video delegates | `zoom-meeting-sdk` (Linux) |
| Zoom-hosted MP4/M4A/transcript assets after meeting end | Meeting/account cloud recording settings + `recording.completed` webhook + recordings download API | `zoom-rest-api` + `zoom-webhooks` |

Use raw recording when the bot must process or persist media itself. Use the cloud-recording path when the requirement is post-meeting retrieval of Zoom-managed recording assets.

## Automatic Join + Recording Flow

```text
zoom-rest-api
  -> get meeting metadata
  -> get OBF or ZAK token
Meeting SDK Linux bot
  -> join with retry
  -> CanStartRawRecording()
  -> StartRawRecording()
  -> subscribe raw audio/video
  -> write PCM/YUV or forward to AI pipeline
Optional post-meeting cloud path
  -> zoom-webhooks recording.completed
  -> zoom-rest-api recordings download
```

## Prerequisites

- Zoom Meeting SDK v5.15+ (Linux)
- Meeting SDK JWT credentials (SDK Key + Secret)
- Server-to-Server OAuth app or OAuth app for REST API access
- REST API scopes: `meeting:read`, `user:read`, optionally `meeting:write` if triggering meetings
- Raw Data entitlement enabled (Admin → Account Settings → Meeting → "Allow access to raw data")

## Configuration

### Retry Parameters (Customizable)

```cpp
// config.h or environment variables
struct BotConfig {
    // Join retry (waiting for owner to be present)
    int join_retry_attempts = 5;          // Max join attempts (default: 5)
    int join_retry_interval_ms = 60000;   // Constant interval: 60s (default: 1min)

    // Mid-meeting reconnection (network failures)
    int reconnect_max_attempts = 3;       // Max reconnection attempts (default: 3)
    int reconnect_base_delay_ms = 2000;   // Initial delay: 2s (default: 2s)
    // Exponential backoff: 2s, 4s, 8s...

    // Meeting schedule polling (if webhook unavailable)
    int schedule_poll_interval_ms = 30000; // Poll every 30s (default: 30s)

    // Timeout settings
    int auth_timeout_ms = 10000;          // SDK auth timeout (default: 10s)
    int join_timeout_ms = 30000;          // Single join attempt timeout (default: 30s)
};

// Load from environment variables (recommended for production)
BotConfig loadConfig() {
    BotConfig cfg;

    // Override defaults from env vars if present
    const char* env;

    if ((env = getenv("BOT_JOIN_RETRY_ATTEMPTS"))) {
        cfg.join_retry_attempts = atoi(env);
    }
    if ((env = getenv("BOT_JOIN_RETRY_INTERVAL_MS"))) {
        cfg.join_retry_interval_ms = atoi(env);
    }
    if ((env = getenv("BOT_RECONNECT_MAX_ATTEMPTS"))) {
        cfg.reconnect_max_attempts = atoi(env);
    }
    if ((env = getenv("BOT_RECONNECT_BASE_DELAY_MS"))) {
        cfg.reconnect_base_delay_ms = atoi(env);
    }

    return cfg;
}
```

### Customization Guide

| Parameter | Default | When to Increase | When to Decrease |
|-----------|---------|------------------|------------------|
| `join_retry_attempts` | 5 | High-priority meetings, owner often late | Testing, short-lived meetings |
| `join_retry_interval_ms` | 60000 (1min) | Meetings with long pre-join buffer | Need faster failure detection |
| `reconnect_max_attempts` | 3 | Unstable networks, critical meetings | Batch processing, cost-sensitive |
| `reconnect_base_delay_ms` | 2000 (2s) | Network latency high (international) | Local network, low latency |

**Recommended Ranges:**
- Join retry attempts: 3-10
- Join retry interval: 30s-5min
- Reconnect attempts: 2-5
- Reconnect base delay: 1s-5s

**Examples:**

```bash
# High-priority production bot (aggressive retries)
export BOT_JOIN_RETRY_ATTEMPTS=10
export BOT_JOIN_RETRY_INTERVAL_MS=30000  # 30s
export BOT_RECONNECT_MAX_ATTEMPTS=5
export BOT_RECONNECT_BASE_DELAY_MS=1000  # 1s

# Cost-sensitive batch processing (conservative)
export BOT_JOIN_RETRY_ATTEMPTS=3
export BOT_JOIN_RETRY_INTERVAL_MS=120000  # 2min
export BOT_RECONNECT_MAX_ATTEMPTS=2
export BOT_RECONNECT_BASE_DELAY_MS=5000   # 5s

# Development/testing (fail fast)
export BOT_JOIN_RETRY_ATTEMPTS=2
export BOT_JOIN_RETRY_INTERVAL_MS=10000   # 10s
export BOT_RECONNECT_MAX_ATTEMPTS=1
export BOT_RECONNECT_BASE_DELAY_MS=1000   # 1s
```

## Step 1: Get Meeting Info + OBF Token (REST API)

### Get Meeting Schedule

```bash
# Get meeting details
curl "https://api.zoom.us/v2/meetings/{meetingId}" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Response:**
```json
{
  "id": 1234567890,
  "topic": "Team Standup",
  "start_time": "2026-02-09T15:00:00Z",
  "password": "abc123",
  "pmi": false
}
```

**Store:** meeting number, password, start time.

### Get OBF Token

The bot joins "on behalf of" a Zoom user. Get the user's OBF token:

```bash
# Get OBF token for user
curl -X POST "https://api.zoom.us/v2/users/{userId}/token?type=obf&ttl=7200" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Response:**
```json
{
  "token": "eyJhbGc...",
  "expire_in": 7200
}
```

**CRITICAL:** The bot cannot join until the **owner** (the user whose OBF token you're using) is present in the meeting. This is why retry logic is essential.

**Error if REST API fails:** ABORT. No meeting info = cannot proceed.

## Step 2: Join Meeting with Retry Logic

### Join Implementation

```cpp
#include <chrono>
#include <thread>

class MeetingBot {
private:
    BotConfig config;
    IMeetingService* meetingService;
    bool joinSuccessful = false;
    bool ownerNotPresentError = false;

public:
    // Attempt to join with retry logic
    bool joinMeetingWithRetry(
        uint64_t meetingNumber,
        const string& password,
        const string& obfToken,
        const string& botDisplayName
    ) {
        for (int attempt = 1; attempt <= config.join_retry_attempts; attempt++) {
            cout << "[JOIN] Attempt " << attempt << "/"
                 << config.join_retry_attempts << endl;

            // Attempt join
            JoinParam joinParam;
            joinParam.userType = SDK_UT_WITHOUT_LOGIN;

            JoinParam4WithoutLogin& param = joinParam.param.withoutloginuserJoin;
            param.meetingNumber = meetingNumber;
            param.userName = botDisplayName.c_str();
            param.psw = password.c_str();
            param.isVideoOff = true;   // Bots typically don't send video
            param.isAudioOff = false;  // Need audio for transcription
            param.app_privilege_token = obfToken.c_str();  // OBF token

            SDKError err = meetingService->Join(joinParam);

            if (err != SDKERR_SUCCESS) {
                cerr << "[JOIN] Join() call failed: " << err << endl;

                // Check if it's a retriable error
                if (shouldRetryJoin(err)) {
                    if (attempt < config.join_retry_attempts) {
                        cout << "[JOIN] Retrying in "
                             << (config.join_retry_interval_ms / 1000)
                             << "s..." << endl;
                        this_thread::sleep_for(
                            chrono::milliseconds(config.join_retry_interval_ms)
                        );
                        continue;
                    }
                }

                // Non-retriable error or out of attempts
                cerr << "[JOIN] Giving up after " << attempt << " attempts" << endl;
                return false;
            }

            // Join() call succeeded, wait for callback
            if (waitForJoinCallback()) {
                cout << "[JOIN] Successfully joined meeting!" << endl;
                return true;
            } else {
                cerr << "[JOIN] Join callback indicated failure" << endl;

                // If owner not present, retry
                if (ownerNotPresentError && attempt < config.join_retry_attempts) {
                    cout << "[JOIN] Owner not present. Retrying in "
                         << (config.join_retry_interval_ms / 1000) << "s..." << endl;
                    this_thread::sleep_for(
                        chrono::milliseconds(config.join_retry_interval_ms)
                    );
                    continue;
                }
            }
        }

        cerr << "[JOIN] Failed to join after "
             << config.join_retry_attempts << " attempts" << endl;
        return false;
    }

private:
    bool shouldRetryJoin(SDKError err) {
        switch (err) {
            case SDKERR_WRONG_USAGE:
            case SDKERR_INVALID_PARAMETER:
            case SDKERR_MODULE_LOAD_FAILED:
                return false;  // Configuration errors, don't retry

            case SDKERR_NETWORK_ERROR:
            case SDKERR_SERVICE_FAILED:
                return true;   // Network/server issues, retry

            default:
                return true;   // Unknown error, retry to be safe
        }
    }

    bool waitForJoinCallback() {
        // Wait for onMeetingStatusChanged callback
        // Implementation depends on your callback handling
        // Typical: use condition variable with timeout

        std::unique_lock<std::mutex> lock(callbackMutex);
        bool success = callbackCV.wait_for(
            lock,
            std::chrono::milliseconds(config.join_timeout_ms),
            [this]{ return joinSuccessful || ownerNotPresentError; }
        );

        return success && joinSuccessful;
    }

public:
    // Callback from SDK
    void onMeetingStatusChanged(MeetingStatus status, int iResult) {
        std::lock_guard<std::mutex> lock(callbackMutex);

        if (status == MEETING_STATUS_INMEETING) {
            joinSuccessful = true;
            callbackCV.notify_one();
        } else if (status == MEETING_STATUS_FAILED) {
            // Check error code for "owner not present"
            if (iResult == MEETING_FAIL_OBF_OWNER_NOT_IN_MEETING) {
                ownerNotPresentError = true;
            }
            joinSuccessful = false;
            callbackCV.notify_one();
        }
    }

private:
    std::mutex callbackMutex;
    std::condition_variable callbackCV;
};
```

### Common Join Errors

| Error Code | Meaning | Action |
|------------|---------|--------|
| `MEETING_FAIL_OBF_OWNER_NOT_IN_MEETING` | OBF token owner not in meeting yet | RETRY (owner might join soon) |
| `MEETING_FAIL_MEETING_NOT_EXIST` | Meeting not started | RETRY if before end time |
| `MEETING_FAIL_INCORRECT_MEETING_NUMBER` | Wrong meeting ID | ABORT (config error) |
| `MEETING_FAIL_MEETING_NOT_START` | Meeting hasn't started | RETRY until start time |
| `MEETING_FAIL_INVALID_TOKEN` | OBF token invalid/expired | ABORT (need new token) |

## Step 3: Start Raw Recording

Once joined, request permission to access raw audio/video:

```cpp
void onMeetingStatusChanged(MeetingStatus status, int iResult) {
    if (status == MEETING_STATUS_INMEETING) {
        cout << "[BOT] Joined successfully, starting raw recording..." << endl;

        // Get recording controller
        IMeetingRecordingController* recordCtrl =
            meetingService->GetMeetingRecordingController();

        if (!recordCtrl) {
            cerr << "[BOT] Failed to get recording controller" << endl;
            return;
        }

        // Check permission
        SDKError canRecord = recordCtrl->CanStartRawRecording();
        if (canRecord != SDKERR_SUCCESS) {
            cerr << "[BOT] Cannot start raw recording: " << canRecord << endl;
            cerr << "[BOT] Check: Raw Data entitlement enabled in Admin settings?" << endl;
            return;
        }

        // Start raw recording (enables raw data flow)
        SDKError err = recordCtrl->StartRawRecording();
        if (err != SDKERR_SUCCESS) {
            cerr << "[BOT] StartRawRecording failed: " << err << endl;
            return;
        }

        cout << "[BOT] Raw recording started, subscribing to media..." << endl;

        // Subscribe to audio/video
        subscribeToRawMedia();
    }
}
```

**IMPORTANT:** `StartRawRecording()` does NOT create a file. It enables access to raw audio/video data streams.

### Manage Recording Lifecycle Explicitly

The bot should treat raw recording as a capability switch plus media subscriptions:

```cpp
class RecordingSession {
public:
    void start(IMeetingService* meetingService) {
        auto* recordCtrl = meetingService->GetMeetingRecordingController();
        if (!recordCtrl) {
            throw std::runtime_error("recording_controller_unavailable");
        }

        SDKError canRecord = recordCtrl->CanStartRawRecording();
        if (canRecord != SDKERR_SUCCESS) {
            throw std::runtime_error("raw_recording_not_permitted");
        }

        SDKError err = recordCtrl->StartRawRecording();
        if (err != SDKERR_SUCCESS) {
            throw std::runtime_error("start_raw_recording_failed");
        }

        audioHelper = GetAudioRawdataHelper();
        audioHelper->subscribe(&audioDelegate, true);

        createRenderer(&videoRenderer, &videoDelegate);
        videoRenderer->setRawDataResolution(ZoomSDKResolution_720P);
        videoRenderer->subscribe(activeUserId, RAW_DATA_TYPE_VIDEO);
    }

    void stop(IMeetingService* meetingService) {
        if (audioHelper) {
            audioHelper->unSubscribe();
        }
        if (videoRenderer) {
            videoRenderer->unSubscribe();
        }

        auto* recordCtrl = meetingService->GetMeetingRecordingController();
        if (recordCtrl) {
            recordCtrl->StopRawRecording();
        }
    }

private:
    IZoomSDKAudioRawDataHelper* audioHelper = nullptr;
    IZoomSDKRenderer* videoRenderer = nullptr;
    MyAudioDelegate audioDelegate;
    MyVideoDelegate videoDelegate;
    uint32_t activeUserId = 0;
};
```

Persisting a recording is your job after raw data arrives. Typical outputs are:

- PCM audio -> WAV/FLAC encoder or streaming transcription pipeline
- YUV420 video -> FFmpeg transcode to MP4 or frame-by-frame CV pipeline
- Mixed bot pipeline -> raw capture first, then post-process after leave

## Step 4: Subscribe to Raw Audio/Video

```cpp
void subscribeToRawMedia() {
    // Subscribe to raw audio
    IZoomSDKAudioRawDataDelegate* audioDelegate = new MyAudioDelegate();
    SDKError audioErr = meetingService->GetMeetingAudioController()
        ->GetMeetingAudioHelper()
        ->subscribe(audioDelegate, true);  // true = mixed audio

    if (audioErr != SDKERR_SUCCESS) {
        cerr << "[AUDIO] Subscribe failed: " << audioErr << endl;
    } else {
        cout << "[AUDIO] Subscribed to mixed audio" << endl;
    }

    // Subscribe to raw video
    IZoomSDKVideoRawDataDelegate* videoDelegate = new MyVideoDelegate();
    SDKError videoErr = meetingService->GetMeetingVideoController()
        ->GetMeetingVideoHelper()
        ->subscribe(videoDelegate);

    if (videoErr != SDKERR_SUCCESS) {
        cerr << "[VIDEO] Subscribe failed: " << videoErr << endl;
    } else {
        cout << "[VIDEO] Subscribed to video streams" << endl;
    }
}
```

### Cloud Recording Alternative

If the requirement is **Zoom-managed cloud recording** instead of raw media capture, use Meeting SDK only for the joining bot and use API/webhook skills for the recording workflow:

```bash
curl -X POST "https://api.zoom.us/v2/users/{userId}/meetings" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "Bot Recorded Meeting",
    "type": 2,
    "start_time": "2026-03-06T18:00:00Z",
    "settings": {
      "auto_recording": "cloud"
    }
  }'
```

Then subscribe to `recording.completed` and download assets through the recordings APIs:

- `zoom-webhooks` -> receive `recording.completed`
- `zoom-rest-api` -> `GET /meetings/{meetingId}/recordings` or `GET /users/{userId}/recordings`

Use this path when the desired output is Zoom-hosted MP4/M4A/transcript files rather than bot-owned raw PCM/YUV.

## Step 5: Mid-Meeting Reconnection

### Connection Monitoring

```cpp
class MeetingBot {
private:
    BotConfig config;
    int reconnectionAttempt = 0;

public:
    void onMeetingStatusChanged(MeetingStatus status, int iResult) {
        switch (status) {
            case MEETING_STATUS_RECONNECTING:
                cout << "[BOT] Connection lost, SDK is reconnecting..." << endl;
                break;

            case MEETING_STATUS_FAILED:
            case MEETING_STATUS_DISCONNECTING:
                handleDisconnection(iResult);
                break;

            case MEETING_STATUS_INMEETING:
                // Reconnection successful
                if (reconnectionAttempt > 0) {
                    cout << "[BOT] Reconnected successfully!" << endl;
                    reconnectionAttempt = 0;  // Reset counter
                }
                break;
        }
    }

private:
    void handleDisconnection(int errorCode) {
        reconnectionAttempt++;

        cout << "[RECONNECT] Disconnected (error: " << errorCode
             << "), attempt " << reconnectionAttempt << "/"
             << config.reconnect_max_attempts << endl;

        if (reconnectionAttempt >= config.reconnect_max_attempts) {
            cerr << "[RECONNECT] Giving up after "
                 << reconnectionAttempt << " attempts" << endl;
            cleanup();
            notifyFailure("Max reconnection attempts exceeded");
            return;
        }

        // Exponential backoff: 2s, 4s, 8s...
        int delay_ms = config.reconnect_base_delay_ms
                       * (1 << (reconnectionAttempt - 1));

        cout << "[RECONNECT] Retrying in " << (delay_ms / 1000) << "s..." << endl;

        // Schedule reconnection
        std::thread([this, delay_ms]() {
            std::this_thread::sleep_for(std::chrono::milliseconds(delay_ms));
            attemptRejoin();
        }).detach();
    }

    void attemptRejoin() {
        // Re-use same meeting number, password, OBF token
        // If OBF token expired, fetch new one from REST API first

        if (isOBFTokenExpired()) {
            cout << "[RECONNECT] OBF token expired, fetching new one..." << endl;
            // TODO: Call REST API to get fresh OBF token
        }

        // Call join again
        bool success = joinMeetingWithRetry(
            cachedMeetingNumber,
            cachedPassword,
            cachedOBFToken,
            cachedBotName
        );

        if (!success) {
            cerr << "[RECONNECT] Rejoin failed" << endl;
            cleanup();
            notifyFailure("Reconnection failed");
        }
    }
};
```

### Customizing Reconnection Behavior

```cpp
// Example: Linear backoff instead of exponential
int delay_ms = config.reconnect_base_delay_ms * reconnectionAttempt;

// Example: Capped exponential backoff (max 30s)
int delay_ms = std::min(
    config.reconnect_base_delay_ms * (1 << (reconnectionAttempt - 1)),
    30000  // Cap at 30s
);

// Example: Jittered backoff (avoid thundering herd)
int base_delay = config.reconnect_base_delay_ms * (1 << (reconnectionAttempt - 1));
int jitter = rand() % 1000;  // Random 0-1000ms
int delay_ms = base_delay + jitter;
```

## Recording Fallback: Local vs Cloud

If raw recording fails, fall back to local or cloud recording:

```cpp
void startRecordingWithFallback() {
    IMeetingRecordingController* ctrl =
        meetingService->GetMeetingRecordingController();

    // Try raw recording first
    if (ctrl->CanStartRawRecording() == SDKERR_SUCCESS) {
        SDKError err = ctrl->StartRawRecording();
        if (err == SDKERR_SUCCESS) {
            cout << "[RECORDING] Using raw recording" << endl;
            return;
        }
    }

    // Fallback: Local recording
    if (ctrl->CanStartRecording(true) == SDKERR_SUCCESS) {
        SDKError err = ctrl->StartRecording(
            chrono::system_clock::now(),
            "/tmp/bot_recording.mp4"
        );
        if (err == SDKERR_SUCCESS) {
            cout << "[RECORDING] Using local recording" << endl;
            return;
        }
    }

    // Fallback: Cloud recording
    if (ctrl->CanStartCloudRecording() == SDKERR_SUCCESS) {
        SDKError err = ctrl->StartCloudRecording();
        if (err == SDKERR_SUCCESS) {
            cout << "[RECORDING] Using cloud recording" << endl;
            return;
        }
    }

    cerr << "[RECORDING] All recording methods failed" << endl;
}
```

## Complete Resilient Bot Example

```cpp
int main() {
    // 1. Load configuration
    BotConfig config = loadConfig();

    // 2. Initialize Meeting SDK
    InitParam initParam;
    initParam.strWebDomain = "https://zoom.us";
    initParam.emLanguageID = LANGUAGE_English;
    initParam.enableLogByDefault = true;

    SDKError err = InitSDK(initParam);
    if (err != SDKERR_SUCCESS) {
        cerr << "InitSDK failed: " << err << endl;
        return 1;
    }

    // 3. Authenticate SDK with JWT
    AuthContext authCtx;
    authCtx.jwt_token = generateJWT(SDK_KEY, SDK_SECRET);

    IAuthService* authService = CreateAuthService();
    authService->SDKAuth(authCtx);

    // Wait for auth callback...

    // 4. Fetch meeting info + OBF token from REST API
    MeetingInfo meetingInfo = fetchMeetingInfoFromAPI(MEETING_ID);
    string obfToken = fetchOBFTokenFromAPI(USER_ID);

    if (meetingInfo.empty() || obfToken.empty()) {
        cerr << "ABORT: Failed to get meeting info or OBF token" << endl;
        return 1;
    }

    // 5. Join meeting with retry
    MeetingBot bot(config);
    bool joined = bot.joinMeetingWithRetry(
        meetingInfo.number,
        meetingInfo.password,
        obfToken,
        "Transcription Bot"
    );

    if (!joined) {
        cerr << "ABORT: Failed to join meeting" << endl;
        return 1;
    }

    // 6. SDK callbacks handle: StartRawRecording, subscribe, reconnection

    // 7. Keep running until meeting ends
    bot.runEventLoop();

    // 8. Cleanup
    bot.cleanup();
    CleanUPSDK();

    return 0;
}
```

## Comparison: Meeting SDK Bot vs RTMS Bot

| Aspect | Meeting SDK Bot | RTMS Bot |
|--------|----------------|----------|
| **Visibility** | Visible participant | Invisible (read-only service) |
| **Authentication** | JWT + OBF token | REST API trigger + webhook |
| **Join Dependency** | Owner must be present | No dependency on participants |
| **Retry Logic** | Required (owner presence) | Not applicable (webhook-based) |
| **Media Access** | Raw audio/video/share via SDK | Audio/video/text/share/chat via WebSocket |
| **Recording Control** | Full (local, cloud, raw) | None (read-only) |
| **Interaction** | Can send chat, reactions | Cannot interact |
| **Resource Usage** | Higher (full SDK) | Lower (WebSocket only) |
| **Use Case** | Interactive bots, recording, moderation | Passive transcription, analytics |

**Choose Meeting SDK Bot when:**
- You need to interact with the meeting (chat, reactions)
- You need local recording control
- You want to be visible in participant list
- You're processing your own meetings

**Choose RTMS Bot when:**
- You only need to observe/transcribe
- You want minimal resource usage
- You prefer invisible operation
- You're processing external meetings

## Troubleshooting

### Bot Never Joins (OBF Owner Not Present)

**Symptom:** All join attempts fail with "owner not in meeting"

**Solution:**
1. Verify owner (OBF token holder) has joined the meeting
2. Increase `join_retry_attempts` or `join_retry_interval_ms`
3. Check meeting start time - don't attempt join before meeting starts
4. Consider webhook: Listen for `meeting.participant_joined` event for owner

### Raw Recording Permission Denied

**Symptom:** `CanStartRawRecording()` returns error

**Solution:**
1. Admin → Account Settings → Meeting → In Meeting (Advanced)
2. Enable "Allow access to raw data (audio, video, sharing) for Meeting SDK"
3. Requires "Raw Data" entitlement from Zoom support

### Frequent Disconnections During Meeting

**Symptom:** Bot reconnects multiple times, then gives up

**Solution:**
1. Increase `reconnect_max_attempts` (e.g., 5 instead of 3)
2. Increase `reconnect_base_delay_ms` if network is slow
3. Check server network stability
4. Monitor CPU/memory usage (insufficient resources can cause disconnects)

### OBF Token Expires During Meeting

**Symptom:** Reconnection fails with "invalid token"

**Solution:**
1. Fetch fresh OBF token in `attemptRejoin()` before rejoining
2. Monitor token expiration (`expire_in` from API response)
3. Request longer-lived tokens (max TTL: 7200s = 2 hours)

## Resources

- **Meeting SDK Linux**: https://developers.zoom.us/docs/meeting-sdk/linux/
- **Raw Data Guide**: https://developers.zoom.us/docs/meeting-sdk/linux/add-features/raw-data/
- **OBF FAQ**: https://developers.zoom.us/docs/meeting-sdk/obf-faq/
- **REST API - Get Meeting**: https://developers.zoom.us/docs/api/rest/reference/zoom-api/methods/#operation/meeting
- **REST API - Get OBF Token**: https://developers.zoom.us/docs/api/rest/reference/zoom-api/methods/#operation/userToken
- **RTMS Bot Alternative**: [../../rtms/examples/rtms-bot.md](../../rtms/examples/rtms-bot.md)
