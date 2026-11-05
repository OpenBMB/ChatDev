# Command Channel

Complete working code for custom command messaging between participants.

**Official Sample**: `VSDK_CommandChannel` in [videosdk-windows-rawdata-sample](https://github.com/zoom/videosdk-windows-rawdata-sample)

---

## Overview

The command channel enables custom data exchange between participants. Use cases:
- Application-specific signaling
- Game state synchronization
- Custom control messages
- Real-time collaboration data

```
┌─────────────────────────────────────────────────────────────────┐
│                    COMMAND CHANNEL FLOW                         │
├─────────────────────────────────────────────────────────────────┤
│  Sender:                                                        │
│    getCmdChannel() → sendCommand() or sendCommandToAll()        │
│                                                                 │
│  Receiver:                                                      │
│    onCommandReceived(sender, command) callback                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Limitations

| Limit | Value |
|-------|-------|
| Max message rate | 60 messages/second |
| Max message size | ~1KB recommended |
| Reliability | Best effort (not guaranteed) |

**Note**: Commands are not persisted - late joiners won't receive previous commands.

---

## Complete Working Code

### CommandHandler.h

```cpp
#pragma once
#include <windows.h>
#include <string>
#include <functional>
#include "zoom_video_sdk_interface.h"

USING_ZOOM_VIDEO_SDK_NAMESPACE

class CommandHandler {
public:
    CommandHandler(IZoomVideoSDK* sdk);

    // Send commands
    bool SendToAll(const std::wstring& command);
    bool SendToUser(IZoomVideoSDKUser* user, const std::wstring& command);

    // Connection status
    bool IsConnected() const { return m_connected; }

    // Callbacks from delegate
    void OnCommandReceived(IZoomVideoSDKUser* sender, const zchar_t* command);
    void OnConnectResult(bool success);

    // Set message handler
    using MessageCallback = std::function<void(IZoomVideoSDKUser*, const std::wstring&)>;
    void SetMessageHandler(MessageCallback callback) { m_callback = callback; }

private:
    IZoomVideoSDK* m_sdk;
    IZoomVideoSDKCmdChannel* m_cmdChannel;
    bool m_connected;
    MessageCallback m_callback;
};
```

### CommandHandler.cpp

```cpp
#include "CommandHandler.h"
#include <iostream>

CommandHandler::CommandHandler(IZoomVideoSDK* sdk)
    : m_sdk(sdk)
    , m_cmdChannel(nullptr)
    , m_connected(false) {
}

bool CommandHandler::SendToAll(const std::wstring& command) {
    if (!m_cmdChannel) {
        m_cmdChannel = m_sdk->getCmdChannel();
    }

    if (!m_cmdChannel) {
        std::cout << "Command channel not available" << std::endl;
        return false;
    }

    ZoomVideoSDKErrors err = m_cmdChannel->sendCommand(nullptr, command.c_str());
    if (err == ZoomVideoSDKErrors_Success) {
        std::wcout << L"Sent to all: " << command << std::endl;
        return true;
    }

    std::cout << "Send failed: " << err << std::endl;
    return false;
}

bool CommandHandler::SendToUser(IZoomVideoSDKUser* user, const std::wstring& command) {
    if (!user) return false;

    if (!m_cmdChannel) {
        m_cmdChannel = m_sdk->getCmdChannel();
    }

    if (!m_cmdChannel) {
        return false;
    }

    ZoomVideoSDKErrors err = m_cmdChannel->sendCommand(user, command.c_str());
    if (err == ZoomVideoSDKErrors_Success) {
        std::wcout << L"Sent to " << user->getUserName()
                   << L": " << command << std::endl;
        return true;
    }

    std::cout << "Send failed: " << err << std::endl;
    return false;
}

void CommandHandler::OnCommandReceived(IZoomVideoSDKUser* sender, const zchar_t* command) {
    if (!sender || !command) return;

    std::wstring cmdStr(command);
    std::wcout << L"Command from " << sender->getUserName()
               << L": " << cmdStr << std::endl;

    // Call user handler if set
    if (m_callback) {
        m_callback(sender, cmdStr);
    }
}

void CommandHandler::OnConnectResult(bool success) {
    m_connected = success;
    std::cout << "Command channel " << (success ? "connected" : "failed") << std::endl;
}
```

### Using in Delegate

```cpp
class MyDelegate : public IZoomVideoSDKDelegate {
private:
    CommandHandler* m_cmdHandler;

public:
    MyDelegate(IZoomVideoSDK* sdk) {
        m_cmdHandler = new CommandHandler(sdk);

        // Set message handler
        m_cmdHandler->SetMessageHandler([this](IZoomVideoSDKUser* sender,
                                                const std::wstring& cmd) {
            HandleCommand(sender, cmd);
        });
    }

    void onSessionJoin() override {
        // Send hello to all participants
        m_cmdHandler->SendToAll(L"hello");
    }

    void onCommandReceived(IZoomVideoSDKUser* sender, const zchar_t* strCmd) override {
        m_cmdHandler->OnCommandReceived(sender, strCmd);
    }

    void onCommandChannelConnectResult(bool isSuccess) override {
        m_cmdHandler->OnConnectResult(isSuccess);
    }

private:
    void HandleCommand(IZoomVideoSDKUser* sender, const std::wstring& cmd) {
        // Parse and handle commands
        if (cmd == L"ping") {
            m_cmdHandler->SendToUser(sender, L"pong");
        }
        else if (cmd.find(L"action:") == 0) {
            // Handle action command
            std::wstring action = cmd.substr(7);
            ProcessAction(action);
        }
    }

    void ProcessAction(const std::wstring& action) {
        std::wcout << L"Processing action: " << action << std::endl;
    }
};
```

---

## JSON Command Pattern

For structured data, use JSON encoding:

```cpp
#include <json/json.h>

// Send JSON command
void SendJsonCommand(CommandHandler* handler, const std::string& type,
                     const Json::Value& data) {
    Json::Value root;
    root["type"] = type;
    root["data"] = data;

    Json::StreamWriterBuilder builder;
    std::string jsonStr = Json::writeString(builder, root);
    std::wstring wideStr(jsonStr.begin(), jsonStr.end());

    handler->SendToAll(wideStr);
}

// Receive and parse JSON
void HandleJsonCommand(const std::wstring& cmd) {
    std::string narrowStr(cmd.begin(), cmd.end());

    Json::Value root;
    Json::CharReaderBuilder builder;
    std::istringstream stream(narrowStr);

    if (Json::parseFromStream(builder, stream, &root, nullptr)) {
        std::string type = root["type"].asString();
        Json::Value data = root["data"];

        if (type == "position") {
            int x = data["x"].asInt();
            int y = data["y"].asInt();
            // Handle position update
        }
    }
}

// Usage
Json::Value posData;
posData["x"] = 100;
posData["y"] = 200;
SendJsonCommand(cmdHandler, "position", posData);
```

---

## IZoomVideoSDKCmdChannel Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `sendCommand(user, cmd)` | `ZoomVideoSDKErrors` | Send to specific user (NULL = all) |

---

## Rate Limiting

The command channel is limited to **60 messages/second**:

```cpp
class RateLimitedSender {
    std::chrono::steady_clock::time_point m_lastSend;
    static const int MIN_INTERVAL_MS = 17;  // ~60/sec

public:
    bool SendWithRateLimit(CommandHandler* handler, const std::wstring& cmd) {
        auto now = std::chrono::steady_clock::now();
        auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(
            now - m_lastSend).count();

        if (elapsed < MIN_INTERVAL_MS) {
            std::this_thread::sleep_for(
                std::chrono::milliseconds(MIN_INTERVAL_MS - elapsed));
        }

        m_lastSend = std::chrono::steady_clock::now();
        return handler->SendToAll(cmd);
    }
};
```

---

## Common Issues

### Commands Not Received

**Cause**: Channel not connected

**Fix**: Wait for `onCommandChannelConnectResult(true)`:
```cpp
void onCommandChannelConnectResult(bool isSuccess) override {
    if (isSuccess) {
        // Now safe to send commands
    }
}
```

### Error 8 (Too Frequent)

**Cause**: Exceeding 60 messages/second limit

**Fix**: Add rate limiting (see above)

### Unicode Issues

**Cause**: Encoding mismatch

**Fix**: Use `std::wstring` consistently:
```cpp
m_cmdChannel->sendCommand(user, L"message");  // Wide string literal
```

---

## Related Documentation

- [Session Join Pattern](session-join-pattern.md) - Session setup
- [Delegate Methods](../references/delegate-methods.md) - Command callbacks
- [API Reference](../references/windows-reference.md) - Method signatures
