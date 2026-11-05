# Local Recording

## Overview

The Meeting SDK provides local recording capabilities through `IMeetingRecordingController`. Local recording saves meeting video/audio to the local disk as MP4 files. This is different from:

- **Cloud Recording** - Saved to Zoom's cloud storage
- **Raw Recording** - Direct access to raw frames (see [raw-video-capture.md](raw-video-capture.md))

## Architecture

```
IMeetingService
    └── GetMeetingRecordingController() → IMeetingRecordingController
                                              ├── SetEvent(IMeetingRecordingCtrlEvent*)
                                              ├── CanStartRecording(bool, unsigned int)
                                              ├── StartRecording(time_t&)
                                              ├── StopRecording()
                                              ├── RequestLocalRecordingPrivilege()
                                              └── IsSupportLocalRecording()
```

## Required Headers

```cpp
#include <meeting_service_interface.h>
#include <meeting_service_components/meeting_recording_interface.h>
#include <meeting_service_components/meeting_participants_ctrl_interface.h>
```

## Step 1: Implement the Recording Event Listener

```cpp
// MeetingRecordingCtrlEventListener.h
#pragma once
#include <meeting_service_components/meeting_recording_interface.h>
#include <functional>

class MeetingRecordingCtrlEventListener
    : public ZOOMSDK::IMeetingRecordingCtrlEvent {
public:
    using PermissionCallback = std::function<void()>;

    MeetingRecordingCtrlEventListener(PermissionCallback onPermissionGranted = nullptr);
    virtual ~MeetingRecordingCtrlEventListener() = default;

    // Local recording status changes
    virtual void onRecordingStatus(ZOOMSDK::RecordingStatus status) override;

    // Cloud recording status changes
    virtual void onCloudRecordingStatus(ZOOMSDK::RecordingStatus status) override;

    // Recording privilege changed (can now record or lost privilege)
    virtual void onRecordPrivilegeChanged(bool bCanRec) override;

    // Result of RequestLocalRecordingPrivilege()
    virtual void onLocalRecordingPrivilegeRequestStatus(
        ZOOMSDK::RequestLocalRecordingStatus status
    ) override;

    // Cloud recording permission request response
    virtual void onRequestCloudRecordingResponse(
        ZOOMSDK::RequestStartCloudRecordingStatus status
    ) override;

    // Host received a recording privilege request
    virtual void onLocalRecordingPrivilegeRequested(
        ZOOMSDK::IRequestLocalRecordingPrivilegeHandler* handler
    ) override;

    // Host received a cloud recording request
    virtual void onStartCloudRecordingRequested(
        ZOOMSDK::IRequestStartCloudRecordingHandler* handler
    ) override;

    // MP4 conversion completed
    virtual void onRecording2MP4Done(
        bool bsuccess,
        int iResult,
        const zchar_t* szPath
    ) override;

    // MP4 conversion progress
    virtual void onRecording2MP4Processing(int iPercentage) override;

    // Custom UI recording layout callback
    virtual void onCustomizedLocalRecordingSourceNotification(
        ZOOMSDK::ICustomizedLocalRecordingLayoutHelper* layout_helper
    ) override;

    // Cloud storage full warning
    virtual void onCloudRecordingStorageFull(time_t gracePeriodDate) override;

    // Smart recording request
    virtual void onEnableAndStartSmartRecordingRequested(
        ZOOMSDK::IRequestEnableAndStartSmartRecordingHandler* handler
    ) override;

    // Smart recording enable action
    virtual void onSmartRecordingEnableActionCallback(
        ZOOMSDK::ISmartRecordingEnableActionHandler* handler
    ) override;

private:
    PermissionCallback m_onPermissionGranted;
};
```

```cpp
// MeetingRecordingCtrlEventListener.cpp
#include "MeetingRecordingCtrlEventListener.h"
#include <iostream>

using namespace ZOOMSDK;

MeetingRecordingCtrlEventListener::MeetingRecordingCtrlEventListener(
    PermissionCallback onPermissionGranted
) : m_onPermissionGranted(onPermissionGranted) {}

void MeetingRecordingCtrlEventListener::onRecordingStatus(RecordingStatus status) {
    switch (status) {
        case Recording_Start:
            std::cout << "Recording started" << std::endl;
            break;
        case Recording_Stop:
            std::cout << "Recording stopped" << std::endl;
            break;
        case Recording_Pause:
            std::cout << "Recording paused" << std::endl;
            break;
        case Recording_Connecting:
            std::cout << "Recording connecting..." << std::endl;
            break;
        case Recording_DiskFull:
            std::cerr << "Recording stopped - disk full!" << std::endl;
            break;
        default:
            std::cout << "Recording status: " << status << std::endl;
    }
}

void MeetingRecordingCtrlEventListener::onCloudRecordingStatus(RecordingStatus status) {
    std::cout << "Cloud recording status: " << status << std::endl;
}

void MeetingRecordingCtrlEventListener::onRecordPrivilegeChanged(bool bCanRec) {
    std::cout << "Recording privilege: " << (bCanRec ? "GRANTED" : "REVOKED") << std::endl;
    if (bCanRec && m_onPermissionGranted) {
        m_onPermissionGranted();
    }
}

void MeetingRecordingCtrlEventListener::onLocalRecordingPrivilegeRequestStatus(
    RequestLocalRecordingStatus status
) {
    switch (status) {
        case LocalRecordingRequestStatus_Granted:
            std::cout << "Recording privilege request: GRANTED" << std::endl;
            break;
        case LocalRecordingRequestStatus_Denied:
            std::cout << "Recording privilege request: DENIED" << std::endl;
            break;
        case LocalRecordingRequestStatus_Timeout:
            std::cout << "Recording privilege request: TIMEOUT" << std::endl;
            break;
        default:
            std::cout << "Recording privilege request status: " << status << std::endl;
    }
}

void MeetingRecordingCtrlEventListener::onRequestCloudRecordingResponse(
    RequestStartCloudRecordingStatus status
) {
    std::cout << "Cloud recording request response: " << status << std::endl;
}

void MeetingRecordingCtrlEventListener::onLocalRecordingPrivilegeRequested(
    IRequestLocalRecordingPrivilegeHandler* handler
) {
    if (handler) {
        std::cout << "Recording privilege requested by user: "
                  << handler->GetRequesterId() << std::endl;

        // Auto-approve (or implement your logic)
        // handler->GrantLocalRecordingPrivilege();
        // handler->DenyLocalRecordingPrivilege();
    }
}

void MeetingRecordingCtrlEventListener::onStartCloudRecordingRequested(
    IRequestStartCloudRecordingHandler* handler
) {
    std::cout << "Cloud recording start requested" << std::endl;
}

void MeetingRecordingCtrlEventListener::onRecording2MP4Done(
    bool bsuccess,
    int iResult,
    const zchar_t* szPath
) {
    if (bsuccess) {
        std::wcout << L"Recording saved to: " << szPath << std::endl;
    } else {
        std::cerr << "Recording conversion failed with error: " << iResult << std::endl;
    }
}

void MeetingRecordingCtrlEventListener::onRecording2MP4Processing(int iPercentage) {
    std::cout << "Converting to MP4: " << iPercentage << "%" << std::endl;
}

void MeetingRecordingCtrlEventListener::onCustomizedLocalRecordingSourceNotification(
    ICustomizedLocalRecordingLayoutHelper* layout_helper
) {
    // Used for custom UI recording layout
}

void MeetingRecordingCtrlEventListener::onCloudRecordingStorageFull(time_t gracePeriodDate) {
    std::cerr << "Cloud recording storage full!" << std::endl;
}

void MeetingRecordingCtrlEventListener::onEnableAndStartSmartRecordingRequested(
    IRequestEnableAndStartSmartRecordingHandler* handler
) {
    // Smart recording feature request
}

void MeetingRecordingCtrlEventListener::onSmartRecordingEnableActionCallback(
    ISmartRecordingEnableActionHandler* handler
) {
    // Smart recording enable action
}
```

## Step 2: Initialize Recording Controller

```cpp
// Global variables
IMeetingRecordingController* g_recordController = nullptr;
MeetingRecordingCtrlEventListener* g_recordListener = nullptr;
IMeetingParticipantsController* g_participantsController = nullptr;

void initializeRecording(IMeetingService* meetingService) {
    // Get recording controller
    g_recordController = meetingService->GetMeetingRecordingController();
    if (!g_recordController) {
        std::cerr << "Failed to get recording controller" << std::endl;
        return;
    }

    // Get participants controller (needed for permission checks)
    g_participantsController = meetingService->GetMeetingParticipantsController();

    // Create and set event listener
    g_recordListener = new MeetingRecordingCtrlEventListener(
        []() {
            // Called when recording privilege is granted
            attemptToStartRecording();
        }
    );

    SDKError err = g_recordController->SetEvent(g_recordListener);
    if (err != SDKERR_SUCCESS) {
        std::cerr << "Failed to set recording listener: " << err << std::endl;
    }

    std::cout << "Recording controller initialized" << std::endl;
}
```

## Step 3: Check Recording Permission

```cpp
bool canStartRecording() {
    if (!g_recordController) return false;

    // Check if local recording is supported
    if (!g_recordController->IsSupportLocalRecording()) {
        std::cout << "Local recording not supported" << std::endl;
        return false;
    }

    // Check if we can start recording
    // false = local recording, 0 = current user
    SDKError err = g_recordController->CanStartRecording(false, 0);

    if (err == SDKERR_SUCCESS) {
        std::cout << "Can start recording" << std::endl;
        return true;
    } else if (err == SDKERR_NO_PERMISSION) {
        std::cout << "No recording permission - requesting..." << std::endl;

        // Request permission from host
        g_recordController->RequestLocalRecordingPrivilege();
        return false;
    } else {
        std::cerr << "Cannot start recording: " << err << std::endl;
        return false;
    }
}
```

## Step 4: Start/Stop Recording

### Start Local Recording

```cpp
void attemptToStartRecording() {
    if (!g_recordController) return;

    if (!canStartRecording()) {
        return;  // Permission request will trigger callback when granted
    }

    time_t startTime;
    SDKError err = g_recordController->StartRecording(startTime);

    if (err == SDKERR_SUCCESS) {
        std::cout << "Recording started at: " << startTime << std::endl;
    } else {
        std::cerr << "Failed to start recording: " << err << std::endl;
    }
}
```

### Stop Recording

```cpp
void stopRecording() {
    if (!g_recordController) return;

    SDKError err = g_recordController->StopRecording();

    if (err == SDKERR_SUCCESS) {
        std::cout << "Recording stopped" << std::endl;
        // Wait for onRecording2MP4Done callback for final file path
    } else {
        std::cerr << "Failed to stop recording: " << err << std::endl;
    }
}
```

### Pause/Resume Recording

```cpp
void pauseRecording() {
    if (!g_recordController) return;

    SDKError err = g_recordController->PauseRecording();
    if (err == SDKERR_SUCCESS) {
        std::cout << "Recording paused" << std::endl;
    }
}

void resumeRecording() {
    if (!g_recordController) return;

    SDKError err = g_recordController->ResumeRecording();
    if (err == SDKERR_SUCCESS) {
        std::cout << "Recording resumed" << std::endl;
    }
}
```

## Step 5: Handle Permission Flow

When you're not the host, you need to request recording permission:

```cpp
void onInMeeting(IMeetingService* meetingService) {
    initializeRecording(meetingService);

    // Check if we're the host
    IUserInfo* myInfo = g_participantsController->GetMySelfUser();
    if (myInfo && myInfo->IsHost()) {
        std::cout << "We are host - can record directly" << std::endl;
        attemptToStartRecording();
    } else {
        std::cout << "Not host - need to request permission" << std::endl;
        if (!canStartRecording()) {
            // Wait for onRecordPrivilegeChanged callback
        }
    }
}

void onIsHost() {
    std::cout << "Now host - can start recording" << std::endl;
    attemptToStartRecording();
}

void onIsCoHost() {
    std::cout << "Now co-host - checking recording permission" << std::endl;
    attemptToStartRecording();
}
```

## Step 6: Monitor Encoder Process (zTscoder.exe)

After `StopRecording()`, Zoom uses `zTscoder.exe` to convert the recording to MP4. You can monitor this process:

```cpp
#include <windows.h>
#include <tlhelp32.h>

bool encoderHasStarted = false;
bool encoderFinished = false;

bool IsProcessRunning(const std::wstring& processName) {
    PROCESSENTRY32 entry;
    entry.dwSize = sizeof(entry);

    HANDLE snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (snapshot == INVALID_HANDLE_VALUE) return false;

    if (!Process32First(snapshot, &entry)) {
        CloseHandle(snapshot);
        return false;
    }

    do {
        if (std::wstring(entry.szExeFile) == processName) {
            CloseHandle(snapshot);
            return true;
        }
    } while (Process32Next(snapshot, &entry));

    CloseHandle(snapshot);
    return false;
}

void monitorEncoder() {
    const std::wstring encoderProcess = L"zTscoder.exe";

    // Check if encoder started
    if (IsProcessRunning(encoderProcess)) {
        encoderHasStarted = true;
        std::cout << "Encoder is running..." << std::endl;
    }

    // Check if encoder finished
    if (encoderHasStarted && !IsProcessRunning(encoderProcess)) {
        encoderFinished = true;
        std::cout << "Encoder finished - recording ready" << std::endl;

        // Now you can upload/move the recording file
        uploadRecording();
    }
}
```

## Complete Integration Example

```cpp
// Message loop with encoder monitoring
int main() {
    LoadConfig();
    InitSDK();

    MSG msg;
    const std::wstring encoderProcess = L"zTscoder.exe";

    while (!g_exit && GetMessage(&msg, nullptr, 0, 0) != 0) {
        TranslateMessage(&msg);
        DispatchMessage(&msg);

        // Monitor encoder after recording stops
        if (IsProcessRunning(encoderProcess)) {
            encoderHasStarted = true;
        }
    }

    // Wait for encoder to finish before cleanup
    while (encoderHasStarted && !encoderFinished) {
        if (!IsProcessRunning(encoderProcess)) {
            encoderFinished = true;
            std::cout << "Recording conversion complete" << std::endl;

            // Upload or process the recording file
            processRecordingFile();
        }
        Sleep(1000);  // Check every second
    }

    // Cleanup
    if (meetingService) DestroyMeetingService(meetingService);
    if (authService) DestroyAuthService(authService);
    CleanUPSDK();

    return 0;
}
```

## Recording Status Values

```cpp
enum RecordingStatus {
    Recording_Start,       // Recording started
    Recording_Stop,        // Recording stopped
    Recording_DiskFull,    // Disk full error
    Recording_Pause,       // Recording paused
    Recording_Connecting   // Connecting to recording service
};
```

## Permission Request Status Values

```cpp
enum RequestLocalRecordingStatus {
    LocalRecordingRequestStatus_Granted,   // Request approved
    LocalRecordingRequestStatus_Denied,    // Request denied
    LocalRecordingRequestStatus_Timeout,   // Request timed out
    LocalRecordingRequestStatus_None       // No status
};
```

## Recording File Location

Local recordings are saved to the user's Zoom recordings folder:
- Default: `%USERPROFILE%\Documents\Zoom\`
- Meeting subfolder: `Meeting ID - Date/`

The exact path is provided in `onRecording2MP4Done()` callback.

## Error Handling

```cpp
SDKError err = g_recordController->StartRecording(startTime);
switch (err) {
    case SDKERR_SUCCESS:
        std::cout << "Recording started" << std::endl;
        break;
    case SDKERR_NO_PERMISSION:
        std::cerr << "No permission to record" << std::endl;
        g_recordController->RequestLocalRecordingPrivilege();
        break;
    case SDKERR_WRONG_USAGE:
        std::cerr << "Cannot record now (meeting not started?)" << std::endl;
        break;
    case SDKERR_SERVICE_FAILED:
        std::cerr << "Recording service failed" << std::endl;
        break;
    case SDKERR_NO_RECORDING_IN_PROGRESS:
        std::cerr << "No recording in progress" << std::endl;
        break;
    default:
        std::cerr << "Error: " << err << std::endl;
}
```

## Common Pitfalls

1. **Permission timing**: Must be in meeting (`MEETING_STATUS_INMEETING`) before checking permission
2. **Host vs participant**: Non-hosts need to request permission first
3. **Encoder wait**: After `StopRecording()`, must wait for `zTscoder.exe` to finish
4. **MP4 callback**: `onRecording2MP4Done()` requires `EnableLocalRecordingConvertProgressBarDialog(false)` before meeting starts
5. **Disk space**: Recording will stop if disk is full (monitor `Recording_DiskFull`)
6. **View mode**: For gallery view recording, call `SwitchToVideoWall()` before starting

## Gallery View Recording

To record gallery view instead of active speaker:

```cpp
void switchToGalleryView() {
    IMeetingUIController* uiController = g_meetingService->GetUIController();
    if (uiController) {
        SDKError err = uiController->SwitchToVideoWall();
        if (err != SDKERR_SUCCESS) {
            std::cerr << "Failed to switch to gallery view" << std::endl;
        }
    }
}

void switchToActiveSpeaker() {
    IMeetingUIController* uiController = g_meetingService->GetUIController();
    if (uiController) {
        uiController->SwitchToActiveSpeaker();
    }
}
```
