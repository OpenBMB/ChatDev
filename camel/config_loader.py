import yaml

class ConfigLoader:
    def __init__(self, config_path='model_config.yaml'):
        self.config_path = config_path
        self.config = self.load_config()

    def load_config(self):
        with open(self.config_path, 'r') as file:
            return yaml.safe_load(file)

    def get_model_config(self, model_name):
        return self.config['models'].get(model_name)

    def get_all_model_configs(self):
        return self.config['models']
