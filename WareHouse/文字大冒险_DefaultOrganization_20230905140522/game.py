'''
This file contains the Game class which represents the game logic.
'''
import random
import tkinter as tk
class Game:
    def __init__(self):
        self.level = 1
        self.maze = None
        self.player_position = None
        self.goal_position = None
    def start(self, canvas):
        self.generate_maze()
        self.draw_maze(canvas)
    def generate_maze(self):
        # Generate a random maze
        self.maze = []
        for _ in range(10):
            row = []
            for _ in range(10):
                if random.random() < 0.3:
                    row.append('墙')
                else:
                    row.append(' ')
            self.maze.append(row)
        self.player_position = (0, 0)
        self.goal_position = (9, 9)
    def draw_maze(self, canvas):
        # Draw the maze on the canvas
        canvas.delete('all')
        for i, row in enumerate(self.maze):
            for j, cell in enumerate(row):
                x1 = j * 50
                y1 = i * 50
                x2 = x1 + 50
                y2 = y1 + 50
                canvas.create_rectangle(x1, y1, x2, y2, fill='white')
                if cell == '墙':
                    canvas.create_text((x1 + x2) / 2, (y1 + y2) / 2, text='墙')
                elif cell == '门':
                    canvas.create_text((x1 + x2) / 2, (y1 + y2) / 2, text='门')
                elif cell == '怪':
                    canvas.create_text((x1 + x2) / 2, (y1 + y2) / 2, text='怪')
    def handle_key_press(self, event):
        # Handle keyboard events
        if event.keysym == 'Up':
            self.move_player(-1, 0)
        elif event.keysym == 'Down':
            self.move_player(1, 0)
        elif event.keysym == 'Left':
            self.move_player(0, -1)
        elif event.keysym == 'Right':
            self.move_player(0, 1)
    def move_player(self, dx, dy):
        x, y = self.player_position
        new_x = x + dx
        new_y = y + dy
        if self.is_valid_move(new_x, new_y):
            self.player_position = (new_x, new_y)
            if self.player_position == self.goal_position:
                self.level += 1
                self.generate_maze()
    def is_valid_move(self, x, y):
        if x < 0 or x >= len(self.maze) or y < 0 or y >= len(self.maze[0]):
            return False
        return self.maze[x][y] != '墙'