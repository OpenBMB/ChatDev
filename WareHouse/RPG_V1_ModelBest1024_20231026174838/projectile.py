'''
This file contains the Projectile class.
'''
import pygame
class Projectile:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.width = 10
        self.height = 10
        self.velocity = 10
    def update(self):
        self.y -= self.velocity
    def draw(self, window):
        pygame.draw.rect(window, (0, 255, 0), (self.x, self.y, self.width, self.height))