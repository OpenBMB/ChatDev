# PulseAudio Setup for Linux

## Why PulseAudio is Required

The Zoom Video SDK for Linux **requires PulseAudio** for raw audio functions. Without it, audio raw data callbacks will not work.

## Installation

```bash
sudo apt update
sudo apt install -y pulseaudio
```

## Configuration

### 1. Create Configuration File

```bash
mkdir -p ~/.config
cat > ~/.config/zoomus.conf << 'CONFIG'
[General]
system.audio.type=default
CONFIG
```

### 2. Start PulseAudio (if not running)

```bash
pulseaudio --check || pulseaudio --start
```

## Docker/Headless Setup

For Docker or headless environments:

```bash
# Install PulseAudio
apt-get update && apt-get install -y pulseaudio

# Create virtual devices
pactl load-module module-null-sink sink_name=virtual_speaker
pactl load-module module-null-source source_name=virtual_mic

# Configure Zoom
mkdir -p ~/.config
echo "[General]" > ~/.config/zoomus.conf
echo "system.audio.type=default" >> ~/.config/zoomus.conf
```

**Better Approach**: Use virtual audio speaker/mic in SDK:

```cpp
session_context.virtualAudioSpeaker = new VirtualSpeaker();
session_context.virtualAudioMic = new VirtualMic();
```

## Verification

```bash
# Check PulseAudio is running
pulseaudio --check && echo "Running" || echo "Not running"

# List audio devices
pactl list sinks short
pactl list sources short

# Test config
cat ~/.config/zoomus.conf
```

## Common Issues

### Issue: PulseAudio not starting

```bash
# Kill existing instance
pulseaudio --kill

# Start fresh
pulseaudio --start

# Check status
pulseaudio --check
```

### Issue: Permission denied

```bash
# Add user to audio group
sudo usermod -aG audio $USER

# Logout and login again
```

### Issue: No audio in Docker

**Solution**: Use virtual audio devices in SDK instead of system audio.
