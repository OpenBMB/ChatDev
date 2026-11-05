---
title: "Web Component View: Breakout Rooms (What’s Possible)"
---

# Web Component View: Breakout Rooms (What’s Possible)

This targets questions like: “How do I create breakout rooms in Component View?”

## First: Confirm Context

- Are you **host** or **participant**?
- Are you using **Client View** (`ZoomMtg`) or **Component View** (`ZoomMtgEmbedded`)?

## Reality Check

Breakout rooms are a host-controlled feature. Even when the SDK UI supports breakout rooms, programmatic creation/open/close often requires:

- correct role (host/co-host)
- the meeting to have breakout rooms enabled
- supported APIs for the view type you’re using

## Where to Look Next

- Feature support table and Component View reference:
  - `meeting-sdk/web/component-view/SKILL.md`
- Client View examples often show breakout room API methods on `ZoomMtg`:
  - `meeting-sdk/web/client-view/SKILL.md`
- Cross-platform breakout room notes:
  - `meeting-sdk/references/breakout-rooms.md`

## Recommended Answer Pattern

1. If the user is on Component View:
   - confirm whether they’re trying to automate breakout rooms or just use the built-in UI
2. If they need automation:
   - identify the exact SDK version and view
   - confirm whether the needed API exists for that view (don’t assume parity)
