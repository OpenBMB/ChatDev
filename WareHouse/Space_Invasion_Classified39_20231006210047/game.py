'''
This file contains the Game class which manages the game logic.
'''
import pygame
from player import Player
from enemy import Enemy
from bullet import Bullet
class Game:
    def __init__(self, screen):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.destroyed_count = 0
        self.paused = False
        # Create the player
        player_x = 400
        player_y = 500
        self.player = Player(player_x, player_y)
        # Create the enemies
        self.enemies = []
        self.spawn_enemies()
        # Create the bullets
        self.bullets = []
    def spawn_enemies(self):
        enemy_x = 100
        enemy_y = 50
        enemy_spacing = 100
        num_enemies = 6
        for i in range(num_enemies):
            enemy = Enemy(enemy_x + i * enemy_spacing, enemy_y)
            self.enemies.append(enemy)
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                quit()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    bullet_x = self.player.x + self.player.width / 2
                    bullet_y = self.player.y
                    bullet = Bullet(bullet_x, bullet_y)
                    self.bullets.append(bullet)
    def update(self):
        if not self.paused:
            for bullet in self.bullets:
                bullet.update()
            for enemy in self.enemies:
                enemy.update()
            self.player.update()
            # Check for collisions between bullets and enemies
            destroyed_enemies = []
            for bullet in self.bullets:
                for enemy in self.enemies:
                    if bullet.collides_with(enemy):
                        destroyed_enemies.append(enemy)
                        self.destroyed_count += 1
            # Remove destroyed enemies and bullets
            for enemy in destroyed_enemies:
                self.enemies.remove(enemy)
            self.bullets = [bullet for bullet in self.bullets if not bullet.collides_with_any(self.enemies)]
    def draw(self):
        self.screen.fill((0, 0, 0))
        for bullet in self.bullets:
            bullet.draw(self.screen)
        for enemy in self.enemies:
            enemy.draw(self.screen)
        self.player.draw(self.screen)
        self.clock.tick(60)
    def get_destroyed_count(self):
        return self.destroyed_count
    def enemy_reached_bottom(self):
        for enemy in self.enemies:
            if enemy.y + enemy.height >= 600:
                return True
        return False
    def pause(self):
        self.paused = True