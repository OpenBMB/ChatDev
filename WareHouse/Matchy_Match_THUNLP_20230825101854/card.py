'''
This file contains the CardItem class which represents a single card in the memory game.
'''
import tkinter as tk
class CardItem:
    def __init__(self, value):
        self.value = value
        self.button = None
        self.is_visible = False
    def __str__(self):
        return str(self.value)
    def show(self):
        # Show the card value
        self.button.config(text=str(self))
        self.is_visible = True
    def hide(self):
        # Hide the card value
        self.button.config(text=" ")
        self.is_visible = False