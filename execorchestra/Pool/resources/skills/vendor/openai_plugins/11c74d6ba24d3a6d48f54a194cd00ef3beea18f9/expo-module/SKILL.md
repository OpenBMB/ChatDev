---
name: expo-module
description: Guide for writing Expo native modules and views using the Expo Modules API (Swift, Kotlin, TypeScript). Covers module definition DSL, native views, shared objects, config plugins, lifecycle hooks, autolinking, and type system. Use when building or modifying native modules for Expo.
version: 1.0.0
license: MIT
---

# Writing Expo Modules

Complete reference for building native modules and views using the Expo Modules API. Covers Swift (iOS), Kotlin (Android), and TypeScript.

## When to Use

- Creating a new Expo native module or native view
- Adding native functionality (camera, sensors, system APIs) to an Expo app
- Wrapping platform SDKs for React Native consumption
- Building config plugins that modify native project files

## References

Consult these resources as needed:

```
references/
  native-module.md           Module definition DSL: Name, Function, AsyncFunction, Property, Constant, Events, type system, shared objects
  native-view.md             Native view components: View, Prop, EventDispatcher, view lifecycle, ref-based functions
  lifecycle.md               Lifecycle hooks: module, iOS app/AppDelegate, Android activity/application listeners
  config-plugin.md           Config plugins: modifying Info.plist, AndroidManifest.xml, reading values in native code
  module-config.md           expo-module.config.json fields and autolinking configuration
```

## Quick Start

### Create a Local Module (in existing app)

**Always scaffold with `create-expo-module` first**, then modify the generated code. This ensures correct podspec, build.gradle, and module config — avoiding common build errors.

```bash
CI=1 npx create-expo-module@latest --local \
  --name MyModule \
  --description "My Expo module" \
  --package expo.modules.mymodule
```

`CI=1` skips interactive prompts and uses the provided flags.

> **Important:** In `CI=1` (non-interactive) mode, the scaffold always creates the directory as `modules/my-module/` because the slug is derived from `customTargetPath` which is `undefined` for `--local` modules — the `--name` flag only sets the native class name, not the directory. After scaffolding, rename it to a kebab-case name matching your module (e.g., `KeyValueStore` → `modules/key-value-store/`), then run `cd ios && pod install` so CocoaPods picks up the correct path. Skipping the rename is fine functionally, but skipping `pod install` after any rename causes iOS build failures ("Build input file cannot be found").

Available flags:

| Flag | Description | Example |
|------|-------------|---------|
| `--name` | Native module name (PascalCase) | `--name KeyValueStore` |
| `--description` | Module description | `--description "Native key-value storage"` |
| `--package` | Android package name | `--package expo.modules.keyvaluestore` |
| `--author-name` | Author name | `--author-name "dev"` |
| `--author-email` | Author email | `--author-email "dev@example.com"` |
| `--author-url` | Author profile URL | `--author-url "https://github.com/dev"` |
| `--repo` | Repository URL | `--repo "https://github.com/dev/repo"` |

The scaffold generates both a **native module** (functions, events, constants) and a **native view component** (WebView example with props and events). After scaffolding:

1. **Decide what you need**: If you only need a native module (no UI), remove the view files. If you only need a native view, remove the module function boilerplate. If you need both, keep both and replace the implementations.
2. **Remove unnecessary boilerplate**: The scaffold includes example code (`hello()` function, `PI` constant, `onChange` event, WebView-based view with `url` prop). Strip all of this and replace with your actual implementation.
3. **Remove web files if not needed**: The scaffold generates `*.web.ts`/`*.web.tsx` files for web platform support. Remove these if the module is native-only. Also remove `"web"` from the `platforms` array in `expo-module.config.json`.

#### What to remove for a module-only (no native view):

- Delete `ios/MyModuleView.swift`, `android/.../MyModuleView.kt`
- Delete `src/MyModuleView.tsx`, `src/MyModuleView.web.tsx`
- Remove the `View(...)` block from the module definition in both Swift and Kotlin
- Remove view-related types from `MyModule.types.ts` and view export from `index.ts`

#### What to remove for a view-only (no module functions):

- Remove `Function`, `AsyncFunction`, `Constant`, `Events` blocks from the module definition (keep `Name` and `View`)
- Simplify the TypeScript module file to only export the view

Generated structure (after renaming from `my-module` to your module's kebab-case name):

```
modules/
  my-module/                     # Rename to kebab-case, e.g. key-value-store/
    android/
      build.gradle
      src/main/java/expo/modules/mymodule/
        MyModule.kt              # Module definition (functions, events, view registration)
        MyModuleView.kt          # Native view (ExpoView subclass)
    ios/
      MyModule.podspec
      MyModule.swift             # Module definition
      MyModuleView.swift         # Native view (ExpoView subclass)
    src/
      MyModule.ts                # Native module binding
      MyModule.web.ts            # Web implementation
      MyModule.types.ts          # Shared types
      MyModuleView.tsx           # Native view component
      MyModuleView.web.tsx       # Web view component
    expo-module.config.json
    index.ts                     # Re-exports module + view
```

### Create a Standalone Module (for publishing)

```bash
npx create-expo-module@latest my-module
```

---

## Module Structure Reference

The Swift and Kotlin DSL share the same structure. Both platforms are shown here for reference — in other reference files, Swift is shown as the primary language unless the Kotlin pattern meaningfully differs.

**Swift (iOS):**

```swift
import ExpoModulesCore

public class MyModule: Module {
  public func definition() -> ModuleDefinition {
    Name("MyModule")

    Function("hello") { (name: String) -> String in
      return "Hello \(name)!"
    }
  }
}
```

**Kotlin (Android):**

```kotlin
package expo.modules.mymodule

import expo.modules.kotlin.modules.Module
import expo.modules.kotlin.modules.ModuleDefinition

class MyModule : Module() {
  override fun definition() = ModuleDefinition {
    Name("MyModule")

    Function("hello") { name: String ->
      "Hello $name!"
    }
  }
}
```

**TypeScript:**

```typescript
import { requireNativeModule } from "expo";

const MyModule = requireNativeModule("MyModule");

export function hello(name: string): string {
  return MyModule.hello(name);
}
```

### expo-module.config.json

```json
{
  "platforms": ["android", "apple"],
  "apple": {
    "modules": ["MyModule"]
  },
  "android": {
    "modules": ["expo.modules.mymodule.MyModule"]
  }
}
```

Note: iOS uses just the class name; Android uses the fully-qualified class name (package + class). See `references/module-config.md` for all fields.
