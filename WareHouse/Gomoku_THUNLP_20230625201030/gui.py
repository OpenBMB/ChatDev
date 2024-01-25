'''
This file contains the GUI class for creating the graphical user interface for the gomoku game.
'''
import tkinter as tk
from PIL import Image, ImageTk
from tkinter import messagebox
class GUI:
    def __init__(self, game):
        # Initialize GUI variables
        self.game = game
        self.black_chess_piece_image = None
        self.white_chess_piece_image = None
        self.background_image = None
        # Create the main window
        self.window = tk.Tk()
        self.window.title("Gomoku")
        self.window.geometry("600x600")
        # Load the images
        self.load_images()
        # Create the game board
        self.create_board()
    def load_images(self):
        self.black_chess_piece_image = ImageTk.PhotoImage(Image.open("./black_chess_piece.png").resize((50, 50)))
        self.white_chess_piece_image = ImageTk.PhotoImage(Image.open("./white_chess_piece.png").resize((50, 50)))
        self.background_image = ImageTk.PhotoImage(Image.open("./background.png").resize((600, 600)))
    def create_board(self):
        self.board_frame = tk.Frame(self.window)
        self.board_frame.pack()
        self.buttons = []
        for row in range(15):
            row_buttons = []
            for col in range(15):
                button = tk.Button(self.board_frame, width=50, height=50, image=self.background_image,
                                   command=lambda r=row, c=col: self.make_move(r, c))
                button.grid(row=row, column=col)
                row_buttons.append(button)
            self.buttons.append(row_buttons)
        self.update_board_gui()
    def make_move(self, row, col):
        self.game.make_move(row, col)
        self.update_board_gui()
        if self.game.game_over:
            if self.game.is_board_full():
                self.show_game_over_message("It's a draw!")
            else:
                self.show_game_over_message(f"Player {3 - self.game.current_player} wins!")
    def show_game_over_message(self, result):
        messagebox.showinfo("Game Over", result)
    def update_board_gui(self):
        for row in range(15):
            for col in range(15):
                if self.game.board[row][col] == 1:
                    self.buttons[row][col].config(image=self.black_chess_piece_image, state=tk.DISABLED)
                elif self.game.board[row][col] == 2:
                    self.buttons[row][col].config(image=self.white_chess_piece_image, state=tk.DISABLED)
    def run(self):
        self.window.mainloop()