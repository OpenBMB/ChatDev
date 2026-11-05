# Cobrowse SDK - Features

Annotations, masking, and advanced features.

## Overview

Cobrowse SDK includes features for privacy, collaboration, and customization.

## Annotations

Agents can draw and highlight on the shared screen.

### Enable Annotations

```javascript
const cobrowse = new ZoomCobrowse({
  sdkKey: SDK_KEY,
  token: token,
  features: {
    annotations: true
  }
});
```

### Annotation Tools

| Tool | Description |
|------|-------------|
| Pointer | Highlight cursor position |
| Draw | Freehand drawing |
| Highlight | Transparent highlight |
| Arrow | Point to elements |

## Privacy Masking

Hide sensitive information from agents.

### Mask Elements

```html
<!-- Add data attribute to sensitive fields -->
<input type="text" data-cobrowse-mask="true" placeholder="SSN" />
<input type="password" data-cobrowse-mask="true" />
<div data-cobrowse-mask="true">Sensitive content</div>
```

### Mask by CSS Selector

```javascript
const cobrowse = new ZoomCobrowse({
  sdkKey: SDK_KEY,
  token: token,
  masking: {
    selectors: [
      '.sensitive-data',
      '#credit-card-field',
      '[data-private]'
    ]
  }
});
```

## Bring Your Own PIN (BYOP)

Use your own PIN system instead of Zoom-generated PINs.

```javascript
const cobrowse = new ZoomCobrowse({
  sdkKey: SDK_KEY,
  token: token,
  byop: {
    enabled: true,
    pin: 'YOUR_CUSTOM_PIN'
  }
});
```

## Session Control

### End Session

```javascript
cobrowse.endSession();
```

### Pause/Resume

```javascript
cobrowse.pause();
cobrowse.resume();
```

### Events

```javascript
cobrowse.on('sessionStarted', (session) => {
  console.log('Session started:', session.pin);
});

cobrowse.on('agentJoined', (agent) => {
  console.log('Agent joined:', agent.name);
});

cobrowse.on('sessionEnded', () => {
  console.log('Session ended');
});
```

## Resources

- **Features docs**: https://developers.zoom.us/docs/cobrowse-sdk/add-features/
