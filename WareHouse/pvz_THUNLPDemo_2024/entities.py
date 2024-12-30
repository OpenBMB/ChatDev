import pygame
import math
from constants import *
from sprites import PLANT_DRAWINGS, ZOMBIE_DRAWINGS

class Plant:
    def __init__(self, x, y, plant_type):
        self.x = x
        self.y = y
        self.type = plant_type
        stats = PLANT_STATS[plant_type]
        self.health = stats["health"]
        self.max_health = stats["health"]
        self.cost = stats["cost"]
        self.rect = pygame.Rect(x * CELL_SIZE, y * CELL_SIZE + TOP_MARGIN, CELL_SIZE, CELL_SIZE)
        self.shoot_timer = 0
        self.shoot_cooldown = 150  # Frames between shots
        self.eating_timer = 0
        self.eating_cooldown = 300  # Frames between chomps
        self.sun_timer = 0
        self.animation_state = "idle"
        self.damaged_state = 0
        
        # Special abilities
        self.is_freezing = plant_type == PlantType.SNOW_PEA
        self.can_eat = plant_type == PlantType.CHOMPER
        self.is_rose = plant_type == PlantType.ROSE_SHOOTER
        
    def update(self):
        if self.type in [PlantType.PEASHOOTER, PlantType.SNOW_PEA, PlantType.ROSE_SHOOTER]:
            self.shoot_timer += 1
        elif self.type == PlantType.SUNFLOWER:
            self.sun_timer += 1
        elif self.type == PlantType.CHOMPER and self.eating_timer > 0:
            self.eating_timer -= 1
            
        # Update damage state
        health_percentage = self.health / self.max_health
        if health_percentage <= 0.3:
            self.damaged_state = 2
        elif health_percentage <= 0.6:
            self.damaged_state = 1

    def can_shoot(self):
        if self.type == PlantType.PEASHOOTER:
            return self.shoot_timer >= 90
        elif self.type == PlantType.SNOW_PEA:
            return self.shoot_timer >= 90
        elif self.type == PlantType.ROSE_SHOOTER:
            return self.shoot_timer >= 100  # Slightly slower fire rate
        return False

    def can_produce_sun(self):
        return self.type == PlantType.SUNFLOWER and self.sun_timer >= 360

    def can_eat_zombie(self):
        return self.type == PlantType.CHOMPER and self.eating_timer <= 0

    def start_eating(self):
        self.eating_timer = 300  # 5 seconds cooldown

    def reset_timer(self):
        if self.type in [PlantType.PEASHOOTER, PlantType.SNOW_PEA, PlantType.ROSE_SHOOTER]:
            self.shoot_timer = 0
        elif self.type == PlantType.SUNFLOWER:
            self.sun_timer = 0

    def draw(self, screen):
        # Draw shadow
        shadow_surface = pygame.Surface((CELL_SIZE, CELL_SIZE//4), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow_surface, (0, 0, 0, 64), (0, 0, CELL_SIZE, CELL_SIZE//4))
        screen.blit(shadow_surface, (self.rect.x, self.rect.y + CELL_SIZE - CELL_SIZE//8))
        
        # Draw plant using the corresponding drawing function
        if self.type in PLANT_DRAWINGS:
            PLANT_DRAWINGS[self.type](screen, self.rect.x, self.rect.y, CELL_SIZE)
        
        # Draw health bar when damaged
        if self.health < self.max_health:
            health_width = max(0, (self.rect.width * self.health) // self.max_health)
            health_rect = pygame.Rect(self.rect.x, self.rect.y - 5, health_width, 3)
            pygame.draw.rect(screen, (255, 0, 0), health_rect)

class Zombie:
    def __init__(self, row, zombie_type):
        self.x = WINDOW_WIDTH / CELL_SIZE
        self.y = row
        self.type = zombie_type
        stats = ZOMBIE_STATS[zombie_type]
        self.health = stats["health"]
        self.max_health = stats["health"]
        self.speed = stats["speed"]
        self.damage = stats["damage"]
        self.rect = pygame.Rect(
            self.x * CELL_SIZE, 
            self.y * CELL_SIZE + TOP_MARGIN, 
            CELL_SIZE, 
            CELL_SIZE
        )
        self.eating = False
        self.stun_timer = 0
        self.frozen_timer = 0
        self.frozen = False
        self.intoxicated_timer = 0
        self.intoxicated = False
        self.animation_state = "walking"
        
        # Special abilities for newspaper zombie
        if self.type == ZombieType.NEWSPAPER:
            self.has_newspaper = True
            self.enraged = False
        else:
            self.has_newspaper = False
            self.enraged = False
        
        # Special abilities for dancing zombie
        if self.type == ZombieType.DANCING:
            self.summon_timer = 300
        else:
            self.summon_timer = 0

    def move(self):
        if not self.eating and self.stun_timer <= 0:
            actual_speed = self.speed
            if self.frozen:
                actual_speed *= 0.5
            if self.intoxicated:
                actual_speed *= 0.3
            if self.type == ZombieType.NEWSPAPER and self.enraged:
                actual_speed *= 1.5
                
            self.x -= actual_speed / FPS
            self.rect.x = self.x * CELL_SIZE
            
        if self.stun_timer > 0:
            self.stun_timer -= 1
            
        if self.frozen:
            self.frozen_timer -= 1
            if self.frozen_timer <= 0:
                self.frozen = False
                
        if self.intoxicated:
            self.intoxicated_timer -= 1
            if self.intoxicated_timer <= 0:
                self.intoxicated = False

    def intoxicate(self):
        self.intoxicated = True
        self.intoxicated_timer = 300

    def take_damage(self, damage):
        self.health -= damage
        if self.type == ZombieType.NEWSPAPER and self.has_newspaper and self.health <= self.max_health * 0.5:
            self.has_newspaper = False
            self.enraged = True
            self.speed *= 1.5

    def freeze(self):
        self.frozen = True
        self.frozen_timer = 300

    def draw(self, screen):
        # Draw shadow
        shadow_surface = pygame.Surface((CELL_SIZE, CELL_SIZE//3), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow_surface, (0, 0, 0, 64), (0, 0, CELL_SIZE, CELL_SIZE//3))
        screen.blit(shadow_surface, (self.rect.x, self.rect.y + CELL_SIZE - CELL_SIZE//6))
        
        # Draw zombie using the corresponding drawing function
        if self.type in ZOMBIE_DRAWINGS:
            ZOMBIE_DRAWINGS[self.type](screen, self.rect.x, self.rect.y, CELL_SIZE)
        
        # Draw frozen effect
        if self.frozen:
            ice_surface = pygame.Surface((CELL_SIZE, CELL_SIZE), pygame.SRCALPHA)
            ice_surface.fill((150, 217, 255, 128))
            screen.blit(ice_surface, self.rect)
            
        # Draw intoxicated effect
        if self.intoxicated:
            love_surface = pygame.Surface((CELL_SIZE, CELL_SIZE), pygame.SRCALPHA)
            time = pygame.time.get_ticks()
            for i in range(3):
                heart_x = self.rect.x + CELL_SIZE//2 + math.cos(time * 0.003 + i * 2) * 15
                heart_y = self.rect.y + CELL_SIZE//3 + math.sin(time * 0.003 + i * 2) * 10
                # Draw heart shape
                pygame.draw.circle(screen, (255, 192, 203, 200), (int(heart_x - 5), int(heart_y)), 5)
                pygame.draw.circle(screen, (255, 192, 203, 200), (int(heart_x + 5), int(heart_y)), 5)
                pygame.draw.polygon(screen, (255, 192, 203, 200), [
                    (heart_x, heart_y + 8),
                    (heart_x - 10, heart_y),
                    (heart_x + 10, heart_y)
                ])
        
        # Health bar
        health_width = max(0, (self.rect.width * self.health) // self.max_health)
        health_rect = pygame.Rect(self.rect.x, self.rect.y - 10, health_width, 5)
        pygame.draw.rect(screen, (255, 0, 0), health_rect)

class Projectile:
    def __init__(self, x, y, damage=20, speed=5, freezing=False, is_rose=False):
        self.x = (x + 0.5) * CELL_SIZE
        self.y = y * CELL_SIZE + TOP_MARGIN + CELL_SIZE // 2
        self.damage = damage
        self.speed = speed
        self.freezing = freezing
        self.is_rose = is_rose
        self.active = True
        self.size = 10  # Set all projectiles to the same size
        self.rect = pygame.Rect(self.x - self.size//2, self.y - self.size//2, self.size, self.size)
        self.trail_positions = []
        self.trail_lifetime = 15 if is_rose else 10
        self.glow_offset = 0
        self.rotation = 0
        self.color = (255, 192, 203) if is_rose else ((0, 191, 255) if freezing else (0, 255, 0))
        self.alpha = 255

    def move(self):
        # Store current position for trail
        self.trail_positions.append((self.rect.x, self.rect.y))
        if len(self.trail_positions) > self.trail_lifetime:
            self.trail_positions.pop(0)
            
        self.rect.x += self.speed
        self.rotation += 15  # Rotate 15 degrees per frame
        
        # Update glow effect
        self.glow_offset = abs(math.sin(pygame.time.get_ticks() * 0.01)) * 2
        
        if self.rect.x > WINDOW_WIDTH:
            self.active = False

    def draw(self, screen):
        # Draw trail with rose petals or regular trail
        for i, (x, y) in enumerate(self.trail_positions):
            alpha = int(255 * (i / len(self.trail_positions)) * 0.5)
            size = int(4 * (i / len(self.trail_positions)))  # Same size for all trails
            
            trail_surface = pygame.Surface((12, 12), pygame.SRCALPHA)  # Same size for all trails
            if self.is_rose:
                # Draw rose petal trail
                petal_color = (255, 192, 203, alpha)  # Pink with alpha
                # Draw multiple petals for a more detailed trail
                for angle in range(0, 360, 72):
                    rad = math.radians(angle + self.rotation)
                    petal_x = 6 + math.cos(rad) * size  # Center at 6 (half of 12)
                    petal_y = 6 + math.sin(rad) * size
                    pygame.draw.circle(trail_surface, petal_color, (int(petal_x), int(petal_y)), size)
            else:
                color = (0, 191, 255, alpha) if self.freezing else (0, 255, 0, alpha)
                pygame.draw.circle(trail_surface, color, (6, 6), size)
            screen.blit(trail_surface, (x - 6, y - 6))

        # Draw main projectile
        if self.is_rose:
            # Draw rose projectile at same size as others
            glow_surface = pygame.Surface((20, 20), pygame.SRCALPHA)
            glow_radius = 8 + self.glow_offset
            glow_color = (255, 192, 203, 64)  # Pink with transparency
            pygame.draw.circle(glow_surface, glow_color, (10, 10), glow_radius)
            screen.blit(glow_surface, (self.rect.x - 10, self.rect.y - 10))
            
            # Main projectile
            pygame.draw.circle(screen, (255, 192, 203), (self.rect.x, self.rect.y), 6)  # Same size as others
            pygame.draw.circle(screen, (255, 105, 180), (self.rect.x, self.rect.y), 4)  # Inner color
            
            # Add highlight
            highlight_pos = (self.rect.x - 2, self.rect.y - 2)
            pygame.draw.circle(screen, (255, 255, 255, 180), highlight_pos, 2)
        else:
            # Draw regular projectile
            glow_color = (0, 191, 255, 64) if self.freezing else (0, 255, 0, 64)
            main_color = (0, 191, 255) if self.freezing else (0, 200, 0)
            inner_color = (173, 216, 230) if self.freezing else (150, 255, 150)
            
            glow_surface = pygame.Surface((20, 20), pygame.SRCALPHA)
            glow_radius = 8 + self.glow_offset
            pygame.draw.circle(glow_surface, glow_color, (10, 10), glow_radius)
            screen.blit(glow_surface, (self.rect.x - 10, self.rect.y - 10))
            
            pygame.draw.circle(screen, main_color, (self.rect.x, self.rect.y), 6)
            pygame.draw.circle(screen, inner_color, (self.rect.x, self.rect.y), 4)
            
            highlight_pos = (self.rect.x - 2, self.rect.y - 2)
            pygame.draw.circle(screen, (255, 255, 255, 180), highlight_pos, 2)