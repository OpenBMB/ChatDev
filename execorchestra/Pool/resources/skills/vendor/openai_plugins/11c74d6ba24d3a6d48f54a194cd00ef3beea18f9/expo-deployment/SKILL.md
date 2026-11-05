---
name: expo-deployment
description: Deploying Expo apps to iOS App Store, Android Play Store, web hosting, and API routes
version: 1.0.0
license: MIT
---

# Deployment

This skill covers deploying Expo applications across all platforms using EAS (Expo Application Services).

## References

Consult these resources as needed:

- ./references/workflows.md -- CI/CD workflows for automated deployments and PR previews
- ./references/testflight.md -- Submitting iOS builds to TestFlight for beta testing
- ./references/app-store-metadata.md -- Managing App Store metadata and ASO optimization
- ./references/play-store.md -- Submitting Android builds to Google Play Store
- ./references/ios-app-store.md -- iOS App Store submission and review process

## Quick Start

### Install EAS CLI

```bash
npm install -g eas-cli
eas login
```

### Initialize EAS

```bash
npx eas-cli@latest init
```

This creates `eas.json` with build profiles.

## Build Commands

### Production Builds

```bash
# iOS App Store build
npx eas-cli@latest build -p ios --profile production

# Android Play Store build
npx eas-cli@latest build -p android --profile production

# Both platforms
npx eas-cli@latest build --profile production
```

### Submit to Stores

```bash
# iOS: Build and submit to App Store Connect
npx eas-cli@latest build -p ios --profile production --submit

# Android: Build and submit to Play Store
npx eas-cli@latest build -p android --profile production --submit

# Shortcut for iOS TestFlight
npx testflight
```

## Web Deployment

Deploy web apps using EAS Hosting:

```bash
# Deploy to production
npx expo export -p web
npx eas-cli@latest deploy --prod

# Deploy PR preview
npx eas-cli@latest deploy
```

## EAS Configuration

Standard `eas.json` for production deployments:

```json
{
  "cli": {
    "version": ">= 16.0.1",
    "appVersionSource": "remote"
  },
  "build": {
    "production": {
      "autoIncrement": true,
      "ios": {
        "resourceClass": "m-medium"
      }
    },
    "development": {
      "developmentClient": true,
      "distribution": "internal"
    }
  },
  "submit": {
    "production": {
      "ios": {
        "appleId": "your@email.com",
        "ascAppId": "1234567890"
      },
      "android": {
        "serviceAccountKeyPath": "./google-service-account.json",
        "track": "internal"
      }
    }
  }
}
```

## Platform-Specific Guides

### iOS

- Use `npx testflight` for quick TestFlight submissions
- Configure Apple credentials via `eas credentials`
- See ./reference/testflight.md for credential setup
- See ./reference/ios-app-store.md for App Store submission

### Android

- Set up Google Play Console service account
- Configure tracks: internal → closed → open → production
- See ./reference/play-store.md for detailed setup

### Web

- EAS Hosting provides preview URLs for PRs
- Production deploys to your custom domain
- See ./reference/workflows.md for CI/CD automation

## Automated Deployments

Use EAS Workflows for CI/CD:

```yaml
# .eas/workflows/release.yml
name: Release

on:
  push:
    branches: [main]

jobs:
  build-ios:
    type: build
    params:
      platform: ios
      profile: production

  submit-ios:
    type: submit
    needs: [build-ios]
    params:
      platform: ios
      profile: production
```

See ./reference/workflows.md for more workflow examples.

## Version Management

EAS manages version numbers automatically with `appVersionSource: "remote"`:

```bash
# Check current versions
eas build:version:get

# Manually set version
eas build:version:set -p ios --build-number 42
```

## Monitoring

```bash
# List recent builds
eas build:list

# Check build status
eas build:view

# View submission status
eas submit:list
```
