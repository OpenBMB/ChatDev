from dataclasses import dataclass, field
from typing import Dict, Optional, Sequence, Union


@dataclass(frozen=True)
class ChatGPTConfig:
    """
    Configuration options for creating chat responses using OpenAI's API.

    Attributes:
        temperature (float): Controls response randomness. Range: 0 to 2.
            Higher values make responses more creative, lower values make them more focused.
            Default is 0.2.
        top_p (float): Controls diversity via nucleus sampling. Range: 0 to 1.
            Default is 1.0.
        n (int): Number of responses to generate per input. Default is 1.
        stream (bool): If True, streams partial responses as they are generated.
            Default is False.
        stop (Optional[Union[str, Sequence[str]]]): Phrases where the API will stop generating
            further text. Default is None.
        max_tokens (Optional[int]): Maximum length of the generated response in tokens.
            Default is None.
        presence_penalty (float): Encourages discussion of new topics. Range: -2.0 to 2.0.
            Default is 0.0.
        frequency_penalty (float): Discourages repetition of the same words. Range: -2.0 to 2.0.
            Default is 0.0.
        logit_bias (Dict[int, float]): Modifies the likelihood of specified tokens appearing.
            Uses token IDs as keys and bias values from -100 to 100.
            Default is an empty dictionary.
        user (str): User ID to help OpenAI monitor and prevent misuse. Default is an empty string.
    """

    temperature: float = 0.2
    top_p: float = 1.0
    n: int = 1
    stream: bool = False
    stop: Optional[Union[str, Sequence[str]]] = None
    max_tokens: Optional[int] = None
    presence_penalty: float = 0.0
    frequency_penalty: float = 0.0
    logit_bias: Dict[int, float] = field(default_factory=dict)
    user: str = ""
