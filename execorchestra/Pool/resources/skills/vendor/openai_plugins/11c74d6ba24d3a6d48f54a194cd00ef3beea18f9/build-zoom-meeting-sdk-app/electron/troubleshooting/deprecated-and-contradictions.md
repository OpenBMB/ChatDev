# Deprecated and Contradictions

Observed from crawled docs and provided SDK package context:

## 1. Electron version guidance contradiction

- Package README mentions installing Electron `33.0.0`.
- Same README also says sample app currently does not support Electron 10 or above.

Action: treat sample README version text as inconsistent and validate against official current compatibility guidance before rollout.

## 2. Deprecated module flags in API reference

Crawled API reference marks deprecations in several areas, including webinar and some setting-related modules.

Action: avoid new dependencies on deprecated modules; isolate behind adapter interfaces if legacy support is required.

## 3. Feature availability caveats

Multiple module docs include "not supported" notes depending on platform/account/meeting context.

Action: gate feature use with runtime capability checks and fail gracefully.

## 4. Python/build toolchain caveat in sample notes

Sample package notes mention build issues with newer Python (distutils-related) and suggest older Python versions.

Action: pin build environment versions in CI and document exact toolchain used for your release branch.
