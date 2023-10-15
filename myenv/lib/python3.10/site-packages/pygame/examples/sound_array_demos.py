#!/usr/bin/env python
""" pygame.examples.sound_array_demos

Creates an echo effect on any Sound object.

Uses sndarray and numpy to create offset faded copies of the
original sound. Currently it just uses hardcoded values for the
number of echos and the delay. Easy for you to recreate as
needed.

version 2. changes:
- Should work with different sample rates now.
- put into a function.
- Uses numpy by default, but falls back on Numeric.
"""
import os
import pygame as pg
from numpy import zeros, int32, int16
import time


# pg.mixer.init(44100, -16, 0)
pg.mixer.init()
# pg.mixer.init(11025, -16, 0)
# pg.mixer.init(11025)


def make_echo(sound, samples_per_second, mydebug=True):
    """returns a sound which is echoed of the last one."""

    echo_length = 3.5

    a1 = pg.sndarray.array(sound)
    if mydebug:
        print(f"SHAPE1: {a1.shape}")

    length = a1.shape[0]

    # myarr = zeros(length+12000)
    myarr = zeros(a1.shape, int32)

    if len(a1.shape) > 1:
        # mult = a1.shape[1]
        size = (a1.shape[0] + int(echo_length * a1.shape[0]), a1.shape[1])
        # size = (a1.shape[0] + int(a1.shape[0] + (echo_length * 3000)), a1.shape[1])
    else:
        # mult = 1
        size = (a1.shape[0] + int(echo_length * a1.shape[0]),)
        # size = (a1.shape[0] + int(a1.shape[0] + (echo_length * 3000)),)

    if mydebug:
        print(int(echo_length * a1.shape[0]))
    myarr = zeros(size, int32)

    if mydebug:
        print(f"size {size}")
        print(myarr.shape)
    myarr[:length] = a1
    # print(myarr[3000:length+3000])
    # print(a1 >> 1)
    # print("a1.shape %s" % (a1.shape,))
    # c = myarr[3000:length+(3000*mult)]
    # print("c.shape %s" % (c.shape,))

    incr = int(samples_per_second / echo_length)
    gap = length

    myarr[incr : gap + incr] += a1 >> 1
    myarr[incr * 2 : gap + (incr * 2)] += a1 >> 2
    myarr[incr * 3 : gap + (incr * 3)] += a1 >> 3
    myarr[incr * 4 : gap + (incr * 4)] += a1 >> 4

    if mydebug:
        print(f"SHAPE2: {myarr.shape}")

    sound2 = pg.sndarray.make_sound(myarr.astype(int16))

    return sound2


def slow_down_sound(sound, rate):
    """returns a sound which is a slowed down version of the original.
    rate - at which the sound should be slowed down.  eg. 0.5 would be half speed.
    """

    raise NotImplementedError()
    # grow_rate = 1 / rate
    # make it 1/rate times longer.
    # a1 = pg.sndarray.array(sound)
    # surf = pg.surfarray.make_surface(a1)
    # print(a1.shape[0] * grow_rate)
    # scaled_surf = pg.transform.scale(surf, (int(a1.shape[0] * grow_rate), a1.shape[1]))
    # print(scaled_surf)
    # print(surf)

    # a2 = a1 * rate
    # print(a1.shape)
    # print(a2.shape)
    # print(a2)
    # sound2 = pg.sndarray.make_sound(a2.astype(int16))
    # return sound2


def sound_from_pos(sound, start_pos, samples_per_second=None, inplace=1):
    """returns a sound which begins at the start_pos.
    start_pos - in seconds from the beginning.
    samples_per_second -
    """

    # see if we want to reuse the sound data or not.
    if inplace:
        a1 = pg.sndarray.samples(sound)
    else:
        a1 = pg.sndarray.array(sound)

    # see if samples per second has been given.  If not, query the pg.mixer.
    #   eg. it might be set to 22050
    if samples_per_second is None:
        samples_per_second = pg.mixer.get_init()[0]

    # figure out the start position in terms of samples.
    start_pos_in_samples = int(start_pos * samples_per_second)

    # cut the beginning off the sound at the start position.
    a2 = a1[start_pos_in_samples:]

    # make the Sound instance from the array.
    sound2 = pg.sndarray.make_sound(a2)

    return sound2


def main():
    """play various sndarray effects"""

    main_dir = os.path.split(os.path.abspath(__file__))[0]
    print(f"mixer.get_init {pg.mixer.get_init()}")

    samples_per_second = pg.mixer.get_init()[0]

    print(("-" * 30) + "\n")
    print("loading sound")
    sound = pg.mixer.Sound(os.path.join(main_dir, "data", "car_door.wav"))

    print("-" * 30)
    print("start positions")
    print("-" * 30)

    start_pos = 0.1
    sound2 = sound_from_pos(sound, start_pos, samples_per_second)

    print(f"sound.get_length {sound.get_length()}")
    print(f"sound2.get_length {sound2.get_length()}")
    sound2.play()
    while pg.mixer.get_busy():
        pg.time.wait(200)

    print("waiting 2 seconds")
    pg.time.wait(2000)
    print("playing original sound")

    sound.play()
    while pg.mixer.get_busy():
        pg.time.wait(200)

    print("waiting 2 seconds")
    pg.time.wait(2000)

    # if 0:
    #    #TODO: this is broken.
    #    print(("-" * 30) + "\n")
    #    print("Slow down the original sound.")
    #    rate = 0.2
    #    slowed_sound = slow_down_sound(sound, rate)
    #    slowed_sound.play()
    #    while pg.mixer.get_busy():
    #        pg.time.wait(200)

    print("-" * 30)
    print("echoing")
    print("-" * 30)

    t1 = time.time()
    sound2 = make_echo(sound, samples_per_second)
    print("time to make echo %i" % (time.time() - t1,))

    print("original sound")
    sound.play()
    while pg.mixer.get_busy():
        pg.time.wait(200)

    print("echoed sound")
    sound2.play()
    while pg.mixer.get_busy():
        pg.time.wait(200)

    sound = pg.mixer.Sound(os.path.join(main_dir, "data", "secosmic_lo.wav"))

    t1 = time.time()
    sound3 = make_echo(sound, samples_per_second)
    print("time to make echo %i" % (time.time() - t1,))

    print("original sound")
    sound.play()
    while pg.mixer.get_busy():
        pg.time.wait(200)

    print("echoed sound")
    sound3.play()
    while pg.mixer.get_busy():
        pg.time.wait(200)

    pg.quit()


if __name__ == "__main__":
    main()
