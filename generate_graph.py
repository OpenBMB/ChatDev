import random
import time
import math
from graphviz import Digraph
import subprocess

class Edge:
    """Represents an edge in a graph with a source and target node."""
    def __init__(self, source: int, target: int):
        self.source = source
        self.target = target

class Graph:
    """Represents a directed graph with various methods to generate and analyze graph structures."""
    def __init__(self, node_num: int, topo: str):
        self.name = topo
        self.node_num = node_num
        self.edges = []
    
    def display_image_with_imgcat(self, image_path):
        """Display the image with imgcat"""
        subprocess.run(["imgcat", image_path])

    def exists_edge(self, source: int, target: int) -> bool:
        """Checks if an edge exists between the source and target nodes."""
        return any(edge.source == source and edge.target == target for edge in self.edges)

    def generate_chain(self):
        """Generates a chain graph with the specified number of nodes."""
        for i in range(self.node_num - 1):
            self.edges.append(Edge(i, i + 1))
        assert len(self.edges) == self.node_num - 1
        return self

    def generate_star(self):
        """Generates a star graph with the specified number of nodes."""
        for i in range(1, self.node_num):
            self.edges.append(Edge(0, i))
        assert len(self.edges) == self.node_num - 1
        return self

    def generate_tree(self):
        """Generates a tree graph with the specified number of nodes."""
        i = 0
        while True:
            self.edges.append(Edge(i, 2 * i + 1))
            if len(self.edges) >= self.node_num - 1:
                break
            self.edges.append(Edge(i, 2 * i + 2))
            if len(self.edges) >= self.node_num - 1:
                break
            i += 1
        assert len(self.edges) == self.node_num - 1
        return self

    def generate_net(self):
        """Generates a complete net graph with the specified number of nodes."""
        for u in range(self.node_num):
            for v in range(self.node_num):
                if u < v:
                    self.edges.append(Edge(u, v))
        assert len(self.edges) == self.node_num * (self.node_num - 1) / 2
        return self

    def generate_mlp(self):
        """Generates a multi-layer perceptron (MLP) graph with the specified number of nodes."""
        layer_num = int(math.log(self.node_num, 2))
        layers = [self.node_num // layer_num for _ in range(layer_num)]
        layers[0] += self.node_num % layer_num

        end_ids, start_ids = [layers[0]], [0]
        for i in range(1, len(layers)):
            start_ids.append(end_ids[-1])
            end_ids.append(end_ids[-1] + layers[i])

        for i in range(len(layers) - 1):
            for u in range(start_ids[i], end_ids[i]):
                for v in range(start_ids[i + 1], end_ids[i + 1]):
                    self.edges.append(Edge(u, v))

        return self

    def generate_random(self):
        """Generates a random graph with the specified number of nodes."""
        self.name = "random"
        edge_num = random.randint(self.node_num-1, self.node_num*(self.node_num-1)/2)
        edges_space = [(u, v) for u in range(self.node_num) for v in range(self.node_num) if u < v]
        random.shuffle(edges_space)

        for i in range(edge_num):
            (u, v) = edges_space[i]
            self.edges.append(Edge(u, v))

        return self

    def get_list(self, reverse=False):
        """Returns a list of edges in the graph, optionally reversed."""
        return [(edge.target, edge.source) if reverse else (edge.source, edge.target) for edge in self.edges]

    def reverse(self):
        """Reverses the direction of all edges in the graph."""
        self.edges = [Edge(edge.target, edge.source) for edge in self.edges]
        return self

    def view(self, reverse=False):
        """Visualizes the graph using Graphviz and saves it to a file."""
        graph_viz = Digraph(format="png", node_attr={"shape": "circle"}, edge_attr={"arrowhead": "normal"})
        llist = self.get_list(reverse)
        for (u, v) in llist:
            graph_viz.edge(str(u), str(v))
        timestamp = time.strftime("%Y%m%d%H%M%S", time.localtime())
        graph_viz.render(directory="./tmp/generated_graphs", filename="graph_{}_{}_{}".format(self.name, self.node_num, timestamp))
        self.display_image_with_imgcat(f"./tmp/generated_graphs/graph_{self.name}_{self.node_num}_{timestamp}.png")
        return self

    def generate_graph(self, reverse=False):
        """Generates a graph based on the specified topology and number of nodes."""
        if self.name == "chain":
            self.generate_chain()
        elif self.name == "star":
            self.generate_star()
        elif self.name == "tree":
            self.generate_tree()
        elif self.name == "net":
            self.generate_net()
        elif self.name == "mlp":
            self.generate_mlp()
        elif self.name == "random":
            self.generate_random()
        else:
            raise ValueError("Invalid topology type specified.")

        # Generate graph structure for config.yaml
        edges = self.get_list(reverse)
        graph_structure = [f"{edge[0]}->{edge[1]}" for edge in edges]
        
        # Read existing config.yaml and update the graph field
        with open("config.yaml", "r") as config_file:
            config_data = config_file.readlines()

        with open("config.yaml", "w") as config_file:
            for line in config_data:
                if line.startswith("graph:"):
                    config_file.write(f'graph: {graph_structure}\n')
                else:
                    config_file.write(line)
        
        return graph_structure

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate a graph based on specified parameters.")
    parser.add_argument("--node_num", type=int, required=True, help="Number of nodes in the graph.")
    parser.add_argument("--topology", type=str, required=True, choices=["chain", "star", "tree", "net", "mlp", "random"], help="Type of graph topology to generate.")
    parser.add_argument("--reverse", action='store_true', required=False, help="Whether or not reverse the graph.")
    args = parser.parse_args()

    graph = Graph(node_num=args.node_num, topo=args.topology)
    graph_structure = graph.generate_graph(args.reverse)
    print("graph:", graph_structure)  # This will replace the graph field in config.yaml
    graph.view(args.reverse)
