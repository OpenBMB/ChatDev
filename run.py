# =========== Copyright 2023 - 2024 Startr.LLC & CAMEL-AI.org. All Rights Reserved. ===========
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# =========== Copyright 2023 - 2024 @ Startr.LLC & CAMEL-AI.org. All Rights Reserved. ===========

import argparse
import logging
import os
import sys
from typing import NoReturn, Tuple, List

# Importing from camel.typing our supported Models
from camel.typing import ModelType

# Constants
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = os.path.join(ROOT_DIR, "CompanyConfig")
DEFAULT_CONFIG_DIR = os.path.join(CONFIG_DIR, "Default")

CONFIG_FILES = [
    "ChatChainConfig.json", 
    "PhaseConfig.json", 
    "RoleConfig.json"
    ]

sys.path.append(ROOT_DIR)

from chatdev.chat_chain import ChatChain

try:
    from openai.types.chat.chat_completion_message_tool_call import (
        ChatCompletionMessageToolCall,
    )
    from openai.types.chat.chat_completion_message import FunctionCall

    openai_new_api = True  # new openai api version
except ImportError:
    openai_new_api = False  # old openai api version
    print(
        "Warning: Your OpenAI version is outdated. \n "
        "Please update as specified in requirement.txt. \n "
        "The old API interface is deprecated and will no longer be supported."
    )


def get_model_choices() -> List[str]:
    """
    Get the list of available model choices from ModelType enum.

    Returns:
        List[str]: List of available model choices.
    """
    return [model.name for model in ModelType]


def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments for the Startr.Team ChatChain.

    Returns:
        argparse.Namespace: Parsed command-line arguments.
    """
    parser = argparse.ArgumentParser(description="Startr.Team ChatChain")

    args_config = {
        "config": ("--config", str, "Default", "Specify the configuration file located under CompanyConfig/",),
        "org":  ("--org", str, "DefaultOrganization", "Name of the organization. The software will be generated in WareHouse/name_org_timestamp.",),
        "task": ("--task", str, "Develop a basic Website.", "Description of the project task."),
        "name": ("--name", str,"Website","Name of software, your software will be generated in WareHouse/name_org_timestamp",),
        "model":("--model", str, "", "GPT Model"),
        "path": ("--path", str, "", "Directory for your files. Startr.Team will build on your software in the Incremental mode",),
    }

    for arg, (flag, type_, default, help_text) in args_config.items():
        if arg == "model":
            choices = get_model_choices()
            parser.add_argument(
                flag,
                type=type_,
                default=default,
                choices=choices,
                help=f"{help_text} (choices: {', '.join(choices)})",
            )
        else:
            parser.add_argument(flag, type=type_, default=default, help=help_text)

    return parser.parse_args()


def get_config(company: str) -> Tuple[str, str, str]:
    """
    Get configuration JSON files for ChatChain.

    This function returns paths to configuration JSON files. It allows for
    customization of parts of the configuration, falling back to default
    configurations when custom ones are not provided.

    Args:
        company (str): Customized configuration name under CompanyConfig/

    Returns:
        Tuple[str, str, str]: Paths to three configuration JSONs:
            [config_path, config_phase_path, config_role_path]

    Note:
        If a custom configuration file doesn't exist, the default one will be used.
    """
    config_dir = os.path.join(CONFIG_DIR, company)
    config_paths = []

    for config_file in CONFIG_FILES:
        company_config_path = os.path.join(config_dir, config_file)
        default_config_path = os.path.join(DEFAULT_CONFIG_DIR, config_file)

        if os.path.exists(company_config_path):
            config_paths.append(company_config_path)
        else:
            config_paths.append(default_config_path)

    return tuple(config_paths)


def check_api_key() -> NoReturn:
    """
    Check if the OpenAI API key is set and exit if it's not.

    Raises:
        SystemExit: If the API key is not set or is empty.
    """
    if "OPENAI_API_KEY" not in os.environ or os.environ["OPENAI_API_KEY"] == "":
        print("\033[94m")
        print("Error: OPENAI_API_KEY environment variable is not set or is empty.")
        print("To fix, please set your OpenAI API key by doing one of the following:")
        print('  1. Run `export OPENAI_API_KEY="your-api-key-here"` in your terminal.')
        print("  2. Add `OPENAI_API_KEY=your-api-key-here`")
        print("     to a new line in a `.env` file in your project's root directory.")
        print("")
        print(
            "If you don't have an API key, sign up at https://platform.openai.com/signup"
        )
        print("\033[0m")
        sys.exit(1)


def main():
    """
    Main function to execute the Startr.Team ChatChain process.
    """
    args = parse_arguments()
    check_api_key()

    config_path, config_phase_path, config_role_path = get_config(args.config)

    chat_chain = ChatChain(
        config_path=config_path,
        config_phase_path=config_phase_path,
        config_role_path=config_role_path,
        task_prompt=args.task,
        project_name=args.name,
        org_name=args.org,
        model_type=ModelType[args.model],
        code_path=args.path,
    )

    logging.basicConfig(
        filename=chat_chain.log_filepath,
        level=logging.INFO,
        format="[%(asctime)s %(levelname)s] %(message)s",
        datefmt="%Y-%d-%m %H:%M:%S",
        encoding="utf-8",
    )

    chat_chain.pre_processing()
    chat_chain.recruit_team()
    chat_chain.execute_chain()
    chat_chain.post_processing()


if __name__ == "__main__":
    main()
