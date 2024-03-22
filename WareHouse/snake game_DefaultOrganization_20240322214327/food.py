'''
This file contains the Food class.
'''
import pygame
import random
class Food:
    def __init__(self, window_width, window_height):
        self.window_width = window_width
        self.window_height = window_height
        self.size = 20
        self.generate()
    def generate(self):
        self.x = random.randint(0, self.window_width - self.size)
        self.y = random.randint(0, self.window_height - self.size)
    def draw(self, window):
        pygame.draw.rect(window, (255, 0, 0), (self.x, self.y, self.size, self.size))