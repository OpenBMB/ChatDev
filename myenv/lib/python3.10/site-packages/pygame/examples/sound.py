#!/usr/bin/env python
""" pygame.examples.sound

Playing a soundfile and waiting for it to finish. You'll need the
pygame.mixer module for this to work. Note how in this simple example
we don't even bother loading all of the pygame package.
Just pick the mixer for sound and time for the delay function.

Optional command line argument: audio file name
"""
import os
import sys
import pygame as pg

main_dir = os.path.split(os.path.abspath(__file__))[0]


def main(file_path=None):
    """Play an audio file as a buffered sound sample

    :param str file_path: audio file (default data/secosmic_low.wav)
    """
    # choose a desired audio format
    pg.mixer.init(11025)  # raises exception on fail

    # load the sound
    sound = pg.mixer.Sound(file_path)

    # start playing
    print("Playing Sound...")
    channel = sound.play()

    # poll until finished
    while channel.get_busy():  # still playing
        print("  ...still going...")
        pg.time.wait(1000)
    print("...Finished")
    pg.quit()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        main(sys.argv[1])
    else:
        main(os.path.join(main_dir, "data", "secosmic_lo.wav"))
