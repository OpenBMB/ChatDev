"""Unified function management."""
import importlib.util
import inspect
import os
from pathlib import Path
from typing import Any, Callable, Dict, Optional

_MODULE_PREFIX = "_dynamic_functions"
_FUNCTION_CALLING_ENV = "MAC_FUNCTIONS_DIR"
_EDGE_FUNCTION_ENV = "MAC_EDGE_FUNCTIONS_DIR"
_EDGE_PROCESSOR_FUNCTION_ENV = "MAC_EDGE_PROCESSOR_FUNCTIONS_DIR"
_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_FUNCTIONS_ROOT = Path("functions")
_DEFAULT_FUNCTION_CALLING_DIR = _DEFAULT_FUNCTIONS_ROOT / "function_calling"
_DEFAULT_EDGE_FUNCTION_DIR = _DEFAULT_FUNCTIONS_ROOT / "edge"
_DEFAULT_EDGE_PROCESSOR_DIR = _DEFAULT_FUNCTIONS_ROOT / "edge_processor"


def _resolve_dir(default: Path, env_var: str | None = None) -> Path:
    """Resolve a directory path with optional environment override."""
    override = os.environ.get(env_var) if env_var else None
    if override:
        return Path(override).expanduser()
    if default.is_absolute():
        return default
    return _REPO_ROOT / default


FUNCTION_CALLING_DIR = _resolve_dir(_DEFAULT_FUNCTION_CALLING_DIR, _FUNCTION_CALLING_ENV).resolve()
EDGE_FUNCTION_DIR = _resolve_dir(_DEFAULT_EDGE_FUNCTION_DIR, _EDGE_FUNCTION_ENV).resolve()
EDGE_PROCESSOR_FUNCTION_DIR = _resolve_dir(_DEFAULT_EDGE_PROCESSOR_DIR, _EDGE_PROCESSOR_FUNCTION_ENV).resolve()


class FunctionManager:
    """Unified function manager for loading and managing functions across the project."""

    def __init__(self, functions_dir: str | Path = "functions") -> None:
        self.functions_dir = Path(functions_dir)
        self.functions: Dict[str, Callable] = {}
        self._loaded = False

    def load_functions(self) -> None:
        """Load all Python functions from functions directory."""
        if self._loaded:
            return
            
        if not self.functions_dir.exists():
            raise ValueError(f"Functions directory does not exist: {self.functions_dir}")

        for file in self.functions_dir.rglob("*.py"):
            if file.name.startswith("_") or file.name == "__init__.py":
                continue
            if "__pycache__" in file.parts:
                continue
                
            module_name = self._build_module_name(file)
            try:
                # Import module dynamically
                spec = importlib.util.spec_from_file_location(module_name, file)
                if spec is None or spec.loader is None:
                    continue
                    
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                current_file = file.resolve()
                # Get all functions defined in the module
                for name, obj in inspect.getmembers(module, inspect.isfunction):
                    if name.startswith("_"):
                        continue
                    # Only register functions defined in the current module/file
                    if getattr(obj, "__module__", None) != module.__name__:
                        code = getattr(obj, "__code__", None)
                        source_path = Path(code.co_filename).resolve() if code else None
                        if source_path != current_file:
                            continue
                    self.functions[name] = obj
            except Exception as e:
                print(f"Error loading module {module_name}: {e}")
        
        self._loaded = True

    def _build_module_name(self, filepath: Path) -> str:
        """Create a unique module name for a function file."""
        relative = filepath.relative_to(self.functions_dir)
        parts = "_".join(relative.with_suffix("").parts) or "module"
        unique_suffix = f"{abs(hash(filepath.as_posix())) & 0xFFFFFFFF:X}"
        return f"{_MODULE_PREFIX}.{parts}_{unique_suffix}"

    def get_function(self, name: str) -> Optional[Callable]:
        """Get a function by name."""
        if not self._loaded:
            self.load_functions()
        return self.functions.get(name)

    def has_function(self, name: str) -> bool:
        """Check if a function exists."""
        if not self._loaded:
            self.load_functions()
        return name in self.functions

    def call_function(self, name: str, *args, **kwargs) -> Any:
        """Call a function by name with given arguments."""
        func = self.get_function(name)
        if func is None:
            raise ValueError(f"Function {name} not found")
        return func(*args, **kwargs)

    def list_functions(self) -> Dict[str, Callable]:
        """List all available functions."""
        if not self._loaded:
            self.load_functions()
        return self.functions.copy()

    def reload_functions(self) -> None:
        """Reload all functions from the functions directory."""
        self.functions.clear()
        self._loaded = False
        self.load_functions()


# Global function manager registry keyed by directory
_function_managers: Dict[Path, FunctionManager] = {}


def get_function_manager(functions_dir: str | Path) -> FunctionManager:
    """Get or create the global function manager instance for a directory."""
    directory = Path(functions_dir).resolve()

    manager = _function_managers.get(directory)
    if manager is None:
        manager = FunctionManager(directory)
        _function_managers[directory] = manager
    return manager
