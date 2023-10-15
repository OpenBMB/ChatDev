'''
This is the main file of the maze game application.
'''
import tkinter as tk
from maze import Maze
class MazeGameApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Maze Game")
        self.geometry("400x400")
        self.maze = Maze()
        self.canvas = tk.Canvas(self, width=400, height=400)
        self.canvas.pack()
        self.draw_maze()
        self.bind("<KeyPress>", self.move_player)
        self.game_over = False
    def draw_maze(self):
        for row in range(self.maze.rows):
            for col in range(self.maze.cols):
                if self.maze.maze[row][col] == 1:
                    self.canvas.create_rectangle(col*40, row*40, (col+1)*40, (row+1)*40, fill="black")
    def move_player(self, event):
        if not self.game_over:
            if event.keysym == "Up":
                self.maze.move_player("up")
            elif event.keysym == "Down":
                self.maze.move_player("down")
            elif event.keysym == "Left":
                self.maze.move_player("left")
            elif event.keysym == "Right":
                self.maze.move_player("right")
            self.canvas.delete("player")
            self.canvas.create_oval(self.maze.player_col*40, self.maze.player_row*40, (self.maze.player_col+1)*40, (self.maze.player_row+1)*40, fill="red", tags="player")
            if self.maze.player_row == self.maze.goal_row and self.maze.player_col == self.maze.goal_col:
                self.canvas.create_text(200, 200, text="Congratulations! You have reached the goal!", font=("Arial", 16), fill="white")
                self.game_over = True
if __name__ == "__main__":
    app = MazeGameApp()
    app.mainloop()