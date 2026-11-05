# Unreal Architecture

## Layer Model

- Unreal game/app layer (C++ and Blueprint graphs).
- Unreal wrapper layer (method adaptation for Blueprint/C++).
- Core Meeting SDK layer (native behavior baseline).
- Backend signature/token service.

## Reference Flow

```text
Unreal Gameplay/UI -> Unreal Wrapper -> Meeting SDK Core -> Zoom services
       ^                 |                 |                  |
       |                 v                 v                  v
   Player actions    Wrapper events    Native callbacks   Meeting state
```

## Key Concept

Always separate:
- wrapper behavior (Unreal-specific), and
- core SDK behavior (native reference semantics).
