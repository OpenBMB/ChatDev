import yaml

class ConfigLoader:
    def __init__(self, config_path='model_config.yaml'):
        self.config_path = config_path
        self.default_config = {
            'temperature': 0.7,
            'top_p': 1.0,
            'n': 1,
            'stream': False,
            'stop': None,
            'presence_penalty': 0.0,
            'frequency_penalty': 0.0,
            'max_tokens': 4096,
            'is_openai': True
        }
        self.config = self.load_config()

    def load_config(self):
        with open(self.config_path, 'r') as file:
            specific_configs = yaml.safe_load(file)
        return self.merge_configs(specific_configs)

    def merge_configs(self, specific_configs):
        models = specific_configs.get('models', {})
        for model_name, model_config in models.items():
            models[model_name] = {**self.default_config, **model_config}
        return {'models': models}

    def get_model_config(self, model_name):
        return self.config['models'].get(model_name)

    def get_all_model_configs(self):
        return self.config['models']
