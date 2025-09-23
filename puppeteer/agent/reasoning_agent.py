import json
import yaml
import os
from tenacity import retry, stop_after_attempt, wait_exponential
import re
from copy import deepcopy

from tools.base.register  import global_tool_registry
from tools.web_search import Web_Search
from tools.code_interpreter import CodeInterpreter
from tools.file_read import FileRead

from agent.agent import Agent
from agent.agent_info.global_info import GlobalInfo
from agent.agent_info.workflow import Action
from agent.agent_info.actions import REASONING_ACTION_LIST, TOOL_ACTION_LIST, TERMINATION_ACTION_LIST

from utils.file_utils import format_code_with_prints, extract_code_from_text, write_code, write_text, read_code

global_config = yaml.safe_load(open("./config/global.yaml", "r"))

class Reasoning_Agent(Agent):
    def __init__(self, role, role_prompt, index,  model="gpt", actions=[], policy=None, global_info=None,initial_dialog_history=None) -> None:
        super().__init__(role, role_prompt, index, model, actions, policy, global_info, initial_dialog_history)


    def activate(self, global_info:GlobalInfo, initial_dialog_history=None):
        if self._activated:
            return 
        self._activated = True
 
        system_step_data = global_info.workflow.valid_tool_results
        prompt_filepath = "prompts/general/system_prompt.json" 
        with open(prompt_filepath, "r") as f:
            system_prompt = json.load(f)
        system_step_data = [self._compress_data(d) for d in system_step_data]
        self.system_prompt  =  "\n".join(system_prompt['system_prompt']).format(self.role_prompt, 
                                                                                str(global_info.task.get("Question")), 
                                                                                str(system_step_data))
        
        self.workspace_path = global_info.workpath

        if initial_dialog_history is None or initial_dialog_history == []:
            self.dialog_history = [{"role": "system", "content": self.system_prompt}]
        else:
            self.dialog_history = deepcopy(initial_dialog_history)
            self.dialog_history[0] = {"role": "system", "content": self.system_prompt}

    def deactivate(self):
        self.initial_dialog_history = deepcopy(self.dialog_history)
        self._activated = False

    def _generate_action_prompt(self, global_info, previous_results, external_tools_enabled):
        prompt_filepath = "prompts/general/action_decide.json"
        with open(prompt_filepath, "r") as f:
            select_prompt = json.load(f)
        
        if external_tools_enabled:
            query_prompt = "\n".join(select_prompt['action_query']).format(
                global_info.workflow.valid_actions,
                global_info.url, 
                global_info.file_name,
                previous_results
            )
        else:
           query_prompt = "\n".join(select_prompt['action_query_without_tools']).format(global_info.workflow.valid_actions, previous_results)
        return query_prompt

    def query_action(self, action, external_tools_enabled):
        if external_tools_enabled:
            results = self.action_collection.query(
                query_texts=action,
                n_results=1
            )
        else:
            results = self.action_collection.query(
                query_texts=action,
                n_results=1,
                where={"category": "reasoning"}
            )
        
        return results
    
    def process_tool_parameters(self, results, global_info):
        parameter = ""
        parameter_type = results.get("metadatas")[0][0].get("input_type")
        
        if "query" in parameter_type:
            pass
        elif "file" in parameter_type and global_info.file_name is not None:
            parameter = global_info.file_name
        elif "url" in parameter_type and global_info.url is not None:
            parameter = global_info.url
        
        if parameter is None:
            parameter = ""
        
        return  parameter
    
    def _compress_data(self, data):
        if len(data) > 5000:
            data = data[:5000]
        return data
    
    def _execute_action(self, format_action, global_info):
        answer = ""
        total_tokens = 0
        print("\033[1;33mAgent {} Execute Action: {}\033[0m".format(self.role, format_action.get("action")))
        code_generated_type = True if global_info.task.get("req")=="code" else False
        text_generated_type = True if global_info.task.get("req")=="text" else False
        
        if format_action.get("action") not in REASONING_ACTION_LIST and format_action.get("action") is not None:
            flag, step_data = self._tool_operation(format_action, global_info)
            step_data = self._compress_data(step_data)
            print("\033[1;33m{} {}\033[0m".format(format_action.get("action"),"Success" if flag else "Failure"))
            
            # for code generation task, correct step data as the result
            if flag and code_generated_type:
                if len(step_data) > 10:
                    code_path = write_code(self.workspace_path, step_data, global_info.code_path)
                    global_info.add_answer({"code_path": code_path, "code": step_data})
                    global_info.code_path = code_path
            elif flag and text_generated_type:
                # for text generation task, store valid step data directly as the answer
                if len(step_data) > 10:
                    global_info.add_answer(step_data)
                    code_path = write_text(self.workspace_path, step_data, global_info.code_path)
                    global_info.add_answer({"code_path": code_path, "code": step_data})
                    global_info.code_path = code_path
            # for code generation task, error code should get corrected
            if flag or code_generated_type:
                tool_result = {"role": "user", "content": "You have get results from {}: {}".format(format_action.get("action"), step_data)}
                self.dialog_history.append(tool_result)
                answer, total_tokens = self._answer_operation(global_info)
                print("\033[1;33mAgent {} answered: {}\033[0m".format(self.role, answer))
    
        if format_action.get("action") in REASONING_ACTION_LIST:
            step_data, total_tokens = self._reasoning_operation(format_action, global_info)
            flag = True
            print("\033[1;33m{} {}\033[0m".format(format_action.get("action"),"Success" if flag else "Failure"))

        if len(global_info.answers) > 0:
            answer = global_info.answers[-1]
        return  step_data, answer, flag, total_tokens

    def _build_current_action(self, format_action, flag=True, answer=None, step_data=None, tokens=0):
        result = {
            "step_data": step_data,
            "answer": answer    
        }
        current_action = Action(action=format_action, result=result, 
                                success="Success" if flag else "Failure", 
                                agent_role=self.role, agent_model=self.model)
        if answer is None and step_data is None:
            current_action.set_cost(tokens=0)
        else:
            current_action.set_cost(tokens=tokens)
        return current_action
    
    def take_action(self, global_info, external_tools_enabled=True, env=None, env_name=None):
        logger = global_info.logger
        total_tokens = 0
        code_generated_type = True if global_info.task.get("req")=="code" else False
        text_generated_type = True if global_info.task.get("req")=="text" else False

        if self.actions[0] in TERMINATION_ACTION_LIST:
            action_json = {"action": self.actions[0], "parameter": ""}
            current_action = self._build_current_action(action_json, flag=True, answer=None, step_data=None)
            terminated = True
            return current_action, terminated
        
        if self.actions[0] in TOOL_ACTION_LIST:
            # only format the action json, without executing it
            prompt_filepath = "prompts/general/actions_external_tools.jsonl"
            prompt = ""
            with open(prompt_filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    json_obj = json.loads(line)
                    if json_obj.get("action") == self.actions[0]:
                        prompt = json_obj.get("prompt")
                        break
            
            if global_info.file_name is not None:
                prompt = "You can access to file named {}.".format(global_info.file_name) + prompt
            elif global_info.url is not None:
                prompt = "You can access to the url {}.".format(global_info.url) + prompt
            elif code_generated_type:
                prompt = "Your previous code {}".format(read_code(global_info.code_path)) + prompt
            elif text_generated_type:
                prompt = "Your previous text {}".format(read_code(global_info.code_path)) + prompt

            response, tokens = self._query(prompt)
            total_tokens += tokens
            action_json = self.json_format.json_reformat(response, global_config.get("max_json_reformat_turns"))

            if not isinstance(action_json, dict):
                action_json = {"action": self.actions[0], "parameter": ""}
            else:
                action_json["action"] = self.actions[0]
                
            message = {"role": "assistant", "content": str(action_json)}
            self.dialog_history[-1] = message
            logger.info("[Action] {}\n".format(action_json))
        
        elif self.actions[0] in REASONING_ACTION_LIST:
            action_json = {"action": self.actions[0], "parameter": ""}
            logger.info("[Action] {}\n".format(action_json))
        
        step_data, answer, flag, tokens = self._execute_action(action_json, global_info)
        total_tokens += tokens
        current_action = self._build_current_action(action_json, flag, answer, step_data, total_tokens)
        logger.info("-"*40)
        terminated = False
        self.deactivate()
        return current_action, terminated

    def _reasoning_operation(self, action, global_info) -> str:
        logger = global_info.logger
        prompt_filepath = "prompts/general/actions_reasoning.jsonl" 
        code_generated_type = True if global_info.task.get("req")=="code" else False
        text_generated_type = True if global_info.task.get("req")=="text" else False
        prompt = ""
        with open(prompt_filepath, "r") as f:
            for line in f:
                json_obj = json.loads(line)
                if json_obj.get("action") == action.get("action"):
                    prompt = json_obj.get("prompt")
                    break
        if code_generated_type or text_generated_type:
            query_prompt =  prompt.format(read_code(global_info.code_path))
        else:
            query_prompt =  prompt.format(global_info.workflow.valid_reasoning_results)
        logger.info("[System Prompt] {}\n[Query] {}\n".format(self.system_prompt, query_prompt))

        raw_response, total_tokens = self._query(query_prompt)
        logger.info("[Reasoning]: "+ raw_response)

        if code_generated_type:
            answer = extract_code_from_text(raw_response)
            logger.info("[Final Answer]: " + answer)
            if len(answer) > 10:
                code_path = write_code(self.workspace_path, answer, global_info.code_path)
                global_info.add_answer(json.dumps({"code_path": code_path, "code": answer}, ensure_ascii=False))
                global_info.code_path = code_path
            reasoning_result = action.get("parameter") + raw_response
            logger.info("[Reasoning Path]: " + reasoning_result)
            return reasoning_result, total_tokens
        elif text_generated_type:
            regex_answer = r"FINAL ANSWER:([\s\S]*)"
            matches = re.findall(regex_answer, raw_response)
            if len(matches) > 0:
                logger.info("[Final Answer]: "+matches[0])
                code_path = write_text(self.workspace_path, matches[0], global_info.code_path)
                global_info.add_answer(json.dumps({"code_path": code_path, "code": matches[0]}, ensure_ascii=False))
                global_info.code_path = code_path
                print("\033[1;33mAgent {} answered: {}\033[0m".format(self.role, matches[0]))
            
            reasoning_result = action.get("parameter") + raw_response
            logger.info("[Reasoning Path]: " + reasoning_result)
            return reasoning_result, total_tokens
        else:
            regex_answer = r"FINAL ANSWER:([\s\S]*)"
            matches = re.findall(regex_answer, raw_response)
            if len(matches) > 0:
                logger.info("[Final Answer]: "+matches[0])
                global_info.add_answer(matches[0])
                print("\033[1;33mAgent {} answered: {}\033[0m".format(self.role, matches[0]))
            
            reasoning_result = action.get("parameter") + raw_response
            logger.info("[Reasoning Path]: " + reasoning_result)
            return reasoning_result, total_tokens
    
    @retry(wait=wait_exponential(min=1, max=3), stop=stop_after_attempt(3))
    def _answer_operation(self, global_info) -> str:
        logger = global_info.logger
        prompt_filepath = "prompts/general/answer_prompt.json" 
        code_generated_type = True if global_info.task.get("req")=="code" else False
        text_generated_type = True if global_info.task.get("req")=="text" else False
        with open(prompt_filepath, "r") as f:
            select_prompt = json.load(f)
        if global_info.task.get("type") == "MMLU" or global_info.task.get("type") == "MMLU-Pro":
            query_prompt =  "\n".join(select_prompt['MMLU_answer'])
        elif global_info.task.get("type") == "GAIA":
            query_prompt =  "\n".join(select_prompt['GAIA_answer'])
        elif global_info.task.get("type") == "GSM-Hard"  or global_info.task.get("type") == "gsm-hard" or global_info.task.get("type") == "GSM8K":
            query_prompt =  "\n".join(select_prompt['gsm_answer'])
        elif code_generated_type:
            query_prompt =  "\n".join(select_prompt['code_answer'])
        elif text_generated_type:
            query_prompt =  "\n".join(select_prompt['text_answer'])
        else: 
            query_prompt =  "\n".join(select_prompt['answer'])
        logger.info("[System Prompt] {}\n[Query] {}\n".format(self.system_prompt, query_prompt))
        
        raw_response, total_tokens = self._query(query_prompt)
        logger.info("[Format to Final Answer]: "+ raw_response)
        
        if code_generated_type:
            answer = extract_code_from_text(raw_response)
            logger.info("[Final Answer]: " + answer)
            if len(answer) > 10:
                code_path = write_code(self.workspace_path, answer, global_info.code_path)
                global_info.add_answer(json.dumps({"code_path": code_path, "code": answer}, ensure_ascii=False))
                global_info.code_path = code_path
            return answer, total_tokens
        elif text_generated_type:
            regex_answer = r"FINAL ANSWER: ([\s\S]*)"
            matches = re.findall(regex_answer, raw_response)
            if len(matches) > 0:
                logger.info("[Final Answer]: "+matches[0])
                code_path = write_text(self.workspace_path, matches[0], global_info.code_path)
                global_info.add_answer(json.dumps({"code_path": code_path, "code": matches[0]}, ensure_ascii=False))
                global_info.code_path = code_path
                return matches[0], total_tokens
            else:
                return "", total_tokens
        else:
            regex_answer = r"FINAL ANSWER: ([\s\S]*)"
            matches = re.findall(regex_answer, raw_response)
            if len(matches) > 0:
                logger.info("[Final Answer]: "+matches[0])
                global_info.add_answer(matches[0])
                return matches[0], total_tokens
            else:
                logger.info("[Error] No final answer found in the response: {}\n".format(raw_response))
                return "", total_tokens

    @retry(wait=wait_exponential(min=3, max=5), stop=stop_after_attempt(2))
    def _query(self, query) -> str:
        prompt = {"role": "user", "content": str(query)}
        if self.dialog_history[-1] != prompt and self.dialog_history[-1]['role'] != 'user':
            self.dialog_history.append(prompt)
        elif self.dialog_history[-1] != prompt and self.dialog_history[-1]['role'] == 'user':
            self.dialog_history[-1]['content'] += str(query)
        self.last_prompt = prompt['content']
        messages = list(self.dialog_history)
        response = self.query_func(messages)
        message = {"role": "assistant", "content": str(response)}
        self.dialog_history.append(dict(message))
        return response

    def _tool_operation(self, action:json, global_info) ->str:
        logger = global_info.logger 
        name = action.get("action")
        parameter = action.get("parameter")
        logger.info("[Action Execution] {}({})\n".format(name, parameter))
        if 1:
            if name == "read_file":
                file_path = os.path.join(self.root_file_path, str(parameter))
                flag, step_data = global_tool_registry.execute_tool(name, file_path=file_path, file_extension=global_info.file_extension)
                logger.info("[Read File] {}: {}".format(("Success"if flag else "Failure"), step_data))
            elif name == "run_python":
                if global_info.task.get("type") != "SRDD" or global_info.task.get("type") != "human-eval":
                    parameter = format_code_with_prints(parameter)
                    timeout_detected = True
                else:
                    timeout_detected = False
                
                if global_info.file_name is not None:
                    file_path = os.path.join(self.root_file_path, global_info.file_name )
                else: 
                    file_path = ""
                flag, step_data = global_tool_registry.execute_tool(name, work_path=self.workspace_path, code=parameter, file_path=file_path, timeout_detected=timeout_detected)
                logger.info("[Run Python] {}: {}".format(("Success"if flag else "Failure"), step_data))
            else:
                flag, step_data = global_tool_registry.execute_tool(name, query=parameter, work_path=self.workspace_path)
                logger.info("[Web Broswing] {}: {}".format(("Success"if flag else "Failure"), step_data))
            return flag, step_data
        else:
            logger.info("Tool {} not registered for agent {}".format(name, self.role))
            print("Tool {} not registered for agent {}".format(name, self.role))
            return None, None   

    def _interaction_operation(self, code, env, global_info) -> str:
        pass 