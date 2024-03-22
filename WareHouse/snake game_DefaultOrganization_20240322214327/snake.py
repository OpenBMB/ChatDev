'''
This file contains the Snake class.
'''
import pygame
class Snake:
    def __init__(self, window_width, window_height):
        self.window_width = window_width
        self.window_height = window_height
        self.size = 20
        self.x = window_width // 2
        self.y = window_height // 2
        self.dx = self.size
        self.dy = 0
        self.body = [(self.x, self.y)]
    def handle_movement(self):
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT] and self.dx != self.size:
            self.dx = -self.size
            self.dy = 0
        elif keys[pygame.K_RIGHT] and self.dx != -self.size:
            self.dx = self.size
            self.dy = 0
        elif keys[pygame.K_UP] and self.dy != self.size:
            self.dx = 0
            self.dy = -self.size
        elif keys[pygame.K_DOWN] and self.dy != -self.size:
            self.dx = 0
            self.dy = self.size
        self.x += self.dx
        self.y += self.dy
        # Update the snake's body
        self.body.insert(0, (self.x, self.y))
        if len(self.body) > 1:
            self.body.pop()
    def draw(self, window):
        for segment in self.body:
            pygame.draw.rect(window, (0, 255, 0), (segment[0], segment[1], self.size, self.size))
    def check_collision(self, food):
        return self.x == food.x and self.y == food.y
    def grow(self):
        self.body.append((self.x, self.y))
    def check_collision_boundaries(self):
        return self.x < 0 or self.x >= self.window_width or self.y < 0 or self.y >= self.window_height
    def check_collision_self(self):
        return (self.x, self.y) in self.body[1:]