'''
Main file for the Texas Hold'em Poker game.
'''
from game import Game
from player import HumanPlayer, AIPlayer
from deck import Deck
def main():
    game = Game()
    game.start()
if __name__ == "__main__":
    main()