import pygame
from gamewindow import GameWindow
from image import Image
from scoreboard import Scoreboard
from image import select_file
import time

def main():
    # Initialize pygame
    pygame.init()
    clock = pygame.time.Clock()
    # Create an instance of GameWindow
    game_window = GameWindow()

    # Get the file path from the user
    file_path = select_file()

    # Create instances of Image
    images = [Image(file_path) for _ in range(10)]

    # Create an instance of Scoreboard
    scoreboard = Scoreboard()

    # Game loop
    running = True
    while running:
        # Event handling
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                # Check if an image was clicked
                for image in images:
                    if image.rect.collidepoint(event.pos):
                        # Update the score
                        scoreboard.update_score()
                        # Remove the image
                        image.remove_image()
        
        # Move the images
        for image in images:
            image.move_image()

        # Update the game window
        game_window.update_window(images, scoreboard)
        clock.tick(60)
    pygame.quit()

if __name__ == "__main__":
    main()
