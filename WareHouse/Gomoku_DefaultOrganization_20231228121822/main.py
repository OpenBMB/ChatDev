'''
This file contains the main logic and GUI integration for the Gomoku game.
'''
import tkinter as tk
from tkinter import messagebox
from utils import print_board
from ai_player import AIPlayer
class GomokuGame:
    def __init__(self):
        self.board = [[' ' for _ in range(15)] for _ in range(15)]
        self.current_player = 'X'
    def play_move(self, row, col):
        if self.board[row][col] == ' ':
            self.board[row][col] = self.current_player
            self.current_player = 'O' if self.current_player == 'X' else 'X'
    def check_winner(self):
        # Check rows
        for row in self.board:
            for col in range(11):
                if row[col] == row[col+1] == row[col+2] == row[col+3] == row[col+4] != ' ':
                    return row[col]
        # Check columns
        for col in range(15):
            for row in range(11):
                if self.board[row][col] == self.board[row+1][col] == self.board[row+2][col] == self.board[row+3][col] == self.board[row+4][col] != ' ':
                    return self.board[row][col]
        # Check diagonals
        for row in range(11):
            for col in range(11):
                if self.board[row][col] == self.board[row+1][col+1] == self.board[row+2][col+2] == self.board[row+3][col+3] == self.board[row+4][col+4] != ' ':
                    return self.board[row][col]
                if self.board[row][col+4] == self.board[row+1][col+3] == self.board[row+2][col+2] == self.board[row+3][col+1] == self.board[row+4][col] != ' ':
                    return self.board[row][col+4]
        return None
class GomokuGUI:
    def __init__(self, game):
        self.game = game
        self.root = tk.Tk()
        self.root.title("Gomoku")
        self.buttons = [[None for _ in range(15)] for _ in range(15)]
        for row in range(15):
            for col in range(15):
                button = tk.Button(self.root, text=' ', width=2, height=1, command=lambda r=row, c=col: self.make_move(r, c))
                button.grid(row=row, column=col)
                self.buttons[row][col] = button
    def make_move(self, row, col):
        self.game.play_move(row, col)
        self.buttons[row][col].config(text=self.game.board[row][col], state='disabled')
        winner = self.game.check_winner()
        if winner:
            self.show_winner(winner)
    def show_winner(self, winner):
        messagebox.showinfo("Game Over", f"Player {winner} wins!")
        self.root.quit()
    def run(self):
        self.root.mainloop()
if __name__ == '__main__':
    game = GomokuGame()
    gui = GomokuGUI(game)
    gui.run()