'''
This file contains the Bullet class which represents the bullets fired by the player.
'''
import pygame
class Bullet:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.width = 8
        self.height = 16
        self.speed = 10
    def update(self):
        self.y -= self.speed
    def draw(self, screen):
        pygame.draw.rect(screen, (0, 255, 0), (self.x, self.y, self.width, self.height))
    def collides_with(self, enemy):
        return pygame.Rect(self.x, self.y, self.width, self.height).colliderect(
            pygame.Rect(enemy.x, enemy.y, enemy.width, enemy.height)
        )
    def collides_with_any(self, enemies):
        for enemy in enemies:
            if self.collides_with(enemy):
                return True
        return False