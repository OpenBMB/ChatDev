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

from camel.typing import ModelType
from chatdev.statistics import prompt_cost
from chatdev.utils import log_visualize

try:
    from openai.types.chat import ChatCompletion

    openai_new_api = True  # new openai api version
except ImportError:
    openai_new_api = False  # old openai api version

import os
import json

OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')
if 'BASE_URL' in os.environ:
    BASE_URL = os.environ['BASE_URL']
else:
    BASE_URL = None

GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY', '')
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY', '')
DEEPSEEK_BASE_URL = os.environ.get('DEEPSEEK_BASE_URL', 'https://api.deepseek.com/v1')
MODEL_PROVIDER = os.environ.get('MODEL_PROVIDER', 'openai').lower()


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
        try:
            encoding = tiktoken.encoding_for_model(self.model_type.value_for_tiktoken)
            num_prompt_tokens = len(encoding.encode(string))
        except:
            num_prompt_tokens = len(string.split()) * 1.3
        gap_between_send_receive = 15 * len(kwargs["messages"])
        num_prompt_tokens += gap_between_send_receive

        if openai_new_api:
            # Experimental, add base_url
            api_key = OPENAI_API_KEY
            base_url = BASE_URL
            
            # Handle provider-specific configurations
            if MODEL_PROVIDER == "deepseek" and DEEPSEEK_API_KEY:
                api_key = DEEPSEEK_API_KEY
                base_url = DEEPSEEK_BASE_URL
            
            if base_url:
                client = openai.OpenAI(
                    api_key=api_key,
                    base_url=base_url,
                )
            else:
                client = openai.OpenAI(
                    api_key=api_key
                )

            num_max_token_map = {
                "gpt-3.5-turbo": 4096,
                "gpt-3.5-turbo-16k": 16384,
                "gpt-3.5-turbo-0613": 4096,
                "gpt-3.5-turbo-16k-0613": 16384,
                "gpt-4": 8192,
                "gpt-4-0613": 8192,
                "gpt-4-32k": 32768,
                "gpt-4-turbo": 100000,
                "gpt-4o": 128000,
                "gpt-4o-mini": 128000,
                "gemini-pro": 32768,
                "gemini-pro-vision": 16384,
                "gemini-1.5-pro": 2097152,
                "gemini-1.5-flash": 1048576,
                "deepseek-chat": 16384,
                "deepseek-coder": 16384,
                "deepseek-chat-v2": 64000,
                "claude-3-opus-20240229": 200000,
                "claude-3-sonnet-20240229": 200000,
                "claude-3-haiku-20240307": 200000,
                "claude-3-5-sonnet-20241022": 200000,
            }
            num_max_token = num_max_token_map.get(self.model_type.value, 16384)
            num_max_completion_tokens = num_max_token - num_prompt_tokens
            if num_max_completion_tokens > 0:
                self.model_config_dict['max_tokens'] = num_max_completion_tokens
            else:
                self.model_config_dict['max_tokens'] = num_max_token

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
                "gpt-4-turbo": 100000,
                "gpt-4o": 128000,
                "gpt-4o-mini": 128000,
                "gemini-pro": 32768,
                "gemini-pro-vision": 16384,
                "gemini-1.5-pro": 2097152,
                "gemini-1.5-flash": 1048576,
                "deepseek-chat": 16384,
                "deepseek-coder": 16384,
                "deepseek-chat-v2": 64000,
                "claude-3-opus-20240229": 200000,
                "claude-3-sonnet-20240229": 200000,
                "claude-3-haiku-20240307": 200000,
                "claude-3-5-sonnet-20241022": 200000,
            }
            num_max_token = num_max_token_map.get(self.model_type.value, 16384)
            num_max_completion_tokens = num_max_token - num_prompt_tokens
            if num_max_completion_tokens > 0:
                self.model_config_dict['max_tokens'] = num_max_completion_tokens
            else:
                self.model_config_dict['max_tokens'] = num_max_token

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


class GeminiModel(ModelBackend):
    r"""Google Gemini API in a unified ModelBackend interface."""

    def __init__(self, model_type: ModelType, model_config_dict: Dict) -> None:
        super().__init__()
        self.model_type = model_type
        self.model_config_dict = model_config_dict
        if not GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY environment variable is not set")
        try:
            import google.generativeai as genai
            self.genai = genai
            genai.configure(api_key=GOOGLE_API_KEY)
        except ImportError:
            raise ImportError("Please install google-generativeai: pip install google-generativeai")

    def run(self, *args, **kwargs):
        try:
            import google.generativeai as genai
        except ImportError:
            raise ImportError("Please install google-generativeai: pip install google-generativeai")
        
        if not GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY environment variable is not set")
        
        model = genai.GenerativeModel(self.model_type.value)
        
        messages = kwargs.get("messages", [])
        # Build conversation history for Gemini
        chat = model.start_chat(history=[])
        prompt_parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                prompt_parts.append(content)
            elif role == "assistant":
                # For multi-turn, we'd need to maintain history
                pass
        
        prompt = "\n".join(prompt_parts) if prompt_parts else "\n".join([msg.get("content", "") for msg in messages])
        
        generation_config = {
            "temperature": self.model_config_dict.get("temperature", 0.2),
            "top_p": self.model_config_dict.get("top_p", 1.0),
            "max_output_tokens": self.model_config_dict.get("max_tokens", 8192),
        }
        
        try:
            response = model.generate_content(
                prompt,
                generation_config=generation_config
            )
            content = response.text if hasattr(response, 'text') and response.text else str(response)
        except Exception as e:
            log_visualize(f"**[Gemini_Error]** {str(e)}")
            raise RuntimeError(f"Gemini API error: {str(e)}")
        
        # Estimate token usage (Gemini doesn't provide exact counts in free tier)
        prompt_tokens = len(prompt.split()) * 1.3
        completion_tokens = len(content.split()) * 1.3
        
        log_visualize(
            "**[Gemini_Usage_Info Receive]**\nModel: {}\nprompt_tokens: ~{}\ncompletion_tokens: ~{}\ntotal_tokens: ~{}\n".format(
                self.model_type.value, int(prompt_tokens), int(completion_tokens), int(prompt_tokens + completion_tokens)))
        
        # Return in OpenAI-compatible format
        if openai_new_api:
            from openai.types.chat import ChatCompletion
            from openai.types.chat.chat_completion import Choice
            from openai.types.chat.chat_completion_message import ChatCompletionMessage
            from openai.types.completion_usage import CompletionUsage
            
            return ChatCompletion(
                id=f"gemini-{self.model_type.value}",
                object="chat.completion",
                created=0,
                model=self.model_type.value,
                choices=[Choice(
                    index=0,
                    message=ChatCompletionMessage(
                        role="assistant",
                        content=content
                    ),
                    finish_reason="stop"
                )],
                usage=CompletionUsage(
                    prompt_tokens=int(prompt_tokens),
                    completion_tokens=int(completion_tokens),
                    total_tokens=int(prompt_tokens + completion_tokens)
                )
            )
        else:
            return {
                "id": f"gemini-{self.model_type.value}",
                "object": "chat.completion",
                "created": 0,
                "model": self.model_type.value,
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": content
                    },
                    "finish_reason": "stop"
                }],
                "usage": {
                    "prompt_tokens": int(prompt_tokens),
                    "completion_tokens": int(completion_tokens),
                    "total_tokens": int(prompt_tokens + completion_tokens)
                }
            }


class DeepSeekModel(ModelBackend):
    r"""DeepSeek API in a unified ModelBackend interface (OpenAI-compatible)."""

    def __init__(self, model_type: ModelType, model_config_dict: Dict) -> None:
        super().__init__()
        self.model_type = model_type
        self.model_config_dict = model_config_dict

    def run(self, *args, **kwargs):
        if not DEEPSEEK_API_KEY:
            raise ValueError("DEEPSEEK_API_KEY environment variable is not set")
        
        string = "\n".join([message["content"] for message in kwargs["messages"]])
        try:
            encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
            num_prompt_tokens = len(encoding.encode(string))
        except:
            num_prompt_tokens = len(string.split()) * 1.3
        
        gap_between_send_receive = 15 * len(kwargs["messages"])
        num_prompt_tokens += gap_between_send_receive

        if openai_new_api:
            client = openai.OpenAI(
                api_key=DEEPSEEK_API_KEY,
                base_url=DEEPSEEK_BASE_URL,
            )

            num_max_token_map = {
                "deepseek-chat": 16384,
                "deepseek-coder": 16384,
                "deepseek-chat-v2": 64000,
            }
            num_max_token = num_max_token_map.get(self.model_type.value, 16384)
            num_max_completion_tokens = num_max_token - num_prompt_tokens
            if num_max_completion_tokens > 0:
                self.model_config_dict['max_tokens'] = num_max_completion_tokens
            else:
                self.model_config_dict['max_tokens'] = num_max_token

            response = client.chat.completions.create(*args, **kwargs, model=self.model_type.value,
                                                      **self.model_config_dict)

            log_visualize(
                "**[DeepSeek_Usage_Info Receive]**\nprompt_tokens: {}\ncompletion_tokens: {}\ntotal_tokens: {}\n".format(
                    response.usage.prompt_tokens, response.usage.completion_tokens,
                    response.usage.total_tokens))
            if not isinstance(response, ChatCompletion):
                raise RuntimeError("Unexpected return from DeepSeek API")
            return response
        else:
            raise RuntimeError("DeepSeek requires OpenAI API version 1.0.0 or higher")


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

        if model_type is None:
            model_type = default_model_type

        # OpenAI models
        if model_type in {
            ModelType.GPT_3_5_TURBO,
            ModelType.GPT_3_5_TURBO_NEW,
            ModelType.GPT_4,
            ModelType.GPT_4_32k,
            ModelType.GPT_4_TURBO,
            ModelType.GPT_4_TURBO_V,
            ModelType.GPT_4O,
            ModelType.GPT_4O_MINI,
        }:
            model_class = OpenAIModel
        # Google Gemini models
        elif model_type in {
            ModelType.GEMINI_PRO,
            ModelType.GEMINI_PRO_VISION,
            ModelType.GEMINI_1_5_PRO,
            ModelType.GEMINI_1_5_FLASH,
        }:
            model_class = GeminiModel
        # DeepSeek models
        elif model_type in {
            ModelType.DEEPSEEK_CHAT,
            ModelType.DEEPSEEK_CODER,
            ModelType.DEEPSEEK_CHAT_V2,
        }:
            model_class = DeepSeekModel
        # OpenAI-compatible models (Claude, Llama, Mistral, etc.)
        elif model_type in {
            ModelType.CLAUDE_3_OPUS,
            ModelType.CLAUDE_3_SONNET,
            ModelType.CLAUDE_3_HAIKU,
            ModelType.CLAUDE_3_5_SONNET,
            ModelType.LLAMA_3_70B,
            ModelType.LLAMA_3_8B,
            ModelType.MISTRAL_LARGE,
            ModelType.MISTRAL_MEDIUM,
            ModelType.MISTRAL_SMALL,
        }:
            model_class = OpenAIModel
        elif model_type == ModelType.STUB:
            model_class = StubModel
        else:
            raise ValueError(f"Unknown model: {model_type}")

        # log_visualize("Model Type: {}".format(model_type))
        inst = model_class(model_type, model_config_dict)
        return inst
