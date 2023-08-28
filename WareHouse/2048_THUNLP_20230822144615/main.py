'''
2048 Game
'''
import tkinter as tk
from game import Game
class GameApp:
    def __init__(self, master):
        self.master = master
        self.master.title("2048 Game")
        self.game = Game()
        self.create_widgets()
    def create_widgets(self):
        self.canvas = tk.Canvas(self.master, width=400, height=400, bg="white")
        self.canvas.pack()
        self.canvas.bind("<Key>", self.handle_keypress)
        self.canvas.focus_set()
    def handle_keypress(self, event):
        if event.keysym == "Up":
            self.game.move_up()
        elif event.keysym == "Down":
            self.game.move_down()
        elif event.keysym == "Left":
            self.game.move_left()
        elif event.keysym == "Right":
            self.game.move_right()
        self.update_grid()
        if self.game.is_game_over():
            self.canvas.unbind("<Key>")
            self.canvas.create_text(200, 200, text="Game Over", font=("Arial", 24), fill="red")
    def update_grid(self):
        self.canvas.delete("all")
        for row in range(10):
            for col in range(10):
                value = self.game.grid[row][col]
                x1 = col * 40
                y1 = row * 40
                x2 = x1 + 40
                y2 = y1 + 40
                self.canvas.create_rectangle(x1, y1, x2, y2, fill="light gray")
                if value != 0:
                    self.canvas.create_text((x1 + x2) / 2, (y1 + y2) / 2, text=str(value))
        self.canvas.update()
def main():
    root = tk.Tk()
    app = GameApp(root)
    root.mainloop()
if __name__ == "__main__":
    main()