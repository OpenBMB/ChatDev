'''
This file contains the Obstacle class which represents the obstacles in the game.
'''
import pygame
class Obstacle:
    def __init__(self, x, y, width, height):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
    def update(self):
        self.x -= 5
    def draw(self, screen):
        pygame.draw.rect(screen, (0, 255, 0), (self.x, self.y, self.width, self.height))