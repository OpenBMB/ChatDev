'''
Track class for managing the racing environment with improved visuals and clear boundaries
'''
import pygame
class Track:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.line_spacing = 100
        self.line_height = 30
        self.line_speed = 5
        self.lines = []
        self.initialize_lines()
        self.road_left = self.width//3
        self.road_right = 2*self.width//3 + 20
    def initialize_lines(self):
        for y in range(0, self.height, self.line_spacing):
            self.lines.append(y)
    def update(self):
        self.lines = [(y + self.line_speed) % self.height for y in self.lines]
    def draw(self, screen):
        # Draw road background
        pygame.draw.rect(screen, (50, 50, 50), 
                        (self.road_left, 0, self.road_right - self.road_left, self.height))
        # Draw road borders
        pygame.draw.rect(screen, (255, 255, 0), (self.road_left - 5, 0, 5, self.height))  # Left border
        pygame.draw.rect(screen, (255, 255, 0), (self.road_right, 0, 5, self.height))  # Right border
        # Draw road lines
        for y in self.lines:
            pygame.draw.rect(screen, (255, 255, 255), 
                           (self.width//2 - 10, y, 20, self.line_height))