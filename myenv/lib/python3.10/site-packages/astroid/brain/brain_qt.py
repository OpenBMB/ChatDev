# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/astroid/blob/main/CONTRIBUTORS.txt

"""Astroid hooks for the PyQT library."""

from astroid import nodes, parse
from astroid.brain.helpers import register_module_extender
from astroid.builder import AstroidBuilder
from astroid.manager import AstroidManager


def _looks_like_signal(
    node: nodes.FunctionDef, signal_name: str = "pyqtSignal"
) -> bool:
    """Detect a Signal node."""
    klasses = node.instance_attrs.get("__class__", [])
    # On PySide2 or PySide6 (since  Qt 5.15.2) the Signal class changed locations
    if node.qname().partition(".")[0] in {"PySide2", "PySide6"}:
        return any(cls.qname() == "Signal" for cls in klasses)  # pragma: no cover
    if klasses:
        try:
            return klasses[0].name == signal_name
        except AttributeError:  # pragma: no cover
            # return False if the cls does not have a name attribute
            pass
    return False


def transform_pyqt_signal(node: nodes.FunctionDef) -> None:
    module = parse(
        """
    _UNSET = object()

    class pyqtSignal(object):
        def connect(self, slot, type=None, no_receiver_check=False):
            pass
        def disconnect(self, slot=_UNSET):
            pass
        def emit(self, *args):
            pass
    """
    )
    signal_cls: nodes.ClassDef = module["pyqtSignal"]
    node.instance_attrs["emit"] = [signal_cls["emit"]]
    node.instance_attrs["disconnect"] = [signal_cls["disconnect"]]
    node.instance_attrs["connect"] = [signal_cls["connect"]]


def transform_pyside_signal(node: nodes.FunctionDef) -> None:
    module = parse(
        """
    class NotPySideSignal(object):
        def connect(self, receiver, type=None):
            pass
        def disconnect(self, receiver):
            pass
        def emit(self, *args):
            pass
    """
    )
    signal_cls: nodes.ClassDef = module["NotPySideSignal"]
    node.instance_attrs["connect"] = [signal_cls["connect"]]
    node.instance_attrs["disconnect"] = [signal_cls["disconnect"]]
    node.instance_attrs["emit"] = [signal_cls["emit"]]


def pyqt4_qtcore_transform():
    return AstroidBuilder(AstroidManager()).string_build(
        """

def SIGNAL(signal_name): pass

class QObject(object):
    def emit(self, signal): pass
"""
    )


register_module_extender(AstroidManager(), "PyQt4.QtCore", pyqt4_qtcore_transform)
AstroidManager().register_transform(
    nodes.FunctionDef, transform_pyqt_signal, _looks_like_signal
)
AstroidManager().register_transform(
    nodes.ClassDef,
    transform_pyside_signal,
    lambda node: node.qname() in {"PySide.QtCore.Signal", "PySide2.QtCore.Signal"},
)
