'''
This file contains the Paddle class that represents a player's paddle.
'''
import pygame
class Paddle:
    def __init__(self, x, y):
        self.width = 10
        self.height = 80
        self.x = x
        self.y = y
        self.speed = 5
        self.rect = pygame.Rect(self.x, self.y - self.height // 2, self.width, self.height)
    def move_up(self):
        self.y -= self.speed
        if self.y < self.height // 2:
            self.y = self.height // 2
    def move_down(self):
        self.y += self.speed
        if self.y > 400 - self.height // 2:
            self.y = 400 - self.height // 2
    def update(self):
        self.rect.y = self.y - self.height // 2
    def draw(self, screen):
        pygame.draw.rect(screen, (255, 255, 255), self.rect)