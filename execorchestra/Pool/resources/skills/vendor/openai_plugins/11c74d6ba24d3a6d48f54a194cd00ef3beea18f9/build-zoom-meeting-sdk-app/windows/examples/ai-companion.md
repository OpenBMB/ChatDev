# AI Companion Features: Smart Summary & Query

## Overview

The `IMeetingAICompanionController` provides Level 3 sub-helpers for AI-powered meeting features:

| Helper | Getter | Status | Purpose |
|--------|--------|--------|---------|
| `IMeetingSmartSummaryHelper` | `GetMeetingSmartSummaryHelper()` | **DEPRECATED** | Legacy smart summary API |
| `IMeetingAICompanionSmartSummaryHelper` | `GetMeetingAICompanionSmartSummaryHelper()` | Current | AI-powered meeting summaries |
| `IMeetingAICompanionQueryHelper` | `GetMeetingAICompanionQueryHelper()` | Current | AI Q&A about meeting content |

---

## Navigation Path

```
IMeetingService
  └─► GetMeetingAICompanionController()
        ├─► GetMeetingSmartSummaryHelper()              // DEPRECATED
        ├─► GetMeetingAICompanionSmartSummaryHelper()   // Smart Summary
        └─► GetMeetingAICompanionQueryHelper()          // AI Query/Q&A
```

---

## Prerequisites

AI Companion features require:
1. Feature enabled in Zoom account settings
2. Host privileges (for starting features)
3. Meeting in progress (`MEETING_STATUS_INMEETING`)

---

## 1. Smart Summary (IMeetingAICompanionSmartSummaryHelper)

AI-generated meeting summaries that capture key points, action items, and decisions.

### Get the Helper

```cpp
IMeetingAICompanionController* aiCtrl = meetingService->GetMeetingAICompanionController();
if (!aiCtrl) return;

IMeetingAICompanionSmartSummaryHelper* summaryHelper =
    aiCtrl->GetMeetingAICompanionSmartSummaryHelper();
if (!summaryHelper) return;
```

### Set Up Event Handler

```cpp
class SmartSummaryEventHandler : public IMeetingAICompanionSmartSummaryHelperEvent {
public:
    void onSmartSummaryStateNotSupported() override {
        // Meeting doesn't support smart summary
        // Account may not have the feature enabled
    }

    void onSmartSummaryStateSupportedButDisabled(
        IMeetingEnableSmartSummaryHandler* handler) override
    {
        // Feature supported but needs to be enabled
        if (handler) {
            if (handler->IsForRequest()) {
                // This is a request from another user
                // Host should decide whether to enable
            } else {
                // Current user can enable directly
                handler->EnableSmartSummary();
            }
        }
    }

    void onSmartSummaryStateEnabledButNotStarted(
        IMeetingStartSmartSummaryHandler* handler) override
    {
        // Feature enabled, ready to start
        if (handler) {
            if (handler->IsForRequest()) {
                // Request from another user to start
            } else {
                // Can start directly
                handler->StartSmartSummary();
            }
        }
    }

    void onSmartSummaryStateStarted(
        IMeetingStopSmartSummaryHandler* handler) override
    {
        // Smart summary is now active
        // handler is nullptr if current user can't stop it
        if (handler) {
            // Can stop if needed
            // handler->StopSmartSummary();
        }
    }

    void onFailedToStartSmartSummary(bool bTimeout) override {
        if (bTimeout) {
            // Request timed out
        } else {
            // Host/cohost declined the request
        }
    }

    void onSmartSummaryEnableRequestReceived(
        IMeetingApproveEnableSmartSummaryHandler* handler) override
    {
        // Another user requested to enable smart summary
        // Host/cohost receives this callback
        if (handler) {
            unsigned int requesterId = handler->GetSenderUserID();
            // Approve or handle the request
            handler->ContinueApprove();
        }
    }

    void onSmartSummaryStartRequestReceived(
        IMeetingApproveStartSmartSummaryHandler* handler) override
    {
        // Another user requested to start smart summary
        if (handler) {
            unsigned int requesterId = handler->GetSenderUserID();
            handler->Approve();  // or handler->Decline();
        }
    }

    void onSmartSummaryEnableActionCallback(
        IMeetingEnableSmartSummaryActionHandler* handler) override
    {
        // Confirmation dialog for enabling smart summary
        if (handler) {
            const zchar_t* title = handler->GetTipTitle();
            const zchar_t* tip = handler->GetTipString();
            // Show UI with tip, then:
            handler->Confirm();  // or handler->Cancel();
        }
    }
};

// Register the handler
SmartSummaryEventHandler summaryHandler;
summaryHelper->SetEvent(&summaryHandler);
```

---

## 2. AI Query (IMeetingAICompanionQueryHelper)

Ask questions about meeting content and get AI-generated answers.

### Get the Helper

```cpp
IMeetingAICompanionController* aiCtrl = meetingService->GetMeetingAICompanionController();
if (!aiCtrl) return;

IMeetingAICompanionQueryHelper* queryHelper =
    aiCtrl->GetMeetingAICompanionQueryHelper();
if (!queryHelper) return;
```

### Set Up Event Handler

```cpp
class AIQueryEventHandler : public IMeetingAICompanionQueryHelperEvent {
public:
    void onQueryStateNotSupported() override {
        // Meeting doesn't support AI query
    }

    void onQueryStateSupportedButDisabled(
        IMeetingEnableQueryHandler* pHandler) override
    {
        // Query supported but disabled
        if (pHandler && !pHandler->IsForRequest()) {
            pHandler->EnableQuery();
        }
    }

    void onQueryStateEnabledButNotStarted(
        IMeetingStartQueryHandler* pHandler) override
    {
        // Query enabled, ready to start
        if (pHandler && !pHandler->IsForRequest()) {
            pHandler->StartMeetingQuery();
        }
    }

    void onQueryStateStarted(IMeetingSendQueryHandler* pHandler) override {
        // Query is active - can now send questions
        if (pHandler) {
            // Get suggested questions
            IList<const zchar_t*>* defaultQuestions =
                pHandler->GetDefaultQueryQuestions();
            if (defaultQuestions) {
                for (int i = 0; i < defaultQuestions->GetCount(); i++) {
                    const zchar_t* question = defaultQuestions->GetItem(i);
                    // Display in UI
                }
            }

            // Check if we can send queries
            if (pHandler->CanSendQuery()) {
                // Send a question
                pHandler->SendQueryQuestion(L"What were the main action items?");
            } else {
                // Need to request privilege
                pHandler->RequestSendQueryPrivilege();
            }
        }
    }

    void onReceiveQueryAnswer(IMeetingAICompanionQueryItem* pQueryItem) override {
        // Received an answer to our question
        if (pQueryItem) {
            const zchar_t* queryId = pQueryItem->GetQueryID();
            const zchar_t* question = pQueryItem->GetQustionContent();
            const zchar_t* answer = pQueryItem->GetAnswerContent();
            time_t timestamp = pQueryItem->GetTimeStamp();

            MeetingAICompanionQueryRequestError errorCode = pQueryItem->GetErrorCode();
            if (errorCode == MeetingAICompanionQueryRequestError_OK) {
                // Display answer to user

                // Send feedback if user indicates quality
                // pQueryItem->Feedback(MeetingAICompanionQueryFeedbackType_Good);
                // or
                // pQueryItem->Feedback(MeetingAICompanionQueryFeedbackType_Bad);
            } else {
                // Handle error
                const zchar_t* errorMsg = pQueryItem->GetErrorMsg();
            }
        }
    }

    void onQuerySettingChanged(MeetingAICompanionQuerySettingOptions eSetting) override {
        // Query settings changed
        switch (eSetting) {
            case MeetingAICompanionQuerySettingOptions_WhenQueryStarted:
                // All can ask about discussions since AI started
                break;
            case MeetingAICompanionQuerySettingOptions_WhenParticipantsJoin:
                // Can ask about discussions since they joined
                break;
            case MeetingAICompanionQuerySettingOptions_OnlyHost:
                // Only host can ask questions
                break;
            // ... handle other settings
        }
    }

    void onFailedToStartQuery(bool bTimeout) override {
        if (bTimeout) {
            // Request timed out
        } else {
            // Request declined
        }
    }

    void onSendQueryPrivilegeChanged(bool canSendQuery) override {
        // Privilege to send queries changed
        if (canSendQuery) {
            // Can now send questions
        } else {
            // Lost ability to send questions
        }
    }

    void onFailedToRequestSendQuery(bool bTimeout) override {
        // Failed to get send query privilege
    }

    // ... other callbacks for request handling
    void onReceiveRequestToEnableQuery(
        IMeetingApproveEnableQueryHandler* pHandler) override {}
    void onReceiveRequestToStartQuery(
        IMeetingApproveStartQueryHandler* pHandler) override {}
    void onQueryEnableActionCallback(
        IMeetingEnableQueryActionHandler* pHandler) override {}
    void onReceiveRequestToSendQuery(
        IMeetingApproveSendQueryHandler* pHandler) override {}
};

// Register the handler
AIQueryEventHandler queryHandler;
queryHelper->SetEvent(&queryHandler);
```

### Change Query Settings (Host Only)

```cpp
bool canChange = false;
SDKError err = queryHelper->CanChangeQuerySetting(canChange);
if (err == SDKERR_SUCCESS && canChange) {
    // Set who can ask questions
    queryHelper->ChangeQuerySettings(
        MeetingAICompanionQuerySettingOptions_WhenParticipantsJoin);

    // Get current setting
    MeetingAICompanionQuerySettingOptions currentSetting =
        queryHelper->GetSelectedQuerySetting();
}
```

### Legal Notices

```cpp
bool isAvailable = false;
queryHelper->IsAICompanionQueryLegalNoticeAvailable(isAvailable);
if (isAvailable) {
    const zchar_t* prompt = queryHelper->GetAICompanionQueryLegalNoticesPrompt();
    const zchar_t* explained = queryHelper->GetAICompanionQueryLegalNoticesExplained();
    // Display legal notice to user
}
```

---

## 3. Controller-Level Operations

The main controller provides global AI Companion controls.

### Turn All AI Features On/Off

```cpp
IMeetingAICompanionController* aiCtrl = meetingService->GetMeetingAICompanionController();

// Check support
if (aiCtrl->IsTurnoffAllAICompanionsSupported()) {
    // Can turn off all AI features
    if (aiCtrl->CanTurnOffAllAICompanions()) {
        bool deleteAssets = false;  // Keep or delete meeting assets
        aiCtrl->TurnOffAllAICompanions(deleteAssets);
    }
}

if (aiCtrl->IsTurnOnAllAICompanionsSupported()) {
    // Can turn on all AI features
    if (aiCtrl->CanTurnOnAllAICompanions()) {
        aiCtrl->TurnOnAllAICompanions();
    }
}
```

### Request Host to Toggle AI Features

```cpp
// For non-host users
if (aiCtrl->CanRequestTurnoffAllAICompanions()) {
    aiCtrl->RequestTurnoffAllAICompanions();
}

if (aiCtrl->CanRequestTurnOnAllAICompanions()) {
    aiCtrl->RequestTurnOnAllAICompanions();
}
```

### Controller Event Handler

```cpp
class AICompanionCtrlEventHandler : public IMeetingAICompanionCtrlEvent {
public:
    void onAICompanionFeatureTurnOffByParticipant(
        IAICompanionFeatureTurnOnAgainHandler* handler) override
    {
        // Participant turned off AI feature before host joined
        if (handler) {
            IList<AICompanionFeature>* features = handler->GetFeatureList();
            IList<AICompanionFeature>* deletedAssets =
                handler->GetAssetsDeletedFeatureList();

            // Host can turn features back on
            handler->TurnOnAgain();
            // Or agree to keep them off
            // handler->AgreeTurnOff();
        }
    }

    void onAICompanionFeatureSwitchRequested(
        IAICompanionFeatureSwitchHandler* handler) override
    {
        // User requested to toggle AI features
        if (handler) {
            unsigned int requesterId = handler->GetRequestUserID();
            bool isTurningOn = handler->IsTurnOn();

            bool deleteAssets = false;
            handler->Agree(deleteAssets);
            // or handler->Decline();
        }
    }

    void onAICompanionFeatureSwitchRequestResponse(
        bool bTimeout, bool bAgree, bool bTurnOn) override
    {
        // Response to our request
        if (!bTimeout && bAgree) {
            // Request approved
        }
    }

    void onAICompanionFeatureCanNotBeTurnedOff(
        IList<AICompanionFeature>* features) override
    {
        // These features cannot be turned off
        if (features) {
            for (int i = 0; i < features->GetCount(); i++) {
                AICompanionFeature feature = features->GetItem(i);
                // Handle each feature
            }
        }
    }

    void onHostUnsupportedStopNotesRequest() override {
        // Host's client doesn't support stopping Notes
    }
};

// Register controller event handler
AICompanionCtrlEventHandler ctrlHandler;
aiCtrl->SetEvent(&ctrlHandler);
```

---

## Complete Example: Smart Summary Flow

```cpp
class SmartSummaryManager {
private:
    IMeetingAICompanionController* m_aiCtrl = nullptr;
    IMeetingAICompanionSmartSummaryHelper* m_summaryHelper = nullptr;

    class SummaryHandler : public IMeetingAICompanionSmartSummaryHelperEvent {
    public:
        SmartSummaryManager* m_manager = nullptr;

        void onSmartSummaryStateNotSupported() override {
            m_manager->OnFeatureNotSupported();
        }

        void onSmartSummaryStateSupportedButDisabled(
            IMeetingEnableSmartSummaryHandler* handler) override {
            if (handler && !handler->IsForRequest()) {
                handler->EnableSmartSummary();
            }
        }

        void onSmartSummaryStateEnabledButNotStarted(
            IMeetingStartSmartSummaryHandler* handler) override {
            if (handler && !handler->IsForRequest()) {
                handler->StartSmartSummary();
            }
        }

        void onSmartSummaryStateStarted(
            IMeetingStopSmartSummaryHandler* handler) override {
            m_manager->OnSummaryStarted(handler);
        }

        void onFailedToStartSmartSummary(bool bTimeout) override {
            m_manager->OnStartFailed(bTimeout);
        }

        void onSmartSummaryEnableRequestReceived(
            IMeetingApproveEnableSmartSummaryHandler* handler) override {
            if (handler) handler->ContinueApprove();
        }

        void onSmartSummaryStartRequestReceived(
            IMeetingApproveStartSmartSummaryHandler* handler) override {
            if (handler) handler->Approve();
        }

        void onSmartSummaryEnableActionCallback(
            IMeetingEnableSmartSummaryActionHandler* handler) override {
            if (handler) handler->Confirm();
        }
    };

    SummaryHandler m_handler;
    IMeetingStopSmartSummaryHandler* m_stopHandler = nullptr;

public:
    bool Initialize(IMeetingService* meetingService) {
        m_aiCtrl = meetingService->GetMeetingAICompanionController();
        if (!m_aiCtrl) return false;

        m_summaryHelper = m_aiCtrl->GetMeetingAICompanionSmartSummaryHelper();
        if (!m_summaryHelper) return false;

        m_handler.m_manager = this;
        m_summaryHelper->SetEvent(&m_handler);
        return true;
    }

    void OnFeatureNotSupported() {
        // Update UI - feature not available
    }

    void OnSummaryStarted(IMeetingStopSmartSummaryHandler* handler) {
        m_stopHandler = handler;
        // Update UI - summary is recording
    }

    void OnStartFailed(bool timeout) {
        // Show error message
    }

    void StopSummary() {
        if (m_stopHandler) {
            m_stopHandler->StopSmartSummary();
            m_stopHandler = nullptr;
        }
    }
};
```

---

## AI Companion Features Summary

| Feature | Description | Assets Generated |
|---------|-------------|------------------|
| `SMART_SUMMARY` | AI meeting summary | Summary document |
| `QUERY` | AI Q&A about meeting | Transcript |
| `SMART_RECORDING` | AI-enhanced recording | Recording with AI insights |

---

## Related Documentation

- [Singleton Hierarchy](../concepts/singleton-hierarchy.md) - Complete navigation map
- [SDK Architecture Pattern](../concepts/sdk-architecture-pattern.md) - Universal 3-step pattern
- [Captions & Transcription](captions-transcription.md) - Related live transcription features
