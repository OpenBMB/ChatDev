import logging
import yaml
import os
import datetime

class LogManager:
    _instance = None

    def __new__(cls, config_path=None, task_name=None):
        if cls._instance is not None:
            cls._instance._cleanup()
        cls._instance = super(LogManager, cls).__new__(cls)
        cls._instance._initialize(config_path, task_name)
        return cls._instance

    def _initialize(self, config_path, task_name):
        self.loggers = {}
        self.global_config = yaml.safe_load(open(config_path, "r"))
        self.task_name = task_name
        self.folder_path = self._create_log_folder()
        self._setup_main_logger()
        self._setup_model_logger()
        self._setup_training_logger()

    def _create_log_folder(self):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        folder_path = os.path.join(self.global_config.get('logging').get('logpath'), self.task_name, timestamp)
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
        return folder_path

    def _setup_main_logger(self):
        main_logger = logging.getLogger('global')
        main_logger.setLevel(self.global_config.get('logging').get('level'))
        fh = logging.FileHandler(os.path.join(self.folder_path, "meta.log"), encoding="utf-8")
        fh.setLevel(self.global_config.get('logging').get('level'))

        formatter = logging.Formatter('[%(asctime)s %(levelname)s]\n%(message)s', datefmt='%Y-%d-%m %H:%M:%S')
        fh.setFormatter(formatter)

        main_logger.addHandler(fh)
    
    def _setup_model_logger(self):
        model_logger = logging.getLogger('model')
        model_logger.setLevel(self.global_config.get('logging').get('level'))
        fh = logging.FileHandler(os.path.join(self.folder_path, "model_query.log"), encoding="utf-8")
        fh.setLevel(self.global_config.get('logging').get('level'))

        formatter = logging.Formatter('[%(asctime)s %(levelname)s]\n%(message)s', datefmt='%Y-%d-%m %H:%M:%S')
        fh.setFormatter(formatter)

        model_logger.addHandler(fh)

    def _setup_training_logger(self):
        training_logger = logging.getLogger('train')
        training_logger.setLevel(self.global_config.get('logging').get('level'))
        fh = logging.FileHandler(os.path.join(self.folder_path,"train.log"), encoding="utf-8")
        fh.setLevel(self.global_config.get('logging').get('level')) 

        formatter = logging.Formatter('[%(asctime)s %(levelname)s]\n%(message)s', datefmt='%Y-%d-%m %H:%M:%S')
        fh.setFormatter(formatter)

        training_logger.addHandler(fh)

    def create_logger(self, name, log_file, level=logging.INFO):
        logger = logging.getLogger(name)
        logger.setLevel(level)

        if not logger.handlers:
            handler = logging.FileHandler(log_file, encoding="utf-8")
            handler.setFormatter(logging.Formatter('[%(asctime)s %(levelname)s]\n%(message)s', datefmt='%Y-%d-%m %H:%M:%S'))
            logger.addHandler(handler)
        logger.propagate = False
        self.loggers[name] = logger

    def get_logger(self, index):
        return self.loggers.get(index, logging.getLogger())
    def _cleanup(self):
        for logger in self.loggers.values():
            handlers = logger.handlers[:]
            for handler in handlers:
                handler.close()
                logger.removeHandler(handler)
        
        main_logger = logging.getLogger('global')
        handlers = main_logger.handlers[:]
        for handler in handlers:
            try:
                handler.close()
                main_logger.removeHandler(handler)
            except Exception as e:
                print(f"Error closing handler: {e}")
        
        model_logger = logging.getLogger('model')
        handlers = model_logger.handlers[:]
        for handler in handlers:
            try:
                handler.close()
                model_logger.removeHandler(handler)
            except Exception as e:
                print(f"Error closing handler: {e}")