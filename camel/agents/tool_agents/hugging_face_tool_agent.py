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
from typing import Any, Optional

from camel.agents.tool_agents import BaseToolAgent


# flake8: noqa :E501
class HuggingFaceToolAgent(BaseToolAgent):
    r"""Tool agent for calling HuggingFace models. This agent is a wrapper
        around agents from the `transformers` library. For more information
        about the available models, please see the `transformers` documentation
        at https://huggingface.co/docs/transformers/transformers_agents.

    Args:
        name (str): The name of the agent.
        *args (Any): Additional positional arguments to pass to the underlying
            Agent class.
        remote (bool, optional): Flag indicating whether to run the agent
            remotely. (default: :obj:`True`)
        **kwargs (Any): Additional keyword arguments to pass to the underlying
            Agent class.
    """

    def __init__(
        self,
        name: str,
        *args: Any,
        remote: bool = True,
        **kwargs: Any,
    ) -> None:
        try:
            # TODO: Support other tool agents
            from transformers.tools import OpenAiAgent
        except ImportError:
            raise ValueError(
                "Could not import transformers tool agents. "
                "Please setup the environment with "
                "pip install huggingface_hub==0.14.1 transformers==4.29.0 diffusers accelerate datasets torch soundfile sentencepiece opencv-python"
            )
        self.agent = OpenAiAgent(*args, **kwargs)
        self.name = name
        self.remote = remote
        self.description = f"""The `{self.name}` is a tool agent that can perform a variety of tasks including:
- Document question answering: given a document (such as a PDF) in image format, answer a question on this document
- Text question answering: given a long text and a question, answer the question in the text
- Unconditional image captioning: Caption the image!
- Image question answering: given an image, answer a question on this image
- Image segmentation: given an image and a prompt, output the segmentation mask of that prompt
- Speech to text: given an audio recording of a person talking, transcribe the speech into text
- Text to speech: convert text to speech
- Zero-shot text classification: given a text and a list of labels, identify to which label the text corresponds the most
- Text summarization: summarize a long text in one or a few sentences
- Translation: translate the text into a given language
- Text downloading: to download a text from a web URL
- Text to image: generate an image according to a prompt, leveraging stable diffusion
- Image transformation: modify an image given an initial image and a prompt, leveraging instruct pix2pix stable diffusion
- Text to video: generate a small video according to a prompt

Here are some python code examples of what you can do with this agent:

Single execution (step) mode, the single execution method is when using the step() method of the agent:
```
# Text to image
rivers_and_lakes_image = {self.name}.step("Draw me a picture of rivers and lakes.")
rivers_and_lakes_image.save("./rivers_and_lakes_image.png")

# Text to image -> Image transformation
sea_add_island_image = {self.name}.step("Draw me a picture of the sea then transform the picture to add an island")
sea_add_island_image.save("./sea_add_island_image.png")

# If you'd like to keep a state across executions or to pass non-text objects to the agent, 
# you can do so by specifying variables that you would like the agent to use. For example,
# you could generate the first image of rivers and lakes, and ask the model to update that picture to add an island by doing the following:
picture = {self.name}.step("Generate a picture of rivers and lakes.")
picture.save("./picture.png")
updated_picture = {self.name}.step("Transform the image in `picture` to add an island to it.", picture=picture)
updated_picture.save("./updated_picture.png")

capybara_sea_image = {self.name}.step("Draw me a picture of the `prompt`", prompt="a capybara swimming in the sea")
capybara_sea_image.save("./capybara_sea_image.png")

# Document question answering
answer = {self.name}.step(
    "In the following `document`, where will the TRRF Scientific Advisory Council Meeting take place?",
    document=document,
)
print(answer)


# Text to image
boat_image = {self.name}.step("Generate an image of a boat in the water")
boat_image.save("./boat_image.png")

# Unconditional image captioning
boat_image_caption = {self.name}.step("Can you caption the `boat_image`?", boat_image=boat_image)
print(boat_image_caption)

# Text to image -> Unconditional image captioning -> Text to speech
boat_audio = {self.name}.step("Can you generate an image of a boat? Please read out loud the contents of the image afterwards")

# Text downloading
document = {self.name}.step("Download the text from http://hf.co")
print(document)

# Text summarization
summary = {self.name}.step("Summarize the following text: `document`", document=document)
print(summary)

# Text downloading -> Text summarization -> Text to speech
audio = {self.name}.step("Read out loud the summary of http://hf.co")
```

Chat-based execution (chat), the agent also has a chat-based approach, using the chat() method:
```
# Clean the chat history
{self.name}.reset()

# Text to image
capybara_image = {self.name}.chat("Show me an an image of a capybara")
capybara_image.save("./capybara_image.png")

# Image transformation
transformed_capybara_image = {self.name}.chat("Transform the image so that it snows")
transformed_capybara_image.save("./transformed_capybara_image.png")

# Image segmentation
segmented_transformed_capybara_image = {self.name}.chat("Show me a mask of the snowy capybaras")
segmented_transformed_capybara_image.save("./segmented_transformed_capybara_image.png")
```
"""

    def reset(self) -> None:
        r"""Resets the chat history of the agent."""
        self.agent.prepare_for_new_chat()

    def step(
        self,
        *args: Any,
        remote: Optional[bool] = None,
        **kwargs: Any,
    ) -> Any:
        r"""Runs the agent in single execution mode.

        Args:
            *args (Any): Positional arguments to pass to the agent.
            remote (bool, optional): Flag indicating whether to run the agent
                remotely. Overrides the default setting. (default: :obj:`None`)
            **kwargs (Any): Keyword arguments to pass to the agent.

        Returns:
            str: The response from the agent.
        """
        if remote is None:
            remote = self.remote
        return self.agent.run(*args, remote=remote, **kwargs)

    def chat(
        self,
        *args: Any,
        remote: Optional[bool] = None,
        **kwargs: Any,
    ) -> Any:
        r"""Runs the agent in a chat conversation mode.

        Args:
            *args (Any): Positional arguments to pass to the agent.
            remote (bool, optional): Flag indicating whether to run the agent
                remotely. Overrides the default setting. (default: :obj:`None`)
            **kwargs (Any): Keyword arguments to pass to the agent.

        Returns:
            str: The response from the agent.
        """
        if remote is None:
            remote = self.remote
        return self.agent.chat(*args, remote=remote, **kwargs)
