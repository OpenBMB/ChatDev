# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/astroid/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

from collections.abc import Callable

from astroid.manager import AstroidManager
from astroid.nodes.scoped_nodes import Module


def register_module_extender(
    manager: AstroidManager, module_name: str, get_extension_mod: Callable[[], Module]
) -> None:
    def transform(node: Module) -> None:
        extension_module = get_extension_mod()
        for name, objs in extension_module.locals.items():
            node.locals[name] = objs
            for obj in objs:
                if obj.parent is extension_module:
                    obj.parent = node

    manager.register_transform(Module, transform, lambda n: n.name == module_name)
