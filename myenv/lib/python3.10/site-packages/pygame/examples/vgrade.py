#!/usr/bin/env python
""" pg.examples.vgrade

This example demonstrates creating an image with numpy
python, and displaying that through SDL. You can look at the
method of importing numpy and pg.surfarray. This method
will fail 'gracefully' if it is not available.
I've tried mixing in a lot of comments where the code might
not be self explanatory, nonetheless it may still seem a bit
strange. Learning to use numpy for images like this takes a
bit of learning, but the payoff is extremely fast image
manipulation in python.

For Pygame 1.9.2 and up, this example also showcases a new feature
of surfarray.blit_surface: array broadcasting. If a source array
has either a width or height of 1, the array is repeatedly blitted
to the surface along that dimension to fill the surface. In fact,
a (1, 1) or (1, 1, 3) array results in a simple surface color fill.

Just so you know how this breaks down. For each sampling of
time, 30% goes to each creating the gradient and blitting the
array. The final 40% goes to flipping/updating the display surface

The window will have no border decorations.

The code also demonstrates use of the timer events.
"""


import os
import pygame as pg

try:
    import numpy as np
    import numpy.random as np_random
except ImportError:
    raise SystemExit("This example requires numpy and the pygame surfarray module")

timer = 0


def stopwatch(message=None):
    "simple routine to time python code"
    global timer
    if not message:
        timer = pg.time.get_ticks()
        return
    now = pg.time.get_ticks()
    runtime = (now - timer) / 1000.0 + 0.001
    print(f"{message} {runtime} seconds\t{(1.0 / runtime):.2f}fps")
    timer = now


def VertGradientColumn(surf, topcolor, bottomcolor):
    "creates a new 3d vertical gradient array"
    topcolor = np.array(topcolor, copy=False)
    bottomcolor = np.array(bottomcolor, copy=False)
    diff = bottomcolor - topcolor
    width, height = surf.get_size()
    # create array from 0.0 to 1.0 triplets
    column = np.arange(height, dtype="float") / height
    column = np.repeat(column[:, np.newaxis], [3], 1)
    # create a single column of gradient
    column = topcolor + (diff * column).astype("int")
    # make the column a 3d image column by adding X
    column = column.astype("uint8")[np.newaxis, :, :]
    # 3d array into 2d array
    return pg.surfarray.map_array(surf, column)


def DisplayGradient(surf):
    "choose random colors and show them"
    stopwatch()
    colors = np_random.randint(0, 255, (2, 3))
    column = VertGradientColumn(surf, colors[0], colors[1])
    pg.surfarray.blit_array(surf, column)
    pg.display.flip()
    stopwatch("Gradient:")


def main():
    pg.init()
    pg.mixer.quit()  # remove ALSA underflow messages for Debian squeeze
    size = 600, 400
    os.environ["SDL_VIDEO_CENTERED"] = "1"
    screen = pg.display.set_mode(size, pg.NOFRAME, 0)

    pg.event.set_blocked(pg.MOUSEMOTION)  # keep our queue cleaner
    pg.time.set_timer(pg.USEREVENT, 500)

    while True:
        event = pg.event.wait()
        if event.type in (pg.QUIT, pg.KEYDOWN, pg.MOUSEBUTTONDOWN):
            break
        elif event.type == pg.USEREVENT:
            DisplayGradient(screen)

    pg.quit()


if __name__ == "__main__":
    main()
