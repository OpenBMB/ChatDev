'''
This file contains the Game class which represents the memory game.
'''
import tkinter as tk
from tkinter import messagebox
from card import CardItem
class Game:
    def __init__(self, root):
        self.root = root
        self.cards = []
        self.create_cards()
        self.shuffle_cards()
        self.create_board()
        self.current_card = None
        self.num_moves = 0
        self.num_matches = 0
        self.create_labels()
    def create_cards(self):
        # Create a list of card values
        values = ["A", "B", "C", "D", "E", "F", "G", "H"]
        # Create two instances of each card value
        for value in values:
            card1 = CardItem(value)
            card2 = CardItem(value)
            self.cards.append(card1)
            self.cards.append(card2)
    def shuffle_cards(self):
        # Shuffle the cards
        import random
        random.shuffle(self.cards)
    def create_board(self):
        # Create the card buttons on the board
        self.buttons = []
        for i, card in enumerate(self.cards):
            button = tk.Button(self.root, text=" ", width=5, height=3, command=lambda i=i: self.select_card(i))
            button.grid(row=i // 4, column=i % 4)
            card.button = button
            self.buttons.append(button)
    def create_labels(self):
        # Create labels for moves and matches
        self.moves_label = tk.Label(self.root, text="Moves: 0")
        self.moves_label.grid(row=len(self.cards) // 4 + 1, column=0, columnspan=2)
        self.matches_label = tk.Label(self.root, text="Matches: 0")
        self.matches_label.grid(row=len(self.cards) // 4 + 1, column=2, columnspan=2)
    def select_card(self, index):
        # Handle card selection
        card = self.cards[index]
        if not card.is_visible:
            card.show()
            if self.current_card is None:
                self.current_card = card
            else:
                if self.current_card.value == card.value:
                    self.current_card = None
                    self.num_matches += 1
                    self.matches_label.config(text="Matches: " + str(self.num_matches))
                    if self.num_matches == len(self.cards) // 2:
                        self.show_game_over_message()
                else:
                    self.root.after(1000, lambda: self.hide_cards(card))
                self.num_moves += 1
                self.moves_label.config(text="Moves: " + str(self.num_moves))
    def hide_cards(self, card):
        # Hide the selected cards
        self.current_card.hide()
        card.hide()
        self.current_card = None
    def show_game_over_message(self):
        # Show a game over message
        messagebox.showinfo("Game Over", "Congratulations! You have completed the game.")