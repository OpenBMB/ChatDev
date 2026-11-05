# Meeting SDK Android Guide

## Scope

Android Meeting SDK integration for default UI, custom UI, auth, start/join, and in-meeting feature modules.

## Validation Snapshot

- Crawled docs path includes: `get-started`, `integrate`, `start-join-mtg-webinar`, `default-ui`, `custom-ui`, `resource/error-codes`.
- API reference snapshot includes class/interface/function maps from `index.html`, `annotated.html`, `classes.html`, `files.html`, and `functions*` pages.
- Local package checked: `zoom-sdk-android-6.7.5.37500` (contains `mobilertc.aar`, sample apps, dynamic sample modules).

## Practical Guidance

1. Initialize and authenticate SDK.
2. Get first successful join in default UI.
3. Add feature flags/settings and error handling.
4. Move to custom UI only for required UX control.
5. Add observability for meeting status and SDK callback failures.
