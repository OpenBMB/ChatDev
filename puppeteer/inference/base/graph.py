from typing import List, Any
from abc import ABC, abstractmethod
from inference.base.edge import Edge


class Graph(ABC):
    def __init__(self) -> None:
        self._nodes = []
        self._edges = []
        self._nodes_num = 0 
        self._edges_num = 0
    
    def initialize_nodes(self, nodes: List[Any]):
        self._nodes = nodes
    
    def _add_node(self, node):
        self._nodes.append(node)

    def _add_edge(self, node1, node2, index):
        edge = Edge(node1, node2, index)
        self._edges.append(edge)
    
    def _get_edge(self, node1, node2):
        idx_list = []
        for edge in self._edges:
            if edge.u == node1 and edge.v == node2:
                idx_list.append(edge.index)
        
        if len(idx_list) > 0:
            return idx_list
        else:        
            return None
    
    def _remove_edges(self, node1, node2):
        self._edges = [edge for edge in self._edges if edge != (node1, node2)]
    
    def adjacency_matrix(self):
        matrix = [[0 for _ in range(len(self._nodes))] for _ in range(len(self._nodes))]
        for edge in self._edges:
            matrix[edge[0].index][edge[1].index] = 1
        return matrix
    
    @abstractmethod
    def visualize(self):
        pass
    