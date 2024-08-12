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
from camel.config_loader import config_loader

from chatdev.statistics import prompt_cost
from chatdev.utils import log_visualize
from camel.utils import log_all_vars

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


import logging


class OpenAIModel(ModelBackend):
    def __init__(self, model_type: ModelType, model_config_dict: Dict) -> None:
        super().__init__()
        self.model_type = model_type
        self.model_config = model_config_dict
        self.client = self._setup_client()
        self.max_tokens = self.model_config.get("max_tokens")
        logging.debug(
            f"Initializing OpenAIModel with model_type: {model_type}, max_tokens: {self.max_tokens}"
        )
        if self.max_tokens is None:
            logging.warning(
                f"max_tokens is None for model {model_type}. Using default value of 4096."
            )
            self.max_tokens = 4096

    def _setup_client(self):

        if BASE_URL:
            return openai.OpenAI(api_key=OPENAI_API_KEY, base_url=BASE_URL)
        return openai.OpenAI(api_key=OPENAI_API_KEY)

    def run(self, *args, **kwargs):
        messages = kwargs.get("messages", [])
        prompt = "\n".join(message["content"] for message in messages)
        # Calculate the number of tokens in the prompt
        # See https://github.com/openai/tiktoken
        # TODO: We need to handle the case where we're using other models
        # TODO: We need to handle the case where we're talking to a local model
        try:
            encoding = tiktoken.encoding_for_model(self.model_type.value)
        except KeyError:
            logging.error(
                f"Could not map {self.model_type.value} to a tokeniser. Using default tokeniser."
            )
            encoding = tiktoken.get_encoding("cl100k_base")
        prompt_tokens = len(encoding.encode(prompt)) + 15 * len(messages)

        logging.debug(
            f"Running OpenAIModel with max_tokens: {self.max_tokens}, prompt_tokens: {prompt_tokens}"
        )
        max_completion_tokens = max(
            0, self.max_tokens - prompt_tokens
        )  # Ensure non-negative

        # Merge default config with model-specific config
        run_config = {**config_loader.get_default_config(), **self.model_config}
        # Remove 'name' and 'is_openai' from run_config as they're not needed for the API call
        run_config.pop("name", None)
        run_config.pop("is_openai", None)

        # Update max_tokens for this specific run
        run_config["max_tokens"] = max_completion_tokens

        # TODO use the base_url from the config file instead of the environment variable

        if "base_url" in run_config:
            run_config.pop("base_url")

        # NOTE self.client is an instance of openai.OpenAI set with _setup_client
        response = self.client.chat.completions.create(
            *args, **kwargs, model=self.model_type.value, **run_config
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
    def create(model_type: ModelType, model_config_dict: Dict = None) -> ModelBackend:
        if model_type is None:
            model_type = ModelType.GPT_3_5_TURBO

        if model_config_dict is None:
            model_config_dict = config_loader.get_model_config(model_type.name)

        logging.debug(
            f"Creating model with type: {model_type}, config: {model_config_dict}"
        )

        if not model_config_dict:
            raise ValueError(f"No configuration found for model type: {model_type}")

        if model_config_dict.get("is_openai", True):
            return OpenAIModel(model_type, model_config_dict)
        elif model_type == ModelType.STUB:
            return StubModel()
        else:
            raise ValueError(f"Unsupported model type: {model_type}")
