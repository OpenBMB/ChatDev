# Setup Guide

This guide focuses on integration structure, not one-click install scripts.

## Prerequisites

- Electron + Node toolchain compatible with your chosen SDK package.
- Native build toolchain for Node addon compilation.
- Backend endpoint for SDK JWT signing.

## Minimal setup checklist

1. Add Meeting SDK Electron package and native artifacts.
2. Wire preload/main process APIs for SDK invocation.
3. Implement secure backend endpoint for JWT generation.
4. Add app-level init/auth/join lifecycle handlers.
5. Add structured logging around SDK callbacks and error codes.

## Security baseline

- Keep SDK secret off client.
- Gate any raw data transport with encryption and access controls.
- Validate all IPC boundaries between renderer and main process.
