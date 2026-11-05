# Module Configuration Reference

## expo-module.config.json

Required for autolinking. Must be adjacent to `package.json`.

```json
{
  "platforms": ["android", "apple", "web"],
  "apple": {
    "modules": ["MyModule"],
    "appDelegateSubscribers": ["MyAppDelegateSubscriber"]
  },
  "android": {
    "modules": ["expo.modules.mymodule.MyModule"]
  }
}
```

### Fields

| Field | Description |
|-------|-------------|
| `platforms` | Array: `"android"`, `"apple"` (or `"ios"`, `"macos"`, `"tvos"`), `"web"`, `"devtools"` |
| `apple.modules` | Swift module class names |
| `apple.appDelegateSubscribers` | Swift AppDelegate subscriber class names |
| `android.modules` | Fully-qualified Kotlin module class names (package + class) |

## Autolinking

Expo autolinking automatically discovers and links modules that have `expo-module.config.json`. No manual native project configuration needed — install via npm, run `pod install`.

### Resolution Order

1. Explicit dependencies in `react-native.config.js`
2. Custom `searchPaths` directories
3. Local `nativeModulesDir` (defaults to `./modules/`)
4. Recursive npm dependency resolution
