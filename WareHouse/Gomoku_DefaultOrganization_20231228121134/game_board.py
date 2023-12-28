'''
This file defines the GameBoard class, which represents the game board for Gomoku.
'''
import tkinter as tk
class GameBoard(tk.Canvas):
    def __init__(self, parent, size=15, cell_size=40):
        super().__init__(parent, width=size*cell_size, height=size*cell_size, bg="white")
        self.size = size
        self.cell_size = cell_size
        self.board = [[0] * size for _ in range(size)]
        self.bind("<Button-1>", self.on_click)
    def draw_board(self):
        self.delete("all")
        for i in range(self.size):
            for j in range(self.size):
                x1 = j * self.cell_size
                y1 = i * self.cell_size
                x2 = (j + 1) * self.cell_size
                y2 = (i + 1) * self.cell_size
                self.create_rectangle(x1, y1, x2, y2, outline="black")
                if self.board[i][j] == 1:
                    self.create_oval(x1, y1, x2, y2, fill="black")
                elif self.board[i][j] == 2:
                    self.create_oval(x1, y1, x2, y2, fill="white")
    def on_click(self, event):
        x = event.x // self.cell_size
        y = event.y // self.cell_size
        if self.board[y][x] == 0:
            self.board[y][x] = 1
            self.draw_board()
        # Check for game over condition
        if self.check_game_over(x, y):
            self.game_over()
    def check_game_over(self, x, y):
        # Check horizontal
        count = 1
        i = x - 1
        while i >= 0 and self.board[y][i] == 1:
            count += 1
            i -= 1
        i = x + 1
        while i < self.size and self.board[y][i] == 1:
            count += 1
            i += 1
        if count >= 5:
            return True
        # Check vertical
        count = 1
        i = y - 1
        while i >= 0 and self.board[i][x] == 1:
            count += 1
            i -= 1
        i = y + 1
        while i < self.size and self.board[i][x] == 1:
            count += 1
            i += 1
        if count >= 5:
            return True
        # Check diagonal (top-left to bottom-right)
        count = 1
        i = x - 1
        j = y - 1
        while i >= 0 and j >= 0 and self.board[j][i] == 1:
            count += 1
            i -= 1
            j -= 1
        i = x + 1
        j = y + 1
        while i < self.size and j < self.size and self.board[j][i] == 1:
            count += 1
            i += 1
            j += 1
        if count >= 5:
            return True
        # Check diagonal (top-right to bottom-left)
        count = 1
        i = x + 1
        j = y - 1
        while i < self.size and j >= 0 and self.board[j][i] == 1:
            count += 1
            i += 1
            j -= 1
        i = x - 1
        j = y + 1
        while i >= 0 and j < self.size and self.board[j][i] == 1:
            count += 1
            i -= 1
            j += 1
        if count >= 5:
            return True
        return False
    def game_over(self):
        self.unbind("<Button-1>")
        self.create_text(
            self.size * self.cell_size // 2,
            self.size * self.cell_size // 2,
            text="Game Over",
            font=("Arial", 24),
            fill="red"
        )