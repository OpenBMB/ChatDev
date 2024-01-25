'''
Game Menu
'''
import pygame
# Initialize the game
pygame.init()
# Set up the game window
window_width = 800
window_height = 600
window = pygame.display.set_mode((window_width, window_height))
pygame.display.set_caption("Greedy Snake Game")
# Define colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
# Define game variables
menu_font = pygame.font.Font(None, 36)
# Define the menu function
def menu():
    running = True
    while running:
        # Handle events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    running = False
        # Clear the window
        window.fill(BLACK)
        # Draw the menu text
        text = menu_font.render("Press Enter to Start", True, WHITE)
        text_rect = text.get_rect(center=(window_width // 2, window_height // 2))
        window.blit(text, text_rect)
        # Update the display
        pygame.display.update()
# Run the menu function
menu()
# Quit the game
pygame.quit()