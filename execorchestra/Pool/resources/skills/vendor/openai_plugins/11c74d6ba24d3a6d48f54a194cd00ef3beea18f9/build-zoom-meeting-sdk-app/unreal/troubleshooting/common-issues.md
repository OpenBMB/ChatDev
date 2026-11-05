# Unreal Common Issues

## 1. Wrapper method mismatch

- Check whether method is available in C++ wrapper, Blueprint wrapper, or both.
- Validate renamed/modified Blueprint node signatures.

## 2. Join/start behavior not matching expectations

- Compare wrapper docs and base SDK semantics.
- Verify token/signature validity and role alignment.

## 3. Version mismatch issues

- Confirm Unreal engine version compatibility with package.
- Verify wrapper package version and docs are from same release family.

## 4. Packaging contradictions

- If changelog/reference links look inconsistent, trust runtime behavior + validated wrapper docs + controlled test matrix.
