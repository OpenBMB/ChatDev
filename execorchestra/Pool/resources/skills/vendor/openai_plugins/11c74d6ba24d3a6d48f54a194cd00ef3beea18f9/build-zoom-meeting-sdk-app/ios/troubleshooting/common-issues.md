# iOS Common Issues

## 1. Join/start fails with generic error

- Validate signature expiry and role.
- Confirm meeting number/passcode mapping.
- Confirm host flow has valid `ZAK`.

## 2. Delegate callbacks missing or late

- Register delegates before invoking join/start.
- Verify lifecycle transitions do not deallocate coordinator/service objects.

## 3. Audio route or interruption issues

- Handle route changes explicitly.
- Re-sync meeting media state after interruption/background return.

## 4. Upgrade regressions

- Compare protocol/category signatures against prior version.
- Re-test custom UI extensions first; they are usually most drift-prone.
