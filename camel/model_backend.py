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
#  Enhanced by Startr.Team (2024)
# =========== Copyright 2024 @  Startr LLC   All Rights Reserved. ===========
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

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
if "BASE_URL" in os.environ:
    BASE_URL = os.environ["BASE_URL"]
else:
    BASE_URL = None


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
    def __init__(self, model_type: ModelType, model_config_dict: Dict) -> None:
        super().__init__()
        self.model_type = model_type
        self.model_config_dict = model_config_dict
        self.client = self._setup_client()
        self.max_tokens = self._get_max_tokens()

    def _setup_client(self):
        if BASE_URL:
            return openai.OpenAI(api_key=OPENAI_API_KEY, base_url=BASE_URL)
        return openai.OpenAI(api_key=OPENAI_API_KEY)

    def _get_max_tokens(self):
        max_token_map = {
            "gpt-3.5-turbo": 4096,
            "gpt-3.5-turbo-16k": 16384,
            "gpt-3.5-turbo-0613": 4096,
            "gpt-3.5-turbo-16k-0613": 16384,
            "gpt-4": 8192,
            "gpt-4-0613": 8192,
            "gpt-4-32k": 32768,
            "gpt-4-turbo": 100000,
            "gpt-4o:": 100000,
            "gpt-4o-mini": 100000,
        }
        return max_token_map.get(self.model_type.value, 4096)

    def run(self, *args, **kwargs):
        messages = kwargs.get("messages", [])
        prompt = "\n".join(message["content"] for message in messages)
        
        encoding = tiktoken.encoding_for_model(self.model_type.value)
        prompt_tokens = len(encoding.encode(prompt)) + 15 * len(messages)
        
        max_completion_tokens = self.max_tokens - prompt_tokens
        self.model_config_dict["max_tokens"] = max_completion_tokens

        response = self.client.chat.completions.create(
            *args, **kwargs, model=self.model_type.value, **self.model_config_dict
        )

        self._log_usage(response.usage)
        return response

    def _log_usage(self, usage):
        cost = prompt_cost(
            self.model_type.value,
            num_prompt_tokens=usage.prompt_tokens,
            num_completion_tokens=usage.completion_tokens,
        )
        log_visualize(
            f"**[OpenAI_Usage_Info Receive]**\n"
            f"prompt_tokens: {usage.prompt_tokens}\n"
            f"completion_tokens: {usage.completion_tokens}\n"
            f"total_tokens: {usage.total_tokens}\n"
            f"cost: ${cost:.6f}\n"
        )


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
                dict(
                    finish_reason="stop",
                    message=dict(content=ARBITRARY_STRING, role="assistant"),
                )
            ],
        )


class ModelFactory:
    @staticmethod
    def create(model_type: ModelType, model_config_dict: Dict) -> ModelBackend:
        model_map = {
            ModelType.GPT_3_5_TURBO: OpenAIModel,
            ModelType.GPT_3_5_TURBO_NEW: OpenAIModel,
            ModelType.GPT_4: OpenAIModel,
            ModelType.GPT_4_TURBO: OpenAIModel,
            ModelType.GPT_4_TURBO_V: OpenAIModel,
            ModelType.STUB: StubModel,
        }

        model_class = model_map.get(model_type, OpenAIModel)
        
        if model_type is None:
            model_type = ModelType.GPT_3_5_TURBO

        return model_class(model_type, model_config_dict)