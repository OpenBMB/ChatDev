'''
This file contains the Maze class that represents the maze in the game.
'''
import random
import tkinter as tk
class Maze:
    def __init__(self):
        self.rows = 10
        self.cols = 10
        self.maze = [[0] * self.cols for _ in range(self.rows)]
        self.player_row = 0
        self.player_col = 0
        self.goal_row = self.rows - 1
        self.goal_col = self.cols - 1
        self.generate_maze()
    def generate_maze(self):
        # Generate a random maze
        for row in range(self.rows):
            for col in range(self.cols):
                if random.random() < 0.3:
                    self.maze[row][col] = 1
    def move_player(self, direction):
        if direction == "up" and self.player_row > 0 and self.maze[self.player_row-1][self.player_col] != 1:
            self.player_row -= 1
        elif direction == "down" and self.player_row < self.rows-1 and self.maze[self.player_row+1][self.player_col] != 1:
            self.player_row += 1
        elif direction == "left" and self.player_col > 0 and self.maze[self.player_row][self.player_col-1] != 1:
            self.player_col -= 1
        elif direction == "right" and self.player_col < self.cols-1 and self.maze[self.player_row][self.player_col+1] != 1:
            self.player_col += 1
        if self.player_row == self.goal_row and self.player_col == self.goal_col:
            print("Congratulations! You have reached the goal!")