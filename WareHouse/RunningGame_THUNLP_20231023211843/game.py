'''
This file handles the game logic and manages the game objects.
'''
import pygame
import random
from sprites import Block, Obstacle
# Initialize pygame
pygame.init()
# Set up the display
screen_width = 800
screen_height = 400
screen = pygame.display.set_mode((screen_width, screen_height))
pygame.display.set_caption("Running Game")
# Define colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
# Define game variables
gravity = 0.75
block_size = 30
block_x = 50
block_y = screen_height - block_size
obstacle_width = 50
obstacle_height = random.randint(100, 300)
obstacle_x = screen_width
obstacle_y = screen_height - obstacle_height
obstacle_speed = 5
score = 0
font = pygame.font.Font(None, 36)
# Create block sprite
block = pygame.sprite.GroupSingle(Block(block_x, block_y, block_size))
# Create obstacle sprite group
obstacles = pygame.sprite.GroupSingle(Obstacle(obstacle_x, obstacle_y, obstacle_width, obstacle_height))
def update_score():
    score_text = font.render("Score: " + str(score), True, BLACK)
    screen.blit(score_text, (10, 10))
# Game loop
running = True
game_over = False
clock = pygame.time.Clock()
while running:
    screen.fill(WHITE)
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                if game_over:
                    game_over = False
                    score = 0
                    block.sprite.rect.y = screen_height - block_size
                    obstacle_height = random.randint(100, 300)
                    obstacle_y = screen_height - obstacle_height
                    obstacle_x = screen_width
                    block.sprite.speed_y = 0
    if not game_over:
        # Update block and obstacle positions
        block.update(gravity)
        obstacles.update(obstacle_speed)
        # Check if obstacle is off the screen
        if obstacles.sprite.rect.x + obstacle_width < 0:
            obstacles.sprite.rect.x = screen_width
            obstacle_height = random.randint(100, 300)
            obstacles.sprite.rect.height = obstacle_height
            obstacles.sprite.rect.y = screen_height - obstacle_height
            score += 1
        # Check for collision
        if pygame.sprite.spritecollide(block.sprite, obstacles, False):
            game_over = True
        # Draw block and obstacle
        block.draw(screen)
        obstacles.draw(screen)
        # Update score
        update_score()
    else:
        # Display game over message
        game_over_text = font.render("Game Over", True, BLACK)
        screen.blit(game_over_text, (screen_width // 2 - 80, screen_height // 2 - 20))
    pygame.display.update()
    clock.tick(60)
pygame.quit()