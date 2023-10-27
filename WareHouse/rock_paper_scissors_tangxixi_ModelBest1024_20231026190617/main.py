'''
The main file to run the rock, paper, scissors game.
'''
from game import Game
from gui import GUI
if __name__ == "__main__":
    game = Game()
    gui = GUI(game)
    gui.run()