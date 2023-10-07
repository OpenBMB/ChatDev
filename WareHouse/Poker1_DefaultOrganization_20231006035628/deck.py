'''
Deck module that defines the Deck class.
'''
import random
class Deck:
    def __init__(self):
        self.cards = self.create_deck()
    def create_deck(self):
        suits = ["Spades", "Hearts", "Diamonds", "Clubs"]
        ranks = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
        deck = []
        for suit in suits:
            for rank in ranks:
                deck.append(rank + " of " + suit)
        return deck
    def shuffle(self):
        random.shuffle(self.cards)
    def draw(self, num_cards):
        cards = []
        for _ in range(num_cards):
            cards.append(self.cards.pop())
        return cards