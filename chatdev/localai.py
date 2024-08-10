# localai | This module recreates the `openai` library for local use with ollama models.
# It runs models on your local machine and will soon support worker systems.
# This library aims to work as a standalone tool with fewer bugs and easy maintenance.

# see: https://raw.githubusercontent.com/latekvo/LocalChatDev/main/camel/localai.py for inspiration
#

from typing import List, Optional
from typing_extensions import Literal
import json
import time
import requests
from dataclasses import dataclass

# Define classes for type recognition in chat_agent.py
@dataclass
class LocalChatCompletionMessage:
    content: Optional[str]
    role: Literal["assistant"]


@dataclass
class LocalCompletionUsage:
    prompt_tokens: str
    completion_tokens: str
    total_tokens: str


@dataclass
class LocalChoice:
    finish_reason: Literal["stop", "length", "tool_calls", "content_filter"]
    index: int
    message: LocalChatCompletionMessage


@dataclass
class LocalChatCompletion:
    id: str
    choices: List[LocalChoice]
    created: int
    model: str
    object: Literal["chat.completion"]
    system_fingerprint: Optional[str] = None
    usage: Optional[LocalCompletionUsage] = None


# Singleton class to manage worker agents
class WorkerManagerMetaclass:
    _instances = {}

    def __call__(self, *args, **kwargs):
        if self not in self._instances:
            self._instances[self] = super(WorkerManagerMetaclass, self).__call__(
                *args, **kwargs
            )
        return self._instances[self]


class WorkerManager(WorkerManagerMetaclass):
    def __init__(self, data):
        self.data = data


class LocalAI:
    class Chat:
        class Completions:
            def create(self, user, messages, max_tokens, *args, **kwargs):
                request_url = self.parent.parent.base_url + "api/chat"
                request_data = {
                    "model": self.parent.parent.model,
                    "messages": messages,
                }

                response = requests.post(
                    url=request_url, json=request_data, stream=True
                )
                response.raise_for_status()

                response_stream = response.iter_lines()
                response_list = []

                repeat_counter = 0
                repeat_token = ""

                prompt_token_count = 0
                response_token_count = 0

                for chunk in response_stream:
                    chunk_json = json.loads(chunk)
                    chunk_text = chunk_json["message"]["content"]
                    chunk_done = chunk_json["done"]

                    if chunk_text == repeat_token:
                        repeat_counter += 1
                    else:
                        repeat_counter = 0
                        repeat_token = chunk_text

                    if chunk_done:
                        prompt_token_count = chunk_json["prompt_eval_count"]
                        response_token_count = chunk_json["eval_count"]
                        response.close()
                        break
                    elif repeat_counter > 5:
                        response.close()
                        break
                    else:
                        response_list.append(chunk_text)

                response_text = "".join(response_list)

                input_cost = prompt_token_count
                output_cost = response_token_count
                total_cost = input_cost + output_cost

                return_object = LocalChatCompletion(
                    id=str(round(time.time() * 1000)),
                    object="chat.completion",
                    created=round(time.time() * 1000),
                    model=self.parent.parent.model,
                    system_fingerprint="system_fingerprint-stud",
                    choices=[
                        LocalChoice(
                            index=0,
                            message=LocalChatCompletionMessage(
                                role="assistant", content=response_text
                            ),
                            finish_reason="stop",
                        )
                    ],
                    usage=LocalCompletionUsage(
                        prompt_tokens=str(input_cost),
                        completion_tokens=str(output_cost),
                        total_tokens=str(total_cost),
                    ),
                )

                return return_object

            def __init__(self, parent):
                self.parent = parent

        def __init__(self, parent):
            self.parent = parent
            self.completions = self.Completions(self)

    def __init__(self, base_url=None, decentralize=False):
        self.base_url = base_url if base_url else "http://localhost:11434/"
        self.model = "phi3"

        self.chat = self.Chat(self)


# Test run functionality
def main():
    local_ai = LocalAI()
    user = "test_user"
    messages = [{"role": "user", "content": "Hello, AI!"}]
    max_tokens = 50

    result = local_ai.chat.completions.create(user, messages, max_tokens)
    print("Test Run Result:")
    print(result)


if __name__ == "__main__":
    main()
