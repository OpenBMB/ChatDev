'''
This file contains the Hand class to manage a player's hand in the UNO game.
'''
class Hand:
    def __init__(self):
        self.cards = []
    def add_card(self, card):
        self.cards.append(card)
    def remove_card(self, card):
        if card in self.cards:
            self.cards.remove(card)
    def get_cards(self):
        return self.cards