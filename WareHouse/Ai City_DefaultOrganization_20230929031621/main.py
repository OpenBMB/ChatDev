'''
This is the main file that will run the stone age city simulation.
'''
from city import City
from agent import Agent
from ui import UI
def main():
    # Create a stone age city
    city = City()
    # Create 10 AI agents
    agents = []
    for _ in range(10):
        agent = Agent()
        agents.append(agent)
    # Add agents to the city
    city.add_agents(agents)
    # Create UI
    ui = UI(city)
    # Start the simulation
    ui.run()
if __name__ == "__main__":
    main()