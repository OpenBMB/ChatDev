#!/usr/bin/env python
""" pg.examples.video

Experimental!

* dialog message boxes with messagebox.
* multiple windows with Window
* driver selection
* Renderer, Texture, and Image classes
* Drawing lines, rects, and such onto Renderers.
"""
import os
import pygame as pg
from pygame._sdl2 import Window, Texture, Image, Renderer, get_drivers, messagebox

data_dir = os.path.join(os.path.split(os.path.abspath(__file__))[0], "data")


def load_img(file):
    return pg.image.load(os.path.join(data_dir, file))


pg.display.init()
pg.key.set_repeat(1000, 10)

for driver in get_drivers():
    print(driver)

import random

try:
    answer = messagebox(
        "I will open two windows! Continue?",
        "Hello!",
        info=True,
        buttons=("Yes", "No", "Chance"),
        return_button=0,
        escape_button=1,
    )
    if answer == 1 or (answer == 2 and random.random() < 0.5):
        import sys

        sys.exit(0)
except:
    pass

win = Window("asdf", resizable=True)
renderer = Renderer(win)
tex = Texture.from_surface(renderer, load_img("alien1.gif"))
img = Image(tex)

running = True

x, y = 250, 50
clock = pg.time.Clock()

backgrounds = [(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255)]
bg_index = 0

renderer.draw_color = backgrounds[bg_index]

win2 = Window("2nd window", size=(256, 256), always_on_top=True)
win2.opacity = 0.5
win2.set_icon(load_img("bomb.gif"))
renderer2 = Renderer(win2)
tex2 = Texture.from_surface(renderer2, load_img("asprite.bmp"))
renderer2.clear()
tex2.draw()
renderer2.present()
del tex2

full = 0

surf = pg.Surface((64, 64))
streamtex = Texture(renderer, (64, 64), streaming=True)
tex_update_interval = 1000
next_tex_update = pg.time.get_ticks()


while running:
    for event in pg.event.get():
        if event.type == pg.QUIT:
            running = False
        elif getattr(event, "window", None) == win2:
            if (
                event.type == pg.KEYDOWN
                and event.key == pg.K_ESCAPE
                or event.type == pg.WINDOWCLOSE
            ):
                win2.destroy()
        elif event.type == pg.KEYDOWN:
            if event.key == pg.K_ESCAPE:
                running = False
            elif event.key == pg.K_LEFT:
                x -= 5
            elif event.key == pg.K_RIGHT:
                x += 5
            elif event.key == pg.K_DOWN:
                y += 5
            elif event.key == pg.K_UP:
                y -= 5
            elif event.key == pg.K_f:
                if full == 0:
                    win.set_fullscreen(True)
                    full = 1
                else:
                    win.set_windowed()
                    full = 0
            elif event.key == pg.K_s:
                readsurf = renderer.to_surface()
                pg.image.save(readsurf, "test.png")

            elif event.key == pg.K_SPACE:
                bg_index = (bg_index + 1) % len(backgrounds)
                renderer.draw_color = backgrounds[bg_index]

    renderer.clear()

    # update texture
    curtime = pg.time.get_ticks()
    if curtime >= next_tex_update:
        for x_ in range(streamtex.width // 4):
            for y_ in range(streamtex.height // 4):
                newcol = (
                    random.randint(0, 255),
                    random.randint(0, 255),
                    random.randint(0, 255),
                    255,
                )
                area = (4 * x_, 4 * y_, 4, 4)
                surf.fill(newcol, area)
        streamtex.update(surf)
        next_tex_update = curtime + tex_update_interval
    streamtex.draw(dstrect=pg.Rect(64, 128, 64, 64))

    img.draw(dstrect=(x, y))

    # TODO: should these be?
    # - line instead of draw_line
    # - point instead of draw_point
    # - rect(rect, width=1)->draw 1 pixel, instead of draw_rect
    # - rect(rect, width=0)->filled ? , instead of fill_rect
    #
    # TODO: should these work with pg.draw.line(renderer, ...) functions?
    renderer.draw_color = (255, 255, 255, 255)
    renderer.draw_line((0, 0), (64, 64))
    renderer.draw_line((64, 64), (128, 0))
    renderer.draw_point((72, 32))
    renderer.draw_rect(pg.Rect(0, 64, 64, 64))
    renderer.fill_rect(pg.Rect(0, 128, 64, 64))
    renderer.draw_color = backgrounds[bg_index]

    renderer.present()

    clock.tick(60)
    win.title = str(f"FPS: {clock.get_fps()}")

pg.quit()
