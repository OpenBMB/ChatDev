'''
Game class for managing the roguelike game.
'''
import pygame
from player import Player
from level import Level
class Game:
    def __init__(self):
        self.screen_width = 800
        self.screen_height = 800
        self.screen = pygame.display.set_mode((self.screen_width, self.screen_height))
        pygame.display.set_caption("Roguelike Game")
        self.clock = pygame.time.Clock()
        self.running = False
        self.player = Player(40, 40)  # Starting position of the player
        self.level = Level()
    def run(self):
        self.running = True
        while self.running:
            self.clock.tick(60)
            self.handle_events()
            self.update()
            self.render()
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_w:
                    self.player.move(0, -1)  # Move up
                elif event.key == pygame.K_s:
                    self.player.move(0, 1)  # Move down
                elif event.key == pygame.K_a:
                    self.player.move(-1, 0)  # Move left
                elif event.key == pygame.K_d:
                    self.player.move(1, 0)  # Move right
    def update(self):
        self.player.update(self.level)
    def render(self):
        self.screen.fill((0, 0, 0))  # Clear the screen
        self.level.draw(self.screen)
        self.player.draw(self.screen)
        pygame.display.flip()