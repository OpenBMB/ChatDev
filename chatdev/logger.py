import logging


class Logger:
    def __init__(self, log_file_name, logger_name, log_level=logging.INFO):
        self.__logger = logging.getLogger(logger_name)
        self.__logger.setLevel(log_level)
        
        formatter = logging.Formatter('[%(asctime)s] - [%(filename)s file line:%(lineno)d] - %(levelname)s: %(message)s')
        
        file_handler = logging.FileHandler(log_file_name)
        file_handler.setFormatter(formatter)
        self.__logger.addHandler(file_handler)
        
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.__logger.addHandler(console_handler)

    def get_logger(self):
        return self.__logger