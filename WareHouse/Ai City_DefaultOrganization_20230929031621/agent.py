'''
This file contains the Agent class which represents the AI agents in the stone age city.
'''
class Agent:
    def __init__(self):
        self.reproduction_count = 0
    def advance(self):
        self.reproduction_count += 1