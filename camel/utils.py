import os
import re
import sys
import time
import zipfile
import inspect
from functools import wraps
from typing import Any, Callable, List, Optional, Set, TypeVar

import requests
import tiktoken

from camel.messages import OpenAIMessage
from camel.typing import ModelType, TaskType
from camel.config_loader import ConfigLoader

F = TypeVar("F", bound=Callable[..., Any])

# Load the model configurations
config_loader = ConfigLoader()
model_configs = config_loader.get_all_model_configs()

# camel/utils.py


def pretty_format(value):
    """Format values for pretty printing."""
    if isinstance(value, dict):
        return (
            "{\n  "
            + ",\n  ".join(f"{repr(k)}: {repr(v)}" for k, v in value.items())
            + "\n}"
        )
    elif isinstance(value, list):
        return "[\n  " + ",\n  ".join(repr(item) for item in value) + "\n]"
    elif isinstance(value, tuple):
        return "(\n  " + ",\n  ".join(repr(item) for item in value) + "\n)"
    elif isinstance(value, set):
        return "{\n  " + ",\n  ".join(repr(item) for item in value) + "\n}"
    elif isinstance(value, str):
        return repr(value)
    else:
        return repr(value)


def log_all_vars(exit_after_log=False):
    """Log all variables in the caller's scope, excluding special variables.

    Parameters:
    exit_after_log (bool): If True, the program will exit after logging variables.
    """
    # Get the caller's frame
    frame = inspect.currentframe().f_back

    # Retrieve all local variables from the caller's frame
    local_vars = frame.f_locals

    # Print a header for clarity
    print("\n" + "=" * 40)
    print("Variables in the current scope:")
    print("=" * 40)

    # Loop through the local variables and print their values
    for var, value in local_vars.items():
        if not (var.startswith("_") or var == ""):
            pretty_value = pretty_format(value)
            print(f"{var:<20} : {pretty_value}")

    # Print a footer for clarity
    print("=" * 40 + "\n")

    # Exit the program if exit_after_log is True
    if exit_after_log:
        sys.exit("Exiting after logging all variables.")


def count_tokens_openai_chat_models(
    messages: List[OpenAIMessage], encoding: Any
) -> int:
    """Count the number of tokens required to generate an OpenAI chat based on a given list of messages."""
    num_tokens = 0
    for message in messages:
        num_tokens += 4  # message follows <im_start>{role/name}\n{content}<im_end>\n
        for key, value in message.items():
            num_tokens += len(encoding.encode(value))
            if key == "name":  # if there's a name, the role is omitted
                num_tokens -= 1  # role is always 1 token
    num_tokens += 2  # every reply is primed with <im_start>assistant
    return num_tokens


def num_tokens_from_messages(messages: List[OpenAIMessage], model: ModelType) -> int:
    """Return the number of tokens used by a list of messages."""
    encoding = tiktoken.get_encoding("cl100k_base")

    if model.name in model_configs:
        return count_tokens_openai_chat_models(messages, encoding)
    else:
        raise NotImplementedError(f"Token counting not implemented for model {model}.")


def get_model_token_limit(model: ModelType) -> int:
    """Return the maximum token limit for a given model."""
    model_config = model_configs.get(model.name)
    if model_config:
        return model_config.get("max_tokens", 0)
    else:
        raise ValueError(f"Unknown model type: {model}")


def openai_api_key_required(func: F) -> F:
    """Decorator that checks if the OpenAI API key is available in the environment variables."""

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        from camel.agents.chat_agent import ChatAgent

        if not isinstance(self, ChatAgent):
            raise ValueError("Expected ChatAgent")
        if self.model == ModelType.STUB or "OPENAI_API_KEY" in os.environ:
            return func(self, *args, **kwargs)
        else:
            raise ValueError("OpenAI API key not found.")

    return wrapper


def print_text_animated(text: str, delay: float = 0.005, end: str = ""):
    """Print the given text with an animated effect."""
    for char in text:
        print(char, end=end, flush=True)
        time.sleep(delay)
    print("\n")


def get_prompt_template_key_words(template: str) -> Set[str]:
    """Return a set of words inside curly braces in the given template string."""
    return set(re.findall(r"{([^}]*)}", template))


def get_first_int(string: str) -> Optional[int]:
    """Return the first integer number found in the given string, or None if not found."""
    match = re.search(r"\d+", string)
    return int(match.group()) if match else None


def download_tasks(task: TaskType, folder_path: str) -> None:
    """Download and extract task files for a given task type."""
    zip_file_path = os.path.join(folder_path, "tasks.zip")

    response = requests.get(
        f"https://huggingface.co/datasets/camel-ai/metadata/resolve/main/{task.value}_tasks.zip"
    )

    with open(zip_file_path, "wb") as f:
        f.write(response.content)

    with zipfile.ZipFile(zip_file_path, "r") as zip_ref:
        zip_ref.extractall(folder_path)

    os.remove(zip_file_path)
