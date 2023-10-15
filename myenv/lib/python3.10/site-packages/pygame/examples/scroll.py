#!/usr/bin/env python
""" pygame.examples.scroll

An zoomed image viewer that demonstrates Surface.scroll

This example shows a scrollable image that has a zoom factor of eight.
It uses the Surface.scroll function to shift the image on the display
surface. A clip rectangle protects a margin area. If called as a function,
the example accepts an optional image file path. If run as a program
it takes an optional file path command line argument. If no file
is provided a default image file is used.

When running click on a black triangle to move one pixel in the direction
the triangle points. Or use the arrow keys. Close the window or press ESC
to quit.
"""
import sys
import os

import pygame as pg
from pygame.transform import scale

main_dir = os.path.dirname(os.path.abspath(__file__))


DIR_UP = 1
DIR_DOWN = 2
DIR_LEFT = 3
DIR_RIGHT = 4

zoom_factor = 8


def draw_arrow(surf, color, posn, direction: int):
    x, y = posn
    if direction == DIR_UP:
        pointlist = ((x - 29, y + 30), (x + 30, y + 30), (x + 1, y - 29), (x, y - 29))
    elif direction == DIR_DOWN:
        pointlist = ((x - 29, y - 29), (x + 30, y - 29), (x + 1, y + 30), (x, y + 30))
    elif direction == DIR_LEFT:
        pointlist = ((x + 30, y - 29), (x + 30, y + 30), (x - 29, y + 1), (x - 29, y))
    else:
        pointlist = ((x - 29, y - 29), (x - 29, y + 30), (x + 30, y + 1), (x + 30, y))
    pg.draw.polygon(surf, color, pointlist)


def add_arrow_button(screen, regions, posn, direction):
    draw_arrow(screen, "black", posn, direction)
    draw_arrow(regions, (direction, 0, 0), posn, direction)


def scroll_view(screen, image: pg.Surface, direction: int, view_rect):
    src_rect = None
    dst_rect = None
    zoom_view_rect = screen.get_clip()
    image_w, image_h = image.get_size()
    if direction == DIR_UP:
        if view_rect.top > 0:
            screen.scroll(dy=zoom_factor)
            view_rect.move_ip(0, -1)
            src_rect = view_rect.copy()
            src_rect.h = 1
            dst_rect = zoom_view_rect.copy()
            dst_rect.h = zoom_factor
    elif direction == DIR_DOWN:
        if view_rect.bottom < image_h:
            screen.scroll(dy=-zoom_factor)
            view_rect.move_ip(0, 1)
            src_rect = view_rect.copy()
            src_rect.h = 1
            src_rect.bottom = view_rect.bottom
            dst_rect = zoom_view_rect.copy()
            dst_rect.h = zoom_factor
            dst_rect.bottom = zoom_view_rect.bottom
    elif direction == DIR_LEFT:
        if view_rect.left > 0:
            screen.scroll(dx=zoom_factor)
            view_rect.move_ip(-1, 0)
            src_rect = view_rect.copy()
            src_rect.w = 1
            dst_rect = zoom_view_rect.copy()
            dst_rect.w = zoom_factor
    elif direction == DIR_RIGHT:
        if view_rect.right < image_w:
            screen.scroll(dx=-zoom_factor)
            view_rect.move_ip(1, 0)
            src_rect = view_rect.copy()
            src_rect.w = 1
            src_rect.right = view_rect.right
            dst_rect = zoom_view_rect.copy()
            dst_rect.w = zoom_factor
            dst_rect.right = zoom_view_rect.right

    if src_rect is not None and dst_rect is not None:
        scale(image.subsurface(src_rect), dst_rect.size, screen.subsurface(dst_rect))
        pg.display.update(zoom_view_rect)


def main(image_file=None):
    if image_file is None:
        image_file = os.path.join(main_dir, "data", "arraydemo.bmp")
    margin = 80
    view_size = (30, 20)
    zoom_view_size = (view_size[0] * zoom_factor, view_size[1] * zoom_factor)
    win_size = (zoom_view_size[0] + 2 * margin, zoom_view_size[1] + 2 * margin)
    background_color = pg.Color("beige")

    pg.init()
    pg.display.set_caption("Scroll Example")

    # set up key repeating so we can hold down the key to scroll.
    old_k_delay, old_k_interval = pg.key.get_repeat()
    pg.key.set_repeat(500, 30)

    try:
        screen = pg.display.set_mode(win_size)
        screen.fill(background_color)
        pg.display.flip()

        image = pg.image.load(image_file).convert()
        image_w, image_h = image.get_size()

        if image_w < view_size[0] or image_h < view_size[1]:
            print("The source image is too small for this example.")
            print("A %i by %i or larger image is required." % zoom_view_size)
            return

        regions = pg.Surface(win_size, 0, 24)
        add_arrow_button(screen, regions, (40, win_size[1] // 2), DIR_LEFT)
        add_arrow_button(
            screen, regions, (win_size[0] - 40, win_size[1] // 2), DIR_RIGHT
        )
        add_arrow_button(screen, regions, (win_size[0] // 2, 40), DIR_UP)
        add_arrow_button(
            screen, regions, (win_size[0] // 2, win_size[1] - 40), DIR_DOWN
        )
        pg.display.flip()

        screen.set_clip((margin, margin, zoom_view_size[0], zoom_view_size[1]))

        view_rect = pg.Rect(0, 0, view_size[0], view_size[1])

        scale(
            image.subsurface(view_rect),
            zoom_view_size,
            screen.subsurface(screen.get_clip()),
        )
        pg.display.flip()

        # the direction we will scroll in.
        direction = None

        clock = pg.time.Clock()
        clock.tick()

        going = True

        while going:
            # wait for events before doing anything.
            # events = [pg.event.wait()] + pg.event.get()
            events = pg.event.get()

            # During the loop, if a key is held, scroll the view.
            keys = pg.key.get_pressed()
            if keys[pg.K_UP]:
                scroll_view(screen, image, DIR_UP, view_rect)
            if keys[pg.K_DOWN]:
                scroll_view(screen, image, DIR_DOWN, view_rect)
            if keys[pg.K_LEFT]:
                scroll_view(screen, image, DIR_LEFT, view_rect)
            if keys[pg.K_RIGHT]:
                scroll_view(screen, image, DIR_RIGHT, view_rect)

            for e in events:
                # quit if the event is quit.
                if e.type == pg.QUIT:
                    going = False

                # handle mouse button presses on arrows.
                elif e.type == pg.MOUSEBUTTONDOWN:
                    direction = regions.get_at(e.pos)[0]

                elif e.type == pg.MOUSEBUTTONUP:
                    direction = None

            if direction:
                scroll_view(screen, image, direction, view_rect)
            clock.tick(30)

    finally:
        pg.key.set_repeat(old_k_delay, old_k_interval)
        pg.quit()


if __name__ == "__main__":
    image_file = sys.argv[1] if len(sys.argv) > 1 else None
    main(image_file)
