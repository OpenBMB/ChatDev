'''
This file defines the Character class, which represents the user-controlled character in the game.
'''
import pygame
class Character(pygame.sprite.Sprite):
    def __init__(self, screen_width, screen_height):
        super().__init__()
        self.image = pygame.Surface((50, 50))
        self.image.fill((0, 0, 255))
        self.rect = self.image.get_rect()
        self.rect.centerx = screen_width // 2
        self.rect.centery = screen_height // 2
    def update(self, mouse_pos):
        self.rect.center = mouse_pos
    def draw(self, screen):
        screen.blit(self.image, self.rect)