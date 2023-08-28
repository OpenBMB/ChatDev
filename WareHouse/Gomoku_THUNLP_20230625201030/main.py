'''
This is the main file for the gomoku game.
'''
from game import Game
from gui import GUI
def main():
    # Create a new game instance
    game = Game()
    # Create a GUI instance and pass the game object
    gui = GUI(game)
    # Start the game loop
    gui.run()
if __name__ == "__main__":
    main()