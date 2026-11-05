# High-Level Scenarios

## 1. Desktop internal meeting client

- User signs in to your app.
- Backend mints SDK JWT.
- Electron app embeds join/start for scheduled meetings.
- Controllers handle mute/video/chat/share.

## 2. Compliance-focused recorder assistant

- Controlled join flow for operator accounts.
- Recording and raw data modules capture meeting artifacts.
- Data moves to internal compliance pipeline.

## 3. Support operations dashboard

- Agents join support sessions from desktop app.
- Use participants/chat/share modules for assistance workflows.
- Waiting room and host control automation for queue handling.

## 4. AI-assisted desktop meeting copilot

- Meeting join via Electron SDK.
- Raw data or AI-related modules feed local/remote AI services.
- Live summary/action extraction in side panel.
