'''
This file contains the Powerup class which represents the powerups in the game.
'''
import pygame
class Powerup:
    def __init__(self, x, y, width, height):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
    def update(self):
        self.x -= 5
    def draw(self, screen):
        pygame.draw.rect(screen, (0, 0, 255), (self.x, self.y, self.width, self.height))