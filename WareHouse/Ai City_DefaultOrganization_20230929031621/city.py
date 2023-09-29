'''
This file contains the City class which represents the stone age city.
'''
class City:
    def __init__(self):
        self.agents = []
    def add_agents(self, agents):
        self.agents.extend(agents)
    def advance(self):
        for agent in self.agents:
            agent.advance()