#!/usr/bin/env python
""" pygame.examples.freetype_misc


Miscellaneous (or misc) means:
  "consisting of a mixture of various things that are not
   usually connected with each other"
   Adjective


All those words you read on computers, magazines, books, and such over the years?
Probably a lot of them were constructed with...

The FreeType Project:  a free, high-quality and portable Font engine.
https://freetype.org

Next time you're reading something. Think of them.


Herein lies a *BOLD* demo consisting of a mixture of various things.

        Not only is it a *BOLD* demo, it's an
        italics demo,
        a rotated demo,
        it's a blend,
        and is sized to go nicely with a cup of tea*.

        * also goes well with coffee.

Enjoy!
"""
import os
import pygame as pg
import pygame.freetype as freetype


def run():
    pg.init()

    fontdir = os.path.dirname(os.path.abspath(__file__))
    font = freetype.Font(os.path.join(fontdir, "data", "sans.ttf"))

    screen = pg.display.set_mode((800, 600))
    screen.fill("gray")

    font.underline_adjustment = 0.5
    font.pad = True
    font.render_to(
        screen,
        (32, 32),
        "Hello World",
        "red3",
        "dimgray",
        size=64,
        style=freetype.STYLE_UNDERLINE | freetype.STYLE_OBLIQUE,
    )
    font.pad = False

    font.render_to(
        screen,
        (32, 128),
        "abcdefghijklm",
        "dimgray",
        "green3",
        size=64,
    )

    font.vertical = True
    font.render_to(screen, (32, 200), "Vertical?", "blue3", None, size=32)
    font.vertical = False

    font.render_to(screen, (64, 190), "Let's spin!", "red3", None, size=48, rotation=55)

    font.render_to(
        screen, (160, 290), "All around!", "green3", None, size=48, rotation=-55
    )

    font.render_to(screen, (250, 220), "and BLEND", (255, 0, 0, 128), None, size=64)

    font.render_to(screen, (265, 237), "or BLAND!", (0, 0xCC, 28, 128), None, size=64)

    # Some pinwheels
    font.origin = True
    for angle in range(0, 360, 45):
        font.render_to(screen, (150, 420), ")", "black", size=48, rotation=angle)
    font.vertical = True
    for angle in range(15, 375, 30):
        font.render_to(screen, (600, 400), "|^*", "orange", size=48, rotation=angle)
    font.vertical = False
    font.origin = False

    utext = "I \u2665 Unicode"
    font.render_to(screen, (298, 320), utext, (0, 0xCC, 0xDD), None, size=64)

    utext = "\u2665"
    font.render_to(screen, (480, 32), utext, "gray", "red3", size=148)

    font.render_to(
        screen,
        (380, 380),
        "...yes, this is an SDL surface",
        "black",
        None,
        size=24,
        style=freetype.STYLE_STRONG,
    )

    font.origin = True
    r = font.render_to(
        screen,
        (100, 530),
        "stretch",
        "red3",
        None,
        size=(24, 24),
        style=freetype.STYLE_NORMAL,
    )
    font.render_to(
        screen,
        (100 + r.width, 530),
        " VERTICAL",
        "red3",
        None,
        size=(24, 48),
        style=freetype.STYLE_NORMAL,
    )

    r = font.render_to(
        screen,
        (100, 580),
        "stretch",
        "blue3",
        None,
        size=(24, 24),
        style=freetype.STYLE_NORMAL,
    )
    font.render_to(
        screen,
        (100 + r.width, 580),
        " HORIZONTAL",
        "blue3",
        None,
        size=(48, 24),
        style=freetype.STYLE_NORMAL,
    )

    pg.display.flip()

    while True:
        if pg.event.wait().type in (pg.QUIT, pg.KEYDOWN, pg.MOUSEBUTTONDOWN):
            break

    pg.quit()


if __name__ == "__main__":
    run()
