# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

import sys
from typing import cast

from pylint.typing import MessageTypesFullName

if sys.version_info >= (3, 8):
    from typing import Literal, TypedDict
else:
    from typing_extensions import Literal, TypedDict


class BadNames(TypedDict):
    """TypedDict to store counts of node types with bad names."""

    argument: int
    attr: int
    klass: int
    class_attribute: int
    class_const: int
    const: int
    inlinevar: int
    function: int
    method: int
    module: int
    variable: int
    typevar: int
    typealias: int


class CodeTypeCount(TypedDict):
    """TypedDict to store counts of lines of code types."""

    code: int
    comment: int
    docstring: int
    empty: int
    total: int


class DuplicatedLines(TypedDict):
    """TypedDict to store counts of lines of duplicated code."""

    nb_duplicated_lines: int
    percent_duplicated_lines: float


class NodeCount(TypedDict):
    """TypedDict to store counts of different types of nodes."""

    function: int
    klass: int
    method: int
    module: int


class UndocumentedNodes(TypedDict):
    """TypedDict to store counts of undocumented node types."""

    function: int
    klass: int
    method: int
    module: int


class ModuleStats(TypedDict):
    """TypedDict to store counts of types of messages and statements."""

    convention: int
    error: int
    fatal: int
    info: int
    refactor: int
    statement: int
    warning: int


# pylint: disable-next=too-many-instance-attributes
class LinterStats:
    """Class used to linter stats."""

    def __init__(
        self,
        bad_names: BadNames | None = None,
        by_module: dict[str, ModuleStats] | None = None,
        by_msg: dict[str, int] | None = None,
        code_type_count: CodeTypeCount | None = None,
        dependencies: dict[str, set[str]] | None = None,
        duplicated_lines: DuplicatedLines | None = None,
        node_count: NodeCount | None = None,
        undocumented: UndocumentedNodes | None = None,
    ) -> None:
        self.bad_names = bad_names or BadNames(
            argument=0,
            attr=0,
            klass=0,
            class_attribute=0,
            class_const=0,
            const=0,
            inlinevar=0,
            function=0,
            method=0,
            module=0,
            variable=0,
            typevar=0,
            typealias=0,
        )
        self.by_module: dict[str, ModuleStats] = by_module or {}
        self.by_msg: dict[str, int] = by_msg or {}
        self.code_type_count = code_type_count or CodeTypeCount(
            code=0, comment=0, docstring=0, empty=0, total=0
        )

        self.dependencies: dict[str, set[str]] = dependencies or {}
        self.duplicated_lines = duplicated_lines or DuplicatedLines(
            nb_duplicated_lines=0, percent_duplicated_lines=0.0
        )
        self.node_count = node_count or NodeCount(
            function=0, klass=0, method=0, module=0
        )
        self.undocumented = undocumented or UndocumentedNodes(
            function=0, klass=0, method=0, module=0
        )

        self.convention = 0
        self.error = 0
        self.fatal = 0
        self.info = 0
        self.refactor = 0
        self.statement = 0
        self.warning = 0

        self.global_note = 0
        self.nb_duplicated_lines = 0
        self.percent_duplicated_lines = 0.0

    def __repr__(self) -> str:
        return str(self)

    def __str__(self) -> str:
        return f"""{self.bad_names}
        {sorted(self.by_module.items())}
        {sorted(self.by_msg.items())}
        {self.code_type_count}
        {sorted(self.dependencies.items())}
        {self.duplicated_lines}
        {self.undocumented}
        {self.convention}
        {self.error}
        {self.fatal}
        {self.info}
        {self.refactor}
        {self.statement}
        {self.warning}
        {self.global_note}
        {self.nb_duplicated_lines}
        {self.percent_duplicated_lines}"""

    def init_single_module(self, module_name: str) -> None:
        """Use through PyLinter.set_current_module so PyLinter.current_name is
        consistent.
        """
        self.by_module[module_name] = ModuleStats(
            convention=0, error=0, fatal=0, info=0, refactor=0, statement=0, warning=0
        )

    def get_bad_names(
        self,
        node_name: Literal[
            "argument",
            "attr",
            "class",
            "class_attribute",
            "class_const",
            "const",
            "inlinevar",
            "function",
            "method",
            "module",
            "variable",
            "typevar",
            "typealias",
        ],
    ) -> int:
        """Get a bad names node count."""
        if node_name == "class":
            return self.bad_names.get("klass", 0)
        return self.bad_names.get(node_name, 0)

    def increase_bad_name(self, node_name: str, increase: int) -> None:
        """Increase a bad names node count."""
        if node_name not in {
            "argument",
            "attr",
            "class",
            "class_attribute",
            "class_const",
            "const",
            "inlinevar",
            "function",
            "method",
            "module",
            "variable",
            "typevar",
            "typealias",
        }:
            raise ValueError("Node type not part of the bad_names stat")

        node_name = cast(
            Literal[
                "argument",
                "attr",
                "class",
                "class_attribute",
                "class_const",
                "const",
                "inlinevar",
                "function",
                "method",
                "module",
                "variable",
                "typevar",
                "typealias",
            ],
            node_name,
        )
        if node_name == "class":
            self.bad_names["klass"] += increase
        else:
            self.bad_names[node_name] += increase

    def reset_bad_names(self) -> None:
        """Resets the bad_names attribute."""
        self.bad_names = BadNames(
            argument=0,
            attr=0,
            klass=0,
            class_attribute=0,
            class_const=0,
            const=0,
            inlinevar=0,
            function=0,
            method=0,
            module=0,
            variable=0,
            typevar=0,
            typealias=0,
        )

    def get_code_count(
        self, type_name: Literal["code", "comment", "docstring", "empty", "total"]
    ) -> int:
        """Get a code type count."""
        return self.code_type_count.get(type_name, 0)

    def reset_code_count(self) -> None:
        """Resets the code_type_count attribute."""
        self.code_type_count = CodeTypeCount(
            code=0, comment=0, docstring=0, empty=0, total=0
        )

    def reset_duplicated_lines(self) -> None:
        """Resets the duplicated_lines attribute."""
        self.duplicated_lines = DuplicatedLines(
            nb_duplicated_lines=0, percent_duplicated_lines=0.0
        )

    def get_node_count(
        self, node_name: Literal["function", "class", "method", "module"]
    ) -> int:
        """Get a node count while handling some extra conditions."""
        if node_name == "class":
            return self.node_count.get("klass", 0)
        return self.node_count.get(node_name, 0)

    def reset_node_count(self) -> None:
        """Resets the node count attribute."""
        self.node_count = NodeCount(function=0, klass=0, method=0, module=0)

    def get_undocumented(
        self, node_name: Literal["function", "class", "method", "module"]
    ) -> float:
        """Get a undocumented node count."""
        if node_name == "class":
            return self.undocumented["klass"]
        return self.undocumented[node_name]

    def reset_undocumented(self) -> None:
        """Resets the undocumented attribute."""
        self.undocumented = UndocumentedNodes(function=0, klass=0, method=0, module=0)

    def get_global_message_count(self, type_name: str) -> int:
        """Get a global message count."""
        return getattr(self, type_name, 0)

    def get_module_message_count(self, modname: str, type_name: str) -> int:
        """Get a module message count."""
        return getattr(self.by_module[modname], type_name, 0)

    def increase_single_message_count(self, type_name: str, increase: int) -> None:
        """Increase the message type count of an individual message type."""
        setattr(self, type_name, getattr(self, type_name) + increase)

    def increase_single_module_message_count(
        self, modname: str, type_name: MessageTypesFullName, increase: int
    ) -> None:
        """Increase the message type count of an individual message type of a
        module.
        """
        self.by_module[modname][type_name] += increase

    def reset_message_count(self) -> None:
        """Resets the message type count of the stats object."""
        self.convention = 0
        self.error = 0
        self.fatal = 0
        self.info = 0
        self.refactor = 0
        self.warning = 0


def merge_stats(stats: list[LinterStats]) -> LinterStats:
    """Used to merge multiple stats objects into a new one when pylint is run in
    parallel mode.
    """
    merged = LinterStats()
    for stat in stats:
        merged.bad_names["argument"] += stat.bad_names["argument"]
        merged.bad_names["attr"] += stat.bad_names["attr"]
        merged.bad_names["klass"] += stat.bad_names["klass"]
        merged.bad_names["class_attribute"] += stat.bad_names["class_attribute"]
        merged.bad_names["class_const"] += stat.bad_names["class_const"]
        merged.bad_names["const"] += stat.bad_names["const"]
        merged.bad_names["inlinevar"] += stat.bad_names["inlinevar"]
        merged.bad_names["function"] += stat.bad_names["function"]
        merged.bad_names["method"] += stat.bad_names["method"]
        merged.bad_names["module"] += stat.bad_names["module"]
        merged.bad_names["variable"] += stat.bad_names["variable"]
        merged.bad_names["typevar"] += stat.bad_names["typevar"]
        merged.bad_names["typealias"] += stat.bad_names["typealias"]

        for mod_key, mod_value in stat.by_module.items():
            merged.by_module[mod_key] = mod_value

        for msg_key, msg_value in stat.by_msg.items():
            try:
                merged.by_msg[msg_key] += msg_value
            except KeyError:
                merged.by_msg[msg_key] = msg_value

        merged.code_type_count["code"] += stat.code_type_count["code"]
        merged.code_type_count["comment"] += stat.code_type_count["comment"]
        merged.code_type_count["docstring"] += stat.code_type_count["docstring"]
        merged.code_type_count["empty"] += stat.code_type_count["empty"]
        merged.code_type_count["total"] += stat.code_type_count["total"]

        for dep_key, dep_value in stat.dependencies.items():
            try:
                merged.dependencies[dep_key].update(dep_value)
            except KeyError:
                merged.dependencies[dep_key] = dep_value

        merged.duplicated_lines["nb_duplicated_lines"] += stat.duplicated_lines[
            "nb_duplicated_lines"
        ]
        merged.duplicated_lines["percent_duplicated_lines"] += stat.duplicated_lines[
            "percent_duplicated_lines"
        ]

        merged.node_count["function"] += stat.node_count["function"]
        merged.node_count["klass"] += stat.node_count["klass"]
        merged.node_count["method"] += stat.node_count["method"]
        merged.node_count["module"] += stat.node_count["module"]

        merged.undocumented["function"] += stat.undocumented["function"]
        merged.undocumented["klass"] += stat.undocumented["klass"]
        merged.undocumented["method"] += stat.undocumented["method"]
        merged.undocumented["module"] += stat.undocumented["module"]

        merged.convention += stat.convention
        merged.error += stat.error
        merged.fatal += stat.fatal
        merged.info += stat.info
        merged.refactor += stat.refactor
        merged.statement += stat.statement
        merged.warning += stat.warning

        merged.global_note += stat.global_note
    return merged
