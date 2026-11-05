# Deployment Guide

## Overview

When releasing or publishing your Meeting SDK app, you need to:
1. Include SDK files from `\bin`
2. Include required Microsoft VC++ runtime libraries
3. NOT re-sign protected SDK files
4. Run cleanup command for upgrades

---

## Required SDK Files

**Development** requires files from:
- `\lib` - Link libraries
- `\h` - Header files
- `\bin` - Runtime DLLs

**Deployment/Release** only requires:
- `\bin` - Runtime DLLs (copy to your app's directory)

---

## Protected Files (DO NOT Re-sign)

These files **cannot be re-signed or have new digital signatures added**. Doing so causes **Error 105035** and fatal errors:

```
CptControl.exe
CptHost.exe
CptInstall.exe
CptService.exe
CptShare.dll
zzhost.dll
zzplugin.dll
aomhost64.exe
```

**Solution**: Skip these files in your code signing process during build/deployment.

---

## Microsoft VC++ Runtime Libraries

You must distribute the appropriate Microsoft Visual C++ runtime libraries with your app.

### x64 Architecture (Most Common)

**Remove** the `bin/aomhost` directory, then copy these DLLs to the same directory as SDK DLLs:

```
concrt140.dll
msvcp140.dll
msvcp140_1.dll
msvcp140_2.dll
msvcp140_codecvt_ids.dll
vccorlib140.dll
vcruntime140.dll
vcruntime140_1.dll
api-ms-win-core-console-l1-1-0.dll
api-ms-win-core-console-l1-2-0.dll
api-ms-win-core-datetime-l1-1-0.dll
api-ms-win-core-debug-l1-1-0.dll
api-ms-win-core-errorhandling-l1-1-0.dll
api-ms-win-core-file-l1-1-0.dll
api-ms-win-core-file-l1-2-0.dll
api-ms-win-core-file-l2-1-0.dll
api-ms-win-core-handle-l1-1-0.dll
api-ms-win-core-heap-l1-1-0.dll
api-ms-win-core-interlocked-l1-1-0.dll
api-ms-win-core-libraryloader-l1-1-0.dll
api-ms-win-core-localization-l1-2-0.dll
api-ms-win-core-memory-l1-1-0.dll
api-ms-win-core-namedpipe-l1-1-0.dll
api-ms-win-core-processenvironment-l1-1-0.dll
api-ms-win-core-processthreads-l1-1-0.dll
api-ms-win-core-processthreads-l1-1-1.dll
api-ms-win-core-profile-l1-1-0.dll
api-ms-win-core-rtlsupport-l1-1-0.dll
api-ms-win-core-string-l1-1-0.dll
api-ms-win-core-synch-l1-1-0.dll
api-ms-win-core-synch-l1-2-0.dll
api-ms-win-core-sysinfo-l1-1-0.dll
api-ms-win-core-timezone-l1-1-0.dll
api-ms-win-core-util-l1-1-0.dll
api-ms-win-crt-conio-l1-1-0.dll
api-ms-win-crt-convert-l1-1-0.dll
api-ms-win-crt-environment-l1-1-0.dll
api-ms-win-crt-filesystem-l1-1-0.dll
api-ms-win-crt-heap-l1-1-0.dll
api-ms-win-crt-locale-l1-1-0.dll
api-ms-win-crt-math-l1-1-0.dll
api-ms-win-crt-multibyte-l1-1-0.dll
api-ms-win-crt-private-l1-1-0.dll
api-ms-win-crt-process-l1-1-0.dll
api-ms-win-crt-runtime-l1-1-0.dll
api-ms-win-crt-stdio-l1-1-0.dll
api-ms-win-crt-string-l1-1-0.dll
api-ms-win-crt-time-l1-1-0.dll
api-ms-win-crt-utility-l1-1-0.dll
ucrtbase.dll
```

### x86 Architecture (32-bit)

Copy these DLLs to **both** `bin` AND `bin/aomhost` directories:

```
concrt140.dll
msvcp140.dll
msvcp140_1.dll
msvcp140_2.dll
msvcp140_codecvt_ids.dll
vccorlib140.dll
vcruntime140.dll
api-ms-win-core-console-l1-1-0.dll
api-ms-win-core-console-l1-2-0.dll
api-ms-win-core-datetime-l1-1-0.dll
api-ms-win-core-debug-l1-1-0.dll
api-ms-win-core-errorhandling-l1-1-0.dll
api-ms-win-core-file-l1-1-0.dll
api-ms-win-core-file-l1-2-0.dll
api-ms-win-core-file-l2-1-0.dll
api-ms-win-core-handle-l1-1-0.dll
api-ms-win-core-heap-l1-1-0.dll
api-ms-win-core-interlocked-l1-1-0.dll
api-ms-win-core-libraryloader-l1-1-0.dll
api-ms-win-core-localization-l1-2-0.dll
api-ms-win-core-memory-l1-1-0.dll
api-ms-win-core-namedpipe-l1-1-0.dll
api-ms-win-core-processenvironment-l1-1-0.dll
api-ms-win-core-processthreads-l1-1-0.dll
api-ms-win-core-processthreads-l1-1-1.dll
api-ms-win-core-profile-l1-1-0.dll
api-ms-win-core-rtlsupport-l1-1-0.dll
api-ms-win-core-string-l1-1-0.dll
api-ms-win-core-synch-l1-1-0.dll
api-ms-win-core-synch-l1-2-0.dll
api-ms-win-core-sysinfo-l1-1-0.dll
api-ms-win-core-timezone-l1-1-0.dll
api-ms-win-core-util-l1-1-0.dll
api-ms-win-crt-conio-l1-1-0.dll
api-ms-win-crt-convert-l1-1-0.dll
api-ms-win-crt-environment-l1-1-0.dll
api-ms-win-crt-filesystem-l1-1-0.dll
api-ms-win-crt-heap-l1-1-0.dll
api-ms-win-crt-locale-l1-1-0.dll
api-ms-win-crt-math-l1-1-0.dll
api-ms-win-crt-multibyte-l1-1-0.dll
api-ms-win-crt-private-l1-1-0.dll
api-ms-win-crt-process-l1-1-0.dll
api-ms-win-crt-runtime-l1-1-0.dll
api-ms-win-crt-stdio-l1-1-0.dll
api-ms-win-crt-string-l1-1-0.dll
api-ms-win-crt-time-l1-1-0.dll
api-ms-win-crt-utility-l1-1-0.dll
ucrtbase.dll
API-MS-Win-core-xstate-l2-1-0.dll
```

### ARM64 Architecture

**Remove** the `bin/aomhost` directory, then copy these DLLs:

```
msvcp140.dll
msvcp140_1.dll
msvcp140_2.dll
msvcp140_atomic_wait.dll
msvcp140_codecvt_ids.dll
vccorlib140.dll
vcruntime140.dll
concrt140.dll
```

---

## Upgrade Installation

When users upgrade from an older version of your app, run this command **with administrator privileges** before installing the new version:

```cmd
cptinstall.exe -uninstall
```

This ensures users who had an older package can use the share function normally.

---

## Visual Studio Project Configuration

### Output Directory
Set to the `bin` folder:
- Configuration Properties → General → Output Directory: `...\bin`

### Include Directories
- Configuration Properties → VC++ Directories → Include Directories: `...\h`

### Library Directories
- Configuration Properties → VC++ Directories → Library Directories: `...\lib`

### Linker Output
- Linker → General → Output File: Your desired `.exe` location

### Debug Information (Release builds)
- C/C++ → Debug Information Format: `None`

---

## Deployment Checklist

- [ ] Copy SDK DLLs from `\bin` to app directory
- [ ] Copy appropriate VC++ runtime DLLs for your architecture
- [ ] For x64/ARM64: Remove `bin/aomhost` directory
- [ ] For x86: Copy runtime DLLs to both `bin` and `bin/aomhost`
- [ ] Exclude protected files from code signing
- [ ] Test on clean machine without Visual Studio installed
- [ ] Include `cptinstall.exe -uninstall` in upgrade process

---

## Common Deployment Issues

### "Missing DLL" errors
**Cause**: VC++ runtime libraries not included
**Fix**: Copy all required runtime DLLs to app directory

### Error 105035
**Cause**: Re-signed protected SDK files
**Fix**: Don't sign `CptControl.exe`, `CptHost.exe`, `CptInstall.exe`, `CptService.exe`, `CptShare.dll`, `zzhost.dll`, `zzplugin.dll`, `aomhost64.exe`

### Share function not working after upgrade
**Cause**: Old CPT components still registered
**Fix**: Run `cptinstall.exe -uninstall` before installing new version

### App works on dev machine but not on target
**Cause**: Target machine missing VC++ redistributable
**Fix**: Either bundle runtime DLLs or require VC++ 2019 Redistributable installation

---

## Alternative: Install VC++ Redistributable

Instead of bundling DLLs, you can require users to install the **Microsoft Visual C++ 2019 Redistributable**:
- [Download VC++ Redistributable](https://docs.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist)

However, bundling the DLLs gives you more control and ensures compatibility.

---

## Related Documentation

- [Build Errors Guide](../troubleshooting/build-errors.md) - Project setup
- [Common Issues](../troubleshooting/common-issues.md) - Error 105035 details
- [Authentication Pattern](../examples/authentication-pattern.md) - Complete working code

---

**Last Updated**: Based on Zoom Windows Meeting SDK v6.7.2.26830
