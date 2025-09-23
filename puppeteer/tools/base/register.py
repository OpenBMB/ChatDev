from typing import Any
from tools.base.base_tool import Tool
class ToolRegistry:
    def __init__(self):
        self.tools = {}

    def register_tool(self, name, tool):
        if name in self.tools:
            raise ValueError(f"Tool with name {name} is already registered.")
        self.tools[name] = tool

    def __call__(self, *args: Any, **kwds: Any):
        def decorator(cls):
            tool_instance = cls(*args, **kwds)
            name = tool_instance.name
            self.register_tool(name, tool_instance)
            return cls
        return decorator
    
    def get_all_tools(self):
        print(self.tools.keys())
    
    def get_tool(self, name):
        if name not in self.tools:
            return None
        else:
            return self.tools[name]

    def execute_tool(self, name, *args, **kwargs):
        tool = self.get_tool(name)
        return tool.execute(*args, **kwargs)

global_tool_registry = ToolRegistry()