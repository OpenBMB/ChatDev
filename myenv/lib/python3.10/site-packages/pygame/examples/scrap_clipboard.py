#!/usr/bin/env python
""" pygame.examples.scrap_clipboard

Demonstrates the clipboard capabilities of pygame.

Copy/paste!


Keyboard Controls
-----------------

g - get and print types in clipboard. If, image blit to screen.
p - place some text into clipboard
a - print types available in the clipboard
i - put image into the clipboard
"""
import os

import pygame as pg
import pygame.scrap as scrap

from io import BytesIO


def usage():
    print("Press the 'g' key to get all of the current clipboard data")
    print("Press the 'p' key to put a string into the clipboard")
    print("Press the 'a' key to get a list of the currently available types")
    print("Press the 'i' key to put an image into the clipboard")


main_dir = os.path.split(os.path.abspath(__file__))[0]

pg.init()
screen = pg.display.set_mode((200, 200))
c = pg.time.Clock()
going = True

# Initialize the scrap module and use the clipboard mode.
scrap.init()
scrap.set_mode(pg.SCRAP_CLIPBOARD)

usage()

while going:
    for e in pg.event.get():
        if e.type == pg.QUIT or (e.type == pg.KEYDOWN and e.key == pg.K_ESCAPE):
            going = False

        elif e.type == pg.KEYDOWN and e.key == pg.K_g:
            # This means to look for data.
            print("Getting the different clipboard data..")
            for t in scrap.get_types():
                r = scrap.get(t)
                if r and len(r) > 500:
                    print(f"Type {t} : (large {len(r)} byte buffer)")
                elif r is None:
                    print(f"Type {t} : None")
                else:
                    print(f"Type {t} : '{r.decode('ascii', 'ignore')}'")
                if "image" in t:
                    namehint = t.split("/")[1]
                    if namehint in ["bmp", "png", "jpg"]:
                        f = BytesIO(r)
                        loaded_surf = pg.image.load(f, "." + namehint)
                        screen.blit(loaded_surf, (0, 0))

        elif e.type == pg.KEYDOWN and e.key == pg.K_p:
            # Place some text into the selection.
            print("Placing clipboard text.")
            scrap.put(pg.SCRAP_TEXT, b"Hello. This is a message from scrap.")

        elif e.type == pg.KEYDOWN and e.key == pg.K_a:
            # Get all available types.
            print("Getting the available types from the clipboard.")
            types = scrap.get_types()
            print(types)
            if len(types) > 0:
                print(f"Contains {types[0]}: {scrap.contains(types[0])}")
                print("Contains _INVALID_: ", scrap.contains("_INVALID_"))

        elif e.type == pg.KEYDOWN and e.key == pg.K_i:
            print("Putting image into the clipboard.")
            scrap.set_mode(pg.SCRAP_CLIPBOARD)
            fp = open(os.path.join(main_dir, "data", "liquid.bmp"), "rb")
            buf = fp.read()
            scrap.put("image/bmp", buf)
            fp.close()

        elif e.type in (pg.KEYDOWN, pg.MOUSEBUTTONDOWN):
            usage()
    pg.display.flip()
    c.tick(40)
pg.quit()
