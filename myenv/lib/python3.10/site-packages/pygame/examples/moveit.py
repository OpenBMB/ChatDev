#!/usr/bin/env python
""" pygame.examples.moveit

This is the full and final example from the Pygame Tutorial,
"How Do I Make It Move". It creates 10 objects and animates
them on the screen.

It also has a separate player character that can be controlled with arrow keys.

Note it's a bit scant on error checking, but it's easy to read. :]
Fortunately, this is python, and we needn't wrestle with a pile of
error codes.
"""
import os
import pygame as pg

main_dir = os.path.split(os.path.abspath(__file__))[0]

# Height and Width of screen
WIDTH = 640
HEIGHT = 480
# Height and width of the sprite
SPRITE_WIDTH = 80
SPRITE_HEIGHT = 60


# our game object class
class GameObject:
    def __init__(self, image, height, speed):
        self.speed = speed
        self.image = image
        self.pos = image.get_rect().move(0, height)

    # move the object.
    def move(self, up=False, down=False, left=False, right=False):
        if right:
            self.pos.right += self.speed
        if left:
            self.pos.right -= self.speed
        if down:
            self.pos.top += self.speed
        if up:
            self.pos.top -= self.speed

        # controls the object such that it cannot leave the screen's viewpoint
        if self.pos.right > WIDTH:
            self.pos.left = 0
        if self.pos.top > HEIGHT - SPRITE_HEIGHT:
            self.pos.top = 0
        if self.pos.right < SPRITE_WIDTH:
            self.pos.right = WIDTH
        if self.pos.top < 0:
            self.pos.top = HEIGHT - SPRITE_HEIGHT


# quick function to load an image
def load_image(name):
    path = os.path.join(main_dir, "data", name)
    return pg.image.load(path).convert()


# here's the full code
def main():
    pg.init()
    clock = pg.time.Clock()
    screen = pg.display.set_mode((WIDTH, HEIGHT))

    player = load_image("player1.gif")
    entity = load_image("alien1.gif")
    background = load_image("liquid.bmp")

    # scale the background image so that it fills the window and
    # successfully overwrites the old sprite position.
    background = pg.transform.scale2x(background)
    background = pg.transform.scale2x(background)

    screen.blit(background, (0, 0))

    objects = []
    p = GameObject(player, 10, 3)
    for x in range(10):
        o = GameObject(entity, x * 40, x)
        objects.append(o)

    pg.display.set_caption("Move It!")

    # This is a simple event handler that enables player input.
    while True:
        # Get all keys currently pressed, and move when an arrow key is held.
        keys = pg.key.get_pressed()
        if keys[pg.K_UP]:
            p.move(up=True)
        if keys[pg.K_DOWN]:
            p.move(down=True)
        if keys[pg.K_LEFT]:
            p.move(left=True)
        if keys[pg.K_RIGHT]:
            p.move(right=True)

        # Draw the background
        screen.blit(background, (0, 0))
        for e in pg.event.get():
            # quit upon screen exit
            if e.type == pg.QUIT:
                return
        for o in objects:
            screen.blit(background, o.pos, o.pos)
        for o in objects:
            o.move(right=True)
            screen.blit(o.image, o.pos)
        screen.blit(p.image, p.pos)
        clock.tick(60)
        pg.display.update()
        pg.time.delay(100)


if __name__ == "__main__":
    main()
    pg.quit()
