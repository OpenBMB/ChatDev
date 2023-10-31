'''
This is a simple endless running game.
'''
import pygame
import random
# Initialize the game
pygame.init()
# Set up the game window
window_width = 800
window_height = 400
window = pygame.display.set_mode((window_width, window_height))
pygame.display.set_caption("Endless Running Game")
# Define colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
# Define game variables
block_size = 50
block_x = 50
block_y = window_height - block_size
block_velocity = 5
obstacle_width = 50
obstacle_height = random.randint(100, 300)
obstacle_x = window_width
obstacle_y = window_height - obstacle_height
score = 0
# Load images
block_image = pygame.image.load("block.png")
block_image = pygame.transform.scale(block_image, (block_size, block_size))
obstacle_image = pygame.Surface((obstacle_width, obstacle_height))
obstacle_image.fill(BLACK)
# Create clock object to control the frame rate
clock = pygame.time.Clock()
# Game loop
running = False
game_over = False
while not game_over:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            game_over = True
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                if not running:
                    running = True
                    score = 0
                    obstacle_x = window_width
    if running:
        # Update block position
        block_y -= block_velocity
        # Update obstacle position
        obstacle_x -= block_velocity
        # Check for collision
        if block_y + block_size > obstacle_y and block_x + block_size > obstacle_x and block_x < obstacle_x + obstacle_width:
            running = False
        # Check if obstacle passed the block
        if obstacle_x + obstacle_width < 0:
            obstacle_width = 50
            obstacle_height = random.randint(100, 300)
            obstacle_x = window_width
            obstacle_y = window_height - obstacle_height
            score += 1
            # Update obstacle image height
            obstacle_image = pygame.Surface((obstacle_width, obstacle_height))
            obstacle_image.fill(BLACK)
        # Clear the window
        window.fill(WHITE)
        # Draw block
        window.blit(block_image, (block_x, block_y))
        # Draw obstacle
        window.blit(obstacle_image, (obstacle_x, obstacle_y))
        # Draw score
        font = pygame.font.Font(None, 36)
        score_text = font.render("Score: " + str(score), True, BLACK)
        window.blit(score_text, (10, 10))
        # Update the display
        pygame.display.update()
    # Set the frame rate
    clock.tick(60)
# Quit the game
pygame.quit()