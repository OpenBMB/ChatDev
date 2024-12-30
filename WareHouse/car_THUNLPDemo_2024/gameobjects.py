'''
Game objects implementation including opponent cars with improved visuals and road constraints
'''
import pygame
import random
class OpponentCar:
    def __init__(self, screen_width):
        self.width = 40
        self.height = 60
        self.screen_width = screen_width
        self.road_left = screen_width//3 + 20
        self.road_right = 2*screen_width//3
        self.reset_position()
        self.color = (0, 0, 255)  # Blue color
        self.speed = random.randint(3, 7)
    def reset_position(self):
        # Ensure opponents spawn within road boundaries
        self.x = random.randint(self.road_left, self.road_right - self.width)
        self.y = random.randint(-300, -100)
    def update(self):
        self.y += self.speed
        if self.y > 600:
            self.reset_position()
    def draw(self, screen):
        # Draw car body
        pygame.draw.rect(screen, self.color, (self.x, self.y, self.width, self.height))
        # Draw car details
        pygame.draw.rect(screen, (0, 0, 0), (self.x + 5, self.y + 10, 10, 40))  # Left wheel
        pygame.draw.rect(screen, (0, 0, 0), (self.x + 25, self.y + 10, 10, 40))  # Right wheel
        pygame.draw.rect(screen, (200, 200, 200), (self.x + 5, self.y + 5, 30, 15))  # Windshield