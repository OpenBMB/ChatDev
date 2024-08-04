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
from dataclasses import dataclass, field
from typing import Dict, Optional, Sequence, Union


@dataclass(frozen=True)
class ChatGPTConfig:
    """Sets up the options for creating chat responses using OpenAI's API.

    Options:
        temperature (float, optional): Controls how random the output is.
            Range: 0 to 2. Higher values make responses more creative,
            lower values make them more focused. (Default: 0.2)

        top_p (float, optional): Another way to control randomness.
            Only considers the most likely options up to this probability.
            Range: 0 to 1. (Default: 1.0)

        n (int, optional): Number of different responses to generate for
            each input. (Default: 1)

        stream (bool, optional): If True, sends partial responses as they
            are created. (Default: False)

        stop (str or list, optional): Up to 4 phrases where the API will
            stop generating more text. (Default: None)

        max_tokens (int, optional): Longest possible response in tokens.
            Total input and output tokens can't exceed the model's limit.
            (Default: None)

        presence_penalty (float, optional): Encourages talking about new topics.
            Range: -2.0 to 2.0. Positive values increase new topic likelihood.
            (Default: 0.0)

        frequency_penalty (float, optional): Discourages repeating the same words.
            Range: -2.0 to 2.0. Positive values reduce word repetition.
            (Default: 0.0)

        logit_bias (dict, optional): Changes how likely specific words are to appear.
            Uses token IDs as keys and values from -100 to 100.
            Positive values make words more likely, negative less likely.
            Extreme values (-100 or 100) can force or prevent word use.
            (Default: {})

        user (str, optional): Your user ID, helps OpenAI prevent misuse.
            (Default: "")
    """
    temperature: float = 0.2
    top_p: float = 1.0
    n: int = 1
    stream: bool = False
    stop: Optional[Union[str, Sequence[str]]] = None
    max_tokens: Optional[int] = None
    presence_penalty: float = 0.0
    frequency_penalty: float = 0.0
    logit_bias: Dict = field(default_factory=dict)
    user: str = ""