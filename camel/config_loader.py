import yaml
from enum import Enum
import logging


class ConfigLoader:
    def __init__(self, config_path="model_config.yaml"):
        self.config_path = config_path
        self.config = self.load_config()
        self.ModelType = self.create_model_type_enum()

    def load_config(self):
        with open(self.config_path, "r") as file:
            return yaml.safe_load(file)

    def get_model_config(self, model_name):
        model_config = self.config["models"].get(model_name)
        if model_config is None:
            raise ValueError(f"No configuration found for model: {model_name}")
        return model_config

    def get_all_model_configs(self):
        return self.config["models"]

    def get_default_config(self):
        return self.config["default_config"]

    def create_model_type_enum(self):
        return Enum(
            "ModelType",
            {key: value["name"] for key, value in self.config["models"].items()},
        )


# Create a single instance of ConfigLoader
config_loader = ConfigLoader()

# Use the dynamically created ModelType enum
ModelType = config_loader.ModelType
