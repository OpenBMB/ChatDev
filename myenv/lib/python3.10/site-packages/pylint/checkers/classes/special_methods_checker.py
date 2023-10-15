# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

"""Special methods checker and helper function's module."""

from __future__ import annotations

from collections.abc import Callable

import astroid
from astroid import bases, nodes, util
from astroid.context import InferenceContext
from astroid.typing import InferenceResult

from pylint.checkers import BaseChecker
from pylint.checkers.utils import (
    PYMETHODS,
    SPECIAL_METHODS_PARAMS,
    decorated_with,
    is_function_body_ellipsis,
    only_required_for_messages,
    safe_infer,
)
from pylint.lint.pylinter import PyLinter

NEXT_METHOD = "__next__"


def _safe_infer_call_result(
    node: nodes.FunctionDef,
    caller: nodes.FunctionDef,
    context: InferenceContext | None = None,
) -> InferenceResult | None:
    """Safely infer the return value of a function.

    Returns None if inference failed or if there is some ambiguity (more than
    one node has been inferred). Otherwise, returns inferred value.
    """
    try:
        inferit = node.infer_call_result(caller, context=context)
        value = next(inferit)
    except astroid.InferenceError:
        return None  # inference failed
    except StopIteration:
        return None  # no values inferred
    try:
        next(inferit)
        return None  # there is ambiguity on the inferred node
    except astroid.InferenceError:
        return None  # there is some kind of ambiguity
    except StopIteration:
        return value


class SpecialMethodsChecker(BaseChecker):
    """Checker which verifies that special methods
    are implemented correctly.
    """

    name = "classes"
    msgs = {
        "E0301": (
            "__iter__ returns non-iterator",
            "non-iterator-returned",
            "Used when an __iter__ method returns something which is not an "
            f"iterable (i.e. has no `{NEXT_METHOD}` method)",
            {
                "old_names": [
                    ("W0234", "old-non-iterator-returned-1"),
                    ("E0234", "old-non-iterator-returned-2"),
                ]
            },
        ),
        "E0302": (
            "The special method %r expects %s param(s), %d %s given",
            "unexpected-special-method-signature",
            "Emitted when a special method was defined with an "
            "invalid number of parameters. If it has too few or "
            "too many, it might not work at all.",
            {"old_names": [("E0235", "bad-context-manager")]},
        ),
        "E0303": (
            "__len__ does not return non-negative integer",
            "invalid-length-returned",
            "Used when a __len__ method returns something which is not a "
            "non-negative integer",
        ),
        "E0304": (
            "__bool__ does not return bool",
            "invalid-bool-returned",
            "Used when a __bool__ method returns something which is not a bool",
        ),
        "E0305": (
            "__index__ does not return int",
            "invalid-index-returned",
            "Used when an __index__ method returns something which is not "
            "an integer",
        ),
        "E0306": (
            "__repr__ does not return str",
            "invalid-repr-returned",
            "Used when a __repr__ method returns something which is not a string",
        ),
        "E0307": (
            "__str__ does not return str",
            "invalid-str-returned",
            "Used when a __str__ method returns something which is not a string",
        ),
        "E0308": (
            "__bytes__ does not return bytes",
            "invalid-bytes-returned",
            "Used when a __bytes__ method returns something which is not bytes",
        ),
        "E0309": (
            "__hash__ does not return int",
            "invalid-hash-returned",
            "Used when a __hash__ method returns something which is not an integer",
        ),
        "E0310": (
            "__length_hint__ does not return non-negative integer",
            "invalid-length-hint-returned",
            "Used when a __length_hint__ method returns something which is not a "
            "non-negative integer",
        ),
        "E0311": (
            "__format__ does not return str",
            "invalid-format-returned",
            "Used when a __format__ method returns something which is not a string",
        ),
        "E0312": (
            "__getnewargs__ does not return a tuple",
            "invalid-getnewargs-returned",
            "Used when a __getnewargs__ method returns something which is not "
            "a tuple",
        ),
        "E0313": (
            "__getnewargs_ex__ does not return a tuple containing (tuple, dict)",
            "invalid-getnewargs-ex-returned",
            "Used when a __getnewargs_ex__ method returns something which is not "
            "of the form tuple(tuple, dict)",
        ),
    }

    def __init__(self, linter: PyLinter) -> None:
        super().__init__(linter)
        self._protocol_map: dict[
            str, Callable[[nodes.FunctionDef, InferenceResult], None]
        ] = {
            "__iter__": self._check_iter,
            "__len__": self._check_len,
            "__bool__": self._check_bool,
            "__index__": self._check_index,
            "__repr__": self._check_repr,
            "__str__": self._check_str,
            "__bytes__": self._check_bytes,
            "__hash__": self._check_hash,
            "__length_hint__": self._check_length_hint,
            "__format__": self._check_format,
            "__getnewargs__": self._check_getnewargs,
            "__getnewargs_ex__": self._check_getnewargs_ex,
        }

    @only_required_for_messages(
        "unexpected-special-method-signature",
        "non-iterator-returned",
        "invalid-length-returned",
        "invalid-bool-returned",
        "invalid-index-returned",
        "invalid-repr-returned",
        "invalid-str-returned",
        "invalid-bytes-returned",
        "invalid-hash-returned",
        "invalid-length-hint-returned",
        "invalid-format-returned",
        "invalid-getnewargs-returned",
        "invalid-getnewargs-ex-returned",
    )
    def visit_functiondef(self, node: nodes.FunctionDef) -> None:
        if not node.is_method():
            return

        inferred = _safe_infer_call_result(node, node)
        # Only want to check types that we are able to infer
        if (
            inferred
            and node.name in self._protocol_map
            and not is_function_body_ellipsis(node)
        ):
            self._protocol_map[node.name](node, inferred)

        if node.name in PYMETHODS:
            self._check_unexpected_method_signature(node)

    visit_asyncfunctiondef = visit_functiondef

    def _check_unexpected_method_signature(self, node: nodes.FunctionDef) -> None:
        expected_params = SPECIAL_METHODS_PARAMS[node.name]

        if expected_params is None:
            # This can support a variable number of parameters.
            return
        if not node.args.args and not node.args.vararg:
            # Method has no parameter, will be caught
            # by no-method-argument.
            return

        if decorated_with(node, ["builtins.staticmethod"]):
            # We expect to not take in consideration self.
            all_args = node.args.args
        else:
            all_args = node.args.args[1:]
        mandatory = len(all_args) - len(node.args.defaults)
        optional = len(node.args.defaults)
        current_params = mandatory + optional

        emit = False  # If we don't know we choose a false negative
        if isinstance(expected_params, tuple):
            # The expected number of parameters can be any value from this
            # tuple, although the user should implement the method
            # to take all of them in consideration.
            emit = mandatory not in expected_params
            # mypy thinks that expected_params has type tuple[int, int] | int | None
            # But at this point it must be 'tuple[int, int]' because of the type check
            expected_params = f"between {expected_params[0]} or {expected_params[1]}"  # type: ignore[assignment]
        else:
            # If the number of mandatory parameters doesn't
            # suffice, the expected parameters for this
            # function will be deduced from the optional
            # parameters.
            rest = expected_params - mandatory
            if rest == 0:
                emit = False
            elif rest < 0:
                emit = True
            elif rest > 0:
                emit = not ((optional - rest) >= 0 or node.args.vararg)

        if emit:
            verb = "was" if current_params <= 1 else "were"
            self.add_message(
                "unexpected-special-method-signature",
                args=(node.name, expected_params, current_params, verb),
                node=node,
            )

    @staticmethod
    def _is_wrapped_type(node: InferenceResult, type_: str) -> bool:
        return (
            isinstance(node, bases.Instance)
            and node.name == type_
            and not isinstance(node, nodes.Const)
        )

    @staticmethod
    def _is_int(node: InferenceResult) -> bool:
        if SpecialMethodsChecker._is_wrapped_type(node, "int"):
            return True

        return isinstance(node, nodes.Const) and isinstance(node.value, int)

    @staticmethod
    def _is_str(node: InferenceResult) -> bool:
        if SpecialMethodsChecker._is_wrapped_type(node, "str"):
            return True

        return isinstance(node, nodes.Const) and isinstance(node.value, str)

    @staticmethod
    def _is_bool(node: InferenceResult) -> bool:
        if SpecialMethodsChecker._is_wrapped_type(node, "bool"):
            return True

        return isinstance(node, nodes.Const) and isinstance(node.value, bool)

    @staticmethod
    def _is_bytes(node: InferenceResult) -> bool:
        if SpecialMethodsChecker._is_wrapped_type(node, "bytes"):
            return True

        return isinstance(node, nodes.Const) and isinstance(node.value, bytes)

    @staticmethod
    def _is_tuple(node: InferenceResult) -> bool:
        if SpecialMethodsChecker._is_wrapped_type(node, "tuple"):
            return True

        return isinstance(node, nodes.Const) and isinstance(node.value, tuple)

    @staticmethod
    def _is_dict(node: InferenceResult) -> bool:
        if SpecialMethodsChecker._is_wrapped_type(node, "dict"):
            return True

        return isinstance(node, nodes.Const) and isinstance(node.value, dict)

    @staticmethod
    def _is_iterator(node: InferenceResult) -> bool:
        if isinstance(node, bases.Generator):
            # Generators can be iterated.
            return True
        if isinstance(node, nodes.ComprehensionScope):
            # Comprehensions can be iterated.
            return True

        if isinstance(node, bases.Instance):
            try:
                node.local_attr(NEXT_METHOD)
                return True
            except astroid.NotFoundError:
                pass
        elif isinstance(node, nodes.ClassDef):
            metaclass = node.metaclass()
            if metaclass and isinstance(metaclass, nodes.ClassDef):
                try:
                    metaclass.local_attr(NEXT_METHOD)
                    return True
                except astroid.NotFoundError:
                    pass
        return False

    def _check_iter(self, node: nodes.FunctionDef, inferred: InferenceResult) -> None:
        if not self._is_iterator(inferred):
            self.add_message("non-iterator-returned", node=node)

    def _check_len(self, node: nodes.FunctionDef, inferred: InferenceResult) -> None:
        if not self._is_int(inferred):
            self.add_message("invalid-length-returned", node=node)
        elif isinstance(inferred, nodes.Const) and inferred.value < 0:
            self.add_message("invalid-length-returned", node=node)

    def _check_bool(self, node: nodes.FunctionDef, inferred: InferenceResult) -> None:
        if not self._is_bool(inferred):
            self.add_message("invalid-bool-returned", node=node)

    def _check_index(self, node: nodes.FunctionDef, inferred: InferenceResult) -> None:
        if not self._is_int(inferred):
            self.add_message("invalid-index-returned", node=node)

    def _check_repr(self, node: nodes.FunctionDef, inferred: InferenceResult) -> None:
        if not self._is_str(inferred):
            self.add_message("invalid-repr-returned", node=node)

    def _check_str(self, node: nodes.FunctionDef, inferred: InferenceResult) -> None:
        if not self._is_str(inferred):
            self.add_message("invalid-str-returned", node=node)

    def _check_bytes(self, node: nodes.FunctionDef, inferred: InferenceResult) -> None:
        if not self._is_bytes(inferred):
            self.add_message("invalid-bytes-returned", node=node)

    def _check_hash(self, node: nodes.FunctionDef, inferred: InferenceResult) -> None:
        if not self._is_int(inferred):
            self.add_message("invalid-hash-returned", node=node)

    def _check_length_hint(
        self, node: nodes.FunctionDef, inferred: InferenceResult
    ) -> None:
        if not self._is_int(inferred):
            self.add_message("invalid-length-hint-returned", node=node)
        elif isinstance(inferred, nodes.Const) and inferred.value < 0:
            self.add_message("invalid-length-hint-returned", node=node)

    def _check_format(self, node: nodes.FunctionDef, inferred: InferenceResult) -> None:
        if not self._is_str(inferred):
            self.add_message("invalid-format-returned", node=node)

    def _check_getnewargs(
        self, node: nodes.FunctionDef, inferred: InferenceResult
    ) -> None:
        if not self._is_tuple(inferred):
            self.add_message("invalid-getnewargs-returned", node=node)

    def _check_getnewargs_ex(
        self, node: nodes.FunctionDef, inferred: InferenceResult
    ) -> None:
        if not self._is_tuple(inferred):
            self.add_message("invalid-getnewargs-ex-returned", node=node)
            return

        if not isinstance(inferred, nodes.Tuple):
            # If it's not an astroid.Tuple we can't analyze it further
            return

        found_error = False

        if len(inferred.elts) != 2:
            found_error = True
        else:
            for arg, check in (
                (inferred.elts[0], self._is_tuple),
                (inferred.elts[1], self._is_dict),
            ):
                if isinstance(arg, nodes.Call):
                    arg = safe_infer(arg)

                if arg and not isinstance(arg, util.UninferableBase):
                    if not check(arg):
                        found_error = True
                        break

        if found_error:
            self.add_message("invalid-getnewargs-ex-returned", node=node)
