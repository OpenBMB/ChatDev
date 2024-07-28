from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from abc import ABC, abstractmethod
import json
import time
import math
import os
import sys
import openai
import faiss
import numpy as np
from datetime import datetime
sys.path.append(os.path.join(os.getcwd(),"ecl"))
#from utils import get_code_embedding,get_text_embedding
from utils import get_easyDict_from_filepath,log_and_print_online
from embedding import OpenAIEmbedding

class MemoryBase(ABC):
    def __init__(self, directory: str) -> None:
        self.directory: str = directory

        cfg = get_easyDict_from_filepath("./ecl/config.yaml")
        self.top_k_code = cfg.retrieval.top_k_code
        self.top_k_text = cfg.retrieval.top_k_text
        self.code_thresh = cfg.retrieval.searchcode_thresh
        self.text_thresh = cfg.retrieval.searchtext_thresh
        self.embedding_method = None

        if cfg.embedding_method == "OpenAI":
            self.embedding_method = OpenAIEmbedding()

        self.content = None
        if os.path.exists(self.directory) and self.directory.endswith('.json'):
            with open(self.directory) as file:
                self.content = json.load(file)
        elif os.path.exists(self.directory) is False:
            with open(self.directory, 'w') as file:
                json.dump({}, file)  # Create an empty JSON file
            file.close()
            print(f"Now the memory file '{self.directory}' is created")
        if self.content is None:
            print("Empty Memory")

    @abstractmethod
    def memory_retrieval(self) -> str:
        pass


    def _get_memory_count(self) ->int:
        if isinstance(self.content,list):
            return self.content[-1].get("total")
        else:
            return 0


class AllMemory(MemoryBase):
    def __init__(self, directory: str):
        super().__init__(directory)

    # unused; init experience list
    def _init_explist(self):
        self.exp_list = None
        if self.content == None:
            self.exp_list = None
        else :
            for t in self.content:
                for experience in t.get("experineces"):
                    self.exp_list.append(experience)

    # clear all memory
    def _memory_clear(self) ->None:
        if os.path.exists(self.directory) and self.directory.endswith('.json'):
            with open(self.directory) as file:
                json.dump({},file)
                file.close()
        self.content = None
    # get code sample
    def get_codesample(self) ->str:
        if self._get_memory_count() >=1:
            return self.content[-1].get("nodes")[-1]["code"]
        else:
            return None
    # get text str sample
    def get_textsample(self) ->str:

        if self._get_memory_count() >=1:
            return self.content[-1].get("edges")[-1].get("instruction")
        else:
            return None
    # get code embedding from code mID
    def _get_codeembedding(self,mid) :
        for t in self.content:
            for node in t["nodes"]:
                if node["mID"] == mid:
                    return node.get("embedding")
    # get instructionstar from sourcecode mID
    def _get_instructionstar(self,mid):
        max_valueGain = -1
        for t in self.content:
            for experience in t["experiences"]:
                if experience == None :
                    pass
                elif experience["sourceMID"] == mid:
                    if experience.get("valueGain") >= max_valueGain:
                        instructionstar = experience.get("instructionStar")
        return instructionstar
    
    # get experience task and dir from sourcecode mID
    def _get_task_from_source(self,mid):
        task = None
        task_dir = None
        for t in self.content:
            for experience in t["experiences"]:
                if experience == None :
                    pass
                elif experience["sourceMID"] == mid:
                    task = t["task"]
                    task_dir = t["dir"]
        return task,task_dir
    
    # get experience task and dir from targetcode mID
    def _get_task_from_target(self,mid):
        task = None
        task_dir = None
        for t in self.content:
            for experience in t["experiences"]:
                if experience == None :
                    pass
                elif experience["targetMID"] == mid:
                    task = t["task"]
                    task_dir = t["dir"]
        return task,task_dir

    # retrieval from MemoryCards
    def memory_retrieval(self,input_message:str, type:str, k = None) :
        if k == None:
            if type == "code":
                return self.search_code(input_message,self.top_k_code)
            elif type == "text":
                return self.search_text(input_message,self.top_k_text)
            else:
                return None
        else:
            if type == "code":
                return self.search_code(input_message, k)
            elif type == "text":
                return self.search_text(input_message, k)
            else:
                return None

    def search_text(self, code_query, k:int):
        """
        search instructionStar from a code query
        
        Keyword arguments:
        code_query -- code input
        k -- the number of instructions to search 
        
        Return: 
        (best k instructionStar, k)
        """

        
        if self._get_memory_count() == 0 or code_query == None or k == 0:
            return None            

        else :
            code_query =  self.embedding_method.get_code_embedding(code_query)
            if isinstance(code_query,list):
                code_query=np.array(code_query,dtype=np.float32)
            code_query = code_query.reshape(1,-1)

            sourcecodemid_list = []# source code mid
            code_embeddings = []# code embedding

            for t in self.content :
                for experience in t["experiences"]:
                    sourcecodemid_list.append(experience.get("sourceMID"))
            sourcecodemid_list = list(set(sourcecodemid_list))# remove duplicates
            for mid in sourcecodemid_list:
                code_embeddings.append(self._get_codeembedding(mid))
            code_embedding_data = np.array(code_embeddings, dtype=np.float32)

            faiss.normalize_L2(code_embedding_data)
            faiss.normalize_L2(code_query)
            # use L2 distance(cosine distance)
            index = faiss.IndexFlatL2(code_embedding_data.shape[1])
            index.add(code_embedding_data)

            # In Faiss, the index.search function returns the square of L2 distance by default (Squared L2 Distance)
            distances, indices = index.search(code_query, k)
            similarities = 1-(1/2)*distances

            task_list = []
            task_dir_list = []

            instructionStar_list = []
            sourceMIDS = []
            for i in range(k):
                index = indices[0][i]
                similarity = similarities[0][i]
                if index != -1 and similarity >= self.text_thresh:
                        task, task_dir = self._get_task_from_source(sourcecodemid_list[index])
                        sourceMIDS.append(sourcecodemid_list[index])
                        task_list.append(task)
                        task_dir_list.append(task_dir)
                        instructionStar_list.append(self._get_instructionstar(sourcecodemid_list[index]))

            filtered_similarities = np.array2string(similarities[:,:k])
            return instructionStar_list, filtered_similarities, sourceMIDS, task_list, task_dir_list

    def search_code(self, text_query, k:int):
        """search best code from a text query
        
        Keyword arguments:
        text_query -- text input
        k -- the number of code to search 
        Return: (best k code, k)
        """

        if self._get_memory_count() == 0 or text_query == None or k == 0:
            return None            
          
        else :
            text_query = self.embedding_method.get_text_embedding(text_query)
            if isinstance(text_query,list):
                text_query=np.array(text_query,dtype=np.float32)
            text_query = text_query.reshape(1,-1)

            text_embeddings = [exp.get("embedding") for t in self.content for exp in t["experiences"]]
            text_embedding_data = np.array(text_embeddings, dtype=np.float32)

            faiss.normalize_L2(text_embedding_data)
            faiss.normalize_L2(text_query)
            # use L2 distance(cosine distance)
            total_instructionStar = text_embedding_data.shape[0]
            index = faiss.IndexFlatL2(text_embedding_data.shape[1])
            index.add(text_embedding_data)
            # In Faiss, the index.search function returns the square of L2 distance by default (Squared L2 Distance)
            distances, indices = index.search(text_query, total_instructionStar)


            similarities = 1-(1/2)*distances

            code_node_list = [node for t in self.content for node in t["nodes"]]
            targetMIDs = []
            target_code = []
            task_list = []
            task_dir_list = []
            filtered_similarities = []
            experience_list = [experience for t in self.content for experience in t["experiences"]]
            counter = 0

            added_set = set()
            for i in range(total_instructionStar):
                index =  indices[0][i]
                similarity = similarities[0][i]
                if index != -1 and counter < k:
                    if similarity <= self.code_thresh:
                        break
                    else:
                        mid = experience_list[index].get("targetMID")
                        if mid not in added_set:
                            targetMIDs.append(mid)
                            added_set.add(mid)
                            counter += 1
                            filtered_similarities.append(str(similarity))
                else:
                    break

            for targetMID in targetMIDs:
                for code_node in code_node_list:
                    if targetMID == code_node.get("mID"):
                        target_code.append(code_node.get("code"))
                        task, task_dir = self._get_task_from_target(targetMID)
                        task_list.append(task)
                        task_dir_list.append(task_dir)
            filtered_similarities = ",".join(filtered_similarities)
            return target_code, filtered_similarities, targetMIDs, task_list, task_dir_list




class Memory:
    def __init__(self):
        self.directory: str = None
        self.id_enabled : bool = False
        self.user_memory_filepath: str = None
        self.assistant_memory_filepath: str = None

        self.update_count = 0
        self.memory_keys: List[str] = ["All"]
        self.memory_data = {}


    def __str__(self) -> str:
        if self.memory_data.get("All") == None:
            return "No existed memory"
        else:
            return "Current memory length:{}".format(self.memory_data["All"]._get_memory_count())

    def _set_embedding(self,experience):
        graph = experience.graph
        edge_start_time = time.time()
        for edge in graph.edges:
            if edge.embedding is None:
                start_time =time.time()
                edge.embedding = self.memory_data["All"].embedding_method.get_text_embedding(edge.instruction)
                end_time = time.time()
                log_and_print_online("DONE: get edge embedding\ntime cost:{}\n".format(end_time-start_time))
        edge_duration =  time.time() - edge_start_time
        log_and_print_online("DONE: got all EDGE embeddings\nEDGE embedding time cost:{}\n".format(edge_duration))
        node_start_time =  time.time()
        for node_id in graph.nodes:
            node = graph.nodes[node_id]
            if node.embedding is None:
                start_time = time.time()
                node.embedding = self.memory_data["All"].embedding_method.get_code_embedding(node.code)
                end_time = time.time()
                log_and_print_online("DONE: get node embedding\ntime cost:{}\n".format(end_time-start_time))
        node_duration = ( time.time() - node_start_time)
        log_and_print_online("DONE: got all NODE embeddings\nNODE embedding time cost:{}\n".format(node_duration))
        exp_start_time = time.time()
        for exp in experience.experiences:
            if exp.embedding is None:
                start_time = time.time()
                exp.embedding = self.memory_data["All"].embedding_method.get_text_embedding(exp.instructionStar)
                end_time = time.time()
                log_and_print_online("DONE: get exprience embedding\ntime cost:{}\n".format(end_time-start_time))
        exp_duration = ( time.time() - exp_start_time)
        log_and_print_online("DONE: got all EXPERIENCE embeddings\nEXPERIENCE embedding time cost:{}\n".format(exp_duration))
        duration = edge_duration + node_duration + exp_duration
        log_and_print_online("All embedding DONE\ntime cost:{}\n".format(duration))

    # create memory path and upload memory from existed memory             
    def upload(self):
        self.directory = os.path.join(os.getcwd(),"ecl","memory")
        if os.path.exists(self.directory) is False:
            os.mkdir(self.directory)
        for key in self.memory_keys:
            if key =="All":
                path = os.path.join(self.directory,"MemoryCards.json")
                self.memory_data[key] = AllMemory(path)

    # upload experience into memory 
    def upload_from_experience(self, experience):
        self._set_embedding(experience)
        with open(self.memory_data["All"].directory, 'w') as file:
            node_data,edge_data = experience.graph.to_dict()
            experience_data = experience.to_dict()

            merged_dic = []
            index = 0
            previous_memory = []

            if self.memory_data["All"].content != None and  len(self.memory_data["All"].content) != 0 :
                previous_memory = self.memory_data["All"].content
            log_and_print_online("len(previous_memory)={}".format(len(previous_memory)))
            if len(previous_memory) != 0 and isinstance(previous_memory,list):
                for index,t in enumerate(previous_memory):
                    if isinstance(t,list):
                        for subindex,subt in enumerate(t):
                            if len(subt)!=0:
                                merged_dic.append(subt)
                    elif len(t)!=0 :
                        merged_dic.append(t)
                index = merged_dic[-1]["total"]
            elif len(previous_memory) != 0 :
                merged_dic.append(previous_memory)
                index = 1

            # remove duplication
            dirList = [t["dir"] for t in merged_dic]

            combined_json_str = {}
            combined_json_str["index"] = index
            combined_json_str["dir"] = experience.graph.directory
            combined_json_str["task"] = experience.graph.task
            combined_json_str["nodes"] = node_data
            combined_json_str["edges"] = edge_data
            combined_json_str["experiences"] = experience_data
            combined_json_str["total"] = combined_json_str["index"]+1

            if self.memory_data["All"].content != None and len(self.memory_data["All"].content)!=0:
                    merged_dic.append(combined_json_str)
            else :
                merged_dic.append(combined_json_str)

            json.dump(merged_dic, file)
            log_and_print_online("len(merged_dic)={}".format(len(merged_dic))+"\n merged_dic dumped to {}".format(self.memory_data["All"].directory))
            log_and_print_online("[Conclusion]:\ntext_prompt_tokens:{}, text_total_tokens:{}\ncode_prompt_tokens:{}, code_total_tokens:{}\nprompt_tokens:{}, total_tokens:{}".format(self.memory_data["All"].embedding_method.text_prompt_tokens,
                                                                                                                                                                                self.memory_data["All"].embedding_method.text_total_tokens,
                                                                                                                                                                                self.memory_data["All"].embedding_method.code_prompt_tokens,
                                                                                                                                                                                self.memory_data["All"].embedding_method.code_total_tokens,
                                                                                                                                                                                self.memory_data["All"].embedding_method.prompt_tokens,
                                                                                                                                                                                self.memory_data["All"].embedding_method.total_tokens))
            file.close()

    # delete memory from index 
    def delete_memroy(self,idx:int):
        with open(self.memory_data["All"].directory, 'w') as file:
            merged_dic = []
            index = 0
            previous_memory = []

            if self.memory_data["All"].content != None and  len(self.memory_data["All"].content) != 0 :
                previous_memory = self.memory_data["All"].content
            if len(previous_memory) != 0 and isinstance(previous_memory,list):
                for index,t in enumerate(previous_memory):
                    if isinstance(t,list):
                        for subindex,subt in enumerate(t):
                            if len(subt)!=0:
                                merged_dic.append(subt)
                    elif len(t)!=0 :
                        merged_dic.append(t)
                index = merged_dic[-1]["total"]
            elif len(previous_memory) != 0 :
                merged_dic.append(previous_memory)
                index = 1

            if idx >= len(merged_dic):
                json.dump(merged_dic,file)
            else :
                merged_dic.pop(idx)
                json.dump(merged_dic,file)
            file.close()




