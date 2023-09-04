'''
This is the main file of the tic-tac-toe game. It handles the game flow, user input, and GUI.
'''
import tkinter as tk
from tkinter import messagebox
from game import Game
class TicTacToeGUI:
    def __init__(self, master):
        self.master = master
        self.master.title("Tic-Tac-Toe")
        self.game = Game()
        self.buttons = []
        self.create_board()
    def create_board(self):
        for i in range(3):
            row = []
            for j in range(3):
                button = tk.Button(self.master, text="", width=10, height=5,
                                   command=lambda i=i, j=j: self.button_click(i, j))
                button.grid(row=i, column=j)
                row.append(button)
            self.buttons.append(row)
    def button_click(self, row, col):
        if self.game.is_game_over():
            return
        if self.game.make_move(row, col):
            self.buttons[row][col].config(text=self.game.current_player)
            if self.game.is_game_over():
                self.show_winner()
    def show_winner(self):
        winner = self.game.get_winner()
        if winner:
            messagebox.showinfo("Game Over", f"Player {winner} wins!")
        else:
            messagebox.showinfo("Game Over", "It's a tie!")
if __name__ == "__main__":
    root = tk.Tk()
    gui = TicTacToeGUI(root)
    root.mainloop()