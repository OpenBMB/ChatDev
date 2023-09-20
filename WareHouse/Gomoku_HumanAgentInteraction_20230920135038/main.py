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
        self.canvas = tk.Canvas(self.master, width=500, height=500, bg="white")
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self.on_click)
        self.draw_board()
        self.restart_button = tk.Button(self.master, text="Restart", command=self.restart)
        self.restart_button.pack()
        self.status_bar = tk.Label(self.master, text="Black's Turn", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    def draw_board(self):
        self.canvas.delete("all")
        cell_width = 500 / 15
        cell_height = 500 / 15
        for row in range(15):
            self.canvas.create_line(0, row * cell_height, 500, row * cell_height)
        for col in range(15):
            self.canvas.create_line(col * cell_width, 0, col * cell_width, 500)
    def on_click(self, event):
        cell_width = 500 / 15
        cell_height = 500 / 15
        x = int(event.x // cell_width)
        y = int(event.y // cell_height)
        if self.game.make_move(x, y):
            self.draw_piece(x, y)
            self.update_status_bar()
        if self.game.check_winner(x, y):
            self.show_winner()
    def draw_piece(self, x, y):
        cell_width = 500 / 15
        cell_height = 500 / 15
        oval_coords = (x * cell_width, y * cell_height, (x + 1) * cell_width, (y + 1) * cell_height)
        color = "black" if self.game.current_player == 1 else "white"
        self.canvas.create_oval(*oval_coords, fill=color)
    def show_winner(self):
        winner = "Black" if self.game.current_player == 1 else "White"
        messagebox.showinfo("Game Over", f"{winner} wins!")
        self.canvas.unbind("<Button-1>")
        self.restart_button.pack_forget()
        self.canvas.bind("<Button-1>", self.restart)
    def restart(self):
        self.game.reset()
        self.draw_board()
        self.canvas.unbind("<Button-1>")
        self.canvas.bind("<Button-1>", self.on_click)
        self.restart_button.pack()
        self.update_status_bar()
    def update_status_bar(self):
        player = "Black" if self.game.current_player == 1 else "White"
        self.status_bar.config(text=f"{player}'s Turn")
if __name__ == "__main__":
    root = tk.Tk()
    app = GomokuApp(root)
    root.mainloop()