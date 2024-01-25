'''
This file contains the GUI class which handles the graphical user interface.
'''
import tkinter as tk
from tkinter import messagebox
class GUI:
    def __init__(self, game):
        self.game = game
        # Create the main window
        self.root = tk.Tk()
        self.root.title("Gomoku")
        self.root.geometry("500x500")
        # Create the game board
        self.board_frame = tk.Frame(self.root)
        self.board_frame.pack()
        self.buttons = []
        for row in range(15):
            row_buttons = []
            for col in range(15):
                button = tk.Button(self.board_frame, width=2, height=1, command=lambda r=row, c=col: self.make_move(r, c))
                button.grid(row=row, column=col)
                row_buttons.append(button)
            self.buttons.append(row_buttons)
    def make_move(self, row, col):
        # Make the move
        if self.game.make_move(row, col):
            # Update the button text
            self.buttons[row][col].config(text="X" if self.game.current_player == 1 else "O")
            # Check for a winner
            winner = self.game.check_winner()
            if winner != 0:
                messagebox.showinfo("Game Over", f"Player {winner} wins!")
                self.root.quit()
    def run(self):
        # Start the main event loop
        self.root.mainloop()