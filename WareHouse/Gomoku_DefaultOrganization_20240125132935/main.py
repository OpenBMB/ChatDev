'''
This is the main file of the Gomoku game.
'''
import tkinter as tk
from tkinter import messagebox
from game import Game
class GomokuApp:
    def __init__(self, master):
        self.master = master
        self.master.title("Gomoku")
        self.game = Game()
        self.canvas = tk.Canvas(self.master, width=600, height=600, bg="white")
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self.on_click)
        self.draw_board()
    def draw_board(self):
        self.canvas.delete("all")
        for i in range(15):
            self.canvas.create_line(40 + i * 40, 40, 40 + i * 40, 600 - 40)
            self.canvas.create_line(40, 40 + i * 40, 600 - 40, 40 + i * 40)
    def on_click(self, event):
        x = (event.x - 40) // 40
        y = (event.y - 40) // 40
        if self.game.make_move(x, y):
            self.draw_piece(x, y)
            if self.game.check_win(x, y):
                self.show_winner()
    def draw_piece(self, x, y):
        color = "black" if self.game.current_player == 1 else "white"
        self.canvas.create_oval(40 + x * 40 - 18, 40 + y * 40 - 18, 40 + x * 40 + 18, 40 + y * 40 + 18, fill=color)
    def show_winner(self):
        winner = "Black" if self.game.current_player == 1 else "White"
        messagebox.showinfo("Game Over", f"{winner} wins!")
        self.master.quit()
if __name__ == "__main__":
    root = tk.Tk()
    app = GomokuApp(root)
    root.mainloop()