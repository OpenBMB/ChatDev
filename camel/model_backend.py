# =========== Copyright 2023 @ CAMEL-AI.org. All Rights Reserved. ===========
# Licensed under the Apache License, Version 2.0 (the “License”);
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an “AS IS” BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# =========== Copyright 2023 @ CAMEL-AI.org. All Rights Reserved. ===========
from abc import ABC, abstractmethod
from typing import Any, Dict

import openai
import tiktoken
import json
import boto3
from camel.typing import ModelType
from chatdev.statistics import prompt_cost
from chatdev.utils import log_visualize
from anthropic_bedrock import AnthropicBedrock
from typing import List,Union
from pydantic import BaseModel
import time

try:
    from openai.types.chat import ChatCompletion

    openai_new_api = True  # new openai api version
except ImportError:
    openai_new_api = False  # old openai api version

import os

OPENAI_API_KEY = os.environ['OPENAI_API_KEY']
if 'BASE_URL' in os.environ:
    BASE_URL = os.environ['BASE_URL']
else:
    BASE_URL = None

BEDROCK_LLM_MODELID_LIST = {'claude-3-sonnet': 'anthropic.claude-3-sonnet-20240229-v1:0',
                            'claude-3-haiku' : 'anthropic.claude-3-haiku-20240307-v1:0'}
BEDROCK_MODEL_NAME = 'claude-3-haiku'
# BEDROCK_MODEL_NAME = 'gpt'
REGION = 'us-west-2'
boto3_bedrock = boto3.client(
    service_name="bedrock-runtime",
    region_name=REGION
)
 
anthropic_bedrock = AnthropicBedrock(
    aws_region=REGION,
)

class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

class Message(BaseModel):
    role: str
    content: str

class Choice(BaseModel):
    index: int
    message: Message
    logprobs: Union[Any, None]  = None # logprobs 可能是 null 或字典
    finish_reason: str

class GPTResponse(BaseModel):
    id: str
    object: str
    created: Union[int] # created 可能是 null
    model: str
    system_fingerprint: str # system_fingerprint 可能是 null
    choices: List[Choice]
    usage: Usage
    
    
def num_tokens_from_string(text, model_name):
    if model_name.startswith("gpt"):
        encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
        num_tokens = len(encoding.encode(text))
    elif model_name.startswith("claude"):
        num_tokens = anthropic_bedrock.count_tokens(text)  # 
    return num_tokens

def reconstruct_to_claude_messages(messages):
    rec_messages = []
    system = None
    for message in messages:
        if message['role'] =='system' and not system:
            system = message["content"] 
            continue
        if rec_messages:
            ##如果第一个消息是assitant,则需要更换成user
            if rec_messages[0]['role'] == 'assistant':
                rec_messages[0] = {"role":'user',"content":rec_messages[0]['content']}
            last_msg = rec_messages[-1]
            last_role = last_msg['role']
            current_role = message['role']
            if last_role == current_role:
                new_content = last_msg['content'] +"\n\n" + message['content']
                rec_messages[-1] = {"role":last_role,"content":new_content}
            else:
                rec_messages.append(message)
        else:
            rec_messages.append(message)
    return system,rec_messages

def convert_bedrock_to_gpt(bedrock_response):
    # 解析Bedrock API响应
    bedrock_data = json.loads(bedrock_response)

    # 创建GPT API响应格式
    gpt_response = {
        "id": bedrock_data["id"],
        "object": "chat.completion",
        "created": int(time.time()), 
        "model": bedrock_data["model"],
        "system_fingerprint": "none",  # 由于Bedrock API响应中没有系统指纹,因此将其设置为None
        "choices": [{
            "index": 0,
            "message": {
                "role": bedrock_data["role"],
                "content": bedrock_data["content"][0]["text"]
            },
            "logprobs": None,  # 由于Bedrock API响应中没有logprobs,因此将其设置为None
            "finish_reason": "stop"
        }],
        "usage": {
            "prompt_tokens": bedrock_data["usage"]["input_tokens"],
            "completion_tokens": bedrock_data["usage"]["output_tokens"],
            "total_tokens": bedrock_data["usage"]["input_tokens"] + bedrock_data["usage"]["output_tokens"]
        }
    }

    # 将GPT API响应格式转换为JSON字符串
    # gpt_response_json = json.dumps(gpt_response)
    gpt_response_object = GPTResponse.parse_obj(gpt_response)
    return gpt_response_object

class ModelBackend(ABC):
    r"""Base class for different model backends.
    May be OpenAI API, a local LLM, a stub for unit tests, etc."""

    @abstractmethod
    def run(self, *args, **kwargs):
        r"""Runs the query to the backend model.

        Raises:
            RuntimeError: if the return value from OpenAI API
            is not a dict that is expected.

        Returns:
            Dict[str, Any]: All backends must return a dict in OpenAI format.
        """
        pass

    
class OpenAIModel(ModelBackend):
    r"""OpenAI API in a unified ModelBackend interface."""

    def __init__(self, model_type: ModelType, model_config_dict: Dict) -> None:
        super().__init__()
        self.model_type = model_type
        self.model_config_dict = model_config_dict

    def run(self, *args, **kwargs):
        string = "\n".join([message["content"] for message in kwargs["messages"]])
        # encoding = tiktoken.encoding_for_model(self.model_type.value)
        # num_prompt_tokens = len(encoding.encode(string))
        
        num_prompt_tokens = num_tokens_from_string(string,self.model_type.value)
        gap_between_send_receive = 15 * len(kwargs["messages"])
        num_prompt_tokens += gap_between_send_receive
        num_max_token_map = {
                "claude-3-sonnet":4096,
                "claude-3-haiku":4096,
                "claude-3-opus":4096,
            }
        use_bedrock = True if BEDROCK_MODEL_NAME.startswith('claude') else False
        # print('self.model_type.value:',self.model_type.value)
        # assert self.model_type.value in num_max_token_map
        if use_bedrock:
            num_max_token = num_max_token_map[BEDROCK_MODEL_NAME]
            num_max_completion_tokens = num_max_token - num_prompt_tokens
            print('kwargs["messages"]:',len(kwargs["messages"]),[item['role'] for item in kwargs["messages"]])
            system,new_messages = reconstruct_to_claude_messages(messages=kwargs["messages"])
            # print('system:',system)
            print('new_messages:',len(new_messages),[item['role'] for item in new_messages])
            input_body = {}
            input_body["anthropic_version"] = "bedrock-2023-05-31"
            input_body["messages"] = new_messages
            input_body["system"] = system
            input_body["max_tokens"] = num_max_completion_tokens
            request_options = {
                "body": json.dumps(input_body),
                "modelId":  BEDROCK_LLM_MODELID_LIST.get(BEDROCK_MODEL_NAME),
                "accept": "application/json",
                "contentType": "application/json",
            }
            boto3_response = boto3_bedrock.invoke_model(**request_options)

            bedrock_response = boto3_response.get('body').read().decode('utf-8')
            response = convert_bedrock_to_gpt(bedrock_response)

            cost = prompt_cost(
                BEDROCK_MODEL_NAME,
                num_prompt_tokens=response.usage.prompt_tokens,
                num_completion_tokens=response.usage.completion_tokens
            )

            log_visualize(
                "**[OpenAI_Usage_Info Receive]**\nprompt_tokens: {}\ncompletion_tokens: {}\ntotal_tokens: {}\ncost: ${:.6f}\n".format(
                    response.usage.prompt_tokens, response.usage.completion_tokens,
                    response.usage.total_tokens, cost))
            # if not isinstance(response, ChatCompletion):
            #     raise RuntimeError("Unexpected return from OpenAI API")
            return response

        elif openai_new_api:
            # Experimental, add base_url
            if BASE_URL:
                client = openai.OpenAI(
                    api_key=OPENAI_API_KEY,
                    base_url=BASE_URL,
                )
            else:
                client = openai.OpenAI(
                    api_key=OPENAI_API_KEY
                )

            num_max_token_map = {
                "gpt-3.5-turbo": 4096,
                "gpt-3.5-turbo-16k": 16384,
                "gpt-3.5-turbo-0613": 4096,
                "gpt-3.5-turbo-16k-0613": 16384,
                "gpt-4": 8192,
                "gpt-4-0613": 8192,
                "gpt-4-32k": 32768,
                "gpt-4-1106-preview": 4096,
                "gpt-4-1106-vision-preview": 4096,
                "claude-3-sonnet":4096,
                "claude-3-haiku":4096,
                "claude-3-opus":4096,
            }
            num_max_token = num_max_token_map[self.model_type.value]
            num_max_completion_tokens = num_max_token - num_prompt_tokens
            self.model_config_dict['max_tokens'] = num_max_completion_tokens

            response = client.chat.completions.create(*args, **kwargs, model=self.model_type.value,
                                                      **self.model_config_dict)

            cost = prompt_cost(
                self.model_type.value,
                num_prompt_tokens=response.usage.prompt_tokens,
                num_completion_tokens=response.usage.completion_tokens
            )

            log_visualize(
                "**[OpenAI_Usage_Info Receive]**\nprompt_tokens: {}\ncompletion_tokens: {}\ntotal_tokens: {}\ncost: ${:.6f}\n".format(
                    response.usage.prompt_tokens, response.usage.completion_tokens,
                    response.usage.total_tokens, cost))
            if not isinstance(response, ChatCompletion):
                raise RuntimeError("Unexpected return from OpenAI API")
            return response
        else:
            num_max_token_map = {
                "gpt-3.5-turbo": 4096,
                "gpt-3.5-turbo-16k": 16384,
                "gpt-3.5-turbo-0613": 4096,
                "gpt-3.5-turbo-16k-0613": 16384,
                "gpt-4": 8192,
                "gpt-4-0613": 8192,
                "gpt-4-32k": 32768,
            }
            num_max_token = num_max_token_map[self.model_type.value]
            num_max_completion_tokens = num_max_token - num_prompt_tokens
            self.model_config_dict['max_tokens'] = num_max_completion_tokens

            response = openai.ChatCompletion.create(*args, **kwargs, model=self.model_type.value,
                                                    **self.model_config_dict)

            cost = prompt_cost(
                self.model_type.value,
                num_prompt_tokens=response["usage"]["prompt_tokens"],
                num_completion_tokens=response["usage"]["completion_tokens"]
            )

            log_visualize(
                "**[OpenAI_Usage_Info Receive]**\nprompt_tokens: {}\ncompletion_tokens: {}\ntotal_tokens: {}\ncost: ${:.6f}\n".format(
                    response["usage"]["prompt_tokens"], response["usage"]["completion_tokens"],
                    response["usage"]["total_tokens"], cost))
            if not isinstance(response, Dict):
                raise RuntimeError("Unexpected return from OpenAI API")
            return response


class StubModel(ModelBackend):
    r"""A dummy model used for unit tests."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__()

    def run(self, *args, **kwargs) -> Dict[str, Any]:
        ARBITRARY_STRING = "Lorem Ipsum"

        return dict(
            id="stub_model_id",
            usage=dict(),
            choices=[
                dict(finish_reason="stop",
                     message=dict(content=ARBITRARY_STRING, role="assistant"))
            ],
        )


class ModelFactory:
    r"""Factory of backend models.

    Raises:
        ValueError: in case the provided model type is unknown.
    """

    @staticmethod
    def create(model_type: ModelType, model_config_dict: Dict) -> ModelBackend:
        default_model_type = ModelType.GPT_3_5_TURBO

        if model_type in {
            ModelType.GPT_3_5_TURBO,
            ModelType.GPT_3_5_TURBO_NEW,
            ModelType.GPT_4,
            ModelType.GPT_4_32k,
            ModelType.GPT_4_TURBO,
            ModelType.GPT_4_TURBO_V,
            ModelType.CLAUDE_3_OPUS,
            ModelType.CLAUDE_3_SONNET,
            ModelType.CLAUDE_3_HAIKU,
            None
        }:
            model_class = OpenAIModel
        elif model_type == ModelType.STUB:
            model_class = StubModel
        else:
            raise ValueError("Unknown model")

        if model_type is None:
            model_type = default_model_type

        # log_visualize("Model Type: {}".format(model_type))
        inst = model_class(model_type, model_config_dict)
        return inst
