import os
import subprocess
import hashlib
from queue import Queue
import re
from utils import cmd,log_and_print_online

class Node:
    def __init__(self):
        self.code = None
        self.version = None
        self.commitMessage = None
        self.mID = None
        self.role = None
        self.degree = 0
        self.value = 0.0
        self.embedding = None

    def create_from_warehouse(self, directory) -> None:
        def _format_code(code):
            code = "\n".join([line for line in code.split("\n") if len(line.strip()) > 0])
            return code

        # Read all .py files
        codebooks = {}
        assert len([filename for filename in os.listdir(directory) if filename.endswith(".py")]) > 0
        for root, directories, filenames in os.walk(directory):
            for filename in filenames:
                if filename.endswith(".py"):
                    codebooks[filename] = _format_code(open(os.path.join(directory, filename), "r", encoding="utf-8").read())

        # Format Codes
        code = ""
        for filename in codebooks.keys():
            filepath = os.path.join(directory, filename)
            code += "{}\n```Python\n{}\n```\n\n".format(filename, codebooks[filename])

        self.code = code
        self.mID = hashlib.md5(self.code.encode(encoding='UTF-8')).hexdigest()

        content = cmd("cd {} && git log --oneline".format(directory)).replace("(HEAD -> main)", "").replace("  ", " ")
        self.commitMessage = " ".join(content.split("\n")[0].split(" ")[1:])
        self.version = float(content.split("\n")[0].split(" ")[1].replace("v", ""))

class Edge:
    def __init__(self, sourceMID, targetMID, instruction, role):
        self.sourceMID = sourceMID
        self.targetMID = targetMID
        self.instruction = instruction
        self.role = role
        self.edgeId = None
        self.embedding = None

class Graph:
    def __init__(self):
        self.task = ""
        self.task_embedding = None
        self.nodes = {}
        self.edges = []
        self.directory:str = None

    def addNode(self, node: Node):
        if node.mID not in self.nodes.keys():
            self.nodes[node.mID] = node

    def addEdge(self, edge: Edge):
        num = "edge_{}".format(len(self.edges))
        edge.edgeId = hashlib.md5(num.encode(encoding='UTF-8')).hexdigest()
        self.edges.append(edge)

    def exists_edge(self, mid1: str, mid2: str):
        for edge in self.edges:
            if edge.sourceMID == mid1 and edge.targetMID == mid2:
                return True
        return False

    def create_from_warehouse(self, directory) -> None:
        self.directory = directory
        content = cmd("cd {} && git log --oneline".format(directory))
        #assert "log commit" in content
        cIDs = ["0" * 7] + [line.split(" ")[0] for line in content.split("\n") if len(line)>0][::-1] # Commit IDs
        log_cID = cIDs[-1]
        cIDs = cIDs[:-1]
        log_and_print_online("commit history:"+ str(cIDs)+ "\nlog commit:"+ str(log_cID))

        # Commit ID -> md5 ID
        # Constructing Nodes
        try:
            cID2mID = {}
            output = ""
            for cID in cIDs:
                if cID == "0" * 7:
                    node = Node()
                    node.code = ""
                    node.mID = hashlib.md5("".encode(encoding='UTF-8')).hexdigest()
                    node.commitMessage = ""
                    node.version = "v0.0"
                    cID2mID[cID] = node.mID
                    self.addNode(node)
                    output += ("Node: {} -> {}\n".format("0" * 7, node.mID))
                else:
                    content = cmd("cd {} && git reset --hard {}".format(directory, cID))
                    node = Node()
                    node.create_from_warehouse(directory)
                    cID2mID[cID] = node.mID
                    self.addNode(node)
                    output += ("Node: {} -> {}\n".format(cID, node.mID))
        finally:
            cmd("cd {} && git reset --hard {}".format(directory, log_cID))
        log_and_print_online(output)
        # Constructing Edges
        for i in range(1, len(cIDs), 1):
            sourceCID = cIDs[i-1]
            targetCID = cIDs[i]
            sourceMID = cID2mID[sourceCID]
            targetMID = cID2mID[targetCID]
            edge = Edge(sourceMID, targetMID, instruction="", role="")
            self.addEdge(edge)
            # print("{} -> {}, {} -> {}".format(sourcecID, targetcID, sourcemID, targetmID))
        self._create_instruction_and_roles_from_log(directory)

    def create_from_log(self, directory) -> None:

        def update_codebook(utterance, codebook):
            def extract_filename_from_line(lines):
                file_name = ""
                for candidate in re.finditer(r"(\w+\.\w+)", lines, re.DOTALL):
                    file_name = candidate.group()
                    file_name = file_name.lower()
                return file_name

            def extract_filename_from_code(code):
                file_name = ""
                regex_extract = r"class (\S+?):\n"
                matches_extract = re.finditer(regex_extract, code, re.DOTALL)
                for match_extract in matches_extract:
                    file_name = match_extract.group(1)
                file_name = file_name.lower().split("(")[0] + ".py"
                return file_name

            def _format_code(code):
                code = "\n".join([line for line in code.split("\n") if len(line.strip()) > 0])
                return code

            regex = r"(.+?)\n```.*?\n(.*?)```"
            matches = re.finditer(regex, utterance, re.DOTALL)
            for match in matches:
                code = match.group(2)
                if "CODE" in code:
                    continue
                group1 = match.group(1)
                filename = extract_filename_from_line(group1)
                if "__main__" in code:
                    filename = "main.py"
                if filename == "":
                    filename = extract_filename_from_code(code)
                assert filename != ""
                if filename is not None and code is not None and len(filename) > 0 and len(code) > 0:
                    codebook[filename] = _format_code(code)

        def get_codes(codebook):
            content = ""
            for filename in codebook.keys():
                content += "{}\n```{}\n{}\n```\n\n".format(filename, "python" if filename.endswith(".py") else
                filename.split(".")[-1], codebook[filename])
            return content

        self.directory = directory
        logdir = [filename for filename in os.listdir(directory) if filename.endswith(".log")]
        if len(logdir) > 0:
            log_filename = logdir[0]
            print("log_filename:", log_filename)
        else:
            return
        content = open(os.path.join(directory, log_filename), "r", encoding='UTF-8').read()

        utterances = []
        regex = r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \w+)\] ([.\s\S\n\r\d\D\t]*?)(?=\n\[\d|$)"
        matches = re.finditer(regex, content, re.DOTALL)
        for match in matches:
            group1 = match.group(1)
            group2 = match.group(2)
            utterances.append("[{}] {}".format(group1, group2))
        utterances = [utterance for utterance in utterances if
                      "flask app.py" not in utterance and "OpenAI_Usage_Info" not in utterance]
        index = [i for i, utterance in enumerate(utterances) if
                 "Programmer<->Chief Technology Officer on : EnvironmentDoc" in utterance]
        if len(index) > 0:
            utterances = utterances[:index[0] - 1]

        utterances_code= [utterance for utterance in utterances if
                           "Programmer<->" in utterance and "EnvironmentDoc" not in utterance and "TestErrorSummary" not in utterance]
        print("len(utterances_code):", len(utterances_code))

        codebook, fingerprints, pre_mid = {}, set(), ""
        for utterance in utterances_code:
            update_codebook(utterance, codebook)

            # construct node
            node = Node()
            node.mID = hashlib.md5(get_codes(codebook).encode(encoding='UTF-8')).hexdigest()
            node.commitMessage = ""
            node.code = get_codes(codebook)
            node.version = float(len(fingerprints))
            if node.mID not in fingerprints:
                fingerprints.add(node.mID)
                self.addNode(node)

            # construct edge
            if pre_mid != "":
                sourceMID = pre_mid
                targetMID = node.mID
                edge = Edge(sourceMID, targetMID, instruction="", role="")
                self.addEdge(edge)
            pre_mid = node.mID

        self._create_instruction_and_roles_from_log(directory)
        
    def _create_instruction_and_roles_from_log(self, directory) -> None:
        logdir = [filename for filename in os.listdir(directory) if filename.endswith(".log")]
        if len(logdir)>0:
            log_filename = logdir[0]
            log_and_print_online("log_filename:"+log_filename)
        else :
            return 
        content = open(os.path.join(directory, log_filename), "r", encoding='UTF-8').read()

        utterances = []
        regex = r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \w+)\] ([.\s\S\n\r\d\D\t]*?)(?=\n\[\d|$)"
        matches = re.finditer(regex, content, re.DOTALL)
        for match in matches:
            group1 = match.group(1)
            group2 = match.group(2)
            # print(group1)
            # print(group2)
            utterances.append(group2)
            # print()
        utterances = [utterance for utterance in utterances if "Chief Technology Officer: **[Start Chat]**" in utterance or "Code Reviewer: **[Start Chat]**" in utterance or "Software Test Engineer: **[Start Chat]**" in utterance]
        if "Test Pass!" in content:
            utterances.append("Software Test Engineer: **[Start Chat]**\n\nTest Pass!")

        instructions, roles = [], []
        for utterance in utterances:
            utterance = utterance.lower()
            instruction = ""
            if "Chief Technology Officer: **[Start Chat]**".lower() in utterance:
                instruction = "write one or multiple files and make sure that every detail of the architecture is implemented as code"
            elif "Code Reviewer: **[Start Chat]**".lower() in utterance:
                instruction = utterance.split("Comments on Codes:".lower())[-1].split("In the software,".lower())[0]
                instruction = instruction.replace("<comment>".lower(), "")
            elif "Software Test Engineer: **[Start Chat]**".lower() in utterance:
                if "Test Pass!".lower() in utterance:
                    instruction = "Test Pass!"
                else:
                    instruction = utterance.split("Error Summary of Test Reports:".lower())[-1].split("Note that each file must strictly follow a markdown code block format".lower())[0]
            else:
                assert False
            role = utterance.split(": **")[0]

            instruction = instruction.strip()
            if instruction.startswith("\""):
                instruction = instruction[1:]
            if instruction.endswith("\""):
                instruction = instruction[:-1]
            instruction = instruction.strip()
            instructions.append(instruction)

            role = role.strip()
            roles.append(role)

        for i in range(len(self.edges)):
            self.edges[i].instruction = instructions[i]
            self.edges[i].role = roles[i]

    def find_shortest_path(self, uMID=None, vMID=None):
        if uMID == None:
            uMID = self.edges[0].sourceMID
        if vMID == None:
            vMID = self.edges[-1].targetMID

        Q, visit, preMID, preEdge = Queue(), {}, {}, {}
        Q.put(uMID)
        visit[uMID] = True
        while not Q.empty():
            mID = Q.get()
            if mID == vMID:
                id, pathNodes, pathEdges = vMID, [], []
                while id != uMID:
                    pathNodes.append(id)
                    pathEdges.append(preEdge[id])
                    id = preMID[id]
                pathNodes.append(uMID)
                pathNodes = pathNodes[::-1]
                pathEdges = pathEdges[::-1]
                return pathNodes, pathEdges
            nextMIDs = [edge.targetMID for edge in self.edges if edge.sourceMID == mID]
            nextEdges = [edge for edge in self.edges if edge.sourceMID == mID]
            for i in range(len(nextMIDs)):
                nextMID = nextMIDs[i]
                nextEdge = nextEdges[i]
                if nextMID not in visit.keys():
                    Q.put(nextMID)
                    visit[nextMID] = True
                    preMID[nextMID] = mID
                    preEdge[nextMID] = nextEdge

    def print(self):
        output = "\n"+"*" * 50 + " Graph " + "*" * 50 + "\n"
        output += "{} Nodes:\n".format(len(self.nodes.keys()))
        for key in self.nodes.keys():
            node = self.nodes[key]
            output += "{}, {}, {}\n".format(node.mID, node.version, node.commitMessage)
        output += "{} Edges:\n".format(len(self.edges))
        for edge in self.edges:
            output += "{}: {} -> {} ({}: {})\n".format(edge.edgeId, edge.sourceMID, edge.targetMID, edge.role, edge.instruction[:60])
        output += "*" * 50 + " Graph " + "*" * 50
        log_and_print_online(output)


    def to_dict(self):
        merged_node_dict = []
        merged_edge_dict = []
        for k,v in self.nodes.items():
            merged_node_dict.append(v.__dict__)
        for index,e in enumerate(self.edges):
            merged_edge_dict.append(e.__dict__ )
        return merged_node_dict,merged_edge_dict
