import os

USE_OPENAI = False
if USE_OPENAI == True:
    import openai
    from openai import OpenAI
    OPENAI_API_KEY = os.environ['OPENAI_API_KEY']
    if 'BASE_URL' in os.environ:
        BASE_URL = os.environ['BASE_URL']
    else:
        BASE_URL = None
else:
    import re
    from urllib.parse import urlencode
    import subprocess
    import json
    import jsonstreams
    from io import StringIO
    from contextlib import redirect_stdout
    BASE_URL = "http://localhost:11434/api/generate"
    mistral_new_api = True  # new mistral api version
import sys
import time
from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
    wait_fixed
)
from utils import log_and_print_online
sys.path.append(os.path.join(os.getcwd(),"ecl"))

class OpenAIEmbedding:
    def __init__(self, **params):
        self.code_prompt_tokens = 0
        self.text_prompt_tokens = 0
        self.code_total_tokens = 0
        self.text_total_tokens = 0

        self.prompt_tokens = 0
        self.total_tokens = 0

    #@retry(wait=wait_random_exponential(min=2, max=5), stop=stop_after_attempt(10))
    @retry(wait=wait_random_exponential(min=1, max=1), stop=stop_after_attempt(1))
    def get_text_embedding(self,text: str):
            if BASE_URL:
                client = openai.OpenAI(
                    api_key=OPENAI_API_KEY,
                    base_url=BASE_URL,
                )
            else:
                client = openai.OpenAI(
                    api_key=OPENAI_API_KEY
                )

            if len(text)>8191:
                  text = text[:8190]
            response = client.embeddings.create(input = text, model="text-embedding-ada-002").model_dump()
            embedding = response['data'][0]['embedding']
            log_and_print_online(
            "Get text embedding from {}:\n**[OpenAI_Usage_Info Receive]**\nprompt_tokens: {}\ntotal_tokens: {}\n".format(
                response["model"],response["usage"]["prompt_tokens"],response["usage"]["total_tokens"]))
            self.text_prompt_tokens += response["usage"]["prompt_tokens"]
            self.text_total_tokens += response["usage"]["total_tokens"]
            self.prompt_tokens += response["usage"]["prompt_tokens"]
            self.total_tokens += response["usage"]["total_tokens"]

            return embedding

    @retry(wait=wait_random_exponential(min=10, max=60), stop=stop_after_attempt(10))
    def get_code_embedding(self,code: str):
            if BASE_URL:
                client = openai.OpenAI(
                    api_key=OPENAI_API_KEY,
                    base_url=BASE_URL,
                )
            else:
                client = openai.OpenAI(
                    api_key=OPENAI_API_KEY
                )
            if len(code) == 0:
                  code = "#"
            elif len(code) >8191:
                  code = code[0:8190]
            response = client.embeddings.create(input=code, model="text-embedding-ada-002").model_dump()
            embedding = response['data'][0]['embedding']
            log_and_print_online(
            "Get code embedding from {}:\n**[OpenAI_Usage_Info Receive]**\nprompt_tokens: {}\ntotal_tokens: {}\n".format(
                response["model"],response["usage"]["prompt_tokens"],response["usage"]["total_tokens"]))
            
            self.code_prompt_tokens += response["usage"]["prompt_tokens"]
            self.code_total_tokens += response["usage"]["total_tokens"]
            self.prompt_tokens += response["usage"]["prompt_tokens"]
            self.total_tokens += response["usage"]["total_tokens"]

            return embedding


class MistralAIEmbedding:
    def __init__(self, **params):
        self.code_prompt_tokens = 0
        self.text_prompt_tokens = 0
        self.code_total_tokens = 0
        self.text_total_tokens = 0

        self.prompt_tokens = 0
        self.total_tokens = 0

    def generate_stream_json_response(self, prompt):
        data = json.dumps({"model": "openhermes", "prompt": prompt})
        process = subprocess.Popen(["curl", "-X", "POST", "-d", data, "http://localhost:11434/api/generate"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        full_response = ""
        with jsonstreams.Stream(jsonstreams.Type.array, filename='./response_log.txt') as output:
            while True:
                line, _ = process.communicate()
                if not line:
                    break
                try:
                    record = line.decode("utf-8").split("\n")
                    for i in range(len(record)-1):
                        data = json.loads(record[i].replace('\0', ''))
                        if "response" in data:
                            full_response += data["response"]
                            with output.subobject() as output_e:
                                output_e.write('response', data["response"])
                        else:
                            return full_response.replace('\0', '')
                    if len(record)==1:
                        data = json.loads(record[0].replace('\0', ''))
                        if "error" in data:
                            full_response += data["error"]
                            with output.subobject() as output_e:
                                output_e.write('error', data["error"])
                    return full_response.replace('\0', '')
                except Exception as error:
                    # handle the exception
                    print("An exception occurred:", error)
        return full_response.replace('\0', '')
    
    #@retry(wait=wait_random_exponential(min=2, max=5), stop=stop_after_attempt(10))
    @retry(wait=wait_random_exponential(min=1, max=1), stop=stop_after_attempt(1))
    def get_text_embedding(self,text: str):
            if len(text)>8191:
                  text = text[:8190]
            response = self.generate_stream_json_response("<|im_start|>user" + '\n' + text + "<|im_end|>")
            embedding = response['data'][0]['embedding']
            log_and_print_online(
            "Get text embedding from {}:\n**[Mistral_Usage_Info Receive]**\nprompt_tokens: {}\ntotal_tokens: {}\n".format(
                response["model"],response["usage"]["prompt_tokens"],response["usage"]["total_tokens"]))
            self.text_prompt_tokens += response["usage"]["prompt_tokens"]
            self.text_total_tokens += response["usage"]["total_tokens"]
            self.prompt_tokens += response["usage"]["prompt_tokens"]
            self.total_tokens += response["usage"]["total_tokens"]

            return embedding

    #@retry(wait=wait_random_exponential(min=10, max=60), stop=stop_after_attempt(10))
    @retry(wait=wait_random_exponential(min=1, max=1), stop=stop_after_attempt(1))
    def get_code_embedding(self,code: str):
            if len(code) == 0:
                  code = "#"
            elif len(code) >8191:
                  code = code[0:8190]
            response = self.generate_stream_json_response("<|im_start|>user" + '\n' + code + "<|im_end|>")
            embedding = response['data'][0]['embedding']
            log_and_print_online(
            "Get code embedding from {}:\n**[Mistral_Usage_Info Receive]**\nprompt_tokens: {}\ntotal_tokens: {}\n".format(
                response["model"],response["usage"]["prompt_tokens"],response["usage"]["total_tokens"]))
            
            self.code_prompt_tokens += response["usage"]["prompt_tokens"]
            self.code_total_tokens += response["usage"]["total_tokens"]
            self.prompt_tokens += response["usage"]["prompt_tokens"]
            self.total_tokens += response["usage"]["total_tokens"]

            return embedding




