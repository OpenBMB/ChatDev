'''
This file contains the Game class which manages the game loop and overall game logic.
'''
import pygame
from player import Player
from obstacle import Obstacle
from powerup import Powerup
import random
class Game:
    def __init__(self):
        self.screen_width = 800
        self.screen_height = 600
        self.screen = pygame.display.set_mode((self.screen_width, self.screen_height))
        pygame.display.set_caption("Retro Runner")
        self.clock = pygame.time.Clock()
        self.is_running = True
        self.player = Player()
        self.obstacles = []
        self.powerups = []
        self.score = 0
    def run(self):
        while self.is_running:
            self.handle_events()
            self.update()
            self.render()
            self.clock.tick(60)
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.is_running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    self.player.jump()
                elif event.key == pygame.K_DOWN:
                    self.player.slide()
    def update(self):
        self.player.update()
        self.spawn_obstacles()
        self.spawn_powerups()
        self.check_collisions()
        self.score += 1
        for obstacle in self.obstacles:
            obstacle.update()
            if obstacle.x + obstacle.width < 0:
                self.obstacles.remove(obstacle)
        for powerup in self.powerups:
            powerup.update()
            if powerup.x + powerup.width < 0:
                self.powerups.remove(powerup)
    def render(self):
        self.screen.fill((0, 0, 0))
        self.player.draw(self.screen)
        for obstacle in self.obstacles:
            obstacle.draw(self.screen)
        for powerup in self.powerups:
            powerup.draw(self.screen)
        self.draw_score()
        pygame.display.flip()
    def spawn_obstacles(self):
        if len(self.obstacles) < 5:
            x = self.screen_width
            y = random.randint(400, 500)
            width = random.randint(50, 100)
            height = random.randint(50, 100)
            obstacle = Obstacle(x, y, width, height)
            self.obstacles.append(obstacle)
    def spawn_powerups(self):
        if len(self.powerups) < 2:
            x = self.screen_width
            y = random.randint(300, 400)
            width = 50
            height = 50
            powerup = Powerup(x, y, width, height)
            self.powerups.append(powerup)
    def check_collisions(self):
        player_rect = pygame.Rect(self.player.x, self.player.y, self.player.width, self.player.height)
        powerups_to_remove = []
        for powerup in self.powerups:
            powerup_rect = pygame.Rect(powerup.x, powerup.y, powerup.width, powerup.height)
            if player_rect.colliderect(powerup_rect):
                powerups_to_remove.append(powerup)
                self.score += 10
        for powerup in powerups_to_remove:
            self.powerups.remove(powerup)
    def draw_score(self):
        font = pygame.font.Font(None, 36)
        score_text = font.render("Score: " + str(self.score), True, (255, 255, 255))
        self.screen.blit(score_text, (10, 10))