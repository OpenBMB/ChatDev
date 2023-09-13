import argparse
import logging
import os
import sys

from camel.typing import ModelType

root = os.path.dirname(__file__)
sys.path.append(root)

from chatdev.chat_chain import ChatChain

class GodMode:
    def __init__(self,
                 project_name: str = None,
                 project_description: str = None):
        config_path, config_phase_path, config_role_path = get_config("Default")
        args2type = {'GPT_3_5_TURBO': ModelType.GPT_3_5_TURBO, 'GPT_4': ModelType.GPT_4, 'GPT_4_32K': ModelType.GPT_4_32k}
        self.name = project_name
        self.description = project_description
        self.chat_chain = ChatChain(config_path=config_path,
                            config_phase_path=config_phase_path,
                            config_role_path=config_role_path,
                            task_prompt=project_description,
                            project_name=project_name,
                            org_name="AutoM8",
                            model_type=ModelType.GPT_3_5_TURBO)
        logging.basicConfig(filename=self.chat_chain.log_filepath, level=logging.INFO,
                    format='[%(asctime)s %(levelname)s] %(message)s',
                    datefmt='%Y-%d-%m %H:%M:%S', encoding="utf-8")
        self.chat_chain.pre_processing()
        self.chat_chain.make_recruitment()

    def next(self):
        if self.chat_chain.executed_steps >= len(self.chat_chain.chain):
            # The end of the chat chain
            self.chat_chain.post_processing()
        else:
            # Process the next chain phase
            self.chat_chain.execute_chain()


# Helper functions

def get_config(company):
    """
    return configuration json files for ChatChain
    user can customize only parts of configuration json files, other files will be left for default
    Args:
        company: customized configuration name under CompanyConfig/

    Returns:
        path to three configuration jsons: [config_path, config_phase_path, config_role_path]
    """
    config_dir = os.path.join(root, "CompanyConfig", company)
    default_config_dir = os.path.join(root, "CompanyConfig", "Default")

    config_files = [
        "ChatChainConfig.json",
        "PhaseConfig.json",
        "RoleConfig.json"
    ]

    config_paths = []

    for config_file in config_files:
        company_config_path = os.path.join(config_dir, config_file)
        default_config_path = os.path.join(default_config_dir, config_file)

        if os.path.exists(company_config_path):
            config_paths.append(company_config_path)
        else:
            config_paths.append(default_config_path)

    return tuple(config_paths)
