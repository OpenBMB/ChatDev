""" pg.examples.go_over_there
This simple tech demo is showcasing the use of Vector2.move_towards()
using multiple circles to represent Vectors. Each circle will have a
random position and speed once the demo starts.

Mouse Controls:
* Use the mouse to click on a new target position

Keyboard Controls:
* Press R to restart the demo
"""
import pygame as pg
import random

MIN_SPEED = 0.25
MAX_SPEED = 5
MAX_BALLS = 1600
SCREEN_SIZE = pg.Vector2(1000, 600)
CIRCLE_RADIUS = 5

pg.init()
screen = pg.display.set_mode(SCREEN_SIZE)
clock = pg.time.Clock()

target_position = None
balls = []


class Ball:
    def __init__(self, position, speed):
        self.position = position
        self.speed = speed


def reset():
    global balls
    global target_position

    target_position = None
    balls = []
    for x in range(MAX_BALLS):
        pos = pg.Vector2(
            random.randint(0, SCREEN_SIZE.x), random.randint(0, SCREEN_SIZE.y)
        )
        speed = random.uniform(MIN_SPEED, MAX_SPEED)

        b = Ball(pos, speed)
        balls.append(b)


reset()
delta_time = 0
running = True
while running:
    for event in pg.event.get():
        if event.type == pg.QUIT:
            running = False

        if event.type == pg.MOUSEBUTTONUP:
            target_position = pg.mouse.get_pos()

        if event.type == pg.KEYUP:
            if event.key == pg.K_ESCAPE:
                running = False

            if event.key == pg.K_r:
                reset()

    screen.fill((31, 143, 65))

    for o in balls:
        if target_position is not None:
            try:
                o.position.move_towards_ip(target_position, o.speed * delta_time)
            except AttributeError:
                raise RuntimeError(
                    f"""Version {pg.__version__} doesn't have Vector.move_towards_ip function.
                    Please update to >=2.1.3"""
                )
        pg.draw.circle(screen, (118, 207, 145), o.position, CIRCLE_RADIUS)

    pg.display.flip()
    delta_time = clock.tick(60)
    pg.display.set_caption(
        f"fps: {round(clock.get_fps(), 2)}, ball count: {len(balls)}"
    )

pg.quit()
