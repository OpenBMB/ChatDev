'''
The graphical user interface for the Gomoku game.
'''
import tkinter as tk
class GomokuGUI:
    def __init__(self, game):
        self.game = game
        self.window = tk.Tk()
        self.window.title("Gomoku")
        self.window.geometry("400x400")
        self.canvas = tk.Canvas(self.window, width=400, height=400)
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self.on_click)
        self.draw_board()
    def run(self):
        self.window.mainloop()
    def draw_board(self):
        self.canvas.delete("all")
        for row in range(15):
            for col in range(15):
                x1 = col * 25
                y1 = row * 25
                x2 = x1 + 25
                y2 = y1 + 25
                if self.game.board[row][col] == 1:
                    self.canvas.create_oval(x1, y1, x2, y2, fill="black")
                elif self.game.board[row][col] == 2:
                    self.canvas.create_oval(x1, y1, x2, y2, fill="white")
    def on_click(self, event):
        row = event.y // 25
        col = event.x // 25
        winner = self.game.make_move(row, col)
        if winner:
            self.canvas.unbind("<Button-1>")
            tk.messagebox.showinfo("Game Over", f"Player {winner} wins!")
        else:
            self.draw_board()