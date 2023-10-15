# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

import contextlib
import warnings
from collections.abc import Generator, Iterator
from typing import Any

from astroid import nodes

from pylint.constants import IS_PYPY, PY38_PLUS, PY39_PLUS
from pylint.testutils.global_test_linter import linter
from pylint.testutils.output_line import MessageTest
from pylint.testutils.unittest_linter import UnittestLinter
from pylint.utils import ASTWalker


class CheckerTestCase:
    """A base testcase class for unit testing individual checker classes."""

    # TODO: Figure out way to type this as type[BaseChecker] while also
    # setting self.checker correctly.
    CHECKER_CLASS: Any
    CONFIG: dict[str, Any] = {}

    def setup_method(self) -> None:
        self.linter = UnittestLinter()
        self.checker = self.CHECKER_CLASS(self.linter)
        for key, value in self.CONFIG.items():
            setattr(self.checker.linter.config, key, value)
        self.checker.open()

    @contextlib.contextmanager
    def assertNoMessages(self) -> Iterator[None]:
        """Assert that no messages are added by the given method."""
        with self.assertAddsMessages():
            yield

    @contextlib.contextmanager
    def assertAddsMessages(
        self, *messages: MessageTest, ignore_position: bool = False
    ) -> Generator[None, None, None]:
        """Assert that exactly the given method adds the given messages.

        The list of messages must exactly match *all* the messages added by the
        method. Additionally, we check to see whether the args in each message can
        actually be substituted into the message string.

        Using the keyword argument `ignore_position`, all checks for position
        arguments (line, col_offset, ...) will be skipped. This can be used to
        just test messages for the correct node.
        """
        yield
        got = self.linter.release_messages()
        no_msg = "No message."
        expected = "\n".join(repr(m) for m in messages) or no_msg
        got_str = "\n".join(repr(m) for m in got) or no_msg
        msg = (
            "Expected messages did not match actual.\n"
            f"\nExpected:\n{expected}\n\nGot:\n{got_str}\n"
        )

        assert len(messages) == len(got), msg

        for expected_msg, gotten_msg in zip(messages, got):
            assert expected_msg.msg_id == gotten_msg.msg_id, msg
            assert expected_msg.node == gotten_msg.node, msg
            assert expected_msg.args == gotten_msg.args, msg
            assert expected_msg.confidence == gotten_msg.confidence, msg

            if ignore_position:
                # Do not check for line, col_offset etc...
                continue

            assert expected_msg.line == gotten_msg.line, msg
            assert expected_msg.col_offset == gotten_msg.col_offset, msg
            if PY38_PLUS and not IS_PYPY or PY39_PLUS:
                # TODO: 3.0: Remove deprecated missing arguments and remove the warning
                if not expected_msg.end_line == gotten_msg.end_line:
                    warnings.warn(  # pragma: no cover
                        f"The end_line attribute of {gotten_msg} does not match "
                        f"the expected value in {expected_msg}. In pylint 3.0 correct end_line "
                        "attributes will be required for MessageTest.",
                        DeprecationWarning,
                        stacklevel=2,
                    )
                if not expected_msg.end_col_offset == gotten_msg.end_col_offset:
                    warnings.warn(  # pragma: no cover
                        f"The end_col_offset attribute of {gotten_msg} does not match "
                        f"the expected value in {expected_msg}. In pylint 3.0 correct end_col_offset "
                        "attributes will be required for MessageTest.",
                        DeprecationWarning,
                        stacklevel=2,
                    )

    def walk(self, node: nodes.NodeNG) -> None:
        """Recursive walk on the given node."""
        walker = ASTWalker(linter)
        walker.add_checker(self.checker)
        walker.walk(node)
