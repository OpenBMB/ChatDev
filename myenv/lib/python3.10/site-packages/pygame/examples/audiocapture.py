#!/usr/bin/env python
""" pygame.examples.audiocapture

A pygame 2 experiment.

* record sound from a microphone
* play back the recorded sound
"""
import pygame as pg
import time

from pygame._sdl2 import (
    get_audio_device_names,
    AudioDevice,
    AUDIO_F32,
    AUDIO_ALLOW_FORMAT_CHANGE,
)
from pygame._sdl2.mixer import set_post_mix


pg.mixer.pre_init(44100, 32, 2, 512)
pg.init()

# init_subsystem(INIT_AUDIO)
names = get_audio_device_names(True)
print(names)

sounds = []
sound_chunks = []


def callback(audiodevice, audiomemoryview):
    """This is called in the sound thread.

    Note, that the frequency and such you request may not be what you get.
    """
    # print(type(audiomemoryview), len(audiomemoryview))
    # print(audiodevice)
    sound_chunks.append(bytes(audiomemoryview))


def postmix_callback(postmix, audiomemoryview):
    """This is called in the sound thread.

    At the end of mixing we get this data.
    """
    print(type(audiomemoryview), len(audiomemoryview))
    print(postmix)


set_post_mix(postmix_callback)

audio = AudioDevice(
    devicename=names[0],
    iscapture=True,
    frequency=44100,
    audioformat=AUDIO_F32,
    numchannels=2,
    chunksize=512,
    allowed_changes=AUDIO_ALLOW_FORMAT_CHANGE,
    callback=callback,
)
# start recording.
audio.pause(0)

print(audio)

print(f"recording with '{names[0]}'")
time.sleep(5)


print("Turning data into a pg.mixer.Sound")
sound = pg.mixer.Sound(buffer=b"".join(sound_chunks))

print("playing back recorded sound")
sound.play()
time.sleep(5)
pg.quit()
