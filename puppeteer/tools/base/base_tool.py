from abc import ABC, abstractmethod
from functools import wraps
import signal
import logging

class Tool(ABC):
    def __init__(self, name, description, execute_function, timeout_duration=1, **kwargs):
        super().__init__()
        self.name = name
        self.description = description
        self.execute_function = execute_function
        self.timeout_duration = timeout_duration
        signal.alarm(0)

    def timeout_handler(self, signum, frame):
        raise TimeoutError(f"Tool execution timed out after {self.timeout_duration} seconds")

    def with_timeout(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            original_handler = signal.signal(signal.SIGALRM, self.timeout_handler)
            signal.alarm(self.timeout_duration)
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, original_handler)
        return wrapper

    @abstractmethod
    def execute(self, *args, **kwargs):
        # Wrap the execute_function with timeout handling
        safe_execute = self.with_timeout(self.execute_function)
        try:
            return safe_execute(*args, **kwargs)
        except TimeoutError as e:
            logging.error(f"Timeout in {self.name}: {str(e)}")
            return False, str(e)
        except Exception as e:
            return False, f"Tool execution failed: {str(e)}"
