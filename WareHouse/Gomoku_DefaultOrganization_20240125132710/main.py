'''
This is the main file for the Gomoku game.
'''
import tkinter as tk
from game import Game
class GomokuApp:
    def __init__(self, master):
        self.master = master
        self.game = Game()
        self.board_size = 15
        self.cell_size = 40
        self.canvas_width = self.board_size * self.cell_size
        self.canvas_height = self.board_size * self.cell_size
        self.canvas = tk.Canvas(self.master, width=self.canvas_width, height=self.canvas_height)
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self.on_click)
        self.draw_board()
    def draw_board(self):
        for i in range(self.board_size):
            self.canvas.create_line(i * self.cell_size, 0, i * self.cell_size, self.canvas_height)
            self.canvas.create_line(0, i * self.cell_size, self.canvas_width, i * self.cell_size)
    def on_click(self, event):
        row = event.y // self.cell_size
        col = event.x // self.cell_size
        self.game.make_move(row, col)
        self.draw_piece(row, col)
        winner = self.game.check_winner()
        if winner != 0:
            self.show_winner(winner)
    def draw_piece(self, row, col):
        x = col * self.cell_size
        y = row * self.cell_size
        if self.game.current_player == 1:
            color = "black"
        else:
            color = "white"
        self.canvas.create_oval(x, y, x + self.cell_size, y + self.cell_size, fill=color)
    def show_winner(self, winner):
        if winner == 1:
            message = "Black wins!"
        else:
            message = "White wins!"
        self.canvas.create_text(self.canvas_width // 2, self.canvas_height // 2, text=message, font=("Arial", 20))
if __name__ == "__main__":
    root = tk.Tk()
    app = GomokuApp(root)
    root.mainloop()