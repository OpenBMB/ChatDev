import json
import boto3
from typing import List,Union,Any
from pydantic import BaseModel
import time
import os
from anthropic_bedrock import AnthropicBedrock


BEDROCK_LLM_MODELID_LIST = {'claude-3-sonnet': 'anthropic.claude-3-sonnet-20240229-v1:0',
                            'claude-3-haiku' : 'anthropic.claude-3-haiku-20240307-v1:0'}


REGION = os.environ.get('region','us-west-2') 

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
    if model_name.startswith("claude"):
        num_tokens = anthropic_bedrock.count_tokens(text)  # 
    else:
        raise ValueError("Unknown model type")
    return num_tokens


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

def claude_invoke(messages:list,system:str,max_tokens:int,model_name:str):
    input_body = {}
    input_body["anthropic_version"] = "bedrock-2023-05-31"
    input_body["messages"] = messages
    input_body["system"] = system
    input_body["max_tokens"] = max_tokens
    request_options = {
        "body": json.dumps(input_body),
        "modelId":  BEDROCK_LLM_MODELID_LIST.get(model_name),
        "accept": "application/json",
        "contentType": "application/json",
    }
    boto3_response = boto3_bedrock.invoke_model(**request_options)

    bedrock_response = boto3_response.get('body').read().decode('utf-8')
    response = convert_bedrock_to_gpt(bedrock_response)
    return response
