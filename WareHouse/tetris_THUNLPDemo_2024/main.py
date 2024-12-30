import pygame
import random
import numpy as np
from typing import List, Tuple, Optional
import os
import math
import time

# Initialize Pygame
pygame.init()
pygame.mixer.init()

# Constants
BLOCK_SIZE = 30
GRID_WIDTH = 10
GRID_HEIGHT = 20
PREVIEW_SIZE = 4

# Calculate window size
SIDE_PANEL_WIDTH = 200
WINDOW_WIDTH = BLOCK_SIZE * GRID_WIDTH + SIDE_PANEL_WIDTH
WINDOW_HEIGHT = BLOCK_SIZE * GRID_HEIGHT

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GRAY = (128, 128, 128)
COLORS = {
    'I': (0, 255, 255),    # Cyan
    'O': (255, 255, 0),    # Yellow
    'T': (128, 0, 128),    # Purple
    'S': (0, 255, 0),      # Green
    'Z': (255, 0, 0),      # Red
    'J': (0, 0, 255),      # Blue
    'L': (255, 165, 0),    # Orange
}

# Game settings
INITIAL_FALL_SPEED = 0.8  # Initial time between falls in seconds
SOFT_DROP_SPEED = 0.05    # Time between falls when soft dropping
SPEED_UP_FACTOR = 0.08    # How much to speed up per level
MIN_FALL_SPEED = 0.1      # Minimum fall speed
LOCK_DELAY = 0.5          # Time in seconds before piece locks in place
MAX_LOCK_RESETS = 15      # Maximum number of lock delay resets

# Animation settings
MOVE_ANIMATION_SPEED = 0.05  # seconds (faster horizontal movement)
ROTATION_ANIMATION_SPEED = 0.08  # seconds
LINE_CLEAR_ANIMATION_TIME = 0.3  # seconds
FLASH_SPEED = 0.05  # seconds

# Tetromino shapes
SHAPES = {
    'I': [[1, 1, 1, 1]],
    'O': [[1, 1], [1, 1]],
    'T': [[0, 1, 0], [1, 1, 1]],
    'S': [[0, 1, 1], [1, 1, 0]],
    'Z': [[1, 1, 0], [0, 1, 1]],
    'J': [[1, 0, 0], [1, 1, 1]],
    'L': [[0, 0, 1], [1, 1, 1]]
}

class AnimationState:
    def __init__(self):
        self.move_progress = 0
        self.rotation_progress = 0
        self.line_clear_progress = 0
        self.flash_progress = 0
        self.last_pos = None
        self.last_shape = None
        self.target_pos = None
        self.target_shape = None
        self.lines_being_cleared = []
        self.flash_active = False

class Particle:
    def __init__(self, x: int, y: int, color: Tuple[int, int, int]):
        self.x = x
        self.y = y
        self.color = color
        self.velocity = [random.uniform(-3, 3), random.uniform(-8, -4)]
        self.life = 255
        self.size = random.randint(2, 6)
        self.rotation = random.uniform(0, 360)
        self.rotation_speed = random.uniform(-5, 5)

    def update(self):
        self.x += self.velocity[0]
        self.y += self.velocity[1]
        self.velocity[1] += 0.2  # Gravity
        self.velocity[0] *= 0.99  # Air resistance
        self.life -= 3
        self.rotation += self.rotation_speed
        return self.life > 0

    def draw(self, screen):
        if self.life <= 0:
            return
        
        alpha = max(0, min(255, self.life))
        color = (*self.color, alpha)
        
        # Create rotated particle
        surface = pygame.Surface((self.size * 2, self.size * 2), pygame.SRCALPHA)
        points = [
            (self.size + math.cos(math.radians(self.rotation)) * self.size,
             self.size + math.sin(math.radians(self.rotation)) * self.size),
            (self.size + math.cos(math.radians(self.rotation + 120)) * self.size,
             self.size + math.sin(math.radians(self.rotation + 120)) * self.size),
            (self.size + math.cos(math.radians(self.rotation + 240)) * self.size,
             self.size + math.sin(math.radians(self.rotation + 240)) * self.size)
        ]
        pygame.draw.polygon(surface, color, points)
        screen.blit(surface, (self.x - self.size, self.y - self.size))

class Tetris:
    def __init__(self):
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption('俄罗斯方块')
        
        self.clock = pygame.time.Clock()
        self.grid = [[None for _ in range(GRID_WIDTH)] for _ in range(GRID_HEIGHT)]
        self.current_piece = None
        self.current_shape = None
        self.current_pos = None
        self.held_piece = None
        self.can_hold = True
        self.next_piece = self._get_random_piece()
        self.game_over = False
        self.score = 0
        self.level = 1
        self.lines_cleared = 0
        self.particles = []
        self.fall_speed = INITIAL_FALL_SPEED
        self.current_fall_speed = INITIAL_FALL_SPEED
        self.last_fall_time = time.time()
        self.lock_delay_time = 0
        self.lock_delay_active = False
        self.lock_reset_count = 0
        self.last_move_time = time.time()
        self.paused = False
        self.combo = 0
        self.force_down = False  # New flag for forcing piece down
        
        # Animation state
        self.animation = AnimationState()
        
        # Load high score
        self.high_score = self._load_high_score()
        
        # Initialize fonts
        self.font_big = pygame.font.Font(None, 48)
        self.font_small = pygame.font.Font(None, 36)
        
        # Load sounds
        self._load_sounds()
        
        # Background gradient
        self.background = self._create_background()

    def _load_sounds(self):
        # Create sounds directory if it doesn't exist
        if not os.path.exists('sounds'):
            os.makedirs('sounds')
            
        # Initialize empty/silent sounds
        empty_sound = pygame.mixer.Sound(buffer=bytes([0]*44))  # Minimal silent sound
        self.sounds = {
            'move': empty_sound,
            'rotate': empty_sound,
            'drop': empty_sound,
            'clear': empty_sound,
            'game_over': empty_sound
        }

    def _create_background(self):
        surface = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT))
        for y in range(WINDOW_HEIGHT):
            progress = y / WINDOW_HEIGHT
            color = (
                int(20 + 20 * math.sin(progress * math.pi)),
                int(10 + 10 * math.sin(progress * math.pi * 2)),
                int(40 + 20 * math.sin(progress * math.pi * 0.5))
            )
            pygame.draw.line(surface, color, (0, y), (WINDOW_WIDTH, y))
        return surface

    def _load_high_score(self) -> int:
        try:
            if os.path.exists('highscore.txt'):
                with open('highscore.txt', 'r') as f:
                    return int(f.read())
        except:
            pass
        return 0

    def _save_high_score(self):
        with open('highscore.txt', 'w') as f:
            f.write(str(self.high_score))

    def _get_random_piece(self) -> str:
        return random.choice(list(SHAPES.keys()))

    def new_piece(self):
        self.current_piece = self.next_piece
        self.next_piece = self._get_random_piece()
        self.current_shape = SHAPES[self.current_piece]
        self.current_pos = [0, GRID_WIDTH//2 - len(self.current_shape[0])//2]
        self.can_hold = True
        
        # Reset animation state
        self.animation.move_progress = 0
        self.animation.rotation_progress = 0
        self.animation.last_pos = self.current_pos.copy()
        self.animation.last_shape = [row[:] for row in self.current_shape]
        self.animation.target_pos = self.current_pos.copy()
        self.animation.target_shape = [row[:] for row in self.current_shape]
        
        # Check if game over
        if self._check_collision():
            self.game_over = True
            self.sounds['game_over'].play()

    def hold_piece(self):
        if not self.can_hold:
            return
        
        self.sounds['rotate'].play()
        
        if self.held_piece is None:
            self.held_piece = self.current_piece
            self.new_piece()
        else:
            self.held_piece, self.current_piece = self.current_piece, self.held_piece
            self.current_shape = SHAPES[self.current_piece]
            self.current_pos = [0, GRID_WIDTH//2 - len(self.current_shape[0])//2]
        
        self.can_hold = False

    def rotate_piece(self, clockwise: bool = True):
        if self.current_piece == 'O':
            return
            
        self.sounds['rotate'].play()
        
        old_shape = self.current_shape
        self.current_shape = np.rot90(self.current_shape, 1 if not clockwise else -1).tolist()
        
        # Update animation state
        self.animation.last_shape = old_shape
        self.animation.target_shape = self.current_shape
        self.animation.rotation_progress = 0
        
        if self._check_collision():
            self.current_shape = old_shape
            self.animation.target_shape = old_shape

    def _check_collision(self) -> bool:
        for y, row in enumerate(self.current_shape):
            for x, cell in enumerate(row):
                if cell:
                    grid_y = self.current_pos[0] + y
                    grid_x = self.current_pos[1] + x
                    
                    if (grid_x < 0 or grid_x >= GRID_WIDTH or
                        grid_y >= GRID_HEIGHT or
                        (grid_y >= 0 and self.grid[grid_y][grid_x] is not None)):
                        return True
        return False

    def _get_ghost_position(self) -> List[int]:
        ghost_pos = self.current_pos.copy()
        temp = self.current_pos.copy()
        
        while True:
            ghost_pos[0] += 1
            self.current_pos = ghost_pos.copy()
            if self._check_collision():
                ghost_pos[0] -= 1
                self.current_pos = temp
                break
        return ghost_pos

    def move(self, dx: int, dy: int):
        old_pos = self.current_pos.copy()
        self.current_pos[1] += dx
        self.current_pos[0] += dy
        
        if dx != 0:
            self.sounds['move'].play()
        
        collision = self._check_collision()
        if collision:
            self.current_pos[1] -= dx
            self.current_pos[0] -= dy
            
            if dy > 0:  # If moving down caused collision
                if not self.lock_delay_active:
                    # Start lock delay when piece first touches ground
                    self.lock_delay_active = True
                    self.lock_delay_time = time.time()
                    self.lock_reset_count = 0
                elif time.time() - self.lock_delay_time > LOCK_DELAY or self.force_down:
                    # Lock piece if lock delay expired or forced down
                    self._place_piece()
                    self._clear_lines()
                    self.new_piece()
                    self.lock_delay_active = False
                    self.force_down = False
            return True
        else:
            # Reset lock delay if piece moved successfully and still touching ground
            if self.lock_delay_active and self.lock_reset_count < MAX_LOCK_RESETS:
                # Check if still touching ground after move
                self.current_pos[0] += 1
                if self._check_collision():
                    self.lock_delay_time = time.time()
                    self.lock_reset_count += 1
                self.current_pos[0] -= 1
            else:
                # If piece is not touching ground, deactivate lock delay
                self.current_pos[0] += 1
                if not self._check_collision():
                    self.lock_delay_active = False
                self.current_pos[0] -= 1
            
            # Update animation state for horizontal movement only
            if dx != 0:
                self.animation.last_pos = old_pos
                self.animation.target_pos = self.current_pos.copy()
                self.animation.move_progress = 0
        return False

    def hard_drop(self):
        self.sounds['drop'].play()
        ghost_pos = self._get_ghost_position()
        self.current_pos = ghost_pos
        self.force_down = True  # Force the piece to lock immediately
        self.move(0, 1)  # This will trigger the locking process

    def _place_piece(self):
        for y, row in enumerate(self.current_shape):
            for x, cell in enumerate(row):
                if cell:
                    grid_y = self.current_pos[0] + y
                    grid_x = self.current_pos[1] + x
                    if 0 <= grid_y < GRID_HEIGHT:
                        self.grid[grid_y][grid_x] = self.current_piece
        
        # Create landing particles
        for x in range(len(self.current_shape[0])):
            color = COLORS[self.current_piece]
            px = (self.current_pos[1] + x) * BLOCK_SIZE
            py = (self.current_pos[0] + len(self.current_shape) - 1) * BLOCK_SIZE
            for _ in range(5):
                self.particles.append(Particle(px, py, color))

    def _clear_lines(self):
        lines_to_clear = []
        for y in range(GRID_HEIGHT):
            if all(cell is not None for cell in self.grid[y]):
                lines_to_clear.append(y)
        
        if not lines_to_clear:
            self.combo = 0
            return
            
        self.sounds['clear'].play()
        self.animation.lines_being_cleared = lines_to_clear
        self.animation.line_clear_progress = 0
        self.animation.flash_active = True
        self.animation.flash_progress = 0
        
        # Create particles for cleared lines
        for y in lines_to_clear:
            for x in range(GRID_WIDTH):
                color = COLORS[self.grid[y][x]]
                px = x * BLOCK_SIZE
                py = y * BLOCK_SIZE
                for _ in range(5):  # 5 particles per block
                    self.particles.append(Particle(px, py, color))
        
        # Clear lines and update score
        for y in lines_to_clear:
            self.grid.pop(y)
            self.grid.insert(0, [None] * GRID_WIDTH)
        
        lines_count = len(lines_to_clear)
        self.lines_cleared += lines_count
        
        # Calculate score with combo bonus
        self.combo += 1
        combo_multiplier = min(self.combo, 10)  # Cap combo at 10x
        base_score = [100, 300, 500, 800][lines_count - 1]
        self.score += base_score * self.level * combo_multiplier
        
        self.level = self.lines_cleared // 10 + 1
        self.fall_speed = max(MIN_FALL_SPEED, 
                            INITIAL_FALL_SPEED - (self.level - 1) * SPEED_UP_FACTOR)
        
        if self.score > self.high_score:
            self.high_score = self.score
            self._save_high_score()

    def _interpolate_position(self, progress: float) -> List[int]:
        if self.animation.last_pos is None or self.animation.target_pos is None:
            return self.current_pos
        
        # Only interpolate horizontal movement
        return [
            self.current_pos[0],  # Vertical position is always current
            self.animation.last_pos[1] + (self.animation.target_pos[1] - self.animation.last_pos[1]) * progress
        ]

    def draw(self):
        # Draw background
        self.screen.blit(self.background, (0, 0))
        
        # Draw grid
        for y in range(GRID_HEIGHT):
            for x in range(GRID_WIDTH):
                pygame.draw.rect(self.screen, GRAY,
                               (x * BLOCK_SIZE, y * BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE), 1)
        
        # Draw placed pieces
        for y in range(GRID_HEIGHT):
            for x in range(GRID_WIDTH):
                if self.grid[y][x]:
                    if y in self.animation.lines_being_cleared:
                        # Skip drawing blocks in lines being cleared during animation
                        if self.animation.line_clear_progress < LINE_CLEAR_ANIMATION_TIME:
                            continue
                    color = COLORS[self.grid[y][x]]
                    pygame.draw.rect(self.screen, color,
                                   (x * BLOCK_SIZE, y * BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE))
                    pygame.draw.rect(self.screen, WHITE,
                                   (x * BLOCK_SIZE, y * BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE), 1)
        
        # Draw ghost piece
        if self.current_piece:
            ghost_pos = self._get_ghost_position()
            for y, row in enumerate(self.current_shape):
                for x, cell in enumerate(row):
                    if cell:
                        color = (*COLORS[self.current_piece], 128)
                        ghost_x = (ghost_pos[1] + x) * BLOCK_SIZE
                        ghost_y = (ghost_pos[0] + y) * BLOCK_SIZE
                        surface = pygame.Surface((BLOCK_SIZE, BLOCK_SIZE), pygame.SRCALPHA)
                        pygame.draw.rect(surface, color, (0, 0, BLOCK_SIZE, BLOCK_SIZE))
                        self.screen.blit(surface, (ghost_x, ghost_y))
        
        # Draw current piece with animation
        if self.current_piece:
            pos = self._interpolate_position(min(1, self.animation.move_progress / MOVE_ANIMATION_SPEED))
            
            for y, row in enumerate(self.current_shape):
                for x, cell in enumerate(row):
                    if cell:
                        color = COLORS[self.current_piece]
                        block_x = (pos[1] + x) * BLOCK_SIZE
                        block_y = (pos[0] + y) * BLOCK_SIZE
                        
                        # Apply rotation animation
                        if self.animation.rotation_progress < ROTATION_ANIMATION_SPEED:
                            progress = self.animation.rotation_progress / ROTATION_ANIMATION_SPEED
                            scale = 1 - math.sin(progress * math.pi) * 0.2
                            
                            # Calculate center of rotation
                            center_x = pos[1] * BLOCK_SIZE + len(row) * BLOCK_SIZE / 2
                            center_y = pos[0] * BLOCK_SIZE + len(self.current_shape) * BLOCK_SIZE / 2
                            
                            # Adjust block position for rotation
                            block_x = center_x + (block_x - center_x) * scale
                            block_y = center_y + (block_y - center_y) * scale
                        
                        pygame.draw.rect(self.screen, color,
                                       (block_x, block_y, BLOCK_SIZE, BLOCK_SIZE))
                        pygame.draw.rect(self.screen, WHITE,
                                       (block_x, block_y, BLOCK_SIZE, BLOCK_SIZE), 1)
        
        # Draw side panel
        panel_x = GRID_WIDTH * BLOCK_SIZE + 10
        
        # Draw next piece preview
        next_text = self.font_small.render('Next:', True, WHITE)
        self.screen.blit(next_text, (panel_x, 20))
        next_shape = SHAPES[self.next_piece]
        for y, row in enumerate(next_shape):
            for x, cell in enumerate(row):
                if cell:
                    color = COLORS[self.next_piece]
                    pygame.draw.rect(self.screen, color,
                                   (panel_x + x * BLOCK_SIZE,
                                    60 + y * BLOCK_SIZE,
                                    BLOCK_SIZE, BLOCK_SIZE))
                    pygame.draw.rect(self.screen, WHITE,
                                   (panel_x + x * BLOCK_SIZE,
                                    60 + y * BLOCK_SIZE,
                                    BLOCK_SIZE, BLOCK_SIZE), 1)
        
        # Draw held piece
        held_text = self.font_small.render('Hold:', True, WHITE)
        self.screen.blit(held_text, (panel_x, 160))
        if self.held_piece:
            held_shape = SHAPES[self.held_piece]
            for y, row in enumerate(held_shape):
                for x, cell in enumerate(row):
                    if cell:
                        color = COLORS[self.held_piece]
                        if not self.can_hold:
                            color = tuple(c//2 for c in color)  # Darken color
                        pygame.draw.rect(self.screen, color,
                                       (panel_x + x * BLOCK_SIZE,
                                        200 + y * BLOCK_SIZE,
                                        BLOCK_SIZE, BLOCK_SIZE))
                        pygame.draw.rect(self.screen, WHITE,
                                       (panel_x + x * BLOCK_SIZE,
                                        200 + y * BLOCK_SIZE,
                                        BLOCK_SIZE, BLOCK_SIZE), 1)
        
        # Draw score and level
        score_text = self.font_small.render(f'Score: {self.score}', True, WHITE)
        self.screen.blit(score_text, (panel_x, 300))
        
        high_score_text = self.font_small.render(f'High: {self.high_score}', True, WHITE)
        self.screen.blit(high_score_text, (panel_x, 340))
        
        level_text = self.font_small.render(f'Level: {self.level}', True, WHITE)
        self.screen.blit(level_text, (panel_x, 380))
        
        lines_text = self.font_small.render(f'Lines: {self.lines_cleared}', True, WHITE)
        self.screen.blit(lines_text, (panel_x, 420))
        
        if self.combo > 1:
            combo_text = self.font_small.render(f'Combo: x{self.combo}', True, WHITE)
            self.screen.blit(combo_text, (panel_x, 460))
        
        # Draw particles
        self.particles = [p for p in self.particles if p.update()]
        for particle in self.particles:
            particle.draw(self.screen)
        
        # Draw line clear flash effect
        if self.animation.flash_active and self.animation.lines_being_cleared:
            flash_alpha = int(255 * (1 - self.animation.flash_progress / FLASH_SPEED))
            if flash_alpha > 0:
                flash_surface = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
                for y in self.animation.lines_being_cleared:
                    pygame.draw.rect(flash_surface, (255, 255, 255, flash_alpha),
                                   (0, y * BLOCK_SIZE, GRID_WIDTH * BLOCK_SIZE, BLOCK_SIZE))
                self.screen.blit(flash_surface, (0, 0))
        
        # Draw game over or pause screen
        if self.game_over:
            self._draw_overlay("Game Over! Press R to restart")
        elif self.paused:
            self._draw_overlay("Paused")
        
        pygame.display.flip()

    def _draw_overlay(self, text: str):
        overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT))
        overlay.set_alpha(128)
        overlay.fill(BLACK)
        self.screen.blit(overlay, (0, 0))
        
        text_surface = self.font_big.render(text, True, WHITE)
        text_rect = text_surface.get_rect(center=(WINDOW_WIDTH//2, WINDOW_HEIGHT//2))
        self.screen.blit(text_surface, text_rect)

    def reset(self):
        self.grid = [[None for _ in range(GRID_WIDTH)] for _ in range(GRID_HEIGHT)]
        self.current_piece = None
        self.current_shape = None
        self.current_pos = None
        self.held_piece = None
        self.can_hold = True
        self.next_piece = self._get_random_piece()
        self.game_over = False
        self.score = 0
        self.level = 1
        self.lines_cleared = 0
        self.particles = []
        self.fall_speed = INITIAL_FALL_SPEED
        self.current_fall_speed = INITIAL_FALL_SPEED
        self.last_fall_time = time.time()
        self.lock_delay_time = 0
        self.lock_delay_active = False
        self.lock_reset_count = 0
        self.combo = 0
        self.animation = AnimationState()
        self.paused = False
        self.new_piece()

    def update_animations(self, dt: float):
        # Update move animation
        if self.animation.move_progress < MOVE_ANIMATION_SPEED:
            self.animation.move_progress += dt
        
        # Update rotation animation
        if self.animation.rotation_progress < ROTATION_ANIMATION_SPEED:
            self.animation.rotation_progress += dt
        
        # Update line clear animation
        if self.animation.line_clear_progress < LINE_CLEAR_ANIMATION_TIME:
            self.animation.line_clear_progress += dt
        
        # Update flash animation
        if self.animation.flash_active:
            self.animation.flash_progress += dt
            if self.animation.flash_progress >= FLASH_SPEED:
                self.animation.flash_active = False
                self.animation.flash_progress = 0

    def run(self):
        self.new_piece()
        last_time = time.time()
        
        while True:
            current_time = time.time()
            dt = current_time - last_time
            last_time = current_time
            
            self.clock.tick(60)
            
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    return
                
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        pygame.quit()
                        return
                    
                    if self.game_over:
                        if event.key == pygame.K_r:
                            self.reset()
                        continue
                    
                    if event.key == pygame.K_p:
                        self.paused = not self.paused
                        continue
                    
                    if self.paused:
                        continue
                    
                    if event.key == pygame.K_LEFT:
                        self.move(-1, 0)
                    elif event.key == pygame.K_RIGHT:
                        self.move(1, 0)
                    elif event.key == pygame.K_DOWN:
                        self.current_fall_speed = SOFT_DROP_SPEED
                    elif event.key == pygame.K_UP:
                        self.rotate_piece()
                    elif event.key == pygame.K_z:
                        self.rotate_piece(False)
                    elif event.key == pygame.K_SPACE:
                        self.hard_drop()
                    elif event.key == pygame.K_c:
                        self.hold_piece()
                
                elif event.type == pygame.KEYUP:
                    if event.key == pygame.K_DOWN:
                        self.current_fall_speed = self.fall_speed
            
            if not self.game_over and not self.paused:
                # Update animations
                self.update_animations(dt)
                
                # Handle automatic falling
                if current_time - self.last_fall_time > self.current_fall_speed:
                    self.move(0, 1)  # Move down one grid
                    self.last_fall_time = current_time
            
            self.draw()

if __name__ == '__main__':
    game = Tetris()
    game.run() 