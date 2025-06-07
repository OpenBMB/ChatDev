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
from chatdev.utils import log_macnet

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
    r"""OpenAI API in a unified ModelBackend interface."""

    def __init__(self, model_type: ModelType, model_config_dict: Dict) -> None:
        super().__init__()
        self.model_type = model_type
        self.model_config_dict = model_config_dict

    def run(self, *args, **kwargs):
        string = "\n".join([message["content"] for message in kwargs["messages"]])
        try:
            encoding = tiktoken.encoding_for_model(self.model_type.name)
            num_prompt_tokens = len(encoding.encode(string))
            gap_between_send_receive = 15 * len(kwargs["messages"])
            num_prompt_tokens += gap_between_send_receive
        except:
            num_prompt_tokens = 0

        if openai_new_api:
            # Experimental, add base_url
            if BASE_URL:
                client = openai.OpenAI(
                    api_key=OPENAI_API_KEY,
                    base_url=BASE_URL,
                )
            else:
                client = openai.OpenAI(api_key=OPENAI_API_KEY)

            num_max_token = self.model_type.num_tokens
            num_max_completion_tokens = num_max_token - num_prompt_tokens
            self.model_config_dict["max_tokens"] = num_max_completion_tokens

            response = client.chat.completions.create(
                *args, **kwargs, model=self.model_type.name, **self.model_config_dict
            )
            # cost = prompt_cost(
            #     self.model_type.name,
            #     num_prompt_tokens=response.usage.prompt_tokens,
            #     num_completion_tokens=response.usage.completion_tokens,
            # )

            # log_macnet(
            #     "\n**[OpenAI_Usage_Info Receive]**\nprompt_tokens: {}\ncompletion_tokens: {}\ntotal_tokens: {}\ncost: ${:.6f}\n".format(
            #         response.usage.prompt_tokens, response.usage.completion_tokens,
            #         response.usage.total_tokens, cost))
            if not isinstance(response, ChatCompletion):
                raise RuntimeError("Unexpected return from OpenAI API")
            return response
        else:
            num_max_token = self.model_type.num_tokens
            num_max_completion_tokens = num_max_token - num_prompt_tokens
            self.model_config_dict["max_tokens"] = num_max_completion_tokens

            response = openai.ChatCompletion.create(
                *args, **kwargs, model=self.model_type.value, **self.model_config_dict
            )

            # cost = prompt_cost(
            #     self.model_type.name,
            #     num_prompt_tokens=response["usage"]["prompt_tokens"],
            #     num_completion_tokens=response["usage"]["completion_tokens"],
            # )

            # log_macnet(
            #     "\n**[OpenAI_Usage_Info Receive]**\nprompt_tokens: {}\ncompletion_tokens: {}\ntotal_tokens: {}\ncost: ${:.6f}\n".format(
            #         response["usage"]["prompt_tokens"], response["usage"]["completion_tokens"],
            #         response["usage"]["total_tokens"], cost))
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
                dict(
                    finish_reason="stop",
                    message=dict(content=ARBITRARY_STRING, role="assistant"),
                )
            ],
        )


class ModelFactory:
    r"""Factory of backend models.

    Raises:
        ValueError: in case the provided model type is unknown.
    """

    @staticmethod
    def create(model_type: ModelType, model_config_dict: Dict) -> ModelBackend:

        model_class = (
            OpenAIModel if model_type and model_type.name != "stub" else StubModel
        )

        # log_visualize("Model Type: {}".format(model_type))
        inst = model_class(model_type, model_config_dict)
        return inst
