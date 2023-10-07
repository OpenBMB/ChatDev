'''
This file defines the Circle class, which represents the randomly sized circles flying around the screen.
'''
import pygame
import random
class Circle(pygame.sprite.Sprite):
    def __init__(self, screen_width, screen_height):
        super().__init__()
        self.radius = random.randint(10, 30)
        self.image = pygame.Surface((self.radius * 2, self.radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(self.image, (255, 0, 0), (self.radius, self.radius), self.radius)
        self.rect = self.image.get_rect()
        # Determine the initial position of the circle on the outside edge
        side = random.randint(0, 3)
        if side == 0:  # Top edge
            self.rect.centerx = random.randint(0, screen_width)
            self.rect.centery = -self.radius
        elif side == 1:  # Right edge
            self.rect.centerx = screen_width + self.radius
            self.rect.centery = random.randint(0, screen_height)
        elif side == 2:  # Bottom edge
            self.rect.centerx = random.randint(0, screen_width)
            self.rect.centery = screen_height + self.radius
        else:  # Left edge
            self.rect.centerx = -self.radius
            self.rect.centery = random.randint(0, screen_height)
        # Determine the initial velocity of the circle
        self.velocity_x = random.randint(-5, 5)
        self.velocity_y = random.randint(-5, 5)
    def update(self, screen_width, screen_height):
        self.rect.centerx += self.velocity_x
        self.rect.centery += self.velocity_y
        # Check if the circle has reached the edge of the screen
        if self.rect.right < 0 or self.rect.left > screen_width or self.rect.bottom < 0 or self.rect.top > screen_height:
            self.kill()
    @staticmethod
    def spawn(circles, screen_width, screen_height):
        if len(circles) < 10:  # Limit the number of circles on the screen
            circle = Circle(screen_width, screen_height)
            circles.add(circle)