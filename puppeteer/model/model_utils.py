from typing import Dict
import logging
from tenacity import retry
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_exponential

logger = logging.getLogger("model")

class APIConfig:
    SLOW_FLAG = False 
    TRUNCATE_FACTOR = 0

def model_log_and_print(content):
    if content is not None:
        logger.info(content)
        print(content)

def truncate_messages(messages):
    max_length = 0
    max_index = 0
    for i, msg in enumerate(messages):
        if len(msg.get('content', '')) > max_length:
            max_length = len(msg['content'])
            max_index = i

    content = messages[max_index]['content']
    factor = 1/(2**APIConfig.TRUNCATE_FACTOR)
    messages[max_index]['content'] = content[:int(len(content)*factor)]  
    return messages


def calc_max_token(messages, max_tokens):
    string = "\n".join([str(message["content"]) for message in messages])
    num_prompt_tokens = int(len(string)//1.8) # approximation of tokens number 
    gap_between_send_receive = 15 * len(messages)
    num_prompt_tokens += gap_between_send_receive

    num_max_completion_tokens = max_tokens - num_prompt_tokens
    logger.info(f"num_prompt_tokens: {num_prompt_tokens}, num_max_completion_tokens: {num_max_completion_tokens}")
    if num_max_completion_tokens < 0:
        logger.warning(f"num_max_completion_tokens is negative: {num_max_completion_tokens}")
        return 0
    return num_max_completion_tokens


@retry(wait=wait_exponential(min=5, max=10), stop=stop_after_attempt(10))
def chat_completion_request(messages, model, new_client, model_config_dict: Dict = None):
    if model_config_dict is None:
        model_config_dict = {
            "temperature": 0.1,
            "top_p": 1.0,
            "n": 1,
            "stream": False,
            "frequency_penalty": 0.0,
            "presence_penalty": 0.0,
            "logit_bias": {},
        }

    json_data = {
        "model": model,
        "messages": messages,
        "max_tokens": 4096,
        "temperature": model_config_dict["temperature"],
        "top_p": model_config_dict["top_p"],
        "n": model_config_dict["n"],
        "stream": model_config_dict["stream"],
        "frequency_penalty": model_config_dict["frequency_penalty"],
        "presence_penalty": model_config_dict["presence_penalty"],
        "logit_bias": model_config_dict["logit_bias"],
    }

    try:
        model_log_and_print("[Model Query] {}".format(messages))
        if APIConfig.SLOW_FLAG:
            messages = truncate_messages(messages=messages)

        response = new_client.chat.completions.create(**json_data)

        completion_tokens = response.usage.completion_tokens
        prompt_tokens = response.usage.prompt_tokens
        total_tokens = response.usage.total_tokens
        if total_tokens == 0:
            total_tokens = prompt_tokens + completion_tokens
        if total_tokens == 0:
            total_tokens = len(response.choices[0].message.content)//1.8
        model_log_and_print(f"[Model Query] Token Usage: \nCompletion Tokens: {completion_tokens} \nPrompt Tokens: {prompt_tokens} \nTotal Tokens: {total_tokens}")
        APIConfig.SLOW_FLAG = False
        APIConfig.TRUNCATE_FACTOR = 0
        return response, total_tokens   

    except Exception as e:
        print("Unable to generate ChatCompletion response. " + f"OpenAI calling Exception: {e}")
        APIConfig.SLOW_FLAG = True
        APIConfig.TRUNCATE_FACTOR += 1
        model_log_and_print(f"[Model Query: ChatCompletion] query failed: {str(e)}")
        raise Exception()