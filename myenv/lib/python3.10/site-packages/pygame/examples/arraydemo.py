#!/usr/bin/env python
""" pygame.examples.arraydemo

Welcome to the arraydemo!

Use the numpy array package to manipulate pixels.

This demo will show you a few things:

* scale up, scale down, flip,
* cross fade
* soften
* put stripes on it!

"""

import os

import pygame as pg
from pygame import surfarray

main_dir = os.path.split(os.path.abspath(__file__))[0]


def surfdemo_show(array_img, name):
    "displays a surface, waits for user to continue"
    screen = pg.display.set_mode(array_img.shape[:2], 0, 32)
    surfarray.blit_array(screen, array_img)
    pg.display.flip()
    pg.display.set_caption(name)
    while True:
        e = pg.event.wait()
        # Force application to only advance when main button is released
        if e.type == pg.MOUSEBUTTONUP and e.button == pg.BUTTON_LEFT:
            break
        elif e.type == pg.KEYDOWN and e.key == pg.K_s:
            pg.image.save(screen, name + ".png")
        elif e.type == pg.QUIT:
            pg.quit()
            raise SystemExit()


def main():
    """show various surfarray effects"""
    import numpy as np
    from numpy import int32, uint

    pg.init()

    print("Using Numpy")
    print("Press the left mouse button to advance image.")
    print('Press the "s" key to save the current image.')

    # allblack
    allblack = np.zeros((128, 128), int32)
    surfdemo_show(allblack, "allblack")

    # striped
    # the element type is required for np.zeros in numpy else
    # an array of float is returned.
    striped = np.zeros((128, 128, 3), int32)
    striped[:] = (255, 0, 0)
    striped[:, ::3] = (0, 255, 255)
    surfdemo_show(striped, "striped")

    # rgbarray
    imagename = os.path.join(main_dir, "data", "arraydemo.bmp")
    imgsurface = pg.image.load(imagename)
    rgbarray = surfarray.array3d(imgsurface)
    surfdemo_show(rgbarray, "rgbarray")

    # flipped
    flipped = rgbarray[:, ::-1]
    surfdemo_show(flipped, "flipped")

    # scaledown
    scaledown = rgbarray[::2, ::2]
    surfdemo_show(scaledown, "scaledown")

    # scaleup
    # the element type is required for np.zeros in numpy else
    # an #array of floats is returned.
    shape = rgbarray.shape
    scaleup = np.zeros((shape[0] * 2, shape[1] * 2, shape[2]), int32)
    scaleup[::2, ::2, :] = rgbarray
    scaleup[1::2, ::2, :] = rgbarray
    scaleup[:, 1::2] = scaleup[:, ::2]
    surfdemo_show(scaleup, "scaleup")

    # redimg
    redimg = np.array(rgbarray)
    redimg[:, :, 1:] = 0
    surfdemo_show(redimg, "redimg")

    # soften
    # having factor as an array forces integer upgrade during multiplication
    # of rgbarray, even for numpy.
    factor = np.array((8,), int32)
    soften = np.array(rgbarray, int32)
    soften[1:, :] += rgbarray[:-1, :] * factor
    soften[:-1, :] += rgbarray[1:, :] * factor
    soften[:, 1:] += rgbarray[:, :-1] * factor
    soften[:, :-1] += rgbarray[:, 1:] * factor
    soften //= 33
    surfdemo_show(soften, "soften")

    # crossfade (50%)
    src = np.array(rgbarray)
    dest = np.zeros(rgbarray.shape)  # dest is float64 by default.
    dest[:] = 20, 50, 100
    diff = (dest - src) * 0.50
    xfade = src + diff.astype(uint)
    surfdemo_show(xfade, "xfade")

    # all done
    pg.quit()


if __name__ == "__main__":
    main()
