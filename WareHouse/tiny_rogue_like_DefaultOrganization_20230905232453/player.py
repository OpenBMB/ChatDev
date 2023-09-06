'''
Player class for managing the player character.
'''
import pygame
import random
class Player:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.width = 10
        self.height = 10
        self.rect = pygame.Rect(self.x, self.y, self.width, self.height)
        self.hp = 100
    def move(self, dx, dy):
        self.x += dx
        self.y += dy
        self.rect.x = self.x
        self.rect.y = self.y
    def update(self, level):
        dx, dy = 0, 0
        if level.is_wall(self.x + dx, self.y + dy):
            self.x -= dx
            self.y -= dy
            self.rect.x = self.x
            self.rect.y = self.y
        elif level.is_door(self.x, self.y):
            level.next_level(self)
        elif level.is_treasure(self.x, self.y):
            self.hp += random.randint(20, 30)
    def draw(self, screen):
        pygame.draw.rect(screen, (255, 0, 0), self.rect)