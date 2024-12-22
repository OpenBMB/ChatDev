class Player:
    def __init__(self, name):
        self.name = name
        self.hand = []
    def add_card(self, card):
        # Add a card to the player's hand
        self.hand.append(card)
    def remove_card(self, card):
        # Remove a card from the player's hand
        self.hand.remove(card)