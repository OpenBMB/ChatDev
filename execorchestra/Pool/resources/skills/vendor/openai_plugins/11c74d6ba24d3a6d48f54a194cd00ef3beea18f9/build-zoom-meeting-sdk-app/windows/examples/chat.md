# Meeting Chat - Send and Receive Messages

## Overview

The Meeting SDK provides a rich chat API through `IMeetingChatController`. You can:
- Send messages to all participants or specific users
- Receive incoming chat messages
- Apply rich text formatting (bold, italic, links, colors)
- Handle file transfers
- Support threaded conversations

## Architecture

```
IMeetingService
    └── GetMeetingChatController() → IMeetingChatController
                                         ├── SetEvent(IMeetingChatCtrlEvent*)
                                         ├── GetChatMessageBuilder() → IChatMsgInfoBuilder
                                         ├── SendChatMsgTo(IChatMsgInfo*)
                                         └── GetChatStatus()
```

## Required Headers

```cpp
#include <meeting_service_interface.h>
#include <meeting_service_components/meeting_chat_interface.h>
```

## Step 1: Implement the Chat Event Listener

```cpp
// MeetingChatEventListener.h
#pragma once
#include <meeting_service_components/meeting_chat_interface.h>

class MeetingChatEventListener : public ZOOMSDK::IMeetingChatCtrlEvent {
public:
    MeetingChatEventListener() = default;
    virtual ~MeetingChatEventListener() = default;

    // Called when a new chat message arrives
    virtual void onChatMsgNotification(
        ZOOMSDK::IChatMsgInfo* chatMsg,
        const zchar_t* content
    ) override;

    // Called when chat privileges change
    virtual void onChatStatusChangedNotification(
        ZOOMSDK::ChatStatus* status
    ) override;

    // Called when a message is deleted
    virtual void onChatMsgDeleteNotification(
        const zchar_t* msgID,
        ZOOMSDK::SDKChatMessageDeleteType deleteBy
    ) override;

    // Called when a message is edited
    virtual void onChatMessageEditNotification(
        ZOOMSDK::IChatMsgInfo* chatMsg
    ) override;

    // Called when meeting chat sharing status changes
    virtual void onShareMeetingChatStatusChanged(bool isStart) override;

    // File transfer callbacks
    virtual void onFileSendStart(ZOOMSDK::ISDKFileSender* sender) override;
    virtual void onFileReceived(ZOOMSDK::ISDKFileReceiver* receiver) override;
    virtual void onFileTransferProgress(ZOOMSDK::SDKFileTransferInfo* info) override;
};
```

```cpp
// MeetingChatEventListener.cpp
#include "MeetingChatEventListener.h"
#include <iostream>

using namespace ZOOMSDK;

void MeetingChatEventListener::onChatMsgNotification(
    IChatMsgInfo* chatMsg,
    const zchar_t* content
) {
    if (chatMsg && content) {
        // Get sender information
        unsigned int senderId = chatMsg->GetSenderUserId();
        const zchar_t* senderName = chatMsg->GetSenderDisplayName();

        // Get message details
        const zchar_t* msgContent = chatMsg->GetContent();
        SDKChatMessageType msgType = chatMsg->GetChatMessageType();

        std::wcout << L"[Chat] " << senderName << L": " << msgContent << std::endl;

        // Check message type
        switch (msgType) {
            case SDKChatMessageType_To_All:
                std::cout << "  (sent to everyone)" << std::endl;
                break;
            case SDKChatMessageType_To_Individual:
                std::cout << "  (private message)" << std::endl;
                break;
            case SDKChatMessageType_To_WaitingRoomUsers:
                std::cout << "  (to waiting room)" << std::endl;
                break;
        }

        // Check if this is a threaded reply
        const zchar_t* threadId = chatMsg->GetThreadID();
        if (threadId && wcslen(threadId) > 0) {
            std::wcout << L"  Thread ID: " << threadId << std::endl;
        }
    }
}

void MeetingChatEventListener::onChatStatusChangedNotification(ChatStatus* status) {
    if (status) {
        std::cout << "Chat status changed" << std::endl;
        // Check what chat privileges are available
    }
}

void MeetingChatEventListener::onChatMsgDeleteNotification(
    const zchar_t* msgID,
    SDKChatMessageDeleteType deleteBy
) {
    std::wcout << L"Message deleted: " << msgID << std::endl;
    switch (deleteBy) {
        case SDKChatMessageDeleteType_By_Self:
            std::cout << "  (deleted by sender)" << std::endl;
            break;
        case SDKChatMessageDeleteType_By_Host:
            std::cout << "  (deleted by host)" << std::endl;
            break;
        case SDKChatMessageDeleteType_By_DLP:
            std::cout << "  (deleted by DLP policy)" << std::endl;
            break;
    }
}

void MeetingChatEventListener::onChatMessageEditNotification(IChatMsgInfo* chatMsg) {
    if (chatMsg) {
        std::wcout << L"Message edited: " << chatMsg->GetContent() << std::endl;
    }
}

void MeetingChatEventListener::onShareMeetingChatStatusChanged(bool isStart) {
    std::cout << "Share meeting chat: " << (isStart ? "started" : "stopped") << std::endl;
}

void MeetingChatEventListener::onFileSendStart(ISDKFileSender* sender) {
    std::cout << "File send started" << std::endl;
}

void MeetingChatEventListener::onFileReceived(ISDKFileReceiver* receiver) {
    std::cout << "File received" << std::endl;
}

void MeetingChatEventListener::onFileTransferProgress(SDKFileTransferInfo* info) {
    // Handle file transfer progress
}
```

## Step 2: Initialize Chat Controller

```cpp
// Global variables
IMeetingChatController* g_chatController = nullptr;
MeetingChatEventListener* g_chatListener = nullptr;

void initializeChat(IMeetingService* meetingService) {
    // Get the chat controller
    g_chatController = meetingService->GetMeetingChatController();
    if (!g_chatController) {
        std::cerr << "Failed to get chat controller" << std::endl;
        return;
    }

    // Create and set event listener
    g_chatListener = new MeetingChatEventListener();
    SDKError err = g_chatController->SetEvent(g_chatListener);
    if (err != SDKERR_SUCCESS) {
        std::cerr << "Failed to set chat event listener: " << err << std::endl;
        return;
    }

    std::cout << "Chat controller initialized" << std::endl;
}
```

## Step 3: Send Chat Messages

### Simple Text Message (To Everyone)

```cpp
void sendMessageToAll(const wchar_t* message) {
    if (!g_chatController) return;

    // Get the message builder
    IChatMsgInfoBuilder* builder = g_chatController->GetChatMessageBuilder();
    if (!builder) {
        std::cerr << "Failed to get message builder" << std::endl;
        return;
    }

    // Build the message
    builder->SetContent(message);
    builder->SetReceiver(0);  // 0 = everyone
    builder->SetMessageType(SDKChatMessageType_To_All);

    // Build and send
    IChatMsgInfo* msgInfo = builder->Build();
    if (msgInfo) {
        SDKError err = g_chatController->SendChatMsgTo(msgInfo);
        if (err == SDKERR_SUCCESS) {
            std::cout << "Message sent successfully" << std::endl;
        } else {
            std::cerr << "Failed to send message: " << err << std::endl;
        }
    }
}
```

### Private Message (To Specific User)

```cpp
void sendPrivateMessage(unsigned int userId, const wchar_t* message) {
    if (!g_chatController) return;

    IChatMsgInfoBuilder* builder = g_chatController->GetChatMessageBuilder();
    if (!builder) return;

    builder->SetContent(message);
    builder->SetReceiver(userId);  // Specific user ID
    builder->SetMessageType(SDKChatMessageType_To_Individual);

    IChatMsgInfo* msgInfo = builder->Build();
    if (msgInfo) {
        SDKError err = g_chatController->SendChatMsgTo(msgInfo);
        if (err == SDKERR_SUCCESS) {
            std::cout << "Private message sent" << std::endl;
        }
    }
}
```

### Rich Text Message with Formatting

```cpp
void sendFormattedMessage() {
    if (!g_chatController) return;

    IChatMsgInfoBuilder* builder = g_chatController->GetChatMessageBuilder();
    if (!builder) return;

    // Set content: "Hello, this is BOLD and this is italic"
    const wchar_t* content = L"Hello, this is BOLD and this is italic";
    builder->SetContent(content);
    builder->SetReceiver(0);
    builder->SetMessageType(SDKChatMessageType_To_All);

    // Apply bold to "BOLD" (positions 14-17, 0-indexed)
    builder->SetBold(14, 18);

    // Apply italic to "italic" (positions 32-37)
    builder->SetItalic(32, 38);

    // Build and send
    IChatMsgInfo* msgInfo = builder->Build();
    if (msgInfo) {
        g_chatController->SendChatMsgTo(msgInfo);
    }
}
```

### Message with Link

```cpp
void sendMessageWithLink() {
    if (!g_chatController) return;

    IChatMsgInfoBuilder* builder = g_chatController->GetChatMessageBuilder();
    if (!builder) return;

    // Set content with link text
    const wchar_t* content = L"Check out this website for more info";
    builder->SetContent(content);
    builder->SetReceiver(0);
    builder->SetMessageType(SDKChatMessageType_To_All);

    // Create link attributes
    InsertLinkAttrs linkAttrs;
    linkAttrs.insertLinkUrl = L"https://zoom.us";

    // Apply link to "this website" (positions 10-21)
    builder->SetInsertLink(linkAttrs, 10, 22);

    IChatMsgInfo* msgInfo = builder->Build();
    if (msgInfo) {
        g_chatController->SendChatMsgTo(msgInfo);
    }
}
```

### Threaded Reply

```cpp
void sendThreadedReply(const wchar_t* threadId, const wchar_t* message) {
    if (!g_chatController) return;

    IChatMsgInfoBuilder* builder = g_chatController->GetChatMessageBuilder();
    if (!builder) return;

    builder->SetContent(message);
    builder->SetReceiver(0);
    builder->SetMessageType(SDKChatMessageType_To_All);
    builder->SetThreadId(threadId);  // Reply to existing thread

    IChatMsgInfo* msgInfo = builder->Build();
    if (msgInfo) {
        g_chatController->SendChatMsgTo(msgInfo);
    }
}
```

## Complete Integration Example

```cpp
void onInMeeting(IMeetingService* meetingService) {
    // Initialize chat when in meeting
    initializeChat(meetingService);

    // Send a greeting
    sendMessageToAll(L"Hello everyone! Bot has joined the meeting.");
}

// Call from your meeting status callback
void MeetingServiceEventListener::onMeetingStatusChanged(
    MeetingStatus status,
    int iResult
) {
    if (status == MEETING_STATUS_INMEETING) {
        onInMeeting(g_meetingService);
    }
}
```

## IChatMsgInfoBuilder Methods Reference

| Method | Description |
|--------|-------------|
| `SetContent(const zchar_t*)` | Set message text content |
| `SetReceiver(unsigned int)` | Set recipient (0 = everyone) |
| `SetMessageType(SDKChatMessageType)` | Set message type (all, individual, waiting room) |
| `SetThreadId(const zchar_t*)` | Set thread ID for replies |
| `SetBold(start, end)` | Apply bold style |
| `SetItalic(start, end)` | Apply italic style |
| `SetUnderline(start, end)` | Apply underline style |
| `SetStrikethrough(start, end)` | Apply strikethrough style |
| `SetFontColor(FontColorAttrs, start, end)` | Set font color |
| `SetBackgroundColor(BackgroundColorAttrs, start, end)` | Set background color |
| `SetFontSize(FontSizeAttrs, start, end)` | Set font size |
| `SetInsertLink(InsertLinkAttrs, start, end)` | Insert hyperlink |
| `SetBulletedList(start, end)` | Apply bulleted list style |
| `SetNumberedList(start, end)` | Apply numbered list style |
| `SetQuotePosition(start, end)` | Apply quote style |
| `SetParagraph(ParagraphAttrs, start, end)` | Set paragraph style (H1, H2, H3) |
| `ClearStyles()` | Clear all styles |
| `Clear()` | Clear all properties |
| `Build()` | Build the IChatMsgInfo object |

## Chat Message Types

```cpp
enum SDKChatMessageType {
    SDKChatMessageType_To_None,              // Invalid
    SDKChatMessageType_To_All,               // To everyone
    SDKChatMessageType_To_Individual,        // Private message
    SDKChatMessageType_To_Individual_Panelist,  // Webinar panelist
    SDKChatMessageType_To_WaitingRoomUsers   // To waiting room
};
```

## Error Handling

```cpp
SDKError err = g_chatController->SendChatMsgTo(msgInfo);
switch (err) {
    case SDKERR_SUCCESS:
        std::cout << "Message sent" << std::endl;
        break;
    case SDKERR_INVALID_PARAMETER:
        std::cerr << "Invalid message parameters" << std::endl;
        break;
    case SDKERR_NO_PERMISSION:
        std::cerr << "No permission to send chat" << std::endl;
        break;
    case SDKERR_WRONG_USAGE:
        std::cerr << "Chat not available (not in meeting?)" << std::endl;
        break;
    default:
        std::cerr << "Failed to send: " << err << std::endl;
}
```

## Common Pitfalls

1. **Chat controller unavailable**: Must be in a meeting (`MEETING_STATUS_INMEETING`)
2. **Position indexing**: Style positions are 0-indexed and use character positions, not byte positions
3. **Unicode support**: Use `wchar_t*` and `std::wstring` for proper Unicode support
4. **Builder reuse**: The builder can be reused, but call `Clear()` between messages
5. **Thread ID**: When replying to a thread, get the thread ID from `IChatMsgInfo::GetThreadID()`
