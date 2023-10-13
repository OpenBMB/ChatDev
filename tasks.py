import logging
from enum import Enum
from pathlib import Path

from camel.typing import ModelType
from chatdev.chat_chain import ChatChain
from invoke import Context, task

ROOT = Path(__file__).parent

GPT_TYPES = {
    "GPT_3_5_TURBO": ModelType.GPT_3_5_TURBO,
    "GPT_4": ModelType.GPT_4,
    "GPT_4_32K": ModelType.GPT_4_32k,
}


class Config:
    class Files(Enum):
        CHAT_CHAIN = "ChatChainConfig.json"
        PHASE = "PhaseConfig.json"
        ROLE = "RoleConfig.json"

    def __init__(self, config: str) -> None:
        self.config_dir = ROOT / "CompanyConfig" / config
        self.chat_chain_path = self._get_config_path(self.Files.CHAT_CHAIN.value)
        self.phase_path = self._get_config_path(self.Files.PHASE.value)
        self.role_path = self._get_config_path(self.Files.ROLE.value)

    def _get_config_path(self, filename: str) -> None:
        config_path = self.config_dir / filename
        if not config_path.exists():
            raise FileNotFoundError(f"Config file {config_path} does not exist.")
        return config_path


@task(
    help={
        "config": "Name of config, which is used to load configuration under CompanyConfig/",
        "org": "Name of organization, your software will be generated in WareHouse/name_org_timestamp",
        "prompt": "Prompt of software",
        "name": "Name of software, your software will be generated in WareHouse/name_org_timestamp",
        "model": f"GPT Model, choose from {set(GPT_TYPES.keys())}",
    }
)
def start(
    _: Context,
    config: str = "Default",
    org: str = "DefaultOrganization",
    prompt: str = "Develop a basic Gomoku game.",
    name: str = "Gomoku",
    model: str = "GPT_3_5_TURBO",
) -> None:
    config = Config(config)
    chat_chain = ChatChain(
        config_path=config.chat_chain_path,
        config_phase_path=config.phase_path,
        config_role_path=config.role_path,
        task_prompt=prompt,
        project_name=name,
        org_name=org,
        model_type=GPT_TYPES[model],
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
