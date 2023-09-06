'''
Main file for the roguelike game.
'''
import pygame
from game import Game
def main():
    pygame.init()
    game = Game()
    game.run()
if __name__ == "__main__":
    main()