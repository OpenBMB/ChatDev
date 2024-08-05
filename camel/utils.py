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
# =========== Copyright 2023 @ CAMEL-AI.org. All Rights Reserved. ==============
#
# File: camel/typing.py
# Description: Enumerations for model, task, role, and phase types.
# 
# ==============================================================================

import os
import re
import zipfile
from functools import wraps
from typing import Any, Callable, List, Optional, Set, TypeVar

import requests
import tiktoken

from camel.messages import OpenAIMessage
from camel.typing import ModelType, TaskType
from camel.config_loader import ConfigLoader

F = TypeVar("F", bound=Callable[..., Any])

import time

# Load the model configurations
config_loader = ConfigLoader()
model_configs = config_loader.get_all_model_configs()

def count_tokens_openai_chat_models(
    messages: List[OpenAIMessage],
    encoding: Any,
) -> int:
    """Counts the number of tokens required to generate an OpenAI chat based
    on a given list of messages.

    Args:
        messages (List[OpenAIMessage]): The list of messages.
        encoding (Any): The encoding method to use.

    Returns:
        int: The number of tokens required.
    """
    num_tokens = 0
    for message in messages:
        # message follows <im_start>{role/name}\n{content}<im_end>\n
        num_tokens += 4
        for key, value in message.items():
            num_tokens += len(encoding.encode(value))
            if key == "name":  # if there's a name, the role is omitted
                num_tokens += -1  # role is always 1 token
    num_tokens += 2  # every reply is primed with <im_start>assistant
    return num_tokens


def num_tokens_from_messages(
    messages: List[OpenAIMessage],
    model: ModelType,
) -> int:
    """Returns the number of tokens used by a list of messages.

    Args:
        messages (List[OpenAIMessage]): The list of messages to count the
            number of tokens for.
        model (ModelType): The OpenAI model used to encode the messages.

    Returns:
        int: The total number of tokens used by the messages.

    Raises:
        NotImplementedError: If the specified `model` is not implemented.

    References:
        - https://github.com/openai/openai-python/blob/main/chatml.md
        - https://platform.openai.com/docs/models/gpt-4
        - https://platform.openai.com/docs/models/gpt-3-5
    """
    try:
        value_for_tiktoken = getattr(model, 'value_for_tiktoken', None)
        if value_for_tiktoken is None:
            raise AttributeError("The model does not have the 'value_for_tiktoken' attribute.")
        encoding = tiktoken.encoding_for_model(value_for_tiktoken)
    except (KeyError, AttributeError) as e:
        print(f"An error occurred: {e}")
        print(f"Using default encoding for model {model}")
        print(f"Dir of model: {dir(model)}")
        encoding = tiktoken.get_encoding("cl100k_base")

    if model.name in model_configs:
        return count_tokens_openai_chat_models(messages, encoding)
    else:
        raise NotImplementedError(
            f"`num_tokens_from_messages` is not presently implemented "
            f"for model {model}. "
            f"See https://github.com/openai/openai-python/blob/main/chatml.md "
            f"for information on how messages are converted to tokens. "
            f"See https://platform.openai.com/docs/models/gpt-4"
            f"or https://platform.openai.com/docs/models/gpt-3-5"
            f"for information about openai chat models."
        )


def get_model_token_limit(model: ModelType) -> int:
    r"""Returns the maximum token limit for a given model.

    Args:
        model (ModelType): The type of the model.

    Returns:
        int: The maximum token limit for the given model.
    """
    model_config = model_configs.get(model.name)
    if model_config:
        return model_config.get('max_tokens', 0)
    else:
        raise ValueError("Unknown model type")


def openai_api_key_required(func: F) -> F:
    """Decorator that checks if the OpenAI API key is available in the
    environment variables.

    Args:
        func (callable): The function to be wrapped.

    Returns:
        callable: The decorated function.

    Raises:
        ValueError: If the OpenAI API key is not found in the environment
            variables.
    """

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        from camel.agents.chat_agent import ChatAgent

        if not isinstance(self, ChatAgent):
            raise ValueError("Expected ChatAgent")
        if self.model == ModelType.STUB:
            return func(self, *args, *kwargs)
        elif "OPENAI_API_KEY" in os.environ:
            return func(self, *args, **kwargs)
        else:
            raise ValueError("OpenAI API key not found.")

    return wrapper


def print_text_animated(text, delay: float = 0.005, end: str = ""):
    """Prints the given text with an animated effect.

    Args:
        text (str): The text to print.
        delay (float, optional): The delay between each character printed.
            (default: :obj:`0.02`)
        end (str, optional): The end character to print after the text.
            (default: :obj:`""`)
    """
    for char in text:
        print(char, end=end, flush=True)
        time.sleep(delay)
    print("\n")


def get_prompt_template_key_words(template: str) -> Set[str]:
    """Given a string template containing curly braces {}, return a set of
    the words inside the braces.

    Args:
        template (str): A string containing curly braces.

    Returns:
        List[str]: A list of the words inside the curly braces.

    Example:
        >>> get_prompt_template_key_words('Hi, {name}! How are you {status}?')
        {'name', 'status'}
    """
    return set(re.findall(r"{([^}]*)}", template))


def get_first_int(string: str) -> Optional[int]:
    """Returns the first integer number found in the given string.

    If no integer number is found, returns None.

    Args:
        string (str): The input string.

    Returns:
        int or None: The first integer number found in the string, or None if
            no integer number is found.
    """
    match = re.search(r"\d+", string)
    if match:
        return int(match.group())
    else:
        return None


def download_tasks(task: TaskType, folder_path: str) -> None:
    """
    Download and extract task files for a given task type.

    Args:
        task (TaskType): The type of task to download.
        folder_path (str): The path where the tasks should be downloaded and extracted.

    Returns:
        None
    """
    # Define the path for the temporary zip file
    zip_file_path = os.path.join(folder_path, "tasks.zip")

    # Download the zip file from Hugging Face
    response = requests.get(
        "https://huggingface.co/datasets/camel-ai/"
        f"metadata/resolve/main/{task.value}_tasks.zip"
    )

    # Save the zip file to the specified folder
    with open(zip_file_path, "wb") as f:
        f.write(response.content)

    # Extract the contents of the zip file
    with zipfile.ZipFile(zip_file_path, "r") as zip_ref:
        zip_ref.extractall(folder_path)

    # Delete the temporary zip file
    os.remove(zip_file_path)
