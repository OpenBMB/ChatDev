'''
This file contains the Enemy class which represents the enemy spaceships.
'''
import pygame
class Enemy:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.width = 64
        self.height = 64
        self.speed = 2
    def update(self):
        self.y += self.speed
        # Reverse direction if enemy reaches screen bounds
        if self.y > 600:
            self.y = 0
    def draw(self, screen):
        pygame.draw.rect(screen, (255, 0, 0), (self.x, self.y, self.width, self.height))