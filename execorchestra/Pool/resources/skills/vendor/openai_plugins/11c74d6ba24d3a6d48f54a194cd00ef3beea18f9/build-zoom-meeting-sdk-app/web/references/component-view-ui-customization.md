---
title: "Web Component View: UI Customization and Limitations"
---

# Web Component View: UI Customization and Limitations

This addresses common questions like:

- “How do I hide meeting info / passcode / invite URL?”
- “How do I remove Participants / Audio / Video / Share buttons?”
- “Can I fully customize the Meeting SDK UI?”

## First: Confirm View Type

- **Component View** (npm): `ZoomMtgEmbedded.createClient()`
- **Client View** (CDN): `ZoomMtg.*`

The available customization knobs differ.

## Component View Customization Entry Point

Component View customization is done via `client.init({ customize: { ... } })`.

The most common knob is `customize.meetingInfo`, which controls what shows in “meeting info” surfaces.

Example reference:
- `meeting-sdk/web/component-view/SKILL.md` (Customize Object section)
- `meeting-sdk/web/SKILL.md` (Key options snippet)

## Hiding “Meeting Info” (Topic/MN/Passcode/Invite)

Use `customize.meetingInfo` to control which fields are displayed.

Important: this controls what the **SDK UI displays**. It does not change the meeting’s underlying security settings.

## Removing Default Buttons (Participants/Audio/Video/Share)

Forum expectation mismatch: the SDK supports **adding** custom toolbar buttons, but “removing all built-in controls” is not always supported (and CSS-hacking the Zoom UI is brittle and can break across SDK updates).

Recommended answer pattern:

1. Ask which exact controls they want removed and why (UX vs compliance).
2. If it’s a compliance/policy requirement (e.g. “prevent recording/screen capture”), treat it as **not solvable purely via SDK UI**.
3. If it’s UX:
   - prefer supported `customize` options
   - otherwise, set expectations about what is and isn’t controllable

## Don’t Use CSS Hacks as a Primary Strategy

You *can* sometimes hide elements with CSS selectors, but:
- it is fragile
- it can break accessibility/flow
- it may violate intended product behavior

Use official knobs first.
