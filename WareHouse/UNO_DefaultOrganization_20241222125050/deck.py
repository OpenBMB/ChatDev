'''
This file contains the Deck class to manage the UNO card deck.
'''
import random
class Deck:
    def __init__(self):
        self.cards = []
        self.create_deck()
    def create_deck(self):
        colors = ["Red", "Green", "Blue", "Yellow"]
        values = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "Skip", "Reverse", "Draw Two"]
        for color in colors:
            self.cards.append(color + " 0")  # Adding zero cards
            for value in values:
                if value != "0":
                    self.cards.append(color + " " + value)  # Adding non-zero cards
        random.shuffle(self.cards)
    def draw_card(self):
        if len(self.cards) > 0:
            return self.cards.pop()
        else:
            return None