# Campaign and Entry Patterns

## Campaign-First Pattern (Recommended)

```html
<script data-apikey="YOUR_API_KEY" src="https://us01ccistatic.zoom.us/us01cci/web-sdk/zcc-sdk.js"></script>
<script>
window.addEventListener('zoomCampaignSdk:ready', () => {
  window.zoomCampaignSdk.show();
  window.zoomCampaignSdk.on('engagement_started', () => {
    console.log('engagement started');
  });
});
</script>
```

## Runtime User Context Refresh

```javascript
window.zoomCampaignSdkConfig = {
  env: 'us01',
  apikey: 'YOUR_API_KEY',
  firstName: 'Ada',
  email: 'ada@example.com'
};

window.addEventListener('zoomCampaignSdk:ready', async () => {
  if (window.zoomCampaignSdk.waitForReady) {
    await window.zoomCampaignSdk.waitForReady();
  }
  window.zoomCampaignSdk.updateUserContext();
});
```

## Entry ID Fallback Pattern

Use entry ID only when your flow requires pre-chat data collection that cannot be handled in campaign configuration.
