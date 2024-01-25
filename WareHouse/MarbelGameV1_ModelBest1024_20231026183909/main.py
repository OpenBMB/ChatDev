'''
This is the main file for the web-based pinball game.
'''
import tkinter as tk
from game import Game
def main():
    # Create the game window
    window = tk.Tk()
    window.title("Web-based Pinball Game")
    # Create the game instance
    game = Game(window)
    # Start the game loop
    game.start()
    # Run the main event loop
    window.mainloop()
if __name__ == "__main__":
    main()