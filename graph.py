import copy
import logging
import os
import random
import signal
import subprocess
import time
from typing import Tuple

import yaml
from camel.agents.chat_agent import ChatAgent
from camel.messages import ChatMessage, SystemMessage
from camel.typing import ModelType, RoleType
from chatdev.codes import Codes
from chatdev.richshell import color_code_diff, justify_in_box
from chatdev.waiting import Pool
from graphviz import Digraph
import subprocess

now = time.strftime("%Y%m%d%H%M%S", time.localtime())

# Set up logging configuration
os.makedirs("./tmp/generated_graphs", exist_ok=True)
os.makedirs("./MacNetLog", exist_ok=True)
os.makedirs("./WareHouse", exist_ok=True)
os.makedirs(f"./MacNetLog/{now}", exist_ok=True)

formatter = logging.Formatter("[%(asctime)s\t%(filename)s]\n%(message)s\n---\n", "%Y-%m-%d %H:%M:%S")
logger = logging.getLogger()
logger.setLevel(logging.INFO)

log_dir = f"./MacNetLog/{now}"
filehandler = logging.FileHandler(filename=f"{log_dir}/{now}.log", encoding="gbk")
filehandler.setFormatter(formatter)
logger.addHandler(filehandler)

console = logging.StreamHandler()
console.setFormatter(formatter)
logger.addHandler(console)


def log_info(message: str, to_console: bool = True) -> None:
    """Log information to console or file."""
    if not to_console:
        logger.removeHandler(console)
    logger.info(message)
    if not to_console:
        logger.addHandler(console)


class Node:
    def __init__(self, node_id: int, temperature: float = 0.2, model: str = "GPT_4O_MINI") -> None:
        """Initialize a Node."""
        self.id: int = node_id
        self.predecessors: list[Node] = []
        self.successors: list[Node] = []
        self.pre_solutions: dict[int, Codes] = {}
        self.solution: Codes = Codes()
        self.frequency_penalty: float = 0.0
        self.presence_penalty: float = 0.0
        self.temperature: float = temperature
        self.system_message: str = " "
        self.pool = None
        self.depth: int = 0

        args2type = {
            'GPT_3_5_TURBO': ModelType.GPT_3_5_TURBO_NEW,
            'GPT_4': ModelType.GPT_4,
            'GPT_4_TURBO': ModelType.GPT_4_TURBO,
            'GPT_4O': ModelType.GPT_4O,
            'GPT_4O_MINI': ModelType.GPT_4O_MINI,
        }
        self.model = args2type[model]

    def create_agent(self, content: str, role_name: str) -> ChatAgent:
        """Create a chat agent."""
        agent = ChatAgent(
            system_message=SystemMessage(content=content, role_name=role_name, role_type=RoleType.ASSISTANT),
            model=self.model,
            temperature=self.temperature,
        )
        return agent

    def exist_bugs(self, directory: str) -> Tuple[bool, str]:
        """Check if there are bugs in the software."""
        success_info = "The software run successfully without errors."
        try:
            if os.name == 'nt':
                command = f"cd {directory} && dir && python main.py"
                process = subprocess.Popen(
                    command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                )
            else:
                command = f"cd {directory} && python3 main.py;"
                process = subprocess.Popen(command,
                                           shell=True,
                                           preexec_fn=os.setsid,
                                           stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE
                                           )
            time.sleep(3)
            return_code = process.returncode
            if process.poll() is None:
                if "killpg" in dir(os):
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                else:
                    os.kill(process.pid, signal.SIGTERM)
                    if process.poll() is None:
                        os.kill(process.pid, signal.CTRL_BREAK_EVENT)
            if return_code == 0:
                return False, success_info
            else:
                error_output = process.stderr.read().decode('utf-8')
                if error_output:
                    if "Traceback".lower() in error_output.lower():
                        errs = error_output.replace(directory + "/", "")
                        return True, errs
                else:
                    return False, success_info
        except subprocess.CalledProcessError as e:
            return True, f"Error: {e}"
        except Exception as ex:
            return True, f"An error occurred: {ex}"
        
        return False, success_info

    def optimize(self, task_prompt: str, pre_solution: str, config: dict, name: str) -> Tuple[str, Codes, str]:
        """Optimize a single solution."""
        logging.info(f"Node {self.id} is optimizing")
        success_info = "The software run successfully without errors."
        error_info = "The software run failed with errors."
        self.suggestions = "None."

        if pre_solution != "":
            instructor_prompt = config.get("Agent").get("instructor_prompt").format(task_prompt, pre_solution)
            message = ChatMessage(content=instructor_prompt,
                                  role_name="User",
                                  role_type=RoleType.USER,
                                  meta_dict=dict(),
                                  role="user")
            self.suggestions = self.create_agent(self.system_message, "assistant").step(message).msgs[0].content

            if self.suggestions.startswith("<API>compile()</API>"):
                pre_codes = Codes(pre_solution)
                pre_codes.write_codes_to_hardware(name)
                dir_name = f"./WareHouse/{name}"
                compiler_flag, compile_info = self.exist_bugs(dir_name)

                if not compiler_flag:
                    self.suggestions = success_info + "\n" + self.suggestions
                else:
                    self.suggestions = error_info + "\n" + compile_info + "\n" + self.suggestions
                    instructor_prompt = "Compiler's feedback: " + error_info + "\n" + compile_info + \
                                        "pre_comments:" + self.suggestions + "\n" + instructor_prompt
                    message = ChatMessage(content=instructor_prompt,
                                          role_name="User",
                                          role_type=RoleType.USER,
                                          meta_dict=dict(),
                                          role="user")
                    self.suggestions = self.create_agent(self.system_message, "assistant").step(message).msgs[0].content
                    self.suggestions = error_info + "\n" + compile_info + "\n" + self.suggestions

        assistant_prompt = config.get("Agent").get("assistant_prompt").format(task_prompt, pre_solution,
                                                                              self.suggestions)
        message = ChatMessage(content=assistant_prompt,
                              role_name="User",
                              role_type=RoleType.USER,
                              meta_dict=dict(),
                              role="user")
        response = self.create_agent(self.system_message, "assistant").step(message).msgs[0].content
        response = "" if response is None else response
        response = response.replace("```", "\n```").replace("'''", "\n'''")
        try:
            codes = Codes(response)
        except Exception as e:
            print(f"Node {self.id} failed to optimize: {e}")
            codes = Codes()

        return response, codes, self.suggestions

    def aggregate(self, prompt: str, retry_limit: int, unit_num: int, layer_directory: str, graph_depth: int,
                  store_dir: str) -> int:
        """Aggregate solutions from predecessors."""
        logging.info(f"Node {self.id} is aggregating with {len(self.pre_solutions)} solutions")

        with open("config.yaml", "r", encoding="utf-8") as f:
            cc_prompt = "\n\n".join(yaml.load(f.read(), Loader=yaml.FullLoader).get("Agent").get("cc_prompt"))
            cc_prompt = self.system_message + cc_prompt

        for file in self.pre_solutions:
            with open(layer_directory + "/solution_{}.txt".format(file), "w") as f:
                for key in self.pre_solutions[file].codebooks.keys():
                    f.write(str(key) + '\n\n' + self.pre_solutions[file].codebooks[key] + '\n\n')

        self.pool = Pool(len(self.pre_solutions), unit_num, layer_directory, self.model)
        for i in range(retry_limit):
            new_codes = self.pool.state_pool_add(layer_directory, cc_prompt, 6000000, prompt,
                                                 Codes(),
                                                 store_dir,
                                                 temperature=1 - self.depth / graph_depth,
                                                 )
            if new_codes is None:
                logging.info(f"Retry Aggregation at round {i}!")
            else:
                self.solution = new_codes
                logging.info(f"Node {self.id} has finished aggregation!")
                return 0
        print(f"ERROR: Node {self.id} has reached the retry limit!\n")
        return 1

    def add_successor(self, node: 'Node') -> None:
        """Add a successor node."""
        self.successors.append(node)

    def add_predecessor(self, node: 'Node') -> None:
        """Add a predecessor node."""
        self.predecessors.append(node)


def parse_string(s: str) -> list[list[Tuple[int, int]]]:
    """Parse a string into individual parts."""

    def parse_part(part: str) -> list[Tuple[int, int]]:
        return_list = []
        for sub_part in part.split(','):
            if '-' in sub_part:
                start, end = map(int, sub_part.split('-'))
                return_list.append((start, end))
            else:
                num = int(sub_part)
                return_list.append((num, num))
        return return_list

    return [parse_part(part) for part in s.split("->")]


class Graph:
    """Represents a directed graph with various methods to generate and analyze graph structures."""

    def __init__(self, config: dict) -> None:
        """Initialize the Graph."""
        self.config = config
        self.now = time.strftime("%Y%m%d%H%M%S", time.localtime())
        self.node_in = Node(node_id=config.get("Node_in_id"), model=config.get("Model"))
        self.node_out = Node(node_id=config.get("Node_out_id"), model=config.get("Model"))
        self.nodes = {config.get("Node_in_id"): self.node_in, config.get("Node_out_id"): self.node_out}
        self.height = 0
        self.input_layer = None
        self.output_layer = None
        self.aggregate_retry_limit = config.get("Aggregate_retry_limit")
        self.aggregate_unit_num = config.get("Aggregate_unit_num")
        self.directory = f"./MacNetLog/{time.strftime('%Y%m%d%H%M%S', time.localtime())}"
        self.depth = 0
        self.model_types = None

    def build_graph(self, type_: str) -> None:
        """Build the graph from the configuration."""
        for raw_line in self.config.get("graph"):
            line = parse_string(raw_line)
            if len(line) == 1:  # In case there is only one layer
                for node_id in range(line[0][0][0], line[0][0][1] + 1):
                    if node_id not in self.nodes:
                        self.add_node(Node(node_id, model=self.config.get("Model")))
            for i in range(len(line) - 1):
                from_node_list = line[i]
                to_node_list = line[i + 1]
                for from_node_tuple in from_node_list:
                    for from_node_id in range(from_node_tuple[0], from_node_tuple[1] + 1):
                        for to_node_tuple in to_node_list:
                            for to_node_id in range(to_node_tuple[0], to_node_tuple[1] + 1):
                                if from_node_id not in self.nodes:
                                    self.add_node(Node(from_node_id, model=self.config.get("Model")))
                                if to_node_id not in self.nodes:
                                    self.add_node(Node(to_node_id, model=self.config.get("Model")))
                                self.add_edge(from_node_id, to_node_id)
        self.input_layer = self.get_input_layer()
        self.output_layer = self.get_output_layer()

        for input_nodes in self.input_layer:
            if (input_nodes.id != self.node_in.id) and (input_nodes.id != self.node_out.id):
                self.add_edge(self.node_in.id, input_nodes.id)

        for output_nodes in self.output_layer:
            if output_nodes.id != self.node_out.id and output_nodes.id != self.node_in.id:
                self.add_edge(output_nodes.id, self.node_out.id)

        if self.circular_check():
            print("ERROR: The graph has circular dependency!")
            self.view(view=True)
            exit(1)
        else:
            self.view()
        self.depth = self.agent_deployment(type_)
    
    def display_image_with_imgcat(self, image_path):
        """Display the image with imgcat"""
        subprocess.run(["imgcat", image_path])

    def view(self, view: bool = False) -> None:
        """Visualize the graph using Graphviz and save it to a file."""
        graph_viz = Digraph(format="png", node_attr={"shape": "circle"}, edge_attr={"arrowhead": "normal"})
        for node in self.nodes.values():
            for successor in node.successors:
                graph_viz.edge(str(node.id), str(successor.id))
        if view:
            graph_viz.view(directory=f"./MacNetLog/{self.now}", filename=f"graph_{self.now}")
        graph_viz.render(directory=f"./MacNetLog/{self.now}", filename=f"graph_{self.now}")
        print("MacNet starts running based on the following graph:")
        self.display_image_with_imgcat(f"./MacNetLog/{self.now}/graph_{self.now}.png")

    def execute(self, prompt: str, name: str) -> None:
        """Execute the reasoning process for the graph."""
        layer = 0
        logging.info(f"Now MacNet starts building the software: {name}")

        while True:
            input_nodes = self.get_input_layer()

            if len(input_nodes) == 0:
                os.makedirs(f"./WareHouse/{name}", exist_ok=True)
                with open(f"./WareHouse/{name}/prompt.txt", "w", encoding="utf-8") as f:
                    f.write(prompt)
                break

            cur_layer_dir = self.directory + f"/Layer {layer}"
            os.makedirs(cur_layer_dir, exist_ok=True)
            if layer == 0 and not os.path.exists(cur_layer_dir + "/Node -1"):
                os.makedirs(cur_layer_dir + "/Node -1")
                with open(cur_layer_dir + "/Node -1/solution.txt", "w", encoding="utf-8") as f:
                    f.write(prompt)

            visited_edges, next_nodes = set(), set()
            for cur_node in input_nodes:
                with open(cur_layer_dir + f"/Node {cur_node.id}/profile.txt", "w", encoding="utf-8") as f:
                    f.write(cur_node.system_message)

                for next_node in cur_node.successors:
                    response, optimized_solution, suggestion = next_node.optimize(task_prompt=prompt,
                                                                                pre_solution=cur_node.solution._get_codes(),
                                                                                config=self.config,
                                                                                name=name)
                    next_node.pre_solutions[cur_node.id] = optimized_solution
                    print("----------------------------------------------Complete!----------------------------------------------------------------------")
                    print(f"(Original Solution on Node {cur_node.id}) ---(Suggestions from Node {next_node.id} on Node {cur_node.id})---> (Optimized Solution on Node {next_node.id}, before Aggregation)")
                    justify_in_box(text=suggestion, title=f"Suggestions on Node {cur_node.id}'s solution:")
                    color_code_diff(cur_node.solution._get_codes(), response, cur_node.id, next_node.id)
                    log_info(f"Original Solution on Node {cur_node.id}:\n{cur_node.solution._get_codes()}", to_console=False)
                    log_info(f"Suggestions from Node {next_node.id} on Node {cur_node.id}:\n{suggestion}", to_console=False)
                    log_info(f"Optimized Solution on Node {next_node.id}:\n{response}", to_console=False)
                    with open(cur_layer_dir + f"/Node {cur_node.id}/suggestions.txt", "a", encoding="utf-8") as f:
                        f.write(f"\n\n{next_node.id}'s suggestion on {cur_node.id}'s solution:\n{suggestion}\n\n")
                    visited_edges.add((cur_node.id, next_node.id))
                    next_nodes.add(next_node.id)

            for node_id in next_nodes:
                node = self.nodes[node_id]
                node_directory = self.directory + f"/Layer {layer + 1}/Node {node.id}"
                os.makedirs(node_directory, exist_ok=True)
                os.makedirs(node_directory + "/pre_solutions", exist_ok=True)
                for prev_node in node.pre_solutions.keys():
                    with open(node_directory + f"/pre_solutions/solution_{prev_node}.txt", "w") as f:
                        for key in node.pre_solutions[prev_node].codebooks.keys():
                            f.write(f"{key}\n\n{node.pre_solutions[prev_node].codebooks[key]}\n\n")

                if len(os.listdir(node_directory + "/pre_solutions")) != len(node.pre_solutions):
                    print("Error: the number of solutions is not equal to the number of files!")
                    exit(1)

                if len(node.pre_solutions) == len(node.predecessors) and len(node.pre_solutions) >= self.aggregate_unit_num:
                    logging.info(f"Node {node.id} is aggregating")
                    agg_layer_dir = node_directory + "/pre_solutions"
                    error_flag = node.aggregate(prompt, self.aggregate_retry_limit, self.aggregate_unit_num,
                                                agg_layer_dir, self.depth, node_directory + "/solution.txt")
                    if error_flag:
                        node.solution = node.pre_solutions[list(node.pre_solutions.keys())[0]]
                        with open(node_directory + "/solution.txt", "w") as f:
                            for key in node.solution.codebooks.keys():
                                f.write(f"{key}\n\n{node.solution.codebooks[key]}\n\n")
                        logging.info(f"Node {node.id} failed aggregating pre_solutions.")
                else:
                    node.solution = node.pre_solutions[list(node.pre_solutions.keys())[0]]
                    with open(node_directory + "/solution.txt", "w") as f:
                        for key in node.solution.codebooks.keys():
                            f.write(f"{key}\n\n{node.solution.codebooks[key]}\n\n")
                    logging.info(f"Node {node.id} has insufficient predecessors, uses pre_solution.")

            for edge in visited_edges:
                self.delete_edge(edge[0], edge[1])
            for cur_node in input_nodes:
                self.delete_node(cur_node.id)

            layer += 1

        self.node_out.solution.write_codes_to_hardware(name)

    def agent_deployment(self, _type):
        """Deploy agents in the graph."""
        new_graph = copy.deepcopy(self)
        layer = -1
        layers = []
        while True:
            input_nodes = new_graph.get_input_layer()

            if len(input_nodes) == 0:
                self.depth = layer
                cur_depth = 0
                for Layer in layers:
                    for node in Layer:
                        self.nodes[node.id].depth = cur_depth
                        self.nodes[node.id].temperature = 1 - cur_depth / self.depth

                        if _type == "None":
                            self.nodes[node.id].system_message = "You are an experienced programmer."
                        else:
                            profile_num = random.randint(1, 99)
                            with open(f"./SRDD_Profile/{_type}/{profile_num}.txt", "r", encoding="utf-8") as f:
                                self.nodes[node.id].system_message = f.read()
                    cur_depth += 1
                break
            layers.append(input_nodes)

            visited_edges, next_nodes = set(), set()
            for cur_node in input_nodes:
                for next_node in cur_node.successors:
                    visited_edges.add((cur_node.id, next_node.id))
                    next_nodes.add(next_node.id)

            for edge in visited_edges:
                new_graph.delete_edge(edge[0], edge[1])
            for cur_node in input_nodes:
                new_graph.delete_node(cur_node.id)

            layer += 1

        return None

    def add_node(self, node: Node):
        """Add a node to the graph."""
        self.nodes[node.id] = node

    def delete_node(self, from_node_id):
        """Delete a node from the graph."""
        del self.nodes[from_node_id]

    def add_edge(self, from_node_id, to_node_id):
        """Add an edge between two nodes."""
        self.nodes[from_node_id].add_successor(self.nodes[to_node_id])
        self.nodes[to_node_id].add_predecessor(self.nodes[from_node_id])

    def delete_edge(self, from_node_id, to_node_id):
        """Delete an edge between two nodes."""
        self.nodes[from_node_id].successors.remove(self.nodes[to_node_id])
        self.nodes[to_node_id].predecessors.remove(self.nodes[from_node_id])

    def get_input_layer(self):
        """Get the input layer of the graph."""
        input_layer = []
        for node in self.nodes.values():
            if len(node.predecessors) == 0:
                input_layer.append(node)
        return input_layer

    def get_output_layer(self):
        """Get the output layer of the graph."""
        output_layer = []
        for node in self.nodes.values():
            if len(node.successors) == 0:
                output_layer.append(node)
        return output_layer

    def circular_check(self):
        """Check if the graph has a circular dependency."""
        visited = set()  # visited nodes
        path = set()  # nodes in the current path

        def dfs(_node):
            if _node in path:
                return True
            if _node in visited:
                return False
            visited.add(_node)
            path.add(_node)
            for successor in _node.successors:
                if dfs(successor):
                    return True
            path.remove(_node)
            return False

        for node in self.nodes.values():
            if node not in visited and dfs(node):
                return True
        return False




