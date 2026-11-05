# EAS Workflows

Automate builds, submissions, and deployments with EAS Workflows.

## Web Deployment

Deploy web apps on push to main:

`.eas/workflows/deploy.yml`

```yaml
name: Deploy

on:
  push:
    branches:
      - main

# https://docs.expo.dev/eas/workflows/syntax/#deploy
jobs:
  deploy_web:
    type: deploy
    params:
      prod: true
```

## PR Previews

### Web PR Previews

```yaml
name: Web PR Preview

on:
  pull_request:
    types: [opened, synchronize]

jobs:
  preview:
    type: deploy
    params:
      prod: false
```

### Native PR Previews with EAS Updates

Deploy OTA updates for pull requests:

```yaml
name: PR Preview

on:
  pull_request:
    types: [opened, synchronize]

jobs:
  publish:
    type: update
    params:
      branch: "pr-${{ github.event.pull_request.number }}"
      message: "PR #${{ github.event.pull_request.number }}"
```

## Production Release

Complete release workflow for both platforms:

```yaml
name: Release

on:
  push:
    tags: ['v*']

jobs:
  build-ios:
    type: build
    params:
      platform: ios
      profile: production

  build-android:
    type: build
    params:
      platform: android
      profile: production

  submit-ios:
    type: submit
    needs: [build-ios]
    params:
      platform: ios
      profile: production

  submit-android:
    type: submit
    needs: [build-android]
    params:
      platform: android
      profile: production
```

## Build on Push

Trigger builds when pushing to specific branches:

```yaml
name: Build

on:
  push:
    branches:
      - main
      - release/*

jobs:
  build:
    type: build
    params:
      platform: all
      profile: production
```

## Conditional Jobs

Run jobs based on conditions:

```yaml
name: Conditional Release

on:
  push:
    branches: [main]

jobs:
  check-changes:
    type: run
    params:
      command: |
        if git diff --name-only HEAD~1 | grep -q "^src/"; then
          echo "has_changes=true" >> $GITHUB_OUTPUT
        fi

  build:
    type: build
    needs: [check-changes]
    if: needs.check-changes.outputs.has_changes == 'true'
    params:
      platform: all
      profile: production
```

## Workflow Syntax Reference

### Triggers

```yaml
on:
  push:
    branches: [main, develop]
    tags: ['v*']
  pull_request:
    types: [opened, synchronize, reopened]
  schedule:
    - cron: '0 0 * * *'  # Daily at midnight
  workflow_dispatch:  # Manual trigger
```

### Job Types

| Type | Purpose |
|------|---------|
| `build` | Create app builds |
| `submit` | Submit to app stores |
| `update` | Publish OTA updates |
| `deploy` | Deploy web apps |
| `run` | Execute custom commands |

### Job Dependencies

```yaml
jobs:
  first:
    type: build
    params:
      platform: ios

  second:
    type: submit
    needs: [first]  # Runs after 'first' completes
    params:
      platform: ios
```

## Tips

- Use `workflow_dispatch` for manual production releases
- Combine PR previews with GitHub status checks
- Use tags for versioned releases
- Keep sensitive values in EAS Secrets, not workflow files
