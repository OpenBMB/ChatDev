---
title: "Multiple Meetings and Multiple Instances"
---

# Multiple Meetings and Multiple Instances

Common forum question: “How do I attend two meeting rooms at the same time?”

## Core Constraint

In most SDK/client integrations, a single Meeting SDK client instance is designed around **one active meeting session at a time**.

If you need “two meetings at once”, you typically need **two separate instances** (and often separate process/browser contexts/devices).

## Practical Options (What Usually Works)

- **Two devices** (simplest operationally)
- **Two separate processes** (desktop apps)
- **Two separate browser profiles/containers** (web), if supported by the environment

## What to Clarify

- Platform (Web vs Windows/macOS vs Android/iOS vs Linux)
- Whether you need:
  - audio/video in both meetings concurrently
  - or just monitoring/viewing one while connected to another
- Any compliance constraints (recording, transcription, etc.)
