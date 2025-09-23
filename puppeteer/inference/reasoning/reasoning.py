from typing import List
import json
import yaml
import os
import copy
import logging

from inference.reasoning.path import ReasoningState, GraphReasoningPath
from inference.graph.agent_graph import AgentGraph
from inference.graph.action_graph import ActionGraph
from inference.policy.REINFORCE_continuous import ContinuousREINFORCE

from utils.logging import LogManager

from agent.register.register import agent_global_registry
from agent.agent_info.global_info import GlobalInfo

from tasks.evaluator import BenchmarkEvaluator

global_config = yaml.safe_load(open("./config/global.yaml", "r"))
main_logger = logging.getLogger('global') 

class GraphReasoning:
    def __init__(self, task:json, graph: AgentGraph, env=None, env_name=None):
        self.task = task
        self.agent_graph = graph
        self.action_graph = ActionGraph()
        self.reasoning_paths: List[GraphReasoningPath] = []
        
        self.max_parallel_paths = global_config.get("graph").get("max_parallel_paths")
        
        self.final_answer = ""
        self.answers = []

        self.global_logger = LogManager("./config/global.yaml", self.task.get("type"))

        self.workspace_path = self.global_logger.folder_path
        self.policy = ContinuousREINFORCE(agent_graph=self.agent_graph, action_graph=self.action_graph)

        self.env = env
        self.env_name = env_name
        main_logger.info("{}[Graph Reasoning Initialized]{}".format("-"*30, "-"*30))
        main_logger.info(global_config)
        main_logger.info(self.agent_graph.role_nodes)
    
    def save_checkpoint(self, save_data):
        main_logger.info("{}[Save Checkpoint]{}".format("-"*30, "-"*30))
        cur_acc = save_data["best_acc"]
        cur_data_len =  save_data["best_data_len"]
        main_logger.info("best acc: {}, data len: {}".format(cur_acc, cur_data_len))
        tag = "acc_{}-data_{}".format(cur_acc, cur_data_len)
        self.policy.save_model(path=None, tag=tag)

    def start(self, save_data):
        if save_data != None:
            self.save_checkpoint(save_data)
        print("-"*10+"\033[1;31mGraph Reasoning Start\033[0m"+"-"*10)
        main_logger.info("{}[Graph Reasoning Start]{}".format("-"*30, "-"*30))
        main_logger.info("Task:\n{}".format(self.task.get("Question")))
        
        # -1 is the default path id for intialization
        global_info = GlobalInfo(path_id=-1, 
                                    workpath=self.workspace_path, 
                                    task=self.task, 
                                    env=self.env, 
                                    env_name=self.env_name)
        matches = self.policy.forward(global_info)
        
        for index, match in enumerate(matches):
            global_info = GlobalInfo(path_id=index, 
                                    workpath=self.workspace_path, 
                                    task=self.task, 
                                    env=self.env, 
                                    env_name=self.env_name)
            agent = agent_global_registry.get_agent_from_idx(match)
            agent.activate(global_info)
            main_logger.info("[Path {} Initialized".format(index))
            print("\033[1;36mPath {} Initialized\033[0m".format(index))
  
            reasoning_path = GraphReasoningPath(start_agent=agent, 
                                                max_parallel_paths=self.max_parallel_paths, 
                                                action_graph=self.action_graph,
                                                agent_sequence=[],
                                                index=index,
                                                global_info = copy.deepcopy(global_info),
                                                global_logger = self.global_logger,
                                                workspace_path=self.workspace_path,
                                                state=copy.deepcopy(ReasoningState.INITIALIZED),
                                                env=self.env,
                                                env_name=self.env_name,
                                                policy=self.policy
                                                )
            self.reasoning_paths.append(reasoning_path)
            main_logger.info("Reasoning Path: {}\nAgent Sequence: {}\n".format(index, reasoning_path.print_agent_sequence()))
    
    def n_step(self, n:int):
        for i in range(n):
            self.step()
            if self.check_finalize():
                break
        return self.finalize()
    
    def step(self):
        main_logger.info("{}[STEP]{}".format("-"*30, "-"*30))

        for reasoning_path in self.reasoning_paths[:self.max_parallel_paths]:
            # Deal with the case where the reasoning path is not finalizing and not spliting
            if reasoning_path.state != ReasoningState.FINALIZING and reasoning_path.state != ReasoningState.SPLITING:
                main_logger.info("{}[Reasoning Path{} STEP]{}".format("-"*30, reasoning_path.index, "-"*30))
                print("\033[1;36mPath {} Step\033[0m".format(reasoning_path.index))
                reasoning_path.step()
                main_logger.info("{}[DONE]: Reasoning Path{} STEP{}".format("-"*30, reasoning_path.index, "-"*30))
        
        buffer_reasoning_paths = []
        for reasoning_path in self.reasoning_paths[:self.max_parallel_paths]: 
            # Deal with the case where the reasoning path is spliting
            if reasoning_path.state == ReasoningState.SPLITING :
                current_path_count = len(self.reasoning_paths) + len(buffer_reasoning_paths)
                print("\033[1;36mPath {} Split\033[0m".format(reasoning_path.index))
                split_reasoning_paths = reasoning_path.split(current_path_count)
                if len(split_reasoning_paths) > 0:
                    main_logger.info("Split Reasoning Paths: {} From Path {}".format([path.index for path in split_reasoning_paths], reasoning_path.index))
                buffer_reasoning_paths.extend(split_reasoning_paths)
            # Deal with the case where the reasoning path is finalizing
            elif reasoning_path.state == ReasoningState.FINALIZING:
                print("\033[1;36mPath {} Finalize\033[0m".format(reasoning_path.index))
                main_logger.info("{}[Reasoning Path{} FINALIZING]{}".format("-"*30, reasoning_path.index, "-"*30))
        print(p for p in self.reasoning_paths)
        self.reasoning_paths.extend(buffer_reasoning_paths)
        self.format_index()
        self.print_paths()
        self.update_graph()
        
        return self.answers

    def aggregate_answers(self, global_info, answers:list, query_func=None) -> str:
        # only choose the last result without any format or extract
        if query_func is None:
            if len(answers) == 0:
                return None
            else:
                main_logger.info("[Aggregation] {}".format(answers[-1]))
                return answers[-1] 
        
        # only choose the last result without any format or extract
        if self.task.get("type") == "SRDD" or self.task.get("type") == "CW":
            main_logger.info("[Aggregation] {}".format(global_info.code_path))
            return global_info.code_path
        
        prompt_filepath = "prompts/general/answer_prompt.json" 
        with open(prompt_filepath, "r") as f:
            prompt = json.load(f)
        
        if self.task.get("type") == "MMLU" or self.task.get("type") == "MMLU-Pro":
            answer_prompt =  "\n".join(prompt["MMLU_aggregation"]).format(str(["{}\n".format(answer) for answer in answers]))
        elif self.task.get("type") == "GAIA":
            answer_prompt =  "\n".join(prompt["GAIA_aggregation"]).format(str(["{}\n".format(answer) for answer in answers]))
        elif self.task.get("type") == "GSM-Hard"  or self.task.get("type") == "gsm-hard" or self.task.get("type") == "GSM8K":
            answer_prompt = "\n".join(prompt["gsm_aggregation"]).format(str(["{}\n".format(answer) for answer in answers]))
        else: 
            answer_prompt = "\n".join(prompt["answer_aggregation"]).format(str(["{}\n".format(answer) for answer in answers]))
        
        main_logger.info("[Aggregating] {}".format(answer_prompt))
        
        raw_response, _ = query_func(messages=answer_prompt)
        main_logger.info("[Aggregation Answer] {}".format(raw_response))
        
        return raw_response if len(raw_response)!=0 else answers[-1]

    def majority_vote(self, answers: List) -> str:
        if self.task.get("type") == "MMLU" or self.task.get("type") == "MMLU-Pro":
            answers = [BenchmarkEvaluator.extract_choice_answer(answer) for answer in answers]
            main_logger.info("[Majority Vote] Answers: {}".format(answers))
        elif self.task.get("type") == "gsm-hard" or self.task.get("type") == "GSM8K":
            answers = [BenchmarkEvaluator.extract_math_answer(answer) for answer in answers]
            main_logger.info("[Majority Vote] Answers: {}".format(answers))
        else:
            main_logger.info("[Majority Vote] Answers: {}".format(answers))

        answer_counts = {}
        for answer in answers:
            answer = str(answer).strip()  # Convert to string and remove whitespace
            answer_counts[answer] = answer_counts.get(answer, 0) + 1
        
        if not answer_counts:
            return ""  # Return empty string if no answers
        
        max_count = max(answer_counts.values())
        most_common = [ans for ans, count in answer_counts.items() if count == max_count]
        main_logger.info("[Majority Vote] Most Common: {}".format(most_common))
        return most_common[-1]

    def finalize(self):
        print("-"*10+"\033[1;31mGraph Reasoning Finalize\033[0m"+"-"*10)
        print(p for p in self.reasoning_paths)
        for idx, reasoning_path in enumerate(self.reasoning_paths):
            if hasattr(reasoning_path, "last_query_func"):
                aggregated_answer = self.aggregate_answers(reasoning_path.global_info, reasoning_path.global_info.state_answers, reasoning_path.last_query_func)
            else:
                aggregated_answer = self.aggregate_answers(reasoning_path.global_info, reasoning_path.global_info.state_answers)
            if self.task.get("type") == "MMLU-Pro":
                transition = {
                'state': reasoning_path.global_info.workflow.state,
                'reward': 1 if BenchmarkEvaluator.check_mmlu(aggregated_answer, self.task.get("Answer")) else -1,
                'action': None,  
                'next_state': None,
                'done': True,
                'path_id': idx 
                }
                print(transition)
                self.policy.finalize_task(transition, reasoning_path.global_info)
            elif self.task.get("type") == "GSM-Hard": 
                transition = {
                'state': reasoning_path.global_info.workflow.state,
                'reward': 1 if BenchmarkEvaluator.check_gsm8k(aggregated_answer, self.task.get("Answer")) else -1,
                'action': None,  
                'next_state': None,
                'done': True,
                'path_id': idx 
                }
                print(transition)
                self.policy.finalize_task(transition, reasoning_path.global_info)

            elif self.task.get("type") == "SRDD":
                reward, metrics = BenchmarkEvaluator.check_srdd(aggregated_answer, reasoning_path.global_info.task.get("Question"))
                transition = {
                'state': reasoning_path.global_info.workflow.state,
                'reward':  reward,
                'action': None,  
                'next_state': None,
                'done': True,
                'path_id': idx ,
                "metrics":metrics
                }
                main_logger.info(metrics)
                self.policy.finalize_task(transition, reasoning_path.global_info)
            elif self.task.get("type") == "CW":
                reward, metrics = BenchmarkEvaluator.check_commongen(concepts=reasoning_path.global_info.task.get("concepts"), text_path=aggregated_answer)
                transition = {
                'state': reasoning_path.global_info.workflow.state,
                'reward': reward,
                'action': None,  
                'next_state': None,
                'done': True,
                'path_id': idx ,
                "metrics":metrics
                }
                main_logger.info(metrics)
                self.policy.finalize_task(transition, reasoning_path.global_info)
            if aggregated_answer is not None:
                self.answers.append(aggregated_answer)
                main_logger.info("[Aggregated Answer From Path {}]: {}".format(idx, aggregated_answer))   
        self.policy.update()
        
        for agent in agent_global_registry.agents.values():
            agent.reset()
        
        if len(self.answers) == 1 or self.task.get("type") == "SRDD" or self.task.get("type") == "CW":
            if len(self.answers) == 0:
                self.final_answer = ""
            else:
                self.final_answer = self.answers[-1]
        else:
            self.final_answer = self.majority_vote(self.answers)
        
        main_logger.info("[Final Answer]: {}".format(self.final_answer))   
        print("-"*10+"\033[1;31mGraph Reasoning Finalized\033[0m"+"-"*10)
        
        return self.final_answer, self.task.get("Answer")
    
    def visualize_path(self):
        for reasoning_path in self.reasoning_paths:
            reasoning_path.global_info.workflow.visualize()
    
    def visualize_graph(self):
        self.agent_graph.visualize(os.path.join(self.workspace_path, "agent_graph.html"))
        self.action_graph.visualize(os.path.join(self.workspace_path, "action_graph.html"))

    def print_paths(self):
        for reasoning_path in self.reasoning_paths:
            main_logger.info("Reasoning Path: {}\nAgent Sequence: {}\n".format(reasoning_path.index, reasoning_path.print_agent_sequence()))
    
    def format_index(self):
        for index, reasoning_path in enumerate(self.reasoning_paths):
            reasoning_path.index = index
    
    def update_graph(self):
        for index, reasoning_path in enumerate(self.reasoning_paths):
            for successor, predecessor in zip(reasoning_path.agent_sequence[:-1], reasoning_path.agent_sequence[1:]):
                successor = agent_global_registry.get_agent_from_idx(successor.get("hash"))
                predecessor = agent_global_registry.get_agent_from_idx(predecessor.get("hash"))
                res = self.agent_graph._get_edge(predecessor, successor)
                if res is None or index not in res:
                    self.agent_graph._add_edge(predecessor, successor, index)
    
    def check_finalize(self):
        for reasoning_path in self.reasoning_paths[:self.max_parallel_paths]:
            if reasoning_path.state != ReasoningState.FINALIZING and reasoning_path.state != ReasoningState.DISCARDING:
                return False
        return True