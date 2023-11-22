'''
This file contains the GameWindow class, which handles the creation and management of the game window.
'''
import pygame
class GameWindow:
    def __init__(self):
        self.width = 800
        self.height = 600
        self.window = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("Red Packet Rain")
    def update_window(self, images, scoreboard):
        # Fill the window with black
        self.window.fill((0, 0, 0))
        # Draw the images
        for image in images:
            self.window.blit(image.image, image.rect)
        # Draw the scoreboard
        self.window.blit(scoreboard.score_text, (10, 10))
        # Update the display
        pygame.display.flip()