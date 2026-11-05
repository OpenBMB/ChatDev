# SDK Architecture Pattern: The Universal Implementation Formula

## Core Concept

The Zoom Windows Meeting SDK follows a **consistent architectural pattern** that applies to EVERY feature. Once you understand this pattern, you can implement ANY feature just by reading the `.h` header files.

---

## The Universal Pattern

Every SDK feature follows this 3-step pattern:

### 1. Get the Controller/Helper (Singleton Pattern)

```cpp
// Pattern: meetingService->Get[Feature]Controller()
IMeetingAudioController* audioCtrl = meetingService->GetMeetingAudioController();
IMeetingChatController* chatCtrl = meetingService->GetMeetingChatController();
IMeetingVideoController* videoCtrl = meetingService->GetMeetingVideoController();
```

### 2. Implement the Event Listener Interface (Observer Pattern)

```cpp
// Pattern: I[Feature]Event or I[Feature]CtrlEvent
class MyAudioListener : public IMeetingAudioCtrlEvent {
    void onUserAudioStatusChange(IList<IUserAudioStatus*>* lstAudioStatusChange) override {
        // React to audio events
    }
    // ... implement all pure virtual methods
};
```

### 3. Register Listener and Use Controller Methods

```cpp
// Pattern: controller->SetEvent(listener), then call methods
audioCtrl->SetEvent(new MyAudioListener());
audioCtrl->MuteAudio(userId, true);  // Use feature
```

---

## Complete Architecture Overview

### The Singleton Services

**Top-level services** (created via global functions):

```cpp
// Authentication Service (JWT, user login)
IAuthService* authService;
CreateAuthService(&authService);

// Meeting Service (join, leave, access features)
IMeetingService* meetingService;
CreateMeetingService(&meetingService);
```

### Feature Controllers (35+ Available)

**All controllers** are accessed through `IMeetingService->Get[Feature]Controller()`:

```cpp
// Audio features
IMeetingAudioController* audioCtrl = meetingService->GetMeetingAudioController();

// Video features
IMeetingVideoController* videoCtrl = meetingService->GetMeetingVideoController();

// Chat features
IMeetingChatController* chatCtrl = meetingService->GetMeetingChatController();

// Participants management
IMeetingParticipantsController* participantsCtrl = meetingService->GetMeetingParticipantsController();

// Recording features
IMeetingRecordingController* recordingCtrl = meetingService->GetMeetingRecordingController();

// Screen sharing
IMeetingShareController* shareCtrl = meetingService->GetMeetingShareController();

// Waiting room
IMeetingWaitingRoomController* waitingRoomCtrl = meetingService->GetMeetingWaitingRoomController();

// Webinar features
IMeetingWebinarController* webinarCtrl = meetingService->GetMeetingWebinarController();

// Breakout rooms
IMeetingBOController* boCtrl = meetingService->GetMeetingBOController();

// AI Companion
IMeetingAICompanionController* aiCtrl = meetingService->GetMeetingAICompanionController();

// Q&A
IMeetingQAController* qaCtrl = meetingService->GetMeetingQAController();

// Polling
IMeetingPollingController* pollingCtrl = meetingService->GetMeetingPollingController();

// Whiteboard
IMeetingWhiteboardController* whiteboardCtrl = meetingService->GetMeetingWhiteboardController();

// Closed captions
IClosedCaptionController* captionCtrl = meetingService->GetMeetingClosedCaptionController();

// Live streaming
IMeetingLiveStreamController* liveStreamCtrl = meetingService->GetMeetingLiveStreamController();

// Emoji reactions
IEmojiReactionController* emojiCtrl = meetingService->GetMeetingEmojiReactionController();

// Interpretation
IMeetingInterpretationController* interpretCtrl = meetingService->GetMeetingInterpretationController();

// Remote support
IMeetingRemoteSupportController* remoteSupportCtrl = meetingService->GetMeetingRemoteSupportController();

// Encryption
IMeetingEncryptionController* encryptionCtrl = meetingService->GetInMeetingEncryptionController();

// ... and 15+ more controllers!
```

**Complete list** (35 controllers as of SDK v6.7.2):
1. `GetMeetingAudioController()` - Audio mute/unmute
2. `GetMeetingVideoController()` - Video start/stop
3. `GetMeetingShareController()` - Screen sharing
4. `GetMeetingChatController()` - Meeting chat
5. `GetMeetingParticipantsController()` - Participant management
6. `GetMeetingRecordingController()` - Recording/raw data
7. `GetMeetingWaitingRoomController()` - Waiting room management
8. `GetMeetingWebinarController()` - Webinar features
9. `GetMeetingBOController()` - Breakout rooms
10. `GetMeetingAICompanionController()` - AI features
11. `GetMeetingQAController()` - Q&A management
12. `GetMeetingPollingController()` - Polls/surveys
13. `GetMeetingWhiteboardController()` - Whiteboard
14. `GetMeetingClosedCaptionController()` - Captions
15. `GetMeetingLiveStreamController()` - Live streaming
16. `GetMeetingEmojiReactionController()` - Emoji reactions
17. `GetMeetingInterpretationController()` - Language interpretation
18. `GetMeetingSignInterpretationController()` - Sign language
19. `GetMeetingRemoteSupportController()` - Remote support
20. `GetMeetingEncryptionController()` - E2E encryption
21. `GetMeetingRawArchivingController()` - Raw archiving
22. `GetMeetingReminderController()` - Meeting reminders
23. `GetMeetingSmartSummaryController()` - Smart summary (deprecated)
24. `GetUIController()` - UI controls
25. `GetAnnotationController()` - Annotations
26. `GetMeetingRemoteController()` - Remote control
27. `GetH323Helper()` - H.323 support
28. `GetMeetingPhoneHelper()` - Phone dial-in
29. `GetMeetingRealNameAuthController()` - Real name auth
30. `GetMeetingAANController()` - Auto Accept Notification
31. `GetMeetingImmersiveController()` - Immersive view
32. `GetMeetingDocsController()` - Documents
33. `GetMeetingIndicatorController()` - Meeting indicators
34. `GetMeetingProductionStudioController()` - Production studio
35. And more in future versions...

---

## Deep Dive: Audio Feature Example

Let's implement audio mute/unmute to demonstrate the pattern:

### Step 1: Read the Header File

Open `SDK/x64/h/meeting_service_components/meeting_audio_interface.h`:

```cpp
// The event listener interface
class IMeetingAudioCtrlEvent {
public:
    virtual void onUserAudioStatusChange(IList<IUserAudioStatus*>* lstAudioStatusChange) = 0;
    virtual void onUserActiveAudioChange(IList<unsigned int>* plstActiveAudioUser) = 0;
    // ... more callback methods
};

// The controller interface
class IMeetingAudioController {
public:
    virtual SDKError SetEvent(IMeetingAudioCtrlEvent* pEvent) = 0;
    virtual SDKError JoinVoip() = 0;
    virtual SDKError MuteAudio(unsigned int userid, bool allowUnmuteBySelf = true) = 0;
    virtual SDKError UnMuteAudio(unsigned int userid) = 0;
    // ... more control methods
};
```

### Step 2: Implement the Event Listener

**AudioEventListener.h**:
```cpp
#pragma once
#include <windows.h>
#include <cstdint>
#include <meeting_service_components/meeting_audio_interface.h>
#include <iostream>

using namespace ZOOM_SDK_NAMESPACE;

class AudioEventListener : public IMeetingAudioCtrlEvent {
public:
    // Implement ALL pure virtual methods from IMeetingAudioCtrlEvent
    void onUserAudioStatusChange(IList<IUserAudioStatus*>* lstAudioStatusChange) override;
    void onUserActiveAudioChange(IList<unsigned int>* plstActiveAudioUser) override;
    void onHostRequestStartAudio(IRequestStartAudioHandler* handler) override;
    void onMuteOnEntryStatusChange(bool bEnabled) override;
    // ... implement all other required methods
};
```

**AudioEventListener.cpp**:
```cpp
#include "AudioEventListener.h"

void AudioEventListener::onUserAudioStatusChange(IList<IUserAudioStatus*>* lstAudioStatusChange) {
    if (!lstAudioStatusChange) return;

    int count = lstAudioStatusChange->GetCount();
    for (int i = 0; i < count; i++) {
        IUserAudioStatus* audioStatus = lstAudioStatusChange->GetItem(i);
        unsigned int userId = audioStatus->GetUserId();
        AudioStatus status = audioStatus->GetStatus();

        std::cout << "[AUDIO] User " << userId << " status changed: " << status << std::endl;
    }
}

void AudioEventListener::onUserActiveAudioChange(IList<unsigned int>* plstActiveAudioUser) {
    if (!plstActiveAudioUser) return;

    int count = plstActiveAudioUser->GetCount();
    std::cout << "[AUDIO] Active speakers: " << count << std::endl;
}

void AudioEventListener::onHostRequestStartAudio(IRequestStartAudioHandler* handler) {
    std::cout << "[AUDIO] Host requests unmute" << std::endl;
    // Auto-accept or ignore based on your logic
    if (handler) {
        handler->Accept();  // or handler->Ignore()
    }
}

void AudioEventListener::onMuteOnEntryStatusChange(bool bEnabled) {
    std::cout << "[AUDIO] Mute on entry: " << (bEnabled ? "enabled" : "disabled") << std::endl;
}
```

### Step 3: Use the Feature

**main.cpp**:
```cpp
void SetupAudioFeatures() {
    // 1. Get the controller (singleton)
    IMeetingAudioController* audioCtrl = meetingService->GetMeetingAudioController();
    if (!audioCtrl) {
        std::cerr << "Failed to get audio controller" << std::endl;
        return;
    }

    // 2. Set event listener
    audioCtrl->SetEvent(new AudioEventListener());

    // 3. Use controller methods

    // Join audio (connect to VoIP)
    SDKError err = audioCtrl->JoinVoip();
    if (err == SDKERR_SUCCESS) {
        std::cout << "[AUDIO] Joined VoIP successfully" << std::endl;
    }

    // Mute yourself (userId = 0 or your own user ID)
    audioCtrl->MuteAudio(0, true);
    std::cout << "[AUDIO] Muted self" << std::endl;

    // Unmute yourself
    audioCtrl->UnMuteAudio(0);
    std::cout << "[AUDIO] Unmuted self" << std::endl;

    // Mute all participants (host only, userId = 0 for all)
    audioCtrl->MuteAudio(0, false);  // false = don't allow self-unmute
    std::cout << "[AUDIO] Muted all participants" << std::endl;
}
```

---

## The Pattern Applied to ANY Feature

### Example: Implementing Chat

**Step 1: Read header** (`meeting_chat_interface.h`)

```cpp
class IMeetingChatCtrlEvent {
    virtual void onChatMsgNotification(IChatMsgInfo* chatMsg) = 0;
    // ... more methods
};

class IMeetingChatController {
    virtual SDKError SetEvent(IMeetingChatCtrlEvent* pEvent) = 0;
    virtual SDKError SendChatTo(const wchar_t* receiver, const wchar_t* content) = 0;
    // ... more methods
};
```

**Step 2: Implement listener**

```cpp
class ChatEventListener : public IMeetingChatCtrlEvent {
    void onChatMsgNotification(IChatMsgInfo* chatMsg) override {
        std::wcout << L"[CHAT] From: " << chatMsg->GetSenderDisplayName()
                   << L", Message: " << chatMsg->GetContent() << std::endl;
    }
};
```

**Step 3: Use it**

```cpp
IMeetingChatController* chatCtrl = meetingService->GetMeetingChatController();
chatCtrl->SetEvent(new ChatEventListener());
chatCtrl->SendChatTo(L"everyone", L"Hello from bot!");
```

### Example: Implementing Screen Share Detection

**Step 1: Read header** (`meeting_sharing_interface.h`)

```cpp
class IMeetingShareCtrlEvent {
    virtual void onSharingStatus(SharingStatus status, unsigned int userId) = 0;
};
```

**Step 2: Implement listener**

```cpp
class ShareEventListener : public IMeetingShareCtrlEvent {
    void onSharingStatus(SharingStatus status, unsigned int userId) override {
        if (status == Sharing_Self_Send_Begin) {
            std::cout << "[SHARE] User " << userId << " started sharing" << std::endl;
        } else if (status == Sharing_Self_Send_End) {
            std::cout << "[SHARE] User " << userId << " stopped sharing" << std::endl;
        }
    }
};
```

**Step 3: Use it**

```cpp
IMeetingShareController* shareCtrl = meetingService->GetMeetingShareController();
shareCtrl->SetEvent(new ShareEventListener());
```

---

## Key Architectural Insights

### 1. Controllers are Singletons

Each controller is a singleton accessed through `meetingService`:

```cpp
// Always returns the SAME instance
IMeetingAudioController* ctrl1 = meetingService->GetMeetingAudioController();
IMeetingAudioController* ctrl2 = meetingService->GetMeetingAudioController();
// ctrl1 == ctrl2 (same pointer)
```

**Why this matters**: You can get the controller anywhere in your code without passing pointers around.

### 2. Event Listeners Use Observer Pattern

```cpp
// SDK maintains the listener internally
audioCtrl->SetEvent(new AudioEventListener());

// SDK calls listener methods when events occur
// You don't call these methods yourself!
```

**Why this matters**: The SDK manages listener lifecycle. Use `new` and let SDK handle cleanup.

### 3. Controllers Have Both Actions and Queries

**Actions** (change state):
```cpp
audioCtrl->MuteAudio(userId, true);        // DO something
chatCtrl->SendChatTo(L"user", L"hello");   // DO something
```

**Queries** (get information):
```cpp
bool isMuted = audioCtrl->IsAudioMuted(userId);    // GET information
bool isHost = participantsCtrl->IsHost(userId);     // GET information
```

### 4. Feature Availability Varies by SDK App Type

Some features require specific permissions:

```cpp
// Recording requires special SDK app type
IMeetingRecordingController* recordingCtrl = meetingService->GetMeetingRecordingController();
if (recordingCtrl) {
    SDKError canRecord = recordingCtrl->CanStartRawRecording();
    if (canRecord == SDKERR_SUCCESS) {
        recordingCtrl->StartRawRecording();
    } else {
        // Not available (wrong app type, insufficient permissions)
    }
}
```

---

## How to Implement Any Feature (Universal Recipe)

### Recipe for Success:

1. **Find the header file**:
   - Look in `SDK/x64/h/meeting_service_components/`
   - File naming: `meeting_[feature]_interface.h`
   - Examples: `meeting_audio_interface.h`, `meeting_chat_interface.h`

2. **Identify the interfaces**:
   - Find `I[Feature]Event` or `I[Feature]CtrlEvent` (for callbacks)
   - Find `I[Feature]Controller` (for actions/queries)

3. **Implement the event listener**:
   - Create class inheriting from `I[Feature]Event`
   - Implement ALL pure virtual methods (use [Interface Methods Guide](../references/interface-methods.md))
   - Add logging to see when events fire

4. **Get the controller**:
   - Call `meetingService->Get[Feature]Controller()`
   - Check for `nullptr` (might not be available)

5. **Register listener and use**:
   - Call `controller->SetEvent(new YourListener())`
   - Call controller methods to use features

6. **Test incrementally**:
   - Start with event logging only
   - Verify events fire correctly
   - Add action methods one at a time

---

## Complete Working Example: Mute Bot

This bot auto-mutes when joining and responds to host unmute requests:

```cpp
#include <windows.h>
#include <cstdint>
#include <meeting_service_components/meeting_audio_interface.h>
#include <iostream>

using namespace ZOOM_SDK_NAMESPACE;

class MuteBotAudioListener : public IMeetingAudioCtrlEvent {
private:
    IMeetingAudioController* audioCtrl;

public:
    MuteBotAudioListener(IMeetingAudioController* ctrl) : audioCtrl(ctrl) {}

    void onUserAudioStatusChange(IList<IUserAudioStatus*>* lstAudioStatusChange) override {
        // Just log for debugging
        std::cout << "[AUDIO] Audio status changed" << std::endl;
    }

    void onUserActiveAudioChange(IList<unsigned int>* plstActiveAudioUser) override {
        // Not needed for this bot
    }

    void onHostRequestStartAudio(IRequestStartAudioHandler* handler) override {
        std::cout << "[AUDIO] Host requested unmute - auto accepting" << std::endl;
        if (handler) {
            handler->Accept();  // Automatically accept host request
        }
    }

    void onMuteOnEntryStatusChange(bool bEnabled) override {
        std::cout << "[AUDIO] Mute on entry: " << bEnabled << std::endl;
    }
};

void SetupMuteBot() {
    // Get audio controller
    IMeetingAudioController* audioCtrl = meetingService->GetMeetingAudioController();
    if (!audioCtrl) return;

    // Register event listener
    audioCtrl->SetEvent(new MuteBotAudioListener(audioCtrl));

    // Join VoIP
    audioCtrl->JoinVoip();

    // Mute self immediately
    audioCtrl->MuteAudio(0, true);

    std::cout << "[BOT] Mute bot active - will auto-accept host unmute requests" << std::endl;
}
```

---

## Advanced Pattern: Multiple Feature Integration

Real bots typically use multiple controllers:

```cpp
void SetupAdvancedBot() {
    // Audio: Auto-mute on join
    IMeetingAudioController* audioCtrl = meetingService->GetMeetingAudioController();
    audioCtrl->SetEvent(new AudioEventListener());
    audioCtrl->JoinVoip();
    audioCtrl->MuteAudio(0, true);

    // Video: Keep video off
    IMeetingVideoController* videoCtrl = meetingService->GetMeetingVideoController();
    videoCtrl->SetEvent(new VideoEventListener());
    // Video off by default when joining with isVideoOff = true

    // Chat: Respond to commands
    IMeetingChatController* chatCtrl = meetingService->GetMeetingChatController();
    chatCtrl->SetEvent(new ChatCommandListener());
    chatCtrl->SendChatTo(L"everyone", L"Bot is ready!");

    // Participants: Track who joins/leaves
    IMeetingParticipantsController* participantsCtrl = meetingService->GetMeetingParticipantsController();
    participantsCtrl->SetEvent(new ParticipantsEventListener());

    // Recording: Capture meeting
    IMeetingRecordingController* recordingCtrl = meetingService->GetMeetingRecordingController();
    if (recordingCtrl->CanStartRawRecording() == SDKERR_SUCCESS) {
        recordingCtrl->StartRawRecording();
    }
}
```

---

## Common Patterns Across All Controllers

### Pattern 1: Check Availability Before Use

```cpp
IMeetingRecordingController* ctrl = meetingService->GetMeetingRecordingController();
if (ctrl) {  // Controller exists
    SDKError canUse = ctrl->CanStartRawRecording();
    if (canUse == SDKERR_SUCCESS) {  // Feature available
        ctrl->StartRawRecording();
    }
}
```

### Pattern 2: User ID = 0 Often Means "Self"

```cpp
audioCtrl->MuteAudio(0, true);      // Mute self
audioCtrl->MuteAudio(userId, true); // Mute specific user
```

### Pattern 3: Event Listeners Are Optional

```cpp
// Some features work without event listener
IMeetingChatController* chatCtrl = meetingService->GetMeetingChatController();
// Don't need SetEvent() if you only send messages, don't receive
chatCtrl->SendChatTo(L"everyone", L"Hello");
```

### Pattern 4: IList<T> Collections

```cpp
IList<unsigned int>* participantList = participantsCtrl->GetParticipantsList();
int count = participantList->GetCount();
for (int i = 0; i < count; i++) {
    unsigned int userId = participantList->GetItem(i);
    // Use userId...
}
```

---

## Troubleshooting

### Controller is nullptr

**Cause**: Feature not available in this SDK app type or meeting state

**Solution**:
- Check if you're in a meeting (`MEETING_STATUS_INMEETING`)
- Verify SDK app permissions in Zoom Marketplace
- Some controllers only available to hosts/co-hosts

### SetEvent() Does Nothing

**Cause**: Forgot Windows message loop

**Solution**: See [Windows Message Loop Guide](../troubleshooting/windows-message-loop.md)

### Methods Return SDKERR_WRONG_USAGE

**Cause**: Called at wrong time or insufficient permissions

**Solution**:
- Check method documentation for prerequisites
- Verify you're in correct meeting state
- Check if you're host/co-host (if required)

---

## Summary: The Universal Formula

```
1. Read header file → Find I[Feature]Controller and I[Feature]Event
2. Implement event listener → Inherit I[Feature]Event, implement all methods
3. Get controller → meetingService->Get[Feature]Controller()
4. Register listener → controller->SetEvent(new YourListener())
5. Use features → Call controller methods
```

**This pattern works for ALL 35+ controllers!**

---

## Next Steps

- Browse all available controllers: `SDK/x64/h/meeting_service_interface.h` (lines 1103-1314)
- Pick a feature you want to implement
- Find its header in `SDK/x64/h/meeting_service_components/`
- Follow the universal pattern above

---

## Related Documentation

- [Interface Methods Guide](../references/interface-methods.md) - How to implement event listeners
- [Authentication Pattern](../examples/authentication-pattern.md) - How to get meetingService
- [Raw Video Capture](../examples/raw-video-capture.md) - Example using recording controller
- [Windows Message Loop](../troubleshooting/windows-message-loop.md) - Required for callbacks

---

**Last Updated**: Based on Zoom Windows Meeting SDK v6.7.2.26830
