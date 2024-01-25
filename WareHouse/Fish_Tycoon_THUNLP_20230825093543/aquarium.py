'''
This file contains the Aquarium class which represents the virtual aquarium.
'''
import random
class Fish:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.speed = random.randint(1, 5)
    def update(self):
        self.x += self.speed
class Effect:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.speed = random.randint(1, 3)
    def update(self):
        self.x += self.speed
class Aquarium:
    def __init__(self):
        self.fishes = []
        self.effects = []
        for _ in range(10):
            x = random.randint(0, 780)
            y = random.randint(0, 580)
            self.fishes.append(Fish(x, y))
        for _ in range(5):
            x = random.randint(0, 780)
            y = random.randint(0, 580)
            self.effects.append(Effect(x, y))
    def update(self):
        for fish in self.fishes:
            fish.update()
        for effect in self.effects:
            effect.update()