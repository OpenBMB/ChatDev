'''
This file contains the Game class that manages the game logic and user interface.
'''
import pygame
from paddle import Paddle
from ball import Ball
class Game:
    def __init__(self):
        self.width = 800
        self.height = 400
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("PingPong Game")
        self.clock = pygame.time.Clock()
        self.running = True
        self.paddle1 = Paddle(20, self.height // 2)
        self.paddle2 = Paddle(self.width - 20, self.height // 2)
        self.ball = Ball(self.width // 2, self.height // 2)
        self.score1 = 0
        self.score2 = 0
        self.font = pygame.font.Font(None, 36)
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                elif event.key == pygame.K_w:
                    self.paddle1.move_up()
                elif event.key == pygame.K_s:
                    self.paddle1.move_down()
                elif event.key == pygame.K_UP:
                    self.paddle2.move_up()
                elif event.key == pygame.K_DOWN:
                    self.paddle2.move_down()
    def update(self):
        self.paddle1.update()
        self.paddle2.update()
        self.ball.update(self.paddle1, self.paddle2)
        if self.ball.rect.left < 0:
            self.score2 += 1
            self.ball.reset()
        elif self.ball.rect.right > self.width:
            self.score1 += 1
            self.ball.reset()
    def draw(self):
        self.screen.fill((0, 0, 0))
        self.paddle1.draw(self.screen)
        self.paddle2.draw(self.screen)
        self.ball.draw(self.screen)
        score_text = self.font.render(f"Player 1: {self.score1}  Player 2: {self.score2}", True, (255, 255, 255))
        self.screen.blit(score_text, (self.width // 2 - score_text.get_width() // 2, 10))
        pygame.display.flip()
    def run(self):
        while self.running:
            self.handle_events()
            self.update()
            self.draw()
            self.clock.tick(60)
            if self.score1 >= 5 or self.score2 >= 5:
                self.game_over()
    def game_over(self):
        self.running = False
        pygame.quit()