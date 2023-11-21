'''
This is the main file for the running game.
'''
import pygame
import random
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
block_y_speed = 0
obstacle_width = 50
obstacle_height = random.randint(100, 300)
obstacle_x = screen_width
obstacle_y = screen_height - obstacle_height
obstacle_speed = 5
score = 0
font = pygame.font.Font(None, 36)
def draw_block():
    pygame.draw.rect(screen, BLACK, (block_x, block_y, block_size, block_size))
def draw_obstacle():
    pygame.draw.rect(screen, BLACK, (obstacle_x, obstacle_y, obstacle_width, obstacle_height))
def update_score():
    score_text = font.render("Score: " + str(score), True, BLACK)
    screen.blit(score_text, (10, 10))
def check_collision():
    if block_y + block_size >= obstacle_y and block_y <= obstacle_y + obstacle_height:
        if block_x + block_size >= obstacle_x and block_x <= obstacle_x + obstacle_width:
            return True
    return False
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
                    block_y = screen_height - block_size
                    obstacle_height = random.randint(100, 300)
                    obstacle_y = screen_height - obstacle_height
                    # Reset obstacle position
                    obstacle_x = screen_width
                    # Reset block speed
                    block_y_speed = 0
    if not game_over:
        # Update block position
        block_y_speed += gravity
        block_y += block_y_speed
        # Update obstacle position
        obstacle_x -= obstacle_speed
        # Check if obstacle is off the screen
        if obstacle_x + obstacle_width < 0:
            obstacle_x = screen_width
            obstacle_height = random.randint(100, 300)
            obstacle_y = screen_height - obstacle_height
            score += 1
        # Check for collision
        if check_collision():
            game_over = True
        # Draw block and obstacle
        draw_block()
        draw_obstacle()
        # Update score
        update_score()
    else:
        # Display game over message
        game_over_text = font.render("Game Over", True, BLACK)
        screen.blit(game_over_text, (screen_width // 2 - 80, screen_height // 2 - 20))
    pygame.display.update()
    clock.tick(60)
pygame.quit()