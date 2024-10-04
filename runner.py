import logging
import os
import sys

from camel.typing import ModelType
from chatdev.chat_chain import ChatChain

root = os.path.dirname(__file__)
sys.path.append(root)
from dotenv import load_dotenv

load_dotenv()


class Runner:
    def run(self, *args, **kwargs):

        def get_config(company):
            config_dir = os.path.join(root, "CompanyConfig", company)
            default_config_dir = os.path.join(root, "CompanyConfig", "Default")

            config_files = [
                "ChatChainConfig.json",
                "PhaseConfig.json",
                "RoleConfig.json",
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

        config_path, config_phase_path, config_role_path = get_config(kwargs['config'])
        chat_chain = ChatChain(
            model_name=kwargs['model_name'],
            user_token=kwargs['user_token'],
            base_url=kwargs['base_url'],
            config_path=config_path,
            config_phase_path=config_phase_path,
            config_role_path=config_role_path,
            task_prompt=kwargs['task'],
            project_name=kwargs['project'],
            org_name='SI-Follow',
            model_type=ModelType.OLLAMA,
            code_path="",
        )
        logging.basicConfig(
            filename=chat_chain.log_filepath,
            level=logging.INFO,
            format="[%(asctime)s %(levelname)s] %(message)s",
            datefmt="%Y-%d-%m %H:%M:%S",
            encoding="utf-8",
        )
        chat_chain.pre_processing()
        chat_chain.make_recruitment()
        chat_chain.execute_chain()
        chat_chain.post_processing()


if __name__ == "__main__":
    runner = Runner()
    runner.run()