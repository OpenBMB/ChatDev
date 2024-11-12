import argparse
from graph import *
import yaml

def load_config():
    """Load configuration from YAML file."""
    with open("config.yaml", "r", encoding="utf-8") as f:
        return yaml.load(f.read(), Loader=yaml.FullLoader)

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='argparse')
    parser.add_argument('--task', type=str, default="Develop a basic Gomoku game.", help="Prompt of software")
    parser.add_argument('--name', type=str, default="Gomoku")
    parser.add_argument('--type', type=str, default="None")
    return parser.parse_args()

def main():
    """Main execution function."""
    config = load_config()
    args = parse_arguments()

    # Graph construction and agents deployment
    graph = Graph(config)
    graph.build_graph(args.type)
    graph.agent_deployment(args.type)
    graph.execute(args.task, args.name)

    with open(graph.directory + "/config.yaml", "w", encoding="utf-8") as f:
        yaml.dump(config, f)
    
    print("MacNet completes!")

if __name__ == "__main__":
    main()