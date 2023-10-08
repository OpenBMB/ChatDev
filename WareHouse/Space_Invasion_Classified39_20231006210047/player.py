'''
This file contains the Player class which represents the player's spaceship.
'''
import pygame
class Player:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.width = 64
        self.height = 64
        self.speed = 5
    def update(self):
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT]:
            self.x -= self.speed
        if keys[pygame.K_RIGHT]:
            self.x += self.speed
        # Keep the player within the screen bounds
        if self.x < 0:
            self.x = 0
        if self.x > 800 - self.width:
            self.x = 800 - self.width
    def draw(self, screen):
        pygame.draw.rect(screen, (255, 255, 255), (self.x, self.y, self.width, self.height))