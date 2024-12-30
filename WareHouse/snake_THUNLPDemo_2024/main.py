import pygame
import random
import sys
import math

# Initialize Pygame
pygame.init()

# Colors
WHITE = (255, 255, 255)
RED = (255, 50, 50)
GREEN = (50, 255, 50)
BLUE = (50, 50, 255)
BLACK = (0, 0, 0)
DARK_GREEN = (34, 139, 34)
GOLD = (255, 215, 0)

# Game settings
WINDOW_SIZE = 800
GRID_SIZE = 20
GRID_COUNT = WINDOW_SIZE // GRID_SIZE
GAME_SPEED = 10

# Create window
screen = pygame.display.set_mode((WINDOW_SIZE, WINDOW_SIZE))
pygame.display.set_caption('贪吃蛇')
clock = pygame.time.Clock()

# Load and create background texture
background = pygame.Surface((WINDOW_SIZE, WINDOW_SIZE))
for y in range(0, WINDOW_SIZE, 4):
    for x in range(0, WINDOW_SIZE, 4):
        shade = random.randint(0, 20)
        pygame.draw.rect(background, (shade, shade, shade), (x, y, 4, 4))

class Particle:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.vx = random.uniform(-2, 2)
        self.vy = random.uniform(-2, 2)
        self.lifetime = 30
        self.color = (random.randint(200, 255), random.randint(200, 255), random.randint(0, 50))
        
    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.lifetime -= 1
        
    def draw(self, surface):
        alpha = int((self.lifetime / 30) * 255)
        particle_surface = pygame.Surface((4, 4), pygame.SRCALPHA)
        particle_surface.fill((*self.color, alpha))
        surface.blit(particle_surface, (int(self.x), int(self.y)))

class Snake:
    def __init__(self):
        self.body = [(GRID_COUNT//2, GRID_COUNT//2)]
        self.direction = (1, 0)
        self.grow = False
        self.angle = 0  # For snake movement animation
        
    def move(self):
        head = self.body[0]
        new_head = (head[0] + self.direction[0], head[1] + self.direction[1])
        
        if not self.grow:
            self.body.pop()
        else:
            self.grow = False
            
        self.body.insert(0, new_head)
        self.angle += 0.2  # Update movement animation
        
    def draw(self):
        for i, segment in enumerate(self.body):
            x = segment[0] * GRID_SIZE
            y = segment[1] * GRID_SIZE
            
            # Create snake skin pattern with gradient
            base_color = (34, max(50, 255 - (i * 8)), 34)
            
            # Add wave effect to snake body
            offset = math.sin(self.angle + i * 0.3) * 2
            
            # Draw main body segment with gradient
            pygame.draw.rect(screen, base_color, (x, y + offset, GRID_SIZE-2, GRID_SIZE-2))
            
            # Add scale pattern
            if i > 0:
                scale_color = (max(20, base_color[0] - 20), 
                             max(20, base_color[1] - 20),
                             max(20, base_color[2] - 20))
                pygame.draw.arc(screen, scale_color,
                              (x + 2, y + offset + 2, GRID_SIZE-6, GRID_SIZE-6),
                              0, 3.14, 2)
            
            # Draw head with special details
            if i == 0:
                # Draw eyes with shine effect
                eye_size = GRID_SIZE // 4
                # Left eye
                pygame.draw.circle(screen, WHITE, 
                    (x + GRID_SIZE//3, y + offset + GRID_SIZE//3), eye_size)
                pygame.draw.circle(screen, BLACK, 
                    (x + GRID_SIZE//3, y + offset + GRID_SIZE//3), eye_size//2)
                pygame.draw.circle(screen, WHITE,
                    (x + GRID_SIZE//3 - 1, y + offset + GRID_SIZE//3 - 1), eye_size//4)
                
                # Right eye
                pygame.draw.circle(screen, WHITE, 
                    (x + 2*GRID_SIZE//3, y + offset + GRID_SIZE//3), eye_size)
                pygame.draw.circle(screen, BLACK, 
                    (x + 2*GRID_SIZE//3, y + offset + GRID_SIZE//3), eye_size//2)
                pygame.draw.circle(screen, WHITE,
                    (x + 2*GRID_SIZE//3 - 1, y + offset + GRID_SIZE//3 - 1), eye_size//4)

class Food:
    def __init__(self):
        self.position = self.get_random_position()
        self.angle = 0
        self.particles = []
        
    def get_random_position(self):
        return (random.randint(0, GRID_COUNT-1), random.randint(0, GRID_COUNT-1))
    
    def update(self):
        self.angle += 0.1
        
        # Update particles
        self.particles = [p for p in self.particles if p.lifetime > 0]
        for particle in self.particles:
            particle.update()
    
    def draw(self):
        x = self.position[0] * GRID_SIZE
        y = self.position[1] * GRID_SIZE
        
        # Draw particles
        for particle in self.particles:
            particle.draw(screen)
        
        # Draw apple with pulsing effect
        size_mod = math.sin(self.angle) * 2
        apple_size = GRID_SIZE//2 - 2 + size_mod
        
        # Draw apple shadow
        shadow_pos = (x + GRID_SIZE//2 + 2, y + GRID_SIZE//2 + 2)
        pygame.draw.circle(screen, (20, 20, 20), shadow_pos, apple_size)
        
        # Draw apple body
        apple_pos = (x + GRID_SIZE//2, y + GRID_SIZE//2)
        pygame.draw.circle(screen, RED, apple_pos, apple_size)
        
        # Draw apple highlight
        highlight_pos = (x + GRID_SIZE//2 - 2, y + GRID_SIZE//2 - 2)
        pygame.draw.circle(screen, (255, 150, 150), highlight_pos, apple_size//3)
        
        # Draw leaf with animation
        leaf_x = x + GRID_SIZE//2 + math.sin(self.angle) * 2
        leaf_y = y + math.cos(self.angle) * 2
        pygame.draw.ellipse(screen, GREEN, (leaf_x, leaf_y, GRID_SIZE//4, GRID_SIZE//3))

def draw_title_and_score(score):
    # Draw game title
    title_font = pygame.font.Font(None, 74)
    title_text = title_font.render('Snake Game', True, GOLD)
    title_shadow = title_font.render('Snake Game', True, (50, 50, 50))
    
    # Add shadow effect
    screen.blit(title_shadow, (WINDOW_SIZE//2 - title_text.get_width()//2 + 2,
                              42))
    screen.blit(title_text, (WINDOW_SIZE//2 - title_text.get_width()//2,
                            40))
    
    # Draw score with fancy styling
    score_font = pygame.font.Font(None, 48)
    score_text = score_font.render(f'Score: {score}', True, WHITE)
    score_shadow = score_font.render(f'Score: {score}', True, (50, 50, 50))
    
    screen.blit(score_shadow, (12, 12))
    screen.blit(score_text, (10, 10))

def main():
    snake = Snake()
    food = Food()
    score = 0
    
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP and snake.direction != (0, 1):
                    snake.direction = (0, -1)
                if event.key == pygame.K_DOWN and snake.direction != (0, -1):
                    snake.direction = (0, 1)
                if event.key == pygame.K_LEFT and snake.direction != (1, 0):
                    snake.direction = (-1, 0)
                if event.key == pygame.K_RIGHT and snake.direction != (-1, 0):
                    snake.direction = (1, 0)
        
        # Move snake
        snake.move()
        
        # Update food animation
        food.update()
        
        # Check collision with food
        if snake.body[0] == food.position:
            snake.grow = True
            food.position = food.get_random_position()
            score += 1
            # Add particles on food collection
            x = food.position[0] * GRID_SIZE
            y = food.position[1] * GRID_SIZE
            for _ in range(20):
                food.particles.append(Particle(x + GRID_SIZE//2, y + GRID_SIZE//2))
            
        # Check collision with walls
        head = snake.body[0]
        if head[0] < 0 or head[0] >= GRID_COUNT or head[1] < 0 or head[1] >= GRID_COUNT:
            pygame.quit()
            sys.exit()
            
        # Check collision with self
        if head in snake.body[1:]:
            pygame.quit()
            sys.exit()
        
        # Draw everything
        screen.blit(background, (0, 0))
        
        # Draw grid lines with fade effect
        for i in range(GRID_COUNT):
            alpha = abs(math.sin(i * 0.1 + pygame.time.get_ticks() * 0.001)) * 30 + 20
            grid_surface = pygame.Surface((WINDOW_SIZE, 1), pygame.SRCALPHA)
            grid_surface.fill((50, 50, 50, int(alpha)))
            screen.blit(grid_surface, (0, i * GRID_SIZE))
            screen.blit(grid_surface, (i * GRID_SIZE, 0))
        
        snake.draw()
        food.draw()
        draw_title_and_score(score)
        
        pygame.display.flip()
        clock.tick(GAME_SPEED)

if __name__ == "__main__":
    main()