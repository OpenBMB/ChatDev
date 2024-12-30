'''
Player car class implementation with improved visual representation and road boundary constraints
'''
import pygame
class PlayerCar:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.width = 40
        self.height = 60
        self.speed = 5
        self.color = (255, 0, 0)  # Red color
    def handle_input(self, keys, screen_width):
        # Road boundaries
        left_boundary = screen_width//3 + 20  # Add padding for visibility
        right_boundary = 2*screen_width//3    # Subtract padding for visibility
        if keys[pygame.K_LEFT] and self.x > left_boundary:
            self.x -= self.speed
        if keys[pygame.K_RIGHT] and self.x < right_boundary - self.width:
            self.x += self.speed
        if keys[pygame.K_UP] and self.y > 0:
            self.y -= self.speed
        if keys[pygame.K_DOWN] and self.y < 600 - self.height:
            self.y += self.speed
    def update(self):
        pass
    def draw(self, screen):
        # Draw car body
        pygame.draw.rect(screen, self.color, (self.x, self.y, self.width, self.height))
        # Draw car details (wheels and windows)
        pygame.draw.rect(screen, (0, 0, 0), (self.x + 5, self.y + 10, 10, 40))  # Left wheel
        pygame.draw.rect(screen, (0, 0, 0), (self.x + 25, self.y + 10, 10, 40))  # Right wheel
        pygame.draw.rect(screen, (200, 200, 200), (self.x + 5, self.y + 5, 30, 15))  # Windshield
    def check_collision(self, other):
        return pygame.Rect(self.x, self.y, self.width, self.height).colliderect(
            pygame.Rect(other.x, other.y, other.width, other.height)
        )