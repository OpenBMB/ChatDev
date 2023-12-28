'''
The main file for the Gomoku game.
'''
import tkinter as tk
from game import GomokuGame
from gui import GomokuGUI
def main():
    # Create the game instance
    game = GomokuGame()
    # Create the GUI instance
    gui = GomokuGUI(game)
    # Start the GUI event loop
    gui.run()
if __name__ == "__main__":
    main()