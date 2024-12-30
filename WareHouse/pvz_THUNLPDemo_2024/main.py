import pygame
import sys
import random
import math
from constants import *
from entities import Plant, Zombie, Projectile
from sprites import PLANT_DRAWINGS, ZOMBIE_DRAWINGS

class Sun:
    def __init__(self, x, y, from_sky=True):
        self.x = x
        self.y = y
        self.initial_x = x
        self.initial_y = y
        self.value = 25
        self.rect = pygame.Rect(x, y, 40, 40)
        self.collected = False
        self.from_sky = from_sky
        self.fall_speed = 1.5
        self.lifetime = 300 if from_sky else 450
        self.hover_offset = 0
        self.hover_speed = 0.03
        self.hover_range = 5
        self.fade_start = 60
        self.alpha = 0
        self.fade_in = 255
        self.glow_offset = 0
        self.size = 40
        self.collect_speed = 5
        self.collecting = False

    def move(self):
        if self.from_sky and self.y < self.initial_y + WINDOW_HEIGHT//3:
            self.y += self.fall_speed
            self.rect.y = self.y
        
        self.hover_offset = math.sin(pygame.time.get_ticks() * self.hover_speed) * self.hover_range
        self.rect.y = self.y + self.hover_offset
        
        self.glow_offset = abs(math.sin(pygame.time.get_ticks() * 0.002)) * 5
        
        if self.fade_in > 0:
            self.alpha = min(255, self.alpha + 10)
            self.fade_in -= 10
        
        self.lifetime -= 1
        if self.lifetime <= self.fade_start:
            self.alpha = max(0, int(255 * (self.lifetime / self.fade_start)))

    def draw(self, screen):
        sun_surface = pygame.Surface((50, 50), pygame.SRCALPHA)
        glow_radius = 25 + self.glow_offset
        pygame.draw.circle(sun_surface, (255, 255, 100, int(self.alpha * 0.3)), (25, 25), glow_radius)
        pygame.draw.circle(sun_surface, (255, 255, 0, self.alpha), (25, 25), 20)
        pygame.draw.circle(sun_surface, (255, 255, 200, self.alpha), (25, 25), 15)
        pygame.draw.circle(sun_surface, (255, 255, 255, int(self.alpha * 0.7)), (25, 25), 8)
        
        screen.blit(sun_surface, (self.rect.x - 5, self.rect.y - 5))

class Game:
    def __init__(self):
        pygame.init()
        pygame.mixer.init()
        # Set window mode with fixed resolution
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("植物大战僵尸 - ChatDev制作")
        self.clock = pygame.time.Clock()
        self.state = GameState.MENU
        # Set scale factors based on window size
        self.base_width = WINDOW_WIDTH
        self.base_height = WINDOW_HEIGHT
        self.scale_x = 1.0
        self.scale_y = 1.0
        
        # Load and play background music
        self.load_music()
        # Add Chinese font
        try:
            self.font = pygame.font.Font("/System/Library/Fonts/PingFang.ttc", 36)
            self.large_font = pygame.font.Font("/System/Library/Fonts/PingFang.ttc", 74)
            self.small_font = pygame.font.Font("/System/Library/Fonts/PingFang.ttc", 24)
        except:
            try:
                self.font = pygame.font.Font("/System/Library/Fonts/STHeiti Light.ttc", 36)
                self.large_font = pygame.font.Font("/System/Library/Fonts/STHeiti Light.ttc", 74)
                self.small_font = pygame.font.Font("/System/Library/Fonts/STHeiti Light.ttc", 24)
            except:
                try:
                    self.font = pygame.font.Font("/System/Library/Fonts/Arial Unicode.ttf", 36)
                    self.large_font = pygame.font.Font("/System/Library/Fonts/Arial Unicode.ttf", 74)
                    self.small_font = pygame.font.Font("/System/Library/Fonts/Arial Unicode.ttf", 24)
                except:
                    print("Warning: Could not load Chinese font, falling back to default font")
                    self.font = pygame.font.Font(None, 36)
                    self.large_font = pygame.font.Font(None, 74)
                    self.small_font = pygame.font.Font(None, 24)
        self.reset_game()

    def load_music(self):
        try:
            pygame.mixer.music.load("assets/music/bgm.mp3")
            pygame.mixer.music.set_volume(0.5)  # Set volume to 50%
            pygame.mixer.music.play(-1)  # -1 means loop indefinitely
        except:
            print("Warning: Could not load background music")

    def reset_game(self):
        self.plants = []
        self.zombies = []
        self.projectiles = []
        self.suns = []
        self.particles = []
        self.sun_points = 2025
        self.selected_plant = None
        self.spawn_timer = 0
        self.sun_spawn_timer = 0
        self.wave_number = 1
        self.wave_timer = 600
        self.score = 0
        self.game_over = False

    def spawn_sun(self):
        if self.sun_spawn_timer <= 0:
            x = random.randint(100, WINDOW_WIDTH - 100)
            self.suns.append(Sun(x, -40))
            self.sun_spawn_timer = random.randint(300, 500)
        self.sun_spawn_timer -= 1

    def spawn_zombie(self):
        if self.spawn_timer <= 0:
            # Ensure minimum number of zombies (5) are present
            if len(self.zombies) < 5 + self.wave_number:
                # Spawn multiple zombies at once if below minimum
                zombies_to_spawn = max(2, 5 + self.wave_number - len(self.zombies))
                for _ in range(zombies_to_spawn):
                    row = random.randint(0, GRID_ROWS - 1)
                    
                    # Zombie type selection based on wave number
                    zombie_types = [
                        ZombieType.NORMAL,
                        ZombieType.CONE,
                        ZombieType.BUCKET,
                        ZombieType.NEWSPAPER,
                        ZombieType.DANCING
                    ]
                        
                    zombie_type = random.choice(zombie_types)
                    self.zombies.append(Zombie(row, zombie_type))
            else:
                # Regular spawn for maintaining zombie presence
                row = random.randint(0, GRID_ROWS - 1)
                zombie_types = [
                    ZombieType.NORMAL,
                    ZombieType.CONE,
                    ZombieType.BUCKET,
                    ZombieType.NEWSPAPER,
                    ZombieType.DANCING
                ]
                    
                zombie_type = random.choice(zombie_types)
                self.zombies.append(Zombie(row, zombie_type))
            
            # Adjust spawn timer based on wave - make it faster
            base_timer = max(100, 300 - (self.wave_number * 40))  # Reduced from 500 to 300
            variation = random.randint(-30, 30)  # Add some randomness
            self.spawn_timer = base_timer + variation
        self.spawn_timer -= 1

    def handle_resize(self, event):
        # Update screen size
        width, height = event.size
        self.screen = pygame.display.set_mode((width, height), pygame.RESIZABLE)
        # Calculate new scale factors
        self.scale_x = width / self.base_width
        self.scale_y = height / self.base_height
        # Update font sizes based on scale
        scale = min(self.scale_x, self.scale_y)
        try:
            self.font = pygame.font.Font("/System/Library/Fonts/PingFang.ttc", int(36 * scale))
            self.large_font = pygame.font.Font("/System/Library/Fonts/PingFang.ttc", int(74 * scale))
            self.small_font = pygame.font.Font("/System/Library/Fonts/PingFang.ttc", int(24 * scale))
        except:
            try:
                self.font = pygame.font.Font("/System/Library/Fonts/STHeiti Light.ttc", int(36 * scale))
                self.large_font = pygame.font.Font("/System/Library/Fonts/STHeiti Light.ttc", int(74 * scale))
                self.small_font = pygame.font.Font("/System/Library/Fonts/STHeiti Light.ttc", int(24 * scale))
            except:
                try:
                    self.font = pygame.font.Font("/System/Library/Fonts/Arial Unicode.ttf", int(36 * scale))
                    self.large_font = pygame.font.Font("/System/Library/Fonts/Arial Unicode.ttf", int(74 * scale))
                    self.small_font = pygame.font.Font("/System/Library/Fonts/Arial Unicode.ttf", int(24 * scale))
                except:
                    self.font = pygame.font.Font(None, int(36 * scale))
                    self.large_font = pygame.font.Font(None, int(74 * scale))
                    self.small_font = pygame.font.Font(None, int(24 * scale))

    def get_scaled_rect(self, rect):
        # Helper function to scale rectangles
        return pygame.Rect(
            rect.x * self.scale_x,
            rect.y * self.scale_y,
            rect.width * self.scale_x,
            rect.height * self.scale_y
        )

    def get_real_pos(self, pos):
        # Convert screen position to game logic position
        return (pos[0] / self.scale_x, pos[1] / self.scale_y)

    def handle_click(self, pos):
        # Convert screen position to game logic position
        x, y = self.get_real_pos(pos)
        
        # Check if clicking on a sun
        for sun in self.suns[:]:
            if sun.rect.collidepoint(x, y) and not sun.collected:
                self.sun_points += sun.value
                self.suns.remove(sun)
                continue

        # Plant placement
        # Calculate grid position
        grid_x = int(x // CELL_SIZE)
        grid_y = int((y - TOP_MARGIN) // CELL_SIZE)
        
        # Check if click is within the planting area
        if 0 <= grid_x < GRID_COLS and 0 <= grid_y < GRID_ROWS:
            # Check if there's already a plant there
            plant_exists = any(p.x == grid_x and p.y == grid_y for p in self.plants)
            
            if not plant_exists and self.selected_plant:
                cost = PLANT_STATS[self.selected_plant]["cost"]
                if self.sun_points >= cost:
                    self.plants.append(Plant(grid_x, grid_y, self.selected_plant))
                    self.sun_points -= cost
                    self.selected_plant = None

    def update_plants(self):
        for plant in self.plants:
            plant.update()
            if plant.can_shoot():
                if plant.type == PlantType.SNOW_PEA:
                    self.projectiles.append(Projectile(plant.x, plant.y, freezing=True))
                elif plant.type == PlantType.ROSE_SHOOTER:
                    # Shoot in current lane and adjacent lanes
                    lanes = [plant.y]  # Current lane
                    if plant.y > 0:  # Add lane above if exists
                        lanes.append(plant.y - 1)
                    if plant.y < GRID_ROWS - 1:  # Add lane below if exists
                        lanes.append(plant.y + 1)
                    for lane in lanes:
                        # Create rose projectile with special properties
                        proj = Projectile(plant.x, lane, damage=20, speed=6, is_rose=True)
                        self.projectiles.append(proj)
                else:
                    self.projectiles.append(Projectile(plant.x, plant.y))
                plant.reset_timer()
            elif plant.can_produce_sun():
                self.suns.append(Sun(plant.rect.x, plant.rect.y, from_sky=False))
                plant.reset_timer()
            elif plant.can_eat_zombie():
                # Check for zombies in range for Chomper
                for zombie in self.zombies[:]:
                    if zombie.y == plant.y and abs(zombie.x - plant.x) <= 1:
                        self.zombies.remove(zombie)
                        plant.start_eating()
                        self.score += 100
                        break

    def update_combat(self):
        # Update projectiles and check collisions
        for projectile in self.projectiles[:]:
            if not projectile.active:
                self.projectiles.remove(projectile)
                continue
                
            projectile.move()
            for zombie in self.zombies[:]:
                if projectile.rect.colliderect(zombie.rect):
                    # Create impact effect based on projectile type
                    if projectile.is_rose:
                        # Rose shooter effect (pink petals)
                        color = (255, 192, 203)  # Pink for rose
                        for _ in range(12):
                            angle = random.uniform(0, 2 * math.pi)
                            speed = random.uniform(3, 6)
                            size = random.uniform(4, 7)
                            self.particles.append({
                                'x': projectile.rect.x,
                                'y': projectile.rect.y,
                                'dx': math.cos(angle) * speed,
                                'dy': math.sin(angle) * speed,
                                'lifetime': 45,
                                'color': (255, 192, 203),
                                'size': size,
                                'rotation': random.uniform(0, 360),
                                'is_petal': True,
                                'shape': 'petal'
                            })
                            # Add sparkle particle
                            self.particles.append({
                                'x': projectile.rect.x,
                                'y': projectile.rect.y,
                                'dx': math.cos(angle) * (speed * 0.7),
                                'dy': math.sin(angle) * (speed * 0.7),
                                'lifetime': 30,
                                'color': (255, 255, 255),
                                'size': size * 0.5,
                                'is_petal': False
                            })
                        zombie.intoxicate()
                    elif projectile.freezing:
                        # Snow pea effect (ice crystals)
                        color = (0, 191, 255)  # Ice blue
                        for _ in range(12):
                            angle = random.uniform(0, 2 * math.pi)
                            speed = random.uniform(3, 6)
                            size = random.uniform(4, 7)
                            self.particles.append({
                                'x': projectile.rect.x,
                                'y': projectile.rect.y,
                                'dx': math.cos(angle) * speed,
                                'dy': math.sin(angle) * speed,
                                'lifetime': 40,
                                'color': (0, 191, 255),
                                'size': size,
                                'rotation': random.uniform(0, 360),
                                'is_petal': True,
                                'shape': 'snowflake'
                            })
                            # Add sparkle particle
                            self.particles.append({
                                'x': projectile.rect.x,
                                'y': projectile.rect.y,
                                'dx': math.cos(angle) * (speed * 0.7),
                                'dy': math.sin(angle) * (speed * 0.7),
                                'lifetime': 25,
                                'color': (255, 255, 255),
                                'size': size * 0.4,
                                'is_petal': False
                            })
                        zombie.freeze()
                    else:
                        # Regular peashooter effect (leaves and splashes)
                        color = (0, 255, 0)  # Green
                        for _ in range(12):
                            angle = random.uniform(0, 2 * math.pi)
                            speed = random.uniform(3, 6)
                            size = random.uniform(4, 7)
                            self.particles.append({
                                'x': projectile.rect.x,
                                'y': projectile.rect.y,
                                'dx': math.cos(angle) * speed,
                                'dy': math.sin(angle) * speed,
                                'lifetime': 35,
                                'color': (0, 200, 0),
                                'size': size,
                                'rotation': random.uniform(0, 360),
                                'is_petal': True,
                                'shape': 'leaf'
                            })
                            # Add splash particle
                            self.particles.append({
                                'x': projectile.rect.x,
                                'y': projectile.rect.y,
                                'dx': math.cos(angle) * (speed * 0.8),
                                'dy': math.sin(angle) * (speed * 0.8),
                                'lifetime': 20,
                                'color': (150, 255, 150),
                                'size': size * 0.6,
                                'is_petal': False
                            })
                    
                    zombie.take_damage(projectile.damage)
                    if projectile.freezing:
                        zombie.freeze()
                    zombie.stun_timer = 2
                    if zombie.health <= 0:
                        # Add death particles
                        for _ in range(12):
                            angle = random.uniform(0, 2 * math.pi)
                            speed = random.uniform(3, 6)
                            self.particles.append({
                                'x': zombie.rect.x + CELL_SIZE//2,
                                'y': zombie.rect.y + CELL_SIZE//2,
                                'dx': math.cos(angle) * speed,
                                'dy': math.sin(angle) * speed,
                                'lifetime': 30,
                                'color': (139, 69, 19),  # Brown for zombie parts
                                'size': random.uniform(3, 6)
                            })
                        self.zombies.remove(zombie)
                        self.score += 100
                    if projectile in self.projectiles:
                        self.projectiles.remove(projectile)
                    break

        # Update particles
        for particle in self.particles[:]:
            particle['x'] += particle['dx']
            particle['y'] += particle['dy']
            particle['lifetime'] -= 1
            if particle['lifetime'] <= 0:
                self.particles.remove(particle)

        # Check zombie-plant interactions
        for zombie in self.zombies:
            for plant in self.plants[:]:
                if zombie.rect.colliderect(plant.rect):
                    zombie.eating = True
                    plant.health -= zombie.damage
                    if plant.health <= 0:
                        # Add plant death particles
                        for _ in range(8):
                            angle = random.uniform(0, 2 * math.pi)
                            speed = random.uniform(2, 4)
                            self.particles.append({
                                'x': plant.rect.x + CELL_SIZE//2,
                                'y': plant.rect.y + CELL_SIZE//2,
                                'dx': math.cos(angle) * speed,
                                'dy': math.sin(angle) * speed,
                                'lifetime': 25,
                                'color': (0, 100, 0),  # Dark green for plant parts
                                'size': random.uniform(2, 5)
                            })
                        self.plants.remove(plant)
                        zombie.eating = False
                    break
            else:
                zombie.eating = False

    def draw_lawn(self):
        # Create a surface for the lawn at base size
        lawn_surface = pygame.Surface((self.base_width, self.base_height))
        lawn_surface.fill(LAWN_GREEN)
        
        # Draw grid with better visuals
        for row in range(GRID_ROWS):
            for col in range(GRID_COLS):
                rect = pygame.Rect(
                    col * CELL_SIZE, 
                    row * CELL_SIZE + TOP_MARGIN,
                    CELL_SIZE, 
                    CELL_SIZE
                )
                if (row + col) % 2 == 0:
                    pygame.draw.rect(lawn_surface, (115, 235, 0), rect)
                pygame.draw.rect(lawn_surface, (100, 200, 0), rect, 1)
        
        # Scale and blit to screen
        scaled_surface = pygame.transform.scale(lawn_surface, self.screen.get_size())
        self.screen.blit(scaled_surface, (0, 0))

    def draw_plant_menu(self):
        menu_height = 100 * self.scale_y
        menu_surface = pygame.Surface((self.screen.get_width(), menu_height), pygame.SRCALPHA)
        pygame.draw.rect(menu_surface, (139, 69, 19, 200), (0, 0, self.screen.get_width(), menu_height))
        
        # Get mouse position for hover effect
        mouse_x, mouse_y = pygame.mouse.get_pos()
        menu_y = mouse_y - (self.screen.get_height() - menu_height)
        
        # Plant cards
        cards = [
            (PlantType.SUNFLOWER, YELLOW, 50),
            (PlantType.PEASHOOTER, GREEN, 100),
            (PlantType.ROSE_SHOOTER, (255, 192, 203), 125),  # Pink color for rose
            (PlantType.CHOMPER, (148, 0, 211), 150),
            (PlantType.SNOW_PEA, (0, 191, 255), 175)
        ]
        
        card_width = 70 * self.scale_x
        card_height = 80 * self.scale_y
        card_spacing = 90 * self.scale_x
        
        for i, (plant_type, color, cost) in enumerate(cards):
            card_x = 10 * self.scale_x + i * card_spacing
            card_rect = pygame.Rect(card_x, 10 * self.scale_y, card_width, card_height)
            
            # Check if card is hovered or selected
            is_hovered = (0 <= menu_y <= card_height + 20 * self.scale_y and 
                         card_x <= mouse_x <= card_x + card_width)
            is_selected = self.selected_plant == plant_type
            
            # Draw card background with hover/selected effect
            if is_selected:
                # Glowing effect for selected card
                glow_surface = pygame.Surface((card_width + 4, card_height + 4), pygame.SRCALPHA)
                pygame.draw.rect(glow_surface, (*PLANT_STATS[plant_type]["color"], 128), 
                               (0, 0, card_width + 4, card_height + 4))
                menu_surface.blit(glow_surface, (card_rect.x - 2, card_rect.y - 2))
                pygame.draw.rect(menu_surface, WHITE, 
                               (card_rect.x - 2, card_rect.y - 2, card_width + 4, card_height + 4), 
                               max(1, int(2 * self.scale_x)))
            elif is_hovered:
                # Hover effect
                pygame.draw.rect(menu_surface, (255, 255, 255, 30), card_rect)
            
            pygame.draw.rect(menu_surface, color, card_rect)
            
            # Draw plant image on card
            if plant_type in PLANT_DRAWINGS:
                # Create a smaller surface for the plant
                plant_surface = pygame.Surface((CELL_SIZE, CELL_SIZE), pygame.SRCALPHA)
                PLANT_DRAWINGS[plant_type](plant_surface, 0, 0, CELL_SIZE)
                # Scale it down to fit the card
                scaled_size = (int(50 * self.scale_x), int(50 * self.scale_y))
                scaled_surface = pygame.transform.scale(plant_surface, scaled_size)
                menu_surface.blit(scaled_surface, 
                                (card_rect.x + 10 * self.scale_x, 
                                 card_rect.y + 5 * self.scale_y))
            
            # Cost indicator with sun icon
            sun_size = 10 * min(self.scale_x, self.scale_y)
            pygame.draw.circle(menu_surface, YELLOW, 
                             (card_rect.x + sun_size, card_rect.bottom - sun_size), 
                             sun_size)
            cost_text = self.small_font.render(str(cost), True, BLACK)
            menu_surface.blit(cost_text, 
                            (card_rect.x + sun_size * 2, 
                             card_rect.bottom - sun_size * 1.5))
            
            # Gray out if can't afford
            if self.sun_points < cost:
                gray_surface = pygame.Surface((card_width, card_height), pygame.SRCALPHA)
                pygame.draw.rect(gray_surface, (128, 128, 128, 180), 
                               (0, 0, card_width, card_height))
                menu_surface.blit(gray_surface, card_rect)
        
        self.screen.blit(menu_surface, (0, self.screen.get_height() - menu_height))

    def draw_hud(self):
        # Sun points
        sun_size = 30 * min(self.scale_x, self.scale_y)
        sun_icon = pygame.Surface((sun_size, sun_size), pygame.SRCALPHA)
        pygame.draw.circle(sun_icon, YELLOW, (sun_size/2, sun_size/2), sun_size/2)
        self.screen.blit(sun_icon, (10 * self.scale_x, 10 * self.scale_y))
        
        sun_text = self.font.render(str(self.sun_points), True, BLACK)
        self.screen.blit(sun_text, (45 * self.scale_x, 15 * self.scale_y))
        
        # Wave number
        wave_text = self.font.render(f"第 {self.wave_number} 波僵尸", True, BLACK)
        self.screen.blit(wave_text, 
                        (self.screen.get_width() - 200 * self.scale_x, 
                         15 * self.scale_y))
        
        # Score
        score_text = self.font.render(f"得分: {self.score}", True, BLACK)
        self.screen.blit(score_text, 
                        (self.screen.get_width()//2 - score_text.get_width()//2, 
                         15 * self.scale_y))

    def draw_watermark(self):
        watermark = self.small_font.render("ChatDev制作", True, (0, 0, 0, 128))
        watermark.set_alpha(128)  # Make it semi-transparent
        self.screen.blit(watermark, 
                        (self.screen.get_width() - watermark.get_width() - 10, 
                         self.screen.get_height() - watermark.get_height() - 10))

    def run(self):
        while True:
            if self.state == GameState.MENU:
                self.run_menu()
            elif self.state == GameState.PLAYING:
                self.run_game()
            elif self.state == GameState.GAME_OVER:
                self.run_game_over()

    def run_menu(self):
        while self.state == GameState.MENU:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:  # Left click
                        # Start game button area
                        button_rect = pygame.Rect(
                            self.screen.get_width()//2 - 100 * self.scale_x,
                            self.screen.get_height()//2,
                            200 * self.scale_x,
                            50 * self.scale_y
                        )
                        if button_rect.collidepoint(event.pos):
                            self.state = GameState.PLAYING
                            self.reset_game()
                elif event.type == pygame.VIDEORESIZE:
                    self.handle_resize(event)

            # Draw menu
            self.screen.fill(LAWN_GREEN)
            
            # Draw title
            title = self.large_font.render("植物大战僵尸", True, BLACK)
            self.screen.blit(title, 
                           (self.screen.get_width()//2 - title.get_width()//2,
                            self.screen.get_height()//4))
            
            # Draw start button
            button_rect = pygame.Rect(
                self.screen.get_width()//2 - 100 * self.scale_x,
                self.screen.get_height()//2,
                200 * self.scale_x,
                50 * self.scale_y
            )
            pygame.draw.rect(self.screen, GREEN, button_rect)
            pygame.draw.rect(self.screen, BLACK, button_rect, 2)
            
            start_text = self.font.render("开始游戏", True, BLACK)
            self.screen.blit(start_text,
                           (self.screen.get_width()//2 - start_text.get_width()//2,
                            self.screen.get_height()//2 + 5 * self.scale_y))
            
            self.draw_watermark()
            
            pygame.display.flip()
            self.clock.tick(FPS)

    def run_game(self):
        while self.state == GameState.PLAYING and not self.game_over:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                elif event.type == pygame.VIDEORESIZE:
                    self.handle_resize(event)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    mouse_pos = pygame.mouse.get_pos()
                    real_pos = self.get_real_pos(mouse_pos)
                    if self.base_height - 100 <= real_pos[1] <= self.base_height:
                        menu_y = real_pos[1] - (self.base_height - 100)
                        if 10 <= menu_y <= 90:
                            card_x = int((real_pos[0] - 10) // 90)  # Convert to integer
                            if 0 <= card_x <= 4:
                                plant_types = [
                                    PlantType.SUNFLOWER,
                                    PlantType.PEASHOOTER,
                                    PlantType.ROSE_SHOOTER,
                                    PlantType.CHOMPER,
                                    PlantType.SNOW_PEA
                                ]
                                if card_x < len(plant_types):
                                    plant_type = plant_types[card_x]
                                    if self.sun_points >= PLANT_STATS[plant_type]["cost"]:
                                        self.selected_plant = plant_type
                    else:
                        self.handle_click(mouse_pos)

            # Update game state
            self.spawn_zombie()
            self.spawn_sun()
            self.update_plants()
            self.update_combat()
            
            # Wave management
            self.wave_timer -= 1
            if self.wave_timer <= 0:
                self.wave_number += 1
                self.wave_timer = 600

            # Move entities
            for zombie in self.zombies:
                zombie.move()
                if zombie.x <= 0:
                    self.game_over = True
                    self.state = GameState.GAME_OVER

            for sun in self.suns[:]:
                sun.move()
                if sun.lifetime <= 0:
                    self.suns.remove(sun)

            # Draw everything
            self.draw_lawn()
            
            # Create a game surface at base size and draw everything on it
            game_surface = pygame.Surface((self.base_width, self.base_height), pygame.SRCALPHA)
            
            for plant in self.plants:
                plant.draw(game_surface)
            
            for zombie in self.zombies:
                zombie.draw(game_surface)
                
            for projectile in self.projectiles:
                projectile.draw(game_surface)
                
            for sun in self.suns:
                sun.draw(game_surface)

            # Draw particles
            for particle in self.particles:
                if particle.get('is_petal', False):
                    # Draw shaped particles based on type
                    shape = particle.get('shape', 'petal')
                    particle_surface = pygame.Surface((particle['size'] * 2, particle['size'] * 2), pygame.SRCALPHA)
                    center = (particle['size'], particle['size'])
                    
                    if shape == 'petal':
                        # Draw rose petal shape
                        for angle in range(0, 360, 72):
                            rad = math.radians(angle + particle['rotation'])
                            petal_x = center[0] + math.cos(rad) * particle['size']
                            petal_y = center[1] + math.sin(rad) * particle['size']
                            pygame.draw.circle(particle_surface, particle['color'], 
                                            (int(petal_x), int(petal_y)), 
                                            int(particle['size'] * 0.6))
                    
                    elif shape == 'snowflake':
                        # Draw snowflake shape
                        for angle in range(0, 360, 45):
                            rad = math.radians(angle + particle['rotation'])
                            # Draw main line
                            end_x = center[0] + math.cos(rad) * particle['size']
                            end_y = center[1] + math.sin(rad) * particle['size']
                            pygame.draw.line(particle_surface, particle['color'],
                                          center, (int(end_x), int(end_y)), 2)
                            # Draw side branches
                            branch_length = particle['size'] * 0.5
                            mid_x = center[0] + math.cos(rad) * particle['size'] * 0.6
                            mid_y = center[1] + math.sin(rad) * particle['size'] * 0.6
                            side_angle1 = rad + math.pi / 4
                            side_angle2 = rad - math.pi / 4
                            pygame.draw.line(particle_surface, particle['color'],
                                          (int(mid_x), int(mid_y)),
                                          (int(mid_x + math.cos(side_angle1) * branch_length),
                                           int(mid_y + math.sin(side_angle1) * branch_length)), 2)
                            pygame.draw.line(particle_surface, particle['color'],
                                          (int(mid_x), int(mid_y)),
                                          (int(mid_x + math.cos(side_angle2) * branch_length),
                                           int(mid_y + math.sin(side_angle2) * branch_length)), 2)
                    
                    elif shape == 'leaf':
                        # Draw leaf shape
                        points = []
                        leaf_length = particle['size'] * 1.5
                        leaf_width = particle['size'] * 0.8
                        rad = math.radians(particle['rotation'])
                        
                        # Create leaf shape points
                        for t in range(0, 360, 10):
                            t_rad = math.radians(t)
                            x = center[0] + math.cos(rad) * leaf_length * math.cos(t_rad) - \
                                math.sin(rad) * leaf_width * math.sin(t_rad)
                            y = center[1] + math.sin(rad) * leaf_length * math.cos(t_rad) + \
                                math.cos(rad) * leaf_width * math.sin(t_rad)
                            points.append((int(x), int(y)))
                        
                        if len(points) > 2:
                            pygame.draw.polygon(particle_surface, particle['color'], points)
                            # Draw leaf vein
                            vein_start = center
                            vein_end = (int(center[0] + math.cos(rad) * leaf_length),
                                      int(center[1] + math.sin(rad) * leaf_length))
                            pygame.draw.line(particle_surface, (0, 150, 0), 
                                          vein_start, vein_end, 1)
                    
                    # Add fade out effect
                    alpha = int(255 * (particle['lifetime'] / 45))
                    particle_surface.set_alpha(alpha)
                    game_surface.blit(particle_surface, 
                                    (particle['x'] - particle['size'],
                                     particle['y'] - particle['size']))
                else:
                    # Draw regular circular particles
                    alpha = int(255 * (particle['lifetime'] / 30))
                    color = (*particle['color'][:3], alpha)
                    pygame.draw.circle(game_surface, color,
                                    (int(particle['x']), int(particle['y'])),
                                    int(particle['size']))

            # Scale and blit the game surface
            scaled_surface = pygame.transform.scale(game_surface, self.screen.get_size())
            self.screen.blit(scaled_surface, (0, 0))

            self.draw_plant_menu()
            self.draw_hud()
            self.draw_watermark()

            pygame.display.flip()
            self.clock.tick(FPS)

    def run_game_over(self):
        while self.state == GameState.GAME_OVER:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:  # Left click
                        self.state = GameState.MENU
                elif event.type == pygame.VIDEORESIZE:
                    self.handle_resize(event)

            # Draw game over screen
            self.screen.fill((0, 0, 0))  # Black background
            
            # Draw game over text
            game_over_text = self.large_font.render("游戏结束", True, RED)
            score_text = self.font.render(f"最终得分: {self.score}", True, WHITE)
            
            self.screen.blit(game_over_text,
                           (self.screen.get_width()//2 - game_over_text.get_width()//2,
                            self.screen.get_height()//3))
            self.screen.blit(score_text,
                           (self.screen.get_width()//2 - score_text.get_width()//2,
                            self.screen.get_height()//2))
            
            self.draw_watermark()
            
            pygame.display.flip()
            self.clock.tick(FPS)

if __name__ == "__main__":
    game = Game()
    game.run() 