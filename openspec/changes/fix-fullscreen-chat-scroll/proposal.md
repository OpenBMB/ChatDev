# Change: Fix Fullscreen Chat Panel Scrolling

## Why
After the persistent chat panel refactoring (commits `5525813` and `d796015`), the fullscreen chat mode is no longer scrollable. When the chat panel is in fullscreen mode (`viewMode === 'chat'`), messages accumulate but users cannot scroll through them.

## What Changes
- Fix CSS flexbox chain in `LaunchView.vue` so that `overflow-y: auto` on `.chat-messages` activates correctly in fullscreen mode
- Add `min-height: 0` to intermediate flex containers (`.chat-panel-content` and `.chat-box`) to allow them to shrink below their content size

## Impact
- Affected specs: chat-panel (new capability spec)
- Affected code: `frontend/src/pages/LaunchView.vue` (CSS only, ~2–3 lines)
