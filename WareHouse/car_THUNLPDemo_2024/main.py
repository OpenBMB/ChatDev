'''
Main game file that initializes the racing game and runs the game loop
'''
import pygame
import sys
from car import PlayerCar
from track import Track
from gameobjects import OpponentCar
class RacingGame:
    def __init__(self):
        pygame.init()
        self.width = 800
        self.height = 600
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("赛车游戏")
        self.clock = pygame.time.Clock()
        self.running = True
        self.game_over = False
        self.font = pygame.font.Font(None, 74)
        self.reset_game()
    def reset_game(self):
        # Initialize player at the center of the road
        road_center = (self.width//3 + (2*self.width//3 + 20)) // 2
        self.player = PlayerCar(road_center - 20, self.height - 100)
        self.track = Track(self.width, self.height)
        self.opponents = [OpponentCar(self.width) for _ in range(3)]
        self.score = 0
        self.game_over = False
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            if event.type == pygame.KEYDOWN and self.game_over:
                if event.key == pygame.K_SPACE:
                    self.reset_game()
        if not self.game_over:
            keys = pygame.key.get_pressed()
            self.player.handle_input(keys, self.width)
    def update(self):
        if not self.game_over:
            self.player.update()
            self.track.update()
            for opponent in self.opponents:
                opponent.update()
                if self.player.check_collision(opponent):
                    self.game_over = True
            self.score += 1
    def render(self):
        self.screen.fill((100, 100, 100))  # Gray background
        self.track.draw(self.screen)
        self.player.draw(self.screen)
        for opponent in self.opponents:
            opponent.draw(self.screen)
        # Draw score
        font = pygame.font.Font(None, 36)
        score_text = font.render(f'Score: {self.score}', True, (255, 255, 255))
        self.screen.blit(score_text, (10, 10))
        if self.game_over:
            game_over_text = self.font.render('GAME OVER', True, (255, 0, 0))
            restart_text = pygame.font.Font(None, 36).render('Press SPACE to restart', True, (255, 255, 255))
            text_rect = game_over_text.get_rect(center=(self.width//2, self.height//2))
            restart_rect = restart_text.get_rect(center=(self.width//2, self.height//2 + 50))
            self.screen.blit(game_over_text, text_rect)
            self.screen.blit(restart_text, restart_rect)
        pygame.display.flip()
    def run(self):
        while self.running:
            self.handle_events()
            self.update()
            self.render()
            self.clock.tick(60)
        pygame.quit()
        sys.exit()
if __name__ == "__main__":
    game = RacingGame()
    game.run()