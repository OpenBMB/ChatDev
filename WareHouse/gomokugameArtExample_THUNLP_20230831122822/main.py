'''
This is the main file for the Gomoku game. It handles the game loop and user interaction.
'''
import pygame
import board
import os
from pygame import image, font
# Initialize Pygame
pygame.init()
# Set the width and height of the game window
WIDTH, HEIGHT = 800, 800
# Set the dimensions of the game board
BOARD_ROWS, BOARD_COLS = 15, 15
# Create the game window
WINDOW = pygame.display.set_mode((WIDTH, HEIGHT))
# Load images
bg_image = pygame.transform.scale(image.load('board_background.png'),(800,800))
player_1_icon = pygame.transform.scale(image.load('player_1_icon.png'),(50,50))
player_2_icon = pygame.transform.scale(image.load('player_2_icon.png'),(50,50))
# Create a game board
game_board = board.Board(BOARD_ROWS, BOARD_COLS, player_1_icon, player_2_icon, WIDTH, HEIGHT)
# Create a font object
font = font.Font(None, 36)
def main():
    clock = pygame.time.Clock()
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.MOUSEBUTTONDOWN and game_board.game_state == 'ongoing':
                x, y = pygame.mouse.get_pos()
                game_board.place_stone(x, y)
        WINDOW.blit(bg_image, (0, 0))
        game_board.draw(WINDOW)
        text = font.render(f"Player {game_board.current_player}'s turn", True, (255, 255, 255))
        WINDOW.blit(text, (20, 20))
        if game_board.game_state == 'ended':
            text = font.render(f"Player {game_board.winner} wins!", True, (255, 255, 255))
            WINDOW.blit(text, (WIDTH // 2 - text.get_width() // 2, HEIGHT // 2 - text.get_height() // 2))
        pygame.display.update()
        clock.tick(60)
    pygame.quit()
if __name__ == "__main__":
    main()