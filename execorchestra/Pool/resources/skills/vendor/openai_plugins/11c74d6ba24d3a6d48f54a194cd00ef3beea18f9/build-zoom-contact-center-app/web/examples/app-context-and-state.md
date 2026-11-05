# Web Example: Engagement-Aware State

```javascript
await zoomSdk.config({
  version: "0.16.0",
  capabilities: [
    "getRunningContext",
    "getEngagementContext",
    "getEngagementStatus",
    "onEngagementContextChange",
    "onEngagementStatusChange",
  ],
});

const stateByEngagement = new Map();
let currentEngagementId = "";

function ensureState(id) {
  if (!stateByEngagement.has(id)) {
    stateByEngagement.set(id, { notes: "", formDraft: {} });
  }
  return stateByEngagement.get(id);
}

async function hydrate() {
  const [ctx, status] = await Promise.all([
    zoomSdk.callZoomApi("getEngagementContext"),
    zoomSdk.callZoomApi("getEngagementStatus"),
  ]);
  currentEngagementId = ctx?.engagementContext?.engagementId || "";
  if (currentEngagementId) ensureState(currentEngagementId);
  render(currentEngagementId, status?.engagementStatus?.state);
}

zoomSdk.addEventListener("onEngagementContextChange", (evt) => {
  currentEngagementId = evt?.engagementContext?.engagementId || "";
  if (currentEngagementId) ensureState(currentEngagementId);
  render(currentEngagementId);
});

zoomSdk.addEventListener("onEngagementStatusChange", (evt) => {
  const state = evt?.engagementStatus?.state;
  if (state === "end" && currentEngagementId) {
    stateByEngagement.delete(currentEngagementId);
  }
  render(currentEngagementId, state);
});

hydrate();
```

## Campaign SDK Ready Gate

```javascript
window.addEventListener("zoomCampaignSdk:ready", () => {
  if (!window.zoomCampaignSdk) return;
  window.zoomCampaignSdk.show();
});
```
