import argparse
from graph import *
import yaml
import json


def load_config(config_file: str = "config.yaml"):
    """Load configuration from YAML file."""
    with open(config_file, "r", encoding="utf-8") as f:
        return yaml.load(f.read(), Loader=yaml.FullLoader)


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="argparse")
    parser.add_argument(
        "--config", type=str, default="config.yaml", help="Configuration file"
    )
    parser.add_argument(
        "--task",
        type=str,
        default="Develop a basic Gomoku game.",
        help="Prompt of software",
    )
    parser.add_argument("--name", type=str, default="Gomoku")
    parser.add_argument("--type", type=str, default="None")
    parser.add_argument(
        "--registry",
        type=str,
        default="models_registry.json",
        help="JSON file listing allowed models and tokens window size",
    )
    return parser.parse_args()


def main():
    """Main execution function."""
    args = parse_arguments()
    config = load_config(args.config)
    models_registry_file = args.registry
    model_name = config.get("Model")
    with open(models_registry_file, "r") as f:
        models_registry = json.load(f)["models"]

    model = ModelType("stub", 100000)
    model_known = False
    for m in models_registry:
        if m["name"] == model_name:
            model = ModelType(**m)
            model_known = True
            break
    if not model_known:
        raise ValueError(f"Unknown model: {model_name}")

    # Graph construction and agents deployment
    graph = Graph(config, model)
    graph.build_graph(args.type)
    graph.agent_deployment(args.type)
    graph.execute(args.task, args.name)

    with open(graph.directory + "/" + args.config, "w", encoding="utf-8") as f:
        yaml.dump(config, f)

    print("MacNet completes!")


if __name__ == "__main__":
    main()
