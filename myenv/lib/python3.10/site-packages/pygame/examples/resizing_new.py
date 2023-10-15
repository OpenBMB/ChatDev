#!/usr/bin/env python
import pygame as pg

pg.init()

RES = (160, 120)
FPS = 30
clock = pg.time.Clock()

screen = pg.display.set_mode(RES, pg.RESIZABLE)
pg.display._set_autoresize(False)

# MAIN LOOP

done = False

i = 0
j = 0

while not done:
    for event in pg.event.get():
        if event.type == pg.KEYDOWN and event.key == pg.K_q:
            done = True
        if event.type == pg.QUIT:
            done = True
        # if event.type==pg.WINDOWRESIZED:
        #    screen=pg.display.get_surface()
        if event.type == pg.VIDEORESIZE:
            screen = pg.display.get_surface()
    i += 1
    i = i % screen.get_width()
    j += i % 2
    j = j % screen.get_height()

    screen.fill((255, 0, 255))
    pg.draw.circle(screen, (0, 0, 0), (100, 100), 20)
    pg.draw.circle(screen, (0, 0, 200), (0, 0), 10)
    pg.draw.circle(screen, (200, 0, 0), (160, 120), 30)
    pg.draw.line(screen, (250, 250, 0), (0, 120), (160, 0))
    pg.draw.circle(screen, (255, 255, 255), (i, j), 5)

    pg.display.flip()
    clock.tick(FPS)
pg.quit()
