# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/astroid/blob/main/CONTRIBUTORS.txt

# pylint: disable=unused-import

import warnings

from astroid.nodes.scoped_nodes import (
    AsyncFunctionDef,
    ClassDef,
    ComprehensionScope,
    DictComp,
    FunctionDef,
    GeneratorExp,
    Lambda,
    ListComp,
    LocalsDictNodeNG,
    Module,
    SetComp,
    _is_metaclass,
    builtin_lookup,
    function_to_method,
    get_wrapping_class,
)

# We cannot create a __all__ here because it would create a circular import
# Please remove astroid/scoped_nodes.py|astroid/node_classes.py in autoflake
# exclude when removing this file.
warnings.warn(
    "The 'astroid.scoped_nodes' module is deprecated and will be replaced by "
    "'astroid.nodes' in astroid 3.0.0",
    DeprecationWarning,
    stacklevel=2,
)
