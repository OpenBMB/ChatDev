# AI Companion in Meeting SDK

Control AI Companion features in embedded Zoom meetings.

## Overview

The Meeting SDK provides `InMeetingAICompanionController` to manage AI Companion features within meetings. This allows you to check status and available features.

**Important**: The Meeting SDK is for human use cases only. It does NOT support bots or AI notetakers. For bot/automated AI processing, use **rtms**.

## Availability

| Platform | Controller Available |
|----------|---------------------|
| Web | Limited (settings-based) |
| Android | ✅ `InMeetingAICompanionController` |
| iOS | ✅ `MobileRTCAICompanionController` |
| Windows | ✅ `IMeetingAICompanionController` |
| macOS | ✅ `ZoomSDKMeetingAICompanionController` |

## AI Companion Features

| Feature | Constant | Description |
|---------|----------|-------------|
| Query | `QUERY` | Ask AI Companion questions during meeting |
| Smart Summary | `SMART_SUMMARY` | Auto-generate meeting summary |
| Smart Recording | `SMART_RECORDING` | Highlight key moments in recording |

## Android

```java
import us.zoom.sdk.*;

// Get AI Companion controller
InMeetingService inMeetingService = ZoomSDK.getInstance().getInMeetingService();
InMeetingAICompanionController aiController = inMeetingService.getInMeetingAICompanionController();

// Check if AI Companion is enabled for this meeting
boolean isEnabled = aiController.isAICompanionEnabled();
Log.d("AICompanion", "Enabled: " + isEnabled);

// Get available features
List<AICompanionFeature> features = aiController.getAvailableFeatures();
for (AICompanionFeature feature : features) {
    Log.d("AICompanion", "Feature available: " + feature.name());
}

// Check specific feature
boolean hasSummary = aiController.isFeatureAvailable(AICompanionFeature.SMART_SUMMARY);
```

### AI Companion Events (Android)

```java
// Listen for AI Companion status changes
inMeetingService.addListener(new InMeetingServiceListener() {
    @Override
    public void onAICompanionActiveChanged(boolean isActive) {
        Log.d("AICompanion", "Active state changed: " + isActive);
    }

    @Override
    public void onAICompanionFeaturesChanged() {
        // Re-check available features
        List<AICompanionFeature> features = aiController.getAvailableFeatures();
    }
});
```

## iOS (Swift)

```swift
import MobileRTC

// Get AI Companion controller
guard let meetingService = MobileRTC.shared().getMeetingService(),
      let aiController = meetingService.getInMeetingAICompanionController() else {
    return
}

// Check if AI Companion is enabled
let isEnabled = aiController.isAICompanionEnabled()
print("AI Companion enabled: \(isEnabled)")

// Get available features
if let features = aiController.getAvailableFeatures() as? [MobileRTCAICompanionFeature] {
    for feature in features {
        print("Feature: \(feature.rawValue)")
    }
}

// Check specific feature
let hasSummary = aiController.isFeatureAvailable(.smartSummary)
```

### AI Companion Events (iOS)

```swift
// Implement delegate
class MeetingDelegate: NSObject, MobileRTCMeetingServiceDelegate {
    func onAICompanionActiveChanged(_ isActive: Bool) {
        print("AI Companion active: \(isActive)")
    }

    func onAICompanionFeaturesChanged() {
        // Refresh available features
    }
}
```

## Windows (C++)

```cpp
#include "zoom_sdk.h"

// Get AI Companion controller
IMeetingService* meetingService = SDKInterfaceWrap::GetInst().GetMeetingService();
IMeetingAICompanionController* aiController = meetingService->GetMeetingAICompanionController();

// Check status
bool isEnabled = aiController->IsAICompanionEnabled();

// Get features
IList<AICompanionFeature>* features = aiController->GetAvailableFeatures();
for (int i = 0; i < features->GetCount(); i++) {
    AICompanionFeature feature = features->GetItem(i);
    // Process feature
}
```

## macOS (Objective-C)

```objc
#import <ZoomSDK/ZoomSDK.h>

// Get AI Companion controller
ZoomSDKMeetingService *meetingService = [[ZoomSDK sharedSDK] getMeetingService];
ZoomSDKMeetingAICompanionController *aiController = [meetingService getAICompanionController];

// Check status
BOOL isEnabled = [aiController isAICompanionEnabled];
NSLog(@"AI Companion enabled: %d", isEnabled);

// Get features
NSArray *features = [aiController getAvailableFeatures];
for (NSNumber *feature in features) {
    NSLog(@"Feature: %@", feature);
}
```

## Web SDK

The Web SDK doesn't expose direct AI Companion controls. AI Companion behavior is determined by:
- Account settings
- Meeting settings
- Host controls

```javascript
// AI Companion features are controlled by meeting/account settings
// The Web SDK respects these settings automatically

// You can check meeting info for AI-related settings
ZoomMtg.getCurrentMeetingInfo(function(result) {
  console.log('Meeting info:', result);
});
```

## Use Cases

### Display AI Companion Status

```java
// Android: Show UI indicator based on AI Companion status
public void updateAICompanionUI() {
    InMeetingAICompanionController aiController = getAIController();

    if (aiController.isAICompanionEnabled()) {
        aiIndicator.setVisibility(View.VISIBLE);

        if (aiController.isFeatureAvailable(AICompanionFeature.SMART_SUMMARY)) {
            summaryBadge.setVisibility(View.VISIBLE);
        }
    } else {
        aiIndicator.setVisibility(View.GONE);
    }
}
```

### Inform Users About AI Features

```swift
// iOS: Show alert about AI features
func showAICompanionInfo() {
    guard let aiController = getAIController() else { return }

    var features: [String] = []

    if aiController.isFeatureAvailable(.smartSummary) {
        features.append("Meeting Summary")
    }
    if aiController.isFeatureAvailable(.smartRecording) {
        features.append("Smart Recording")
    }

    if !features.isEmpty {
        let message = "AI Companion features active: \(features.joined(separator: ", "))"
        showAlert(title: "AI Companion", message: message)
    }
}
```

## Limitations

| Limitation | Notes |
|------------|-------|
| No bot support | Meeting SDK is for human use only |
| Read-only | Cannot enable/disable features via SDK |
| Settings-dependent | Features depend on account/meeting settings |
| No transcript access | Use REST API or RTMS for transcripts |

## Related

- **[AI Companion Integration Use Case](../../general/use-cases/ai-companion-integration.md)** - Full integration guide
- **rtms** - For real-time transcript access
- **zoom-rest-api** - For meeting summaries and transcripts after meeting
