from ._version import __version__

# Temporary hotfix for flake8-docstrings
from .checker import ConventionChecker, check
from .parser import AllError
from .violations import Error, conventions
