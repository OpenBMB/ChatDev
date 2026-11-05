# Command Channel

Complete working code for custom command messaging between participants on Linux.

**Official Sample**: [videosdk-linux-raw-recording-sample](https://github.com/zoom/videosdk-linux-raw-recording-sample)

---

## Overview

The command channel enables custom data exchange between participants within the same session. Use cases:
- Application-specific signaling
- Session transfer / waiting room coordination
- Real-time collaboration data
- Custom control messages

```
+-------------------------------------------------------------------+
|                    COMMAND CHANNEL FLOW (Linux)                    |
+-------------------------------------------------------------------+
|  Sender:                                                          |
|    getCmdChannel() -> sendCommand(nullptr, msg) [broadcast]       |
|    getCmdChannel() -> sendCommand(user, msg)    [targeted]        |
|                                                                   |
|  Receiver:                                                        |
|    onCommandReceived(sender, command) callback                    |
|                                                                   |
|  IMPORTANT: Command channel is SESSION-SCOPED.                    |
|  It does NOT span across different sessions.                      |
+-------------------------------------------------------------------+
```

**Key differences from Windows**: On Linux, strings are `const char*` (UTF-8), not `const wchar_t*` (wide strings). See [Windows Command Channel](../../windows/examples/command-channel.md) for comparison.

---

## Limitations

| Limit | Value |
|-------|-------|
| Max message rate | 60 messages/second |
| Max message size | ~1KB recommended |
| Reliability | Best effort (not guaranteed) |
| Scope | Same session only |

**Note**: Commands are not persisted - late joiners won't receive previous commands.

---

## Threading Requirement

ALL SDK calls — including `getCmdChannel()` and `sendCommand()` — must be made from the GLib main thread. Calling SDK methods from a `std::thread` or any background thread returns `ZoomVideoSDKErrors_Internal_Error` (error code 2).

Use `g_idle_add()` to schedule SDK calls from background threads. See [Common Issues](../troubleshooting/common-issues.md) for details.

---

## Complete Working Code

### CommandHandler.h

```cpp
#ifndef COMMAND_HANDLER_H
#define COMMAND_HANDLER_H

#include "zoom_video_sdk_api.h"
#include "zoom_video_sdk_interface.h"
#include <glib.h>
#include <string>
#include <functional>

USING_ZOOM_VIDEO_SDK_NAMESPACE

class CommandHandler {
public:
    CommandHandler(IZoomVideoSDK* sdk);

    // Send commands (MUST be called from GLib main thread)
    bool SendToAll(const std::string& command);
    bool SendToUser(IZoomVideoSDKUser* user, const std::string& command);

    // Schedule send from a background thread (thread-safe)
    void SendToAllFromBackground(const std::string& command);

    // Connection status
    bool IsConnected() const { return m_connected; }

    // Callbacks from delegate
    void OnCommandReceived(IZoomVideoSDKUser* sender, const char* command);
    void OnConnectResult(bool success);

    // Set message handler
    using MessageCallback = std::function<void(IZoomVideoSDKUser*, const std::string&)>;
    void SetMessageHandler(MessageCallback callback) { m_callback = callback; }

private:
    IZoomVideoSDK* m_sdk;
    IZoomVideoSDKCmdChannel* m_cmdChannel;
    bool m_connected;
    MessageCallback m_callback;
};

#endif // COMMAND_HANDLER_H
```

### CommandHandler.cpp

```cpp
#include "CommandHandler.h"
#include <cstdio>

// Context struct for g_idle_add() — used to schedule SDK calls from background threads
struct SendCmdContext {
    IZoomVideoSDK* sdk;
    std::string cmd;
};

// Runs on the GLib main thread — safe to call SDK methods here
static gboolean sendCommandOnMainThread(gpointer data) {
    auto* ctx = static_cast<SendCmdContext*>(data);
    IZoomVideoSDKCmdChannel* ch = ctx->sdk->getCmdChannel();
    if (ch) {
        ZoomVideoSDKErrors err = ch->sendCommand(nullptr, ctx->cmd.c_str());
        if (err != ZoomVideoSDKErrors_Success) {
            printf("[CMD] Send failed: %d\n", err);
        }
    }
    delete ctx;
    return G_SOURCE_REMOVE;  // One-shot — do not repeat
}

CommandHandler::CommandHandler(IZoomVideoSDK* sdk)
    : m_sdk(sdk)
    , m_cmdChannel(nullptr)
    , m_connected(false) {
}

bool CommandHandler::SendToAll(const std::string& command) {
    if (!m_cmdChannel) {
        m_cmdChannel = m_sdk->getCmdChannel();
    }

    if (!m_cmdChannel) {
        printf("[CMD] Command channel not available\n");
        return false;
    }

    ZoomVideoSDKErrors err = m_cmdChannel->sendCommand(nullptr, command.c_str());
    if (err == ZoomVideoSDKErrors_Success) {
        printf("[CMD] Sent to all: %s\n", command.c_str());
        return true;
    }

    printf("[CMD] Send failed: %d\n", err);
    return false;
}

bool CommandHandler::SendToUser(IZoomVideoSDKUser* user, const std::string& command) {
    if (!user) return false;

    if (!m_cmdChannel) {
        m_cmdChannel = m_sdk->getCmdChannel();
    }

    if (!m_cmdChannel) {
        return false;
    }

    ZoomVideoSDKErrors err = m_cmdChannel->sendCommand(user, command.c_str());
    if (err == ZoomVideoSDKErrors_Success) {
        printf("[CMD] Sent to %s: %s\n", user->getUserName(), command.c_str());
        return true;
    }

    printf("[CMD] Send failed: %d\n", err);
    return false;
}

void CommandHandler::SendToAllFromBackground(const std::string& command) {
    // Thread-safe: g_idle_add queues work onto the GLib main loop
    auto* ctx = new SendCmdContext{m_sdk, command};
    g_idle_add(sendCommandOnMainThread, ctx);
}

void CommandHandler::OnCommandReceived(IZoomVideoSDKUser* sender, const char* command) {
    if (!sender || !command) return;

    std::string cmdStr(command);
    printf("[CMD] From %s: %s\n", sender->getUserName(), cmdStr.c_str());

    if (m_callback) {
        m_callback(sender, cmdStr);
    }
}

void CommandHandler::OnConnectResult(bool success) {
    m_connected = success;
    printf("[CMD] Command channel %s\n", success ? "connected" : "failed");
}
```

### Using in Delegate

```cpp
class BotDelegate : public IZoomVideoSDKDelegate {
private:
    CommandHandler* m_cmdHandler;

public:
    BotDelegate(IZoomVideoSDK* sdk) {
        m_cmdHandler = new CommandHandler(sdk);

        m_cmdHandler->SetMessageHandler([this](IZoomVideoSDKUser* sender,
                                                const std::string& cmd) {
            HandleCommand(sender, cmd);
        });
    }

    void onCommandChannelConnectResult(bool isSuccess) override {
        m_cmdHandler->OnConnectResult(isSuccess);
        if (isSuccess) {
            // Channel ready — safe to send commands now
            m_cmdHandler->SendToAll("{\"type\":\"hello\"}");
        }
    }

    void onCommandReceived(IZoomVideoSDKUser* sender, const zchar_t* strCmd) override {
        m_cmdHandler->OnCommandReceived(sender, strCmd);
    }

    // ... other delegate methods ...

private:
    void HandleCommand(IZoomVideoSDKUser* sender, const std::string& cmd) {
        // Parse JSON commands
        if (cmd.find("\"type\":\"ping\"") != std::string::npos) {
            m_cmdHandler->SendToUser(sender, "{\"type\":\"pong\"}");
        }
    }
};
```

---

## Sending from a Background Thread

If you need to trigger a command from a polling thread, HTTP handler, or any non-main thread, use `SendToAllFromBackground()` which internally uses `g_idle_add()`:

```cpp
// From a background polling thread:
void pollingThread(CommandHandler* cmdHandler) {
    while (running) {
        std::string data = fetchDataFromServer();
        if (!data.empty()) {
            // Thread-safe — schedules on GLib main thread
            cmdHandler->SendToAllFromBackground(data);
        }
        std::this_thread::sleep_for(std::chrono::seconds(3));
    }
}
```

**Do NOT call `sendCommand()` directly from background threads** — it returns error code 2 (`Internal_Error`).

---

## Command Channel Lifecycle

1. Call `joinSession()` — the command channel connects automatically
2. `onCommandChannelConnectResult(true)` fires when ready
3. Send commands with `sendCommand(nullptr, msg)` (broadcast) or `sendCommand(user, msg)` (targeted)
4. Receive commands via `onCommandReceived(sender, command)` callback
5. Channel disconnects when you leave the session

**Session-scoped**: The command channel only works between participants in the same session. It does NOT span across different sessions.

---

## Common Issues

### Commands Not Received

**Cause**: Channel not connected yet

**Fix**: Wait for `onCommandChannelConnectResult(true)` before sending:
```cpp
void onCommandChannelConnectResult(bool isSuccess) override {
    if (isSuccess) {
        // NOW safe to send commands
    }
}
```

### Error 2 (Internal_Error) on sendCommand

**Cause**: Calling SDK from a background thread

**Fix**: Use `g_idle_add()` to schedule on the GLib main thread (see SendToAllFromBackground above).

### Targeted Send Fails

**Cause**: User pointer may be stale if user disconnected

**Fix**: Use broadcast (`sendCommand(nullptr, msg)`) which is more reliable:
```cpp
// More reliable — broadcast to all
cmdChannel->sendCommand(nullptr, msg.c_str());

// Risky — user pointer may be stale
cmdChannel->sendCommand(userPtr, msg.c_str());
```

---

## Related Documentation

- [Session Join Pattern](session-join-pattern.md) - Session setup with GLib main loop
- [Common Issues](../troubleshooting/common-issues.md) - Threading and GLib requirements
- [Windows Command Channel](../../windows/examples/command-channel.md) - Windows equivalent (uses wchar_t)
- [Web Command Channel](../../web/examples/command-channel.md) - Web SDK equivalent
- [Authorization](../../references/authorization.md) - JWT roleType for host/co-host
