# Cobrowse SDK - API Reference

SDK methods and events.

## Initialization

```javascript
const cobrowse = new ZoomCobrowse(config);
```

### Config Options

| Option | Type | Description |
|--------|------|-------------|
| `sdkKey` | string | Your SDK Key |
| `token` | string | JWT token |
| `features.annotations` | boolean | Enable annotations |
| `masking.selectors` | array | CSS selectors to mask |
| `byop.enabled` | boolean | Use custom PINs |
| `byop.pin` | string | Custom PIN value |

## Methods

### startSession()

Start a cobrowse session.

```javascript
const session = await cobrowse.startSession();
// Returns: { pin: string, sessionId: string }
```

### endSession()

End the current session.

```javascript
await cobrowse.endSession();
```

### pause()

Pause screen sharing.

```javascript
cobrowse.pause();
```

### resume()

Resume screen sharing.

```javascript
cobrowse.resume();
```

## Events

### sessionStarted

```javascript
cobrowse.on('sessionStarted', (session) => {
  // session.pin - PIN for agent to join
  // session.sessionId - Unique session ID
});
```

### agentJoined

```javascript
cobrowse.on('agentJoined', (agent) => {
  // agent.name - Agent display name
  // agent.userId - Agent user ID
});
```

### agentLeft

```javascript
cobrowse.on('agentLeft', (agent) => {
  // Agent disconnected
});
```

### sessionEnded

```javascript
cobrowse.on('sessionEnded', () => {
  // Session terminated
});
```

### error

```javascript
cobrowse.on('error', (error) => {
  // error.code - Error code
  // error.message - Error description
});
```

## Resources

- **SDK Reference**: https://developers.zoom.us/docs/cobrowse-sdk/sdk-reference/
