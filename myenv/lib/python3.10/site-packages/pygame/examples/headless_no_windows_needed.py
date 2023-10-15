#!/usr/bin/env python
""" pygame.examples.headless_no_windows_needed

How to use pygame with no windowing system, like on headless servers.

Thumbnail generation with scaling is an example of what you can do with pygame.
NOTE: the pygame scale function uses mmx/sse if available, and can be run
  in multiple threads.
"""
usage = """-scale inputimage outputimage new_width new_height
eg.  -scale in.png out.png 50 50

"""

import os
import sys

# set SDL to use the dummy NULL video driver,
#   so it doesn't need a windowing system.
os.environ["SDL_VIDEODRIVER"] = "dummy"

import pygame as pg

# Some platforms need to init the display for some parts of pg.
pg.display.init()
screen = pg.display.set_mode((1, 1))


def scaleit(fin, fout, w, h):
    i = pg.image.load(fin)

    if hasattr(pg.transform, "smoothscale"):
        scaled_image = pg.transform.smoothscale(i, (w, h))
    else:
        scaled_image = pg.transform.scale(i, (w, h))
    pg.image.save(scaled_image, fout)


def main(fin, fout, w, h):
    """smoothscale image file named fin as fout with new size (w,h)"""
    scaleit(fin, fout, w, h)


if __name__ == "__main__":
    if "-scale" in sys.argv:
        fin, fout, w, h = sys.argv[2:]
        w, h = map(int, [w, h])
        main(fin, fout, w, h)
    else:
        print(usage)
