'''
This is the main file of the maze generator application.
'''
import tkinter as tk
import random
from maze import Maze
class MazeGeneratorApp:
    def __init__(self, master):
        self.master = master
        self.master.title("Maze Generator")
        self.canvas = tk.Canvas(self.master, width=500, height=500)
        self.canvas.pack()
        self.generate_button = tk.Button(self.master, text="Generate Maze", command=self.generate_maze)
        self.generate_button.pack()
        self.maze = None
    def generate_maze(self):
        self.canvas.delete("all")
        # Create a new maze object
        self.maze = Maze(20, 20)
        # Generate the maze
        self.maze.generate()
        # Draw the maze on the canvas
        cell_size = 20
        start_row = random.randint(0, self.maze.rows - 1)
        start_col = random.randint(0, self.maze.cols - 1)
        end_row = random.randint(0, self.maze.rows - 1)
        end_col = random.randint(0, self.maze.cols - 1)
        for row in range(self.maze.rows):
            for col in range(self.maze.cols):
                x1 = col * cell_size
                y1 = row * cell_size
                x2 = x1 + cell_size
                y2 = y1 + cell_size
                if self.maze.grid[row][col].walls["top"]:
                    self.canvas.create_line(x1, y1, x2, y1)
                if self.maze.grid[row][col].walls["right"]:
                    self.canvas.create_line(x2, y1, x2, y2)
                if self.maze.grid[row][col].walls["bottom"]:
                    self.canvas.create_line(x1, y2, x2, y2)
                if self.maze.grid[row][col].walls["left"]:
                    self.canvas.create_line(x1, y1, x1, y2)
                if row == start_row and col == start_col:
                    self.canvas.create_rectangle(x1, y1, x2, y2, fill="green")
                if row == end_row and col == end_col:
                    self.canvas.create_rectangle(x1, y1, x2, y2, fill="red")
# Create the main window
root = tk.Tk()
# Create the maze generator app
app = MazeGeneratorApp(root)
# Start the main event loop
root.mainloop()