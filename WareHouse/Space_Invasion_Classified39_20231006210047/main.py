'''
This is the main file that runs the arcade game.
'''
import pygame
from game import Game
def main():
    # Initialize the game
    pygame.init()
    # Set up the game window
    screen_width = 800
    screen_height = 600
    screen = pygame.display.set_mode((screen_width, screen_height))
    pygame.display.set_caption("Space Invaders")
    # Create a game instance
    game = Game(screen)
    # Run the game loop
    while True:
        game.handle_events()
        game.update()
        game.draw()
        # Spawn more enemies when there are none left on screen
        if len(game.enemies) == 0:
            game.spawn_enemies()
        # Display the count of destroyed enemies
        destroyed_count = game.get_destroyed_count()
        font = pygame.font.Font(None, 36)
        text = font.render(f"Destroyed: {destroyed_count}", True, (255, 255, 255))
        screen.blit(text, (screen_width - text.get_width() - 10, 10))
        # Pause the game and display "GAME OVER" when an enemy reaches the bottom of the screen
        if game.enemy_reached_bottom():
            game.pause()
            game_over_text = font.render("GAME OVER", True, (255, 0, 0))
            screen.blit(game_over_text, (screen_width // 2 - game_over_text.get_width() // 2, screen_height // 2 - game_over_text.get_height() // 2))
        pygame.display.update()
if __name__ == "__main__":
    main()