# Live Transcription

Complete working code for real-time speech-to-text transcription.

**Official Sample**: `VSDK_TranscriptionAndTranslation` in [videosdk-windows-rawdata-sample](https://github.com/zoom/videosdk-windows-rawdata-sample)

---

## Overview

Live transcription provides real-time captions of speech. Features:
- Automatic speech recognition
- Multiple language support
- Speaker identification
- Translation (optional)

```
┌─────────────────────────────────────────────────────────────────┐
│                    TRANSCRIPTION FLOW                           │
├─────────────────────────────────────────────────────────────────┤
│  1. Enable transcription → startLiveTranscription()             │
│  2. Receive captions → onLiveTranscriptionMsgInfoReceived()     │
│  3. Display/process text                                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Prerequisites

- Live transcription must be enabled for the session
- Valid Zoom account with transcription feature

---

## Complete Working Code

### TranscriptionManager.h

```cpp
#pragma once
#include <windows.h>
#include <string>
#include <vector>
#include <functional>
#include "zoom_video_sdk_interface.h"

USING_ZOOM_VIDEO_SDK_NAMESPACE

struct TranscriptionMessage {
    std::wstring speakerName;
    std::wstring text;
    bool isFinal;
    unsigned long long timestamp;
};

class TranscriptionManager {
public:
    TranscriptionManager(IZoomVideoSDK* sdk);

    // Control
    bool StartTranscription();
    bool StopTranscription();
    bool IsTranscribing() const { return m_isTranscribing; }

    // Language settings
    bool SetSpokenLanguage(ILiveTranscriptionLanguage* language);
    bool SetTranslationLanguage(ILiveTranscriptionLanguage* language);
    std::vector<ILiveTranscriptionLanguage*> GetAvailableLanguages();

    // Callbacks from delegate
    void OnStatusChanged(ZoomVideoSDKLiveTranscriptionStatus status);
    void OnMessageReceived(ILiveTranscriptionMessageInfo* info);
    void OnOriginalLanguageReceived(ILiveTranscriptionMessageInfo* info);
    void OnError(ILiveTranscriptionLanguage* spoken,
                 ILiveTranscriptionLanguage* transcript);

    // Set message handler
    using MessageCallback = std::function<void(const TranscriptionMessage&)>;
    void SetMessageHandler(MessageCallback callback) { m_callback = callback; }

private:
    IZoomVideoSDK* m_sdk;
    IZoomVideoSDKLiveTranscriptionHelper* m_helper;
    bool m_isTranscribing;
    MessageCallback m_callback;
};
```

### TranscriptionManager.cpp

```cpp
#include "TranscriptionManager.h"
#include <iostream>

TranscriptionManager::TranscriptionManager(IZoomVideoSDK* sdk)
    : m_sdk(sdk)
    , m_helper(nullptr)
    , m_isTranscribing(false) {
}

bool TranscriptionManager::StartTranscription() {
    m_helper = m_sdk->getLiveTranscriptionHelper();
    if (!m_helper) {
        std::cout << "Transcription helper not available" << std::endl;
        return false;
    }

    // Check if transcription is available
    if (!m_helper->canStartLiveTranscription()) {
        std::cout << "Cannot start transcription" << std::endl;
        return false;
    }

    ZoomVideoSDKErrors err = m_helper->startLiveTranscription();
    if (err == ZoomVideoSDKErrors_Success) {
        std::cout << "Transcription started" << std::endl;
        return true;
    }

    std::cout << "Start transcription failed: " << err << std::endl;
    return false;
}

bool TranscriptionManager::StopTranscription() {
    if (!m_helper) return false;

    ZoomVideoSDKErrors err = m_helper->stopLiveTranscription();
    if (err == ZoomVideoSDKErrors_Success) {
        std::cout << "Transcription stopped" << std::endl;
        m_isTranscribing = false;
        return true;
    }

    return false;
}

std::vector<ILiveTranscriptionLanguage*> TranscriptionManager::GetAvailableLanguages() {
    std::vector<ILiveTranscriptionLanguage*> languages;

    if (!m_helper) {
        m_helper = m_sdk->getLiveTranscriptionHelper();
    }

    if (m_helper) {
        IVideoSDKVector<ILiveTranscriptionLanguage*>* langList =
            m_helper->getAvailableSpokenLanguages();

        if (langList) {
            for (int i = 0; i < langList->GetCount(); i++) {
                languages.push_back(langList->GetItem(i));
            }
        }
    }

    return languages;
}

bool TranscriptionManager::SetSpokenLanguage(ILiveTranscriptionLanguage* language) {
    if (!m_helper || !language) return false;

    ZoomVideoSDKErrors err = m_helper->setSpokenLanguage(language);
    if (err == ZoomVideoSDKErrors_Success) {
        std::wcout << L"Spoken language set to: "
                   << language->getLTTLanguageName() << std::endl;
        return true;
    }
    return false;
}

bool TranscriptionManager::SetTranslationLanguage(ILiveTranscriptionLanguage* language) {
    if (!m_helper || !language) return false;

    ZoomVideoSDKErrors err = m_helper->setTranslationLanguage(language);
    if (err == ZoomVideoSDKErrors_Success) {
        std::wcout << L"Translation language set to: "
                   << language->getLTTLanguageName() << std::endl;
        return true;
    }
    return false;
}

void TranscriptionManager::OnStatusChanged(ZoomVideoSDKLiveTranscriptionStatus status) {
    switch (status) {
        case ZoomVideoSDKLiveTranscription_Status_Start:
            std::cout << "Transcription started" << std::endl;
            m_isTranscribing = true;
            break;

        case ZoomVideoSDKLiveTranscription_Status_Stop:
            std::cout << "Transcription stopped" << std::endl;
            m_isTranscribing = false;
            break;

        case ZoomVideoSDKLiveTranscription_Status_Connecting:
            std::cout << "Transcription connecting..." << std::endl;
            break;

        default:
            std::cout << "Transcription status: " << status << std::endl;
    }
}

void TranscriptionManager::OnMessageReceived(ILiveTranscriptionMessageInfo* info) {
    if (!info) return;

    TranscriptionMessage msg;

    // Get speaker
    IZoomVideoSDKUser* speaker = info->getSpeaker();
    if (speaker) {
        msg.speakerName = speaker->getUserName();
    }

    // Get text
    const zchar_t* text = info->getMessageContent();
    if (text) {
        msg.text = text;
    }

    // Get metadata
    msg.isFinal = (info->getMessageType() ==
                   ZoomVideoSDKLiveTranscriptionOperationType_Complete);
    msg.timestamp = info->getTimeStamp();

    // Display
    std::wcout << L"[" << msg.speakerName << L"] " << msg.text;
    if (msg.isFinal) {
        std::wcout << L" (final)";
    }
    std::wcout << std::endl;

    // Call user handler
    if (m_callback) {
        m_callback(msg);
    }
}

void TranscriptionManager::OnOriginalLanguageReceived(ILiveTranscriptionMessageInfo* info) {
    // Original language message (before translation)
    if (!info) return;

    const zchar_t* text = info->getMessageContent();
    if (text) {
        std::wcout << L"[Original] " << text << std::endl;
    }
}

void TranscriptionManager::OnError(ILiveTranscriptionLanguage* spoken,
                                    ILiveTranscriptionLanguage* transcript) {
    std::cout << "Transcription error" << std::endl;
    if (spoken) {
        std::wcout << L"Spoken language: " << spoken->getLTTLanguageName() << std::endl;
    }
    if (transcript) {
        std::wcout << L"Transcript language: " << transcript->getLTTLanguageName() << std::endl;
    }
}
```

### Using in Delegate

```cpp
class MyDelegate : public IZoomVideoSDKDelegate {
private:
    TranscriptionManager* m_transcription;

public:
    MyDelegate(IZoomVideoSDK* sdk) {
        m_transcription = new TranscriptionManager(sdk);

        // Set message handler
        m_transcription->SetMessageHandler([](const TranscriptionMessage& msg) {
            // Process transcription (e.g., save to file, analyze)
            if (msg.isFinal) {
                SaveTranscript(msg.speakerName, msg.text);
            }
        });
    }

    void onSessionJoin() override {
        // Start transcription
        m_transcription->StartTranscription();
    }

    void onLiveTranscriptionStatus(ZoomVideoSDKLiveTranscriptionStatus status) override {
        m_transcription->OnStatusChanged(status);
    }

    void onLiveTranscriptionMsgInfoReceived(ILiveTranscriptionMessageInfo* info) override {
        m_transcription->OnMessageReceived(info);
    }

    void onOriginalLanguageMsgReceived(ILiveTranscriptionMessageInfo* info) override {
        m_transcription->OnOriginalLanguageReceived(info);
    }

    void onLiveTranscriptionMsgError(ILiveTranscriptionLanguage* spoken,
                                      ILiveTranscriptionLanguage* transcript) override {
        m_transcription->OnError(spoken, transcript);
    }

    // ... other callbacks
};
```

---

## Message Types

| Type | Description |
|------|-------------|
| `ZoomVideoSDKLiveTranscriptionOperationType_N` | Interim result (may change) |
| `ZoomVideoSDKLiveTranscriptionOperationType_Complete` | Final result |
| `ZoomVideoSDKLiveTranscriptionOperationType_Update` | Updated previous result |

**Note**: Interim results allow real-time display but may be revised.

---

## ILiveTranscriptionMessageInfo Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `getMessageContent()` | `const zchar_t*` | Transcribed text |
| `getSpeaker()` | `IZoomVideoSDKUser*` | Speaker user object |
| `getTimeStamp()` | `unsigned long long` | Message timestamp |
| `getMessageType()` | `ZoomVideoSDKLiveTranscriptionOperationType` | Interim/final |
| `getMessageID()` | `const zchar_t*` | Unique message ID |

---

## Language Support

### List Available Languages

```cpp
auto languages = transcriptionManager->GetAvailableLanguages();
for (auto lang : languages) {
    std::wcout << lang->getLTTLanguageID() << L": "
               << lang->getLTTLanguageName() << std::endl;
}
```

### Common Language Codes

| Code | Language |
|------|----------|
| `en` | English |
| `es` | Spanish |
| `fr` | French |
| `de` | German |
| `zh` | Chinese |
| `ja` | Japanese |

---

## Common Issues

### Transcription Not Available

**Cause**: Feature not enabled for session

**Fix**: Check `canStartLiveTranscription()` first:
```cpp
if (helper->canStartLiveTranscription()) {
    helper->startLiveTranscription();
}
```

### No Messages Received

**Cause**: No one is speaking or audio not connected

**Fix**: Ensure audio is connected:
```cpp
void onSessionJoin() override {
    sdk->getAudioHelper()->startAudio();  // Connect audio first
    transcription->StartTranscription();
}
```

### Wrong Language

**Cause**: Spoken language not set correctly

**Fix**: Set spoken language:
```cpp
auto languages = manager->GetAvailableLanguages();
for (auto lang : languages) {
    if (wcscmp(lang->getLTTLanguageID(), L"en") == 0) {
        manager->SetSpokenLanguage(lang);
        break;
    }
}
```

---

## Related Documentation

- [Raw Audio Capture](raw-audio-capture.md) - Alternative audio processing
- [Session Join Pattern](session-join-pattern.md) - Session setup
- [Delegate Methods](../references/delegate-methods.md) - Transcription callbacks
- [API Reference](../references/windows-reference.md) - Method signatures
