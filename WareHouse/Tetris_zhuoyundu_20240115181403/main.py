import tkinter as tk
import random
from tetris_shapes import ShapeI, ShapeJ, ShapeL, ShapeO, ShapeS, ShapeT, ShapeZ
class Tetris:
    def __init__(self, root):
        self.root = root
        self.canvas = tk.Canvas(self.root, width=300, height=600, bg="white")
        self.canvas.pack()
        self.board = Board()
        self.current_shape = None
        self.is_game_over = False
        self.root.bind("<KeyPress>", self.handle_keypress)
        self.root.after(1000, self.update)
    def start_game(self):
        self.current_shape = self.generate_shape()
        self.draw()
    def update(self):
        if not self.is_game_over:
            self.move_shape_down()
            self.draw()
            self.root.after(1000, self.update)
    def draw(self):
        self.canvas.delete("all")
        self.draw_board()
        if self.current_shape:
            self.draw_shape(self.current_shape)
    def draw_board(self):
        for row in range(len(self.board.grid)):
            for col in range(len(self.board.grid[row])):
                if self.board.grid[row][col] == 1:
                    x1 = col * 30
                    y1 = row * 30
                    x2 = x1 + 30
                    y2 = y1 + 30
                    self.canvas.create_rectangle(x1, y1, x2, y2, fill="blue")
    def draw_shape(self, shape):
        for coord in shape.get_coordinates():
            x1 = coord[0] * 30
            y1 = coord[1] * 30
            x2 = x1 + 30
            y2 = y1 + 30
            self.canvas.create_rectangle(x1, y1, x2, y2, fill="red")
    def handle_keypress(self, event):
        if event.keysym == "Left":
            self.move_shape_left()
        elif event.keysym == "Right":
            self.move_shape_right()
        elif event.keysym == "Down":
            self.move_shape_down()
        elif event.keysym == "Up":
            self.rotate_shape()
    def move_shape_left(self):
        if self.current_shape:
            self.current_shape.move_left()
            if not self.board.is_valid_move(self.current_shape):
                self.current_shape.move_right()
    def move_shape_right(self):
        if self.current_shape:
            self.current_shape.move_right()
            if not self.board.is_valid_move(self.current_shape):
                self.current_shape.move_left()
    def move_shape_down(self):
        if self.current_shape:
            self.current_shape.move_down()
            if not self.board.is_valid_move(self.current_shape):
                self.current_shape.move_up()
                self.board.place_shape(self.current_shape)
                self.clear_lines()
                self.current_shape = self.generate_shape()
                if not self.board.is_valid_move(self.current_shape):
                    self.is_game_over = True
    def rotate_shape(self):
        if self.current_shape:
            self.current_shape.rotate()
            if not self.board.is_valid_move(self.current_shape):
                self.current_shape.rotate_back()
    def clear_lines(self):
        lines_to_clear = []
        for row in range(len(self.board.grid)):
            if all(self.board.grid[row]):
                lines_to_clear.append(row)
        for line in lines_to_clear:
            del self.board.grid[line]
            self.board.grid.insert(0, [0] * self.board.cols)
    def generate_shape(self):
        shapes = [ShapeI, ShapeJ, ShapeL, ShapeO, ShapeS, ShapeT, ShapeZ]
        shape = random.choice(shapes)
        return shape()
class Board:
    def __init__(self):
        self.rows = 20
        self.cols = 10
        self.grid = [[0] * self.cols for _ in range(self.rows)]
    def is_valid_move(self, shape):
        for coord in shape.get_coordinates():
            row = coord[1]
            col = coord[0]
            if row < 0 or row >= self.rows or col < 0 or col >= self.cols or self.grid[row][col] == 1:
                return False
        return True
    def place_shape(self, shape):
        for coord in shape.get_coordinates():
            row = coord[1]
            col = coord[0]
            self.grid[row][col] = 1
    def is_game_over(self):
        return any(self.grid[0])
if __name__ == "__main__":
    root = tk.Tk()
    tetris = Tetris(root)
    tetris.start_game()
    root.mainloop()