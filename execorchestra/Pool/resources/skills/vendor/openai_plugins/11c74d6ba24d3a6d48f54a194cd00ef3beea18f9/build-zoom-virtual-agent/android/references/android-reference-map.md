# Android Reference Map

## Core Docs

- Get started: https://developers.zoom.us/docs/virtual-agent/android/get-started/
- Integration scenarios: https://developers.zoom.us/docs/virtual-agent/android/integration-scenarios/
- JavaScript events: https://developers.zoom.us/docs/virtual-agent/android/javascript-events/
- Resources: https://developers.zoom.us/docs/virtual-agent/android/resources/

## Observed Sample Patterns

- Java and Kotlin implementations follow the same bridge contract.
- Bridge command routing centers around `commonHandler` JSON payloads.
- `support_handoff` events are emitted from JS and consumed in native layer.
