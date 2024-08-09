import os
import re
import time
import zipfile
from functools import wraps
from typing import Any, Callable, List, Optional, Set, TypeVar

import requests
import tiktoken

from camel.messages import OpenAIMessage
from camel.typing import ModelType, TaskType
from camel.config_loader import ConfigLoader

F = TypeVar('F', bound=Callable[..., Any])

# Load the model configurations
config_loader = ConfigLoader()
model_configs = config_loader.get_all_model_configs()

def count_tokens_openai_chat_models(messages: List[OpenAIMessage], encoding: Any) -> int:
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
        return model_config.get('max_tokens', 0)
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