#!/usr/bin/env python
""" pygame.examples.fonty

Here we load a .TTF True Type font file, and display it in
a basic pygame window.

Demonstrating several Font object attributes.

- basic window, event, and font management.
"""
import pygame as pg


def main():
    # initialize
    pg.init()
    resolution = 400, 200
    screen = pg.display.set_mode(resolution)

    ##    pg.mouse.set_cursor(*pg.cursors.diamond)

    fg = 250, 240, 230
    bg = 5, 5, 5
    wincolor = 40, 40, 90

    # fill background
    screen.fill(wincolor)

    # load font, prepare values
    font = pg.font.Font(None, 80)
    text = "Fonty"
    size = font.size(text)

    # no AA, no transparency, normal
    ren = font.render(text, 0, fg, bg)
    screen.blit(ren, (10, 10))

    # no AA, transparency, underline
    font.set_underline(1)
    ren = font.render(text, 0, fg)
    screen.blit(ren, (10, 40 + size[1]))
    font.set_underline(0)

    a_sys_font = pg.font.SysFont("Arial", 60)

    # AA, no transparency, bold
    a_sys_font.set_bold(1)
    ren = a_sys_font.render(text, 1, fg, bg)
    screen.blit(ren, (30 + size[0], 10))
    a_sys_font.set_bold(0)

    # AA, transparency, italic
    a_sys_font.set_italic(1)
    ren = a_sys_font.render(text, 1, fg)
    screen.blit(ren, (30 + size[0], 40 + size[1]))
    a_sys_font.set_italic(0)

    # Get some metrics.
    print(f"Font metrics for 'Fonty':  {a_sys_font.metrics(text)}")
    ch = "\u3060"
    msg = f"Font metrics for '{ch}':  {a_sys_font.metrics(ch)}"
    print(msg)

    ## #some_japanese_unicode = u"\u304b\u3070\u306b"
    ##some_japanese_unicode = unicode_('%c%c%c') % (0x304b, 0x3070, 0x306b)

    # AA, transparency, italic
    ##ren = a_sys_font.render(some_japanese_unicode, 1, fg)
    ##screen.blit(ren, (30 + size[0], 40 + size[1]))

    # show the surface and await user quit
    pg.display.flip()
    while True:
        # use event.wait to keep from polling 100% cpu
        if pg.event.wait().type in (pg.QUIT, pg.KEYDOWN, pg.MOUSEBUTTONDOWN):
            break
    pg.quit()


if __name__ == "__main__":
    main()
