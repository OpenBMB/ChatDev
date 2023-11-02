'''
The GUI class representing the graphical user interface.
'''
import tkinter as tk
from tkinter import messagebox
class GUI:
    def __init__(self, game):
        self.game = game
        self.window = tk.Tk()
        self.window.title("Rock, Paper, Scissors")
        self.window.geometry("300x200")
        self.message_label = tk.Label(self.window, text="Make your choice:")
        self.message_label.pack()
        self.choices_frame = tk.Frame(self.window)
        self.choices_frame.pack()
        self.rock_button = tk.Button(self.choices_frame, text="Rock", command=self.play_rock)
        self.rock_button.pack(side=tk.LEFT)
        self.paper_button = tk.Button(self.choices_frame, text="Paper", command=self.play_paper)
        self.paper_button.pack(side=tk.LEFT)
        self.scissors_button = tk.Button(self.choices_frame, text="Scissors", command=self.play_scissors)
        self.scissors_button.pack(side=tk.LEFT)
        self.scores_label = tk.Label(self.window, text="Scores: Player - 0, Computer - 0")
        self.scores_label.pack()
    def run(self):
        self.window.mainloop()
    def play_rock(self):
        self.play_round("rock")
    def play_paper(self):
        self.play_round("paper")
    def play_scissors(self):
        self.play_round("scissors")
    def play_round(self, player_choice):
        self.game.play_round(player_choice)
        self.update_scores()
        self.update_choices()
        winner = self.game.determine_winner(self.game.player_choice, self.game.computer_choice)
        if winner == "player":
            messagebox.showinfo("Result", "You win!")
        elif winner == "computer":
            messagebox.showinfo("Result", "Computer wins!")
        else:
            messagebox.showinfo("Result", "It's a tie!")
    def update_scores(self):
        scores_text = f"Scores: Player - {self.game.player_score}, Computer - {self.game.computer_score}"
        self.scores_label.config(text=scores_text)
    def update_choices(self):
        self.message_label.config(text=f"Your choice: {self.game.player_choice}, Computer's choice: {self.game.computer_choice}")