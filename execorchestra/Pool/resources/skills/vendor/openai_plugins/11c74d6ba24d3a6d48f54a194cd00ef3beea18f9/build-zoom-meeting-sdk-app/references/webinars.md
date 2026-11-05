# Meeting SDK - Webinars

Embed webinar experiences using Meeting SDK.

## Overview

Meeting SDK can join webinars, not just meetings. This guide covers webinar-specific features and considerations.

## Webinar vs Meeting

| Feature | Meeting | Webinar |
|---------|---------|---------|
| Max participants | 100-1000 | 500-50,000 |
| Participant roles | Host, co-host, participant | Host, panelist, attendee |
| Attendee video | Yes | No (view-only) |
| Attendee audio | Yes | Raise hand to unmute |
| Q&A | No | Yes |
| Registration | Optional | Common |
| Practice session | No | Yes |

## Joining Webinars

### Web SDK

```javascript
const client = ZoomMtgEmbedded.createClient();

await client.init({
  zoomAppRoot: document.getElementById('meetingSDKElement'),
  language: 'en-US',
});

// Join webinar (same as meeting)
await client.join({
  sdkKey: SDK_KEY,
  signature: signature,
  meetingNumber: webinarId,  // Webinar ID
  userName: 'Attendee Name',
  userEmail: 'attendee@example.com',  // Required for registration
  passWord: password,
  tk: registrantToken,  // If registration required
});
```

### Registration Token

If the webinar requires registration:

```javascript
// 1. Register via API first
const response = await axios.post(
  `https://api.zoom.us/v2/webinars/${webinarId}/registrants`,
  {
    email: 'attendee@example.com',
    first_name: 'John',
    last_name: 'Doe'
  },
  { headers: { 'Authorization': `Bearer ${accessToken}` }}
);

// 2. Get registrant token
const registrantToken = response.data.registrant_id;

// 3. Use token when joining
await client.join({
  // ... other params
  tk: registrantToken,
});
```

### Native SDKs (iOS/Android/Windows)

```swift
// iOS - Join webinar
let joinParam = ZoomSDKJoinWebinarParam()
joinParam.webinarNumber = webinarNumber
joinParam.userName = "Attendee"
joinParam.userEmail = "attendee@example.com"
joinParam.webinarPassword = password
joinParam.webinarToken = registrantToken  // If registered

meetingService.joinWebinar(with: joinParam)
```

```kotlin
// Android - Join webinar
val joinParams = JoinMeetingParams().apply {
    meetingNo = webinarId
    displayName = "Attendee"
    password = webinarPassword
}

// Webinar uses same joinMeeting API
meetingService.joinMeetingWithParams(context, joinParams, JoinMeetingOptions())
```

## Attendee vs Panelist

### Role Detection

```javascript
// Web SDK
client.on('user-updated', (payload) => {
  const { userId } = payload;
  const user = client.getUser(userId);

  // Check role
  if (user.isHost) {
    console.log('User is host');
  } else if (user.userRole === 'panelist') {
    console.log('User is panelist');
  } else {
    console.log('User is attendee');
  }
});
```

### Attendee Limitations

Attendees in webinars have restricted capabilities:

| Action | Attendee Can Do? |
|--------|------------------|
| View video | Yes |
| Send video | No |
| Listen to audio | Yes |
| Unmute self | No (must be promoted) |
| Send chat | To panelists/everyone (if enabled) |
| Ask Q&A | Yes |
| Raise hand | Yes |

## Q&A Feature

### Web SDK Q&A

```javascript
// Check if Q&A is enabled
const qaClient = client.getQAClient();
const isQAEnabled = qaClient.isQAEnabled();

// Ask a question
await qaClient.askQuestion('What is the pricing?', false);  // false = public

// Answer a question (panelist/host only)
await qaClient.answerQuestion(questionId, 'The pricing is...');

// Get all questions
const questions = qaClient.getAllQuestions();
questions.forEach(q => {
  console.log(`Q: ${q.text}`);
  console.log(`A: ${q.answerText || 'Unanswered'}`);
});

// Q&A events
client.on('question-created', (payload) => {
  console.log('New question:', payload.question.text);
});

client.on('answer-created', (payload) => {
  console.log('Answer:', payload.answer.text);
});
```

### Native SDK Q&A

```swift
// iOS
let qaController = meetingService.getWebinarQAController()

// Ask question
qaController?.askQuestion("What is the pricing?", isAnonymous: false)

// Get questions (host/panelist)
let questions = qaController?.getAllQuestionList()
```

## Raise Hand

### Web SDK

```javascript
// Raise hand
client.raiseHand();

// Lower hand
client.lowerHand();

// Check status
const myself = client.getCurrentUser();
console.log('Hand raised:', myself.bRaiseHand);

// Event
client.on('user-updated', (payload) => {
  if (payload.bRaiseHand !== undefined) {
    console.log(`${payload.userId} ${payload.bRaiseHand ? 'raised' : 'lowered'} hand`);
  }
});
```

### Native SDK

```swift
// iOS
let webinarController = meetingService.getWebinarController()
webinarController?.raiseHand()
webinarController?.lowerHand()
```

## Promote/Demote Attendees

Hosts can promote attendees to panelists:

```javascript
// Web SDK (host only)
const webinarClient = client.getWebinarClient();

// Promote to panelist (allows video/audio)
await webinarClient.promoteAttendee(userId);

// Demote back to attendee
await webinarClient.demoteAttendee(userId);

// Allow attendee to talk (temporary unmute)
await webinarClient.allowAttendeeTalk(userId);
await webinarClient.disallowAttendeeTalk(userId);
```

## Polling

### Web SDK Polling

```javascript
// Get polling client
const pollingClient = client.getPollingClient();

// Check if polling available
const isAvailable = pollingClient.isPollingEnabled();

// Submit poll answer (attendee)
await pollingClient.submitPollAnswer(pollId, [
  { questionId: 'q1', answerIds: ['a1'] }
]);

// Poll events
client.on('poll-started', (payload) => {
  console.log('Poll started:', payload.poll);
  displayPoll(payload.poll);
});

client.on('poll-ended', (payload) => {
  console.log('Poll ended');
});
```

## Practice Session

Before a webinar starts, hosts can run a practice session:

```javascript
// Detect practice session
client.on('meeting-status-changed', (payload) => {
  if (payload.status === 'practice') {
    console.log('In practice session - attendees cannot join yet');
  } else if (payload.status === 'webinar') {
    console.log('Webinar is live');
  }
});
```

## Chat in Webinars

Chat permissions differ in webinars:

```javascript
// Get chat privilege
const chatClient = client.getChatClient();
const privilege = chatClient.getPrivilege();

// privilege values:
// 1 = No one
// 2 = Host and panelists only
// 3 = Everyone publicly
// 4 = Everyone publicly and privately

// Send to panelists (attendee)
await chatClient.send('Question about pricing', /* to all panelists */);

// Send to everyone (if allowed)
await chatClient.sendToAll('Hello everyone!');
```

## Webinar-Specific Events

```javascript
// Web SDK events
client.on('webinar-invite', (payload) => {
  // Attendee invited to become panelist
});

client.on('webinar-depromote', (payload) => {
  // Demoted from panelist to attendee
});

client.on('webinar-allow-attendee-chat', (payload) => {
  // Chat permissions changed
});

client.on('webinar-attendee-status', (payload) => {
  // Attendee count updated
  console.log('Attendees:', payload.attendeeCount);
});
```

## Best Practices

### For Large Webinars

1. **Disable attendee video** - Already default for webinars
2. **Use Q&A instead of chat** - More organized for large audiences
3. **Pre-register attendees** - Better tracking and control
4. **Test with practice session** - Verify setup before going live

### UI Considerations

```javascript
// Adjust UI based on role
function setupUI(role) {
  if (role === 'attendee') {
    // Hide video controls (can't send video)
    hideElement('#videoControls');

    // Show Q&A and raise hand
    showElement('#qaPanel');
    showElement('#raiseHandButton');

    // Disable unmute (until promoted)
    disableElement('#unmuteButton');
  } else if (role === 'panelist' || role === 'host') {
    // Full controls
    showAllControls();
  }
}
```

## Resources

- **Webinar API**: https://developers.zoom.us/docs/api/rest/reference/zoom-api/methods/#tag/Webinars
- **Meeting SDK Webinar**: https://developers.zoom.us/docs/meeting-sdk/web/webinar/
- **Developer Forum**: https://devforum.zoom.us/
