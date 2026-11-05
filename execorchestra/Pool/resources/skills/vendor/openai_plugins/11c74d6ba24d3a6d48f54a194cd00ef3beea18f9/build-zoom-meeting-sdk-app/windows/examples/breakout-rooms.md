# Breakout Rooms Example

## Overview

This guide shows how to manage breakout rooms in the Zoom Windows Meeting SDK. Breakout rooms functionality works with **both Default UI and Custom UI**.

---

## Understanding Breakout Room Roles

Breakout room functionality is controlled by **five distinct roles**. A user can have multiple roles simultaneously.

| Role | Interface | Capabilities |
|------|-----------|--------------|
| **Data** | `IBOData` | Read breakout room info, user assignments, names |
| **Admin** | `IBOAdmin` | Manage running BOs, receive help requests, assign users, broadcast |
| **Creator** | `IBOCreator` | Create/modify BOs, configure settings, preassign users |
| **Assistant** | `IBOAssistant` | Join any BO without assignment (minor role) |
| **Attendee** | `IBOAttendee` | Join assigned BO, request help from admin |

**Typical role combinations**:
- **Host**: Creator + Admin + Data
- **Co-host**: Admin + Data
- **Regular participant**: Attendee + Data

---

## Step 1: Set Up Role Listener

First, implement `IMeetingBOControllerEvent` to receive role assignment callbacks:

**BOControllerEventListener.h**:
```cpp
#pragma once
#include <windows.h>
#include <cstdint>
#include <meeting_service_components/meeting_breakout_rooms_interface_v2.h>
#include <iostream>

using namespace ZOOM_SDK_NAMESPACE;

class BOControllerEventListener : public IMeetingBOControllerEvent {
public:
    // Role assignment callbacks - store interface pointers when received
    void onHasCreatorRightsNotification(IBOCreator* pCreatorObj) override {
        std::cout << "[BO] Received CREATOR role" << std::endl;
        m_boCreator = pCreatorObj;
    }

    void onHasAdminRightsNotification(IBOAdmin* pAdminObj) override {
        std::cout << "[BO] Received ADMIN role" << std::endl;
        m_boAdmin = pAdminObj;
    }

    void onHasAttendeeRightsNotification(IBOAttendee* pAttendeeObj) override {
        std::cout << "[BO] Received ATTENDEE role" << std::endl;
        m_boAttendee = pAttendeeObj;
    }

    void onHasDataHelperRightsNotification(IBOData* pDataHelperObj) override {
        std::cout << "[BO] Received DATA role" << std::endl;
        m_boData = pDataHelperObj;
    }

    void onHasAssistantRightsNotification(IBOAssistant* pAssistantObj) override {
        std::cout << "[BO] Received ASSISTANT role" << std::endl;
        m_boAssistant = pAssistantObj;
    }

    // Role removal callbacks - clear interface pointers
    void onLostCreatorRightsNotification() override {
        std::cout << "[BO] Lost CREATOR role" << std::endl;
        m_boCreator = nullptr;
    }

    void onLostAdminRightsNotification() override {
        std::cout << "[BO] Lost ADMIN role" << std::endl;
        m_boAdmin = nullptr;
    }

    void onLostAttendeeRightsNotification() override {
        std::cout << "[BO] Lost ATTENDEE role" << std::endl;
        m_boAttendee = nullptr;
    }

    void onLostDataHelperRightsNotification() override {
        std::cout << "[BO] Lost DATA role" << std::endl;
        m_boData = nullptr;
    }

    void onLostAssistantRightsNotification() override {
        std::cout << "[BO] Lost ASSISTANT role" << std::endl;
        m_boAssistant = nullptr;
    }

    // BO status changes
    void onNewBroadcastMessageReceived(const zchar_t* strMsg, unsigned int nSenderID) override {
        std::wcout << L"[BO] Broadcast message: " << strMsg << std::endl;
    }

    void onBOStopCountDown(unsigned int nSeconds) override {
        std::cout << "[BO] Rooms closing in " << nSeconds << " seconds" << std::endl;
    }

    void onHostInviteReturnToMainSession(const zchar_t* strName, IReturnToMainSessionHandler* pHandler) override {
        std::wcout << L"[BO] Host inviting back to main session from: " << strName << std::endl;
    }

    void onBOStatusChanged(BO_STATUS eStatus) override {
        std::cout << "[BO] Status changed: " << eStatus << std::endl;
    }

    // Accessors for stored interfaces
    IBOCreator* GetCreator() { return m_boCreator; }
    IBOAdmin* GetAdmin() { return m_boAdmin; }
    IBOAttendee* GetAttendee() { return m_boAttendee; }
    IBOData* GetData() { return m_boData; }
    IBOAssistant* GetAssistant() { return m_boAssistant; }

private:
    IBOCreator* m_boCreator = nullptr;
    IBOAdmin* m_boAdmin = nullptr;
    IBOAttendee* m_boAttendee = nullptr;
    IBOData* m_boData = nullptr;
    IBOAssistant* m_boAssistant = nullptr;
};
```

**Register the listener**:
```cpp
void SetupBreakoutRoomListener() {
    IMeetingBOController* boController = meetingService->GetMeetingBOController();
    if (!boController) {
        std::cerr << "[BO] ERROR: Failed to get BO controller" << std::endl;
        return;
    }

    BOControllerEventListener* boListener = new BOControllerEventListener();
    boController->SetEvent(boListener);

    std::cout << "[BO] Breakout room listener registered" << std::endl;
}
```

---

## Step 2: Creator Role - Create & Configure Breakout Rooms

If you're the host, you'll receive the Creator role and can create rooms:

```cpp
void CreateBreakoutRooms(IBOCreator* creator) {
    if (!creator) {
        std::cerr << "[BO] ERROR: No creator role" << std::endl;
        return;
    }

    // Option A: Create single room
    bool success = creator->CreateBO(L"Discussion Room 1");
    std::cout << "[BO] Create room 1: " << (success ? "OK" : "FAILED") << std::endl;

    success = creator->CreateBO(L"Discussion Room 2");
    std::cout << "[BO] Create room 2: " << (success ? "OK" : "FAILED") << std::endl;

    // Option B: Batch create rooms
    IList<const zchar_t*>* roomNames = /* your list of names */;
    success = creator->CreateGroupBO(roomNames);
    std::cout << "[BO] Batch create: " << (success ? "OK" : "FAILED") << std::endl;
}
```

**Configure breakout room options**:
```cpp
void ConfigureBreakoutRooms(IBOCreator* creator) {
    if (!creator) return;

    BOOption option;

    // Timer settings
    option.IsBOTimerEnabled = true;
    option.timerDuration = 15;  // 15 minutes
    option.IsTimerAutoStopBOEnabled = true;  // Auto-close after timer

    // Countdown before closing
    option.countdown = BOStopCountdown_Seconds_60;  // 60 second warning

    // Participant permissions
    option.IsParticipantCanChooseBO = true;      // Participants can self-select room
    option.IsParticipantCanReturnToMainSessionAtAnyTime = true;
    option.IsAutoMoveAllAssignedParticipantsEnabled = true;

    // For webinars
    option.IsPanelistCanChooseBO = true;
    option.IsAttendeeCanChooseBO = true;
    option.IsAttendeeContained = true;

    // User limits per room
    option.IsUserConfigMaxRoomUserLimitsEnabled = true;
    option.nUserConfigMaxRoomUserLimits = 10;

    bool success = creator->SetBOOption(option);
    std::cout << "[BO] Configure options: " << (success ? "OK" : "FAILED") << std::endl;
}
```

**Preassign users to rooms** (before rooms start):
```cpp
void PreassignUser(IBOCreator* creator, IBOData* data, const zchar_t* userName, const zchar_t* roomName) {
    if (!creator || !data) return;

    // Find user ID
    IList<const zchar_t*>* unassignedUsers = data->GetUnassignedUserList();
    const zchar_t* userId = nullptr;

    for (int i = 0; i < unassignedUsers->GetCount(); i++) {
        const zchar_t* uid = unassignedUsers->GetItem(i);
        if (wcscmp(data->GetBOUserName(uid), userName) == 0) {
            userId = uid;
            break;
        }
    }

    if (!userId) {
        std::wcerr << L"[BO] User not found: " << userName << std::endl;
        return;
    }

    // Find room ID
    IList<const zchar_t*>* roomIds = data->GetBOMeetingIDList();
    const zchar_t* roomId = nullptr;

    for (int i = 0; i < roomIds->GetCount(); i++) {
        const zchar_t* rid = roomIds->GetItem(i);
        IBOMeeting* room = data->GetBOMeetingByID(rid);
        if (room && wcscmp(room->GetBOName(), roomName) == 0) {
            roomId = rid;
            break;
        }
    }

    if (!roomId) {
        std::wcerr << L"[BO] Room not found: " << roomName << std::endl;
        return;
    }

    // Assign user to room
    bool success = creator->AssignUserToBO(userId, roomId);
    std::wcout << L"[BO] Assign " << userName << L" to " << roomName << L": "
               << (success ? L"OK" : L"FAILED") << std::endl;
}
```

---

## Step 3: Admin Role - Manage Running Breakout Rooms

Once rooms are created, the Admin role manages them:

```cpp
void StartBreakoutRooms(IBOAdmin* admin) {
    if (!admin) {
        std::cerr << "[BO] ERROR: No admin role" << std::endl;
        return;
    }

    if (!admin->CanStartBO()) {
        std::cerr << "[BO] Cannot start BOs - check if rooms are created and users assigned" << std::endl;
        return;
    }

    bool success = admin->StartBO();
    std::cout << "[BO] Start rooms: " << (success ? "OK" : "FAILED") << std::endl;
}

void StopBreakoutRooms(IBOAdmin* admin) {
    if (!admin) return;

    bool success = admin->StopBO();
    std::cout << "[BO] Stop rooms: " << (success ? "OK" : "FAILED") << std::endl;
}
```

**Assign users to RUNNING rooms**:
```cpp
void AssignUserToRunningRoom(IBOAdmin* admin, const zchar_t* userId, const zchar_t* roomId) {
    if (!admin) return;

    bool success = admin->AssignNewUserToRunningBO(userId, roomId);
    std::cout << "[BO] Assign to running room: " << (success ? "OK" : "FAILED") << std::endl;
}

void SwitchUserRoom(IBOAdmin* admin, const zchar_t* userId, const zchar_t* newRoomId) {
    if (!admin) return;

    bool success = admin->SwitchAssignedUserToRunningBO(userId, newRoomId);
    std::cout << "[BO] Switch user room: " << (success ? "OK" : "FAILED") << std::endl;
}
```

**Broadcast message to all rooms**:
```cpp
void BroadcastMessage(IBOAdmin* admin, const wchar_t* message) {
    if (!admin) return;

    bool success = admin->BroadcastMessage(message);
    std::wcout << L"[BO] Broadcast: " << (success ? L"OK" : L"FAILED") << std::endl;
}
```

**Handle help requests**:
```cpp
class BOAdminEventListener : public IBOAdminEvent {
public:
    void onHelpRequestReceived(const zchar_t* strUserID) override {
        std::cout << "[BO] Help request from user: " << strUserID << std::endl;

        // Option 1: Join their room to help
        m_admin->JoinBOByUserRequest(strUserID);

        // Option 2: Ignore the request
        // m_admin->IgnoreUserHelpRequest(strUserID);
    }

    void onStartBOError(BOControllerError errCode) override {
        std::cerr << "[BO] Start error: " << errCode << std::endl;
    }

    void onBOEndTimerUpdated(int remaining, bool isTimesUpNotice) override {
        std::cout << "[BO] Timer: " << remaining << " seconds remaining" << std::endl;
    }

    void SetAdmin(IBOAdmin* admin) { m_admin = admin; }

private:
    IBOAdmin* m_admin = nullptr;
};
```

---

## Step 4: Data Role - Read Breakout Room Information

The Data role lets you read BO information:

```cpp
void ListBreakoutRooms(IBOData* data) {
    if (!data) return;

    IList<const zchar_t*>* roomIds = data->GetBOMeetingIDList();
    if (!roomIds) {
        std::cout << "[BO] No breakout rooms" << std::endl;
        return;
    }

    std::cout << "[BO] Found " << roomIds->GetCount() << " breakout rooms:" << std::endl;

    for (int i = 0; i < roomIds->GetCount(); i++) {
        const zchar_t* roomId = roomIds->GetItem(i);
        IBOMeeting* room = data->GetBOMeetingByID(roomId);

        if (room) {
            std::wcout << L"  Room: " << room->GetBOName() << std::endl;

            // List users in this room
            IList<const zchar_t*>* users = room->GetBOUserList();
            if (users) {
                for (int j = 0; j < users->GetCount(); j++) {
                    const zchar_t* userId = users->GetItem(j);
                    BO_USER_STATUS status = room->GetBOUserStatus(userId);
                    std::wcout << L"    - " << data->GetBOUserName(userId)
                               << L" (status: " << status << L")" << std::endl;
                }
            }
        }
    }
}

void ListUnassignedUsers(IBOData* data) {
    if (!data) return;

    IList<const zchar_t*>* unassigned = data->GetUnassignedUserList();
    if (!unassigned || unassigned->GetCount() == 0) {
        std::cout << "[BO] No unassigned users" << std::endl;
        return;
    }

    std::cout << "[BO] Unassigned users:" << std::endl;
    for (int i = 0; i < unassigned->GetCount(); i++) {
        const zchar_t* userId = unassigned->GetItem(i);
        std::wcout << L"  - " << data->GetBOUserName(userId);
        if (data->IsBOUserMyself(userId)) {
            std::wcout << L" (me)";
        }
        std::wcout << std::endl;
    }
}
```

**Listen for data updates**:
```cpp
class BODataEventListener : public IBODataEvent {
public:
    void onBOInfoUpdated(const zchar_t* strBOID) override {
        std::cout << "[BO] Room info updated: " << strBOID << std::endl;
    }

    void OnBOListInfoUpdated() override {
        std::cout << "[BO] Room list updated" << std::endl;
    }

    void onUnAssignedUserUpdated() override {
        std::cout << "[BO] Unassigned user list updated" << std::endl;
    }
};

// Register: data->SetEvent(new BODataEventListener());
```

---

## Step 5: Attendee Role - Join & Leave Breakout Rooms

As a regular participant:

```cpp
void JoinMyBreakoutRoom(IBOAttendee* attendee) {
    if (!attendee) {
        std::cerr << "[BO] ERROR: No attendee role" << std::endl;
        return;
    }

    // Get your assigned room name
    const zchar_t* roomName = attendee->GetBoName();
    std::wcout << L"[BO] Your assigned room: " << roomName << std::endl;

    // Join the room
    bool success = attendee->JoinBo();
    std::cout << "[BO] Join room: " << (success ? "OK" : "FAILED") << std::endl;
}

void LeaveBreakoutRoom(IBOAttendee* attendee) {
    if (!attendee) return;

    if (!attendee->IsCanReturnMainSession()) {
        std::cerr << "[BO] Cannot return to main session (disabled by host)" << std::endl;
        return;
    }

    bool success = attendee->LeaveBo();
    std::cout << "[BO] Leave room: " << (success ? "OK" : "FAILED") << std::endl;
}

void RequestHelpFromHost(IBOAttendee* attendee) {
    if (!attendee) return;

    // Only request help if host is NOT already in your room
    if (attendee->IsHostInThisBO()) {
        std::cout << "[BO] Host is already in this room" << std::endl;
        return;
    }

    bool success = attendee->RequestForHelp();
    std::cout << "[BO] Help request: " << (success ? "sent" : "FAILED") << std::endl;
}
```

---

## Step 6: Assistant Role - Join Any Room

Co-hosts typically get the Assistant role:

```cpp
void JoinAnyRoom(IBOAssistant* assistant, const zchar_t* roomId) {
    if (!assistant) return;

    bool success = assistant->JoinBO(roomId);
    std::cout << "[BO] Join room: " << (success ? "OK" : "FAILED") << std::endl;
}

void LeaveCurrentRoom(IBOAssistant* assistant) {
    if (!assistant) return;

    bool success = assistant->LeaveBO();
    std::cout << "[BO] Leave room: " << (success ? "OK" : "FAILED") << std::endl;
}
```

---

## Error Codes

| Code | Name | Description |
|------|------|-------------|
| 0 | `BOControllerError_NULL_POINTER` | BO controller is null - SDK not initialized |
| 1 | `BOControllerError_WRONG_CURRENT_STATUS` | Incorrect current status |
| 2 | `BOControllerError_TOKEN_NOT_READY` | Token is not ready |
| 3 | `BOControllerError_NO_PRIVILEGE` | No privilege to perform action |
| 4 | `BOControllerError_BO_LIST_IS_UPLOADING` | BO list is being uploaded |
| 5 | `BOControllerError_UPLOAD_FAIL` | BO list upload failed |
| 6 | `BOControllerError_NO_ONE_HAS_BEEN_ASSIGNED` | Cannot start - no users assigned |
| 100 | `BOControllerError_UNKNOWN` | Unknown error |

---

## Complete Workflow Example

```cpp
void OnInMeeting() {
    // Set up listener first
    SetupBreakoutRoomListener();

    // Wait for role callbacks...
}

void OnCreatorRoleReceived(IBOCreator* creator, IBOData* data) {
    // Step 1: Configure options
    ConfigureBreakoutRooms(creator);

    // Step 2: Create rooms
    creator->CreateBO(L"Team Alpha");
    creator->CreateBO(L"Team Beta");

    // Step 3: Wait for onCreateBOResponse callback...
}

void OnRoomsCreated(IBOCreator* creator, IBOData* data, IBOAdmin* admin) {
    // Step 4: Assign users
    PreassignUser(creator, data, L"John", L"Team Alpha");
    PreassignUser(creator, data, L"Jane", L"Team Beta");

    // Step 5: Start rooms
    StartBreakoutRooms(admin);
}

void OnAttendeeRoleReceived(IBOAttendee* attendee) {
    // As a participant, join your assigned room
    JoinMyBreakoutRoom(attendee);
}
```

---

## Related Documentation

- [Common Issues](../troubleshooting/common-issues.md) - Error code reference
- [Interface Methods](../references/interface-methods.md) - Complete interface reference
- [Custom UI Architecture](../concepts/custom-ui-architecture.md) - How UI works with breakout rooms

---

**Last Updated**: Based on Zoom Windows Meeting SDK v6.7.2.26830
