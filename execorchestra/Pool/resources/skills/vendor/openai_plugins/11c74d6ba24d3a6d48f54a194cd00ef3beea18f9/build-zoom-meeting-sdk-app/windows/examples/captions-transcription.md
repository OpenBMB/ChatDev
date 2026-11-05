# Closed Captions and Live Transcription

## Overview

The Meeting SDK provides two related caption features through `IClosedCaptionController`:

1. **Manual Closed Captions** - Host assigns someone to type captions manually
2. **Live Transcription** - Automatic speech-to-text with optional translation

Both features support multi-language translation when enabled.

## Architecture

```
IMeetingService
    └── GetMeetingClosedCaptionController() → IClosedCaptionController
                                                  ├── SetEvent(IClosedCaptionControllerEvent*)
                                                  ├── EnableCaptions(bool)
                                                  ├── StartLiveTranscription()
                                                  ├── SetMeetingSpokenLanguage(int)
                                                  ├── SetTranslationLanguage(int)
                                                  └── SendClosedCaption(const zchar_t*)
```

## Required Headers

```cpp
#include <meeting_service_interface.h>
#include <meeting_service_components/meeting_closedcaption_interface.h>
```

## Step 1: Implement the Caption Event Listener

```cpp
// ClosedCaptionControllerEventListener.h
#pragma once
#include <meeting_service_components/meeting_closedcaption_interface.h>
#include <functional>

class ClosedCaptionControllerEventListener
    : public ZOOMSDK::IClosedCaptionControllerEvent {
public:
    using TranscriptionCallback = std::function<void(const std::wstring&, unsigned int)>;
    using CaptionCallback = std::function<void(const std::wstring&, unsigned int)>;

    ClosedCaptionControllerEventListener(
        TranscriptionCallback onTranscription = nullptr,
        CaptionCallback onCaption = nullptr
    );
    virtual ~ClosedCaptionControllerEventListener() = default;

    // Called when assigned to send closed captions
    virtual void onAssignedToSendCC(bool bAssigned) override;

    // Called when manual closed caption is received
    virtual void onClosedCaptionMsgReceived(
        const zchar_t* ccMsg,
        unsigned int sender_id,
        time_t time
    ) override;

    // Called when live transcription status changes
    virtual void onLiveTranscriptionStatus(
        ZOOMSDK::SDKLiveTranscriptionStatus status
    ) override;

    // Called when original (untranslated) message is received
    virtual void onOriginalLanguageMsgReceived(
        ZOOMSDK::ILiveTranscriptionMessageInfo* messageInfo
    ) override;

    // Called when translated transcription message is received
    virtual void onLiveTranscriptionMsgInfoReceived(
        ZOOMSDK::ILiveTranscriptionMessageInfo* messageInfo
    ) override;

    // Called when translation error occurs
    virtual void onLiveTranscriptionMsgError(
        ZOOMSDK::ILiveTranscriptionLanguage* spokenLanguage,
        ZOOMSDK::ILiveTranscriptionLanguage* transcriptLanguage
    ) override;

    // Host receives this when someone requests transcription
    virtual void onRequestForLiveTranscriptReceived(
        unsigned int requester_id,
        bool bAnonymous
    ) override;

    // Called when request status changes
    virtual void onRequestLiveTranscriptionStatusChange(bool bEnabled) override;

    // Called when caption enable status changes
    virtual void onCaptionStatusChanged(bool bEnabled) override;

    // Called when someone requests to start captions
    virtual void onStartCaptionsRequestReceived(
        ZOOMSDK::ICCRequestHandler* handler
    ) override;

    // Called when caption request is approved
    virtual void onStartCaptionsRequestApproved() override;

    // Called when manual caption status changes
    virtual void onManualCaptionStatusChanged(bool bEnabled) override;

    // Called when spoken language changes
    virtual void onSpokenLanguageChanged(
        ZOOMSDK::ILiveTranscriptionLanguage* spokenLanguage
    ) override;

private:
    TranscriptionCallback m_onTranscription;
    CaptionCallback m_onCaption;
    std::string wstringToUtf8(const std::wstring& wstr);
};
```

```cpp
// ClosedCaptionControllerEventListener.cpp
#include "ClosedCaptionControllerEventListener.h"
#include <iostream>

using namespace ZOOMSDK;

ClosedCaptionControllerEventListener::ClosedCaptionControllerEventListener(
    TranscriptionCallback onTranscription,
    CaptionCallback onCaption
) : m_onTranscription(onTranscription), m_onCaption(onCaption) {}

void ClosedCaptionControllerEventListener::onAssignedToSendCC(bool bAssigned) {
    std::cout << "Assigned to send CC: " << (bAssigned ? "yes" : "no") << std::endl;
}

void ClosedCaptionControllerEventListener::onClosedCaptionMsgReceived(
    const zchar_t* ccMsg,
    unsigned int sender_id,
    time_t time
) {
    if (ccMsg) {
        std::wstring wstr(ccMsg);
        std::string utf8 = wstringToUtf8(wstr);
        std::cout << "[CC] " << utf8 << std::endl;

        if (m_onCaption) {
            m_onCaption(wstr, sender_id);
        }
    }
}

void ClosedCaptionControllerEventListener::onLiveTranscriptionStatus(
    SDKLiveTranscriptionStatus status
) {
    switch (status) {
        case SDK_LiveTranscription_Status_Stop:
            std::cout << "Live transcription: STOPPED" << std::endl;
            break;
        case SDK_LiveTranscription_Status_Start:
            std::cout << "Live transcription: STARTED" << std::endl;
            break;
        case SDK_LiveTranscription_Status_User_Sub:
            std::cout << "Live transcription: USER SUBSCRIBED" << std::endl;
            break;
        case SDK_LiveTranscription_Status_Connecting:
            std::cout << "Live transcription: CONNECTING" << std::endl;
            break;
    }
}

void ClosedCaptionControllerEventListener::onOriginalLanguageMsgReceived(
    ILiveTranscriptionMessageInfo* messageInfo
) {
    if (!messageInfo) return;

    // Only process complete messages (not partial/streaming)
    if (messageInfo->GetMessageOperationType() == SDK_LiveTranscription_OperationType_Complete) {
        const zchar_t* content = messageInfo->GetMessageContent();
        if (content) {
            std::wstring wstr(content);
            std::string utf8 = wstringToUtf8(wstr);
            std::cout << "[Original] " << utf8 << std::endl;
        }
    }
}

void ClosedCaptionControllerEventListener::onLiveTranscriptionMsgInfoReceived(
    ILiveTranscriptionMessageInfo* messageInfo
) {
    if (!messageInfo) return;

    // Only process complete messages
    SDKLiveTranscriptionOperationType opType = messageInfo->GetMessageOperationType();
    if (opType == SDK_LiveTranscription_OperationType_Complete) {
        const zchar_t* content = messageInfo->GetMessageContent();
        unsigned int speakerId = messageInfo->GetSpeakerID();

        if (content) {
            std::wstring wstr(content);
            std::string utf8 = wstringToUtf8(wstr);
            std::cout << "[Transcription] " << utf8 << std::endl;

            if (m_onTranscription) {
                m_onTranscription(wstr, speakerId);
            }
        }
    }
}

void ClosedCaptionControllerEventListener::onLiveTranscriptionMsgError(
    ILiveTranscriptionLanguage* spokenLanguage,
    ILiveTranscriptionLanguage* transcriptLanguage
) {
    std::cout << "Transcription error occurred" << std::endl;
    if (spokenLanguage) {
        std::wcout << L"  Spoken: " << spokenLanguage->GetLanguageName() << std::endl;
    }
    if (transcriptLanguage) {
        std::wcout << L"  Target: " << transcriptLanguage->GetLanguageName() << std::endl;
    }
}

void ClosedCaptionControllerEventListener::onRequestForLiveTranscriptReceived(
    unsigned int requester_id,
    bool bAnonymous
) {
    std::cout << "Live transcript requested by user "
              << (bAnonymous ? "(anonymous)" : std::to_string(requester_id))
              << std::endl;
}

void ClosedCaptionControllerEventListener::onRequestLiveTranscriptionStatusChange(bool bEnabled) {
    std::cout << "Request transcription status: " << (bEnabled ? "enabled" : "disabled") << std::endl;
}

void ClosedCaptionControllerEventListener::onCaptionStatusChanged(bool bEnabled) {
    std::cout << "Caption status: " << (bEnabled ? "enabled" : "disabled") << std::endl;
}

void ClosedCaptionControllerEventListener::onStartCaptionsRequestReceived(
    ICCRequestHandler* handler
) {
    std::cout << "Caption start request received" << std::endl;
    // Host can approve or deny here
}

void ClosedCaptionControllerEventListener::onStartCaptionsRequestApproved() {
    std::cout << "Caption start request approved" << std::endl;
}

void ClosedCaptionControllerEventListener::onManualCaptionStatusChanged(bool bEnabled) {
    std::cout << "Manual caption: " << (bEnabled ? "enabled" : "disabled") << std::endl;
}

void ClosedCaptionControllerEventListener::onSpokenLanguageChanged(
    ILiveTranscriptionLanguage* spokenLanguage
) {
    if (spokenLanguage) {
        std::wcout << L"Spoken language changed to: "
                   << spokenLanguage->GetLanguageName() << std::endl;
    }
}

std::string ClosedCaptionControllerEventListener::wstringToUtf8(const std::wstring& wstr) {
    std::string utf8Str;
    for (wchar_t wchar : wstr) {
        if (wchar < 0x80) {
            utf8Str += static_cast<char>(wchar);
        } else if (wchar < 0x800) {
            utf8Str += static_cast<char>(0xC0 | ((wchar >> 6) & 0x1F));
            utf8Str += static_cast<char>(0x80 | (wchar & 0x3F));
        } else {
            utf8Str += static_cast<char>(0xE0 | ((wchar >> 12) & 0x0F));
            utf8Str += static_cast<char>(0x80 | ((wchar >> 6) & 0x3F));
            utf8Str += static_cast<char>(0x80 | (wchar & 0x3F));
        }
    }
    return utf8Str;
}
```

## Step 2: Initialize Caption Controller

```cpp
// Global variables
IClosedCaptionController* g_captionController = nullptr;
ClosedCaptionControllerEventListener* g_captionListener = nullptr;

void initializeCaptions(IMeetingService* meetingService) {
    // Get the caption controller
    g_captionController = meetingService->GetMeetingClosedCaptionController();
    if (!g_captionController) {
        std::cerr << "Failed to get caption controller" << std::endl;
        return;
    }

    // Create and set event listener
    g_captionListener = new ClosedCaptionControllerEventListener(
        // Transcription callback
        [](const std::wstring& text, unsigned int speakerId) {
            // Process transcription text
            std::wcout << L"Speaker " << speakerId << L": " << text << std::endl;
        },
        // Caption callback
        [](const std::wstring& text, unsigned int senderId) {
            // Process manual caption
            std::wcout << L"Caption: " << text << std::endl;
        }
    );

    SDKError err = g_captionController->SetEvent(g_captionListener);
    if (err != SDKERR_SUCCESS) {
        std::cerr << "Failed to set caption listener: " << err << std::endl;
        return;
    }

    std::cout << "Caption controller initialized" << std::endl;
}
```

## Step 3: Enable Live Transcription

### Check Feature Availability

```cpp
void checkTranscriptionFeatures() {
    if (!g_captionController) return;

    std::cout << "=== Transcription Features ===" << std::endl;
    std::cout << "Captions enabled: "
              << g_captionController->IsCaptionsEnabled() << std::endl;
    std::cout << "Live transcription feature: "
              << g_captionController->IsLiveTranscriptionFeatureEnabled() << std::endl;
    std::cout << "Manual caption enabled: "
              << g_captionController->IsMeetingManualCaptionEnabled() << std::endl;
    std::cout << "Multi-language transcription: "
              << g_captionController->IsMultiLanguageTranscriptionEnabled() << std::endl;
    std::cout << "Receive spoken language: "
              << g_captionController->IsReceiveSpokenLanguageContentEnabled() << std::endl;
    std::cout << "Request to start enabled: "
              << g_captionController->IsRequestToStartLiveTranscriptionEnabled() << std::endl;
    std::cout << "Text translation enabled: "
              << g_captionController->IsTextLiveTranslationEnabled() << std::endl;
}
```

### Start Live Transcription (with Translation)

```cpp
void startLiveTranscription() {
    if (!g_captionController) return;

    SDKError err;

    // Start live transcription service
    err = g_captionController->StartLiveTranscription();
    if (err != SDKERR_SUCCESS) {
        std::cerr << "Failed to start transcription: " << err << std::endl;
        // May need host permission
    }

    // Set spoken language (0 = English)
    // Use GetAvailableSpokenLanguageList() to get all options
    err = g_captionController->SetMeetingSpokenLanguage(0);
    if (err != SDKERR_SUCCESS) {
        std::cerr << "Failed to set spoken language: " << err << std::endl;
    }

    // Set translation language (1 = Chinese, -1 = disable translation)
    err = g_captionController->SetTranslationLanguage(1);
    if (err != SDKERR_SUCCESS) {
        std::cerr << "Failed to set translation language: " << err << std::endl;
    }

    // Enable receiving original spoken language content
    err = g_captionController->EnableReceiveSpokenLanguageContent(true);
    if (err != SDKERR_SUCCESS) {
        std::cerr << "Failed to enable spoken language content: " << err << std::endl;
    }

    std::cout << "Live transcription started" << std::endl;
}
```

### Stop Live Transcription

```cpp
void stopLiveTranscription() {
    if (!g_captionController) return;

    SDKError err = g_captionController->StopLiveTranscription();
    if (err == SDKERR_SUCCESS) {
        std::cout << "Live transcription stopped" << std::endl;
    }
}
```

## Step 4: Manual Closed Captions (Host Only)

### Enable Manual Captions

```cpp
void enableManualCaptions() {
    if (!g_captionController) return;

    SDKError err;

    // Enable captions feature
    err = g_captionController->EnableCaptions(true);
    if (err != SDKERR_SUCCESS) {
        std::cerr << "Failed to enable captions: " << err << std::endl;
    }

    // Enable manual caption mode
    err = g_captionController->EnableMeetingManualCaption(true);
    if (err != SDKERR_SUCCESS) {
        std::cerr << "Failed to enable manual captions: " << err << std::endl;
    }

    std::cout << "Manual captions enabled" << std::endl;
}
```

### Assign Caption Privilege

```cpp
void assignCaptionPrivilege(unsigned int userId, bool assign) {
    if (!g_captionController) return;

    // Host assigns someone to type captions
    // userId = 0 means current user
    SDKError err = g_captionController->AssignCCPrivilege(userId, assign);
    if (err == SDKERR_SUCCESS) {
        std::cout << "Caption privilege "
                  << (assign ? "assigned to" : "removed from")
                  << " user " << userId << std::endl;
    } else {
        std::cerr << "Failed to assign caption privilege: " << err << std::endl;
    }
}
```

### Send Manual Caption

```cpp
void sendManualCaption(const wchar_t* captionText) {
    if (!g_captionController) return;

    // Only works if you have been assigned CC privilege
    SDKError err = g_captionController->SendClosedCaption(captionText);
    if (err == SDKERR_SUCCESS) {
        std::cout << "Caption sent" << std::endl;
    } else if (err == SDKERR_NO_PERMISSION) {
        std::cerr << "No permission to send captions" << std::endl;
    }
}
```

## Complete Integration Example

```cpp
void onInMeeting(IMeetingService* meetingService) {
    initializeCaptions(meetingService);

    // Check available features
    checkTranscriptionFeatures();

    // Start live transcription with translation
    startLiveTranscription();
}

// For host: enable manual captions
void onIsHost() {
    enableManualCaptions();
    assignCaptionPrivilege(0, true);  // Assign to self
}
```

## Language IDs

Common language IDs for `SetMeetingSpokenLanguage()` and `SetTranslationLanguage()`:

| ID | Language |
|----|----------|
| 0 | English |
| 1 | Chinese (Simplified) |
| 2 | Japanese |
| 3 | German |
| 4 | French |
| 5 | Russian |
| 6 | Portuguese |
| 7 | Spanish |
| 8 | Korean |
| -1 | Disable translation |

Use `GetAvailableSpokenLanguageList()` and `GetAvailableTranslationLanguageList()` to get the full list of supported languages for the meeting.

## Transcription Operation Types

```cpp
enum SDKLiveTranscriptionOperationType {
    SDK_LiveTranscription_OperationType_None = 0,
    SDK_LiveTranscription_OperationType_Add,      // New text added
    SDK_LiveTranscription_OperationType_Update,   // Text updated
    SDK_LiveTranscription_OperationType_Delete,   // Text deleted
    SDK_LiveTranscription_OperationType_Complete, // Sentence complete
    SDK_LiveTranscription_OperationType_NotSupported
};
```

**Important**: Only process `SDK_LiveTranscription_OperationType_Complete` for final transcription text. Other types represent partial/streaming results.

## Transcription Status

```cpp
enum SDKLiveTranscriptionStatus {
    SDK_LiveTranscription_Status_Stop = 0,    // Not running
    SDK_LiveTranscription_Status_Start = 1,   // Running
    SDK_LiveTranscription_Status_User_Sub = 2, // User subscribed
    SDK_LiveTranscription_Status_Connecting = 10  // Connecting
};
```

## Error Handling

```cpp
SDKError err = g_captionController->StartLiveTranscription();
switch (err) {
    case SDKERR_SUCCESS:
        std::cout << "Transcription started" << std::endl;
        break;
    case SDKERR_NO_PERMISSION:
        std::cerr << "No permission (need host or feature disabled)" << std::endl;
        break;
    case SDKERR_WRONG_USAGE:
        std::cerr << "Feature not available in this meeting" << std::endl;
        break;
    case SDKERR_SERVICE_FAILED:
        std::cerr << "Service failed to start" << std::endl;
        break;
    default:
        std::cerr << "Error: " << err << std::endl;
}
```

## Common Pitfalls

1. **Multi-language transcription**: Must be enabled in meeting settings for translation to work
2. **Manual captions vs transcription**: These are separate features - enable the one you need
3. **Partial results**: Filter by `GetMessageOperationType() == Complete` to avoid streaming updates
4. **Language ID -1**: Setting translation language to -1 receives closed captions without translation
5. **Host permission**: Most enable/disable operations require host privileges
6. **Unicode handling**: Caption text is `zchar_t*` (wide string) - convert to UTF-8 for display
