# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/astroid/blob/main/CONTRIBUTORS.txt

"""Astroid hooks for the UUID module."""
from astroid.manager import AstroidManager
from astroid.nodes.node_classes import Const
from astroid.nodes.scoped_nodes import ClassDef


def _patch_uuid_class(node: ClassDef) -> None:
    # The .int member is patched using __dict__
    node.locals["int"] = [Const(0, parent=node)]


AstroidManager().register_transform(
    ClassDef, _patch_uuid_class, lambda node: node.qname() == "uuid.UUID"
)
