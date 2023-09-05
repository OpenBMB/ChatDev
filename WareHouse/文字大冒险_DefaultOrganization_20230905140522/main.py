'''
This is the main file of the roguelike game.
'''
import tkinter as tk
from game import Game
def main():
    # Create the game object
    game = Game()
    # Create the main window
    root = tk.Tk()
    root.title("Roguelike Game")
    # Create the game canvas
    canvas = tk.Canvas(root, width=800, height=600)
    canvas.pack()
    # Bind keyboard events to game actions
    root.bind("<KeyPress>", game.handle_key_press)
    # Start the game loop
    game.start(canvas)
    # Run the main window event loop
    root.mainloop()
if __name__ == "__main__":
    main()