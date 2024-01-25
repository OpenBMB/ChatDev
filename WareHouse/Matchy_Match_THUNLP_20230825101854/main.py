'''
This is the main file for the card matching memory game.
'''
import tkinter as tk
from game import Game
def main():
    root = tk.Tk()
    root.title("Memory Game")
    game = Game(root)
    root.mainloop()
if __name__ == "__main__":
    main()