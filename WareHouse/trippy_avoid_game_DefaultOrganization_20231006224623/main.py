'''
This is the main file of the game. It initializes the game window, handles user input, and updates the game state.
'''
import pygame
import sys
from character import Character
from circle import Circle
# Initialize pygame
pygame.init()
# Set up the game window
screen_width = 800
screen_height = 600
screen = pygame.display.set_mode((screen_width, screen_height))
pygame.display.set_caption("Circle Dodge Game")
# Create the character
character = Character(screen_width, screen_height)
# Create a group to hold the circles
circles = pygame.sprite.Group()
# Game loop
game_over = False
clock = pygame.time.Clock()
while not game_over:
    # Handle events
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            game_over = True
    # Clear the screen
    screen.fill((255, 255, 255))
    # Update the character
    character.update(pygame.mouse.get_pos())
    # Spawn new circles
    Circle.spawn(circles, screen_width, screen_height)
    # Update and draw the circles
    circles.update(screen_width, screen_height)
    circles.draw(screen)
    # Check for collision with character
    if pygame.sprite.spritecollide(character, circles, False):
        game_over = True
    # Draw the character
    character.draw(screen)
    # Update the display
    pygame.display.flip()
    # Limit the frame rate to 60 FPS
    clock.tick(60)
# Game over screen
screen.fill((255, 255, 255))
font = pygame.font.Font(None, 36)
text = font.render("Game Over", True, (0, 0, 0))
text_rect = text.get_rect(center=(screen_width // 2, screen_height // 2))
screen.blit(text, text_rect)
pygame.display.flip()
pygame.time.wait(2000)
pygame.quit()
sys.exit()