## ADDED Requirements

### Requirement: Fullscreen Chat Scrolling
The chat messages area SHALL be scrollable when the chat panel is in fullscreen mode and messages exceed the visible viewport height.

#### Scenario: Messages overflow in fullscreen chat
- **WHEN** the chat panel is in fullscreen mode (`viewMode === 'chat'`)
- **AND** the number of chat messages exceeds the visible area
- **THEN** the `.chat-messages` container SHALL allow vertical scrolling via `overflow-y: auto`

#### Scenario: Scroll position preserved on new message
- **WHEN** the user is scrolled to the bottom of the chat
- **AND** a new message arrives
- **THEN** the chat SHALL auto-scroll to show the latest message
