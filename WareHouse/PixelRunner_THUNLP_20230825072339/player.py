'''
This file contains the Player class which represents the player character.
'''
import pygame
class Player:
    def __init__(self):
        self.width = 50
        self.height = 50
        self.x = 100
        self.y = 400
        self.velocity = 0
        self.is_jumping = False
        self.is_sliding = False
    def jump(self):
        if not self.is_jumping and not self.is_sliding:
            self.velocity = -10
            self.is_jumping = True
    def slide(self):
        if not self.is_jumping and not self.is_sliding:
            self.height = 25
            self.y += 25
            self.is_sliding = True
    def update(self):
        if self.is_jumping:
            self.velocity += 0.5
            self.y += self.velocity
            if self.y >= 400:
                self.y = 400
                self.velocity = 0
                self.is_jumping = False
        elif self.is_sliding:
            self.height = 50
            self.y -= 25
            self.is_sliding = False
    def draw(self, screen):
        pygame.draw.rect(screen, (255, 0, 0), (self.x, self.y, self.width, self.height))