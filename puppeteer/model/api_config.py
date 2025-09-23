import yaml

class APIConfig:
    def __init__(self):
        self._config = self._init_config()
    
    def _init_config(self):
        global_config = yaml.safe_load(open("config/global.yaml", "r"))
        key_config = {
            "openai":{
            "openai_api_key": global_config.get("api_keys").get("openai_api_key"),
            "openai_base_url": global_config.get("api_keys").get("openai_base_url", None),
            },
            "retry_times": global_config.get("max_retry_times", 10),
            "weight_path": global_config.get("model_weight_path")
        }
        return key_config

    def get(self, provider: str) -> dict:
        return self._config.get(provider, {})
    
    def global_openai_client(self):
        from openai import OpenAI
        api_key = self._config.get("openai").get("openai_api_key", None)
        base_url = self._config.get("openai").get("openai_base_url", None)
        return OpenAI(api_key=api_key, base_url=base_url)

api_config = APIConfig()