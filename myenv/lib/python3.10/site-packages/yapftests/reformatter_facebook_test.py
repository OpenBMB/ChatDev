# Copyright 2016 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Facebook tests for yapf.reformatter."""

import textwrap
import unittest

from yapf.yapflib import reformatter
from yapf.yapflib import style

from yapftests import yapf_test_helper


class TestsForFacebookStyle(yapf_test_helper.YAPFTest):

  @classmethod
  def setUpClass(cls):
    style.SetGlobalStyle(style.CreateFacebookStyle())

  def testNoNeedForLineBreaks(self):
    unformatted_code = textwrap.dedent("""\
        def overly_long_function_name(
          just_one_arg, **kwargs):
          pass
        """)
    expected_formatted_code = textwrap.dedent("""\
        def overly_long_function_name(just_one_arg, **kwargs):
            pass
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testDedentClosingBracket(self):
    unformatted_code = textwrap.dedent("""\
        def overly_long_function_name(
          first_argument_on_the_same_line,
          second_argument_makes_the_line_too_long):
          pass
        """)
    expected_formatted_code = textwrap.dedent("""\
        def overly_long_function_name(
            first_argument_on_the_same_line, second_argument_makes_the_line_too_long
        ):
            pass
        """)  # noqa
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testBreakAfterOpeningBracketIfContentsTooBig(self):
    unformatted_code = textwrap.dedent("""\
        def overly_long_function_name(a, b, c, d, e, f, g, h, i, j, k, l, m,
          n, o, p, q, r, s, t, u, v, w, x, y, z):
          pass
        """)
    expected_formatted_code = textwrap.dedent("""\
        def overly_long_function_name(
            a, b, c, d, e, f, g, h, i, j, k, l, m, n, o, p, q, r, s, t, u, \
v, w, x, y, z
        ):
            pass
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testDedentClosingBracketWithComments(self):
    unformatted_code = textwrap.dedent("""\
        def overly_long_function_name(
          # comment about the first argument
          first_argument_with_a_very_long_name_or_so,
          # comment about the second argument
          second_argument_makes_the_line_too_long):
          pass
        """)
    expected_formatted_code = textwrap.dedent("""\
        def overly_long_function_name(
            # comment about the first argument
            first_argument_with_a_very_long_name_or_so,
            # comment about the second argument
            second_argument_makes_the_line_too_long
        ):
            pass
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testDedentImportAsNames(self):
    code = textwrap.dedent("""\
        from module import (
            internal_function as function,
            SOME_CONSTANT_NUMBER1,
            SOME_CONSTANT_NUMBER2,
            SOME_CONSTANT_NUMBER3,
        )
        """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testDedentTestListGexp(self):
    unformatted_code = textwrap.dedent("""\
        try:
            pass
        except (
            IOError, OSError, LookupError, RuntimeError, OverflowError
        ) as exception:
            pass

        try:
            pass
        except (
            IOError, OSError, LookupError, RuntimeError, OverflowError,
        ) as exception:
            pass
        """)
    expected_formatted_code = textwrap.dedent("""\
        try:
            pass
        except (
            IOError, OSError, LookupError, RuntimeError, OverflowError
        ) as exception:
            pass

        try:
            pass
        except (
            IOError,
            OSError,
            LookupError,
            RuntimeError,
            OverflowError,
        ) as exception:
            pass
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testBrokenIdempotency(self):
    # TODO(ambv): The following behaviour should be fixed.
    pass0_code = textwrap.dedent("""\
        try:
            pass
        except (IOError, OSError, LookupError, RuntimeError, OverflowError) as exception:
            pass
        """)  # noqa
    pass1_code = textwrap.dedent("""\
        try:
            pass
        except (
            IOError, OSError, LookupError, RuntimeError, OverflowError
        ) as exception:
            pass
        """)
    llines = yapf_test_helper.ParseAndUnwrap(pass0_code)
    self.assertCodeEqual(pass1_code, reformatter.Reformat(llines))

    pass2_code = textwrap.dedent("""\
        try:
            pass
        except (
            IOError, OSError, LookupError, RuntimeError, OverflowError
        ) as exception:
            pass
        """)
    llines = yapf_test_helper.ParseAndUnwrap(pass1_code)
    self.assertCodeEqual(pass2_code, reformatter.Reformat(llines))

  def testIfExprHangingIndent(self):
    unformatted_code = textwrap.dedent("""\
        if True:
            if True:
                if True:
                    if not self.frobbies and (
                       self.foobars.counters['db.cheeses'] != 1 or
                       self.foobars.counters['db.marshmellow_skins'] != 1):
                        pass
        """)
    expected_formatted_code = textwrap.dedent("""\
        if True:
            if True:
                if True:
                    if not self.frobbies and (
                        self.foobars.counters['db.cheeses'] != 1 or
                        self.foobars.counters['db.marshmellow_skins'] != 1
                    ):
                        pass
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testSimpleDedenting(self):
    unformatted_code = textwrap.dedent("""\
        if True:
            self.assertEqual(result.reason_not_added, "current preflight is still running")
        """)  # noqa
    expected_formatted_code = textwrap.dedent("""\
        if True:
            self.assertEqual(
                result.reason_not_added, "current preflight is still running"
            )
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testDedentingWithSubscripts(self):
    unformatted_code = textwrap.dedent("""\
        class Foo:
            class Bar:
                @classmethod
                def baz(cls, clues_list, effect, constraints, constraint_manager):
                    if clues_lists:
                       return cls.single_constraint_not(clues_lists, effect, constraints[0], constraint_manager)

        """)  # noqa
    expected_formatted_code = textwrap.dedent("""\
        class Foo:
            class Bar:
                @classmethod
                def baz(cls, clues_list, effect, constraints, constraint_manager):
                    if clues_lists:
                        return cls.single_constraint_not(
                            clues_lists, effect, constraints[0], constraint_manager
                        )
        """)  # noqa
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testDedentingCallsWithInnerLists(self):
    code = textwrap.dedent("""\
        class _():
            def _():
                cls.effect_clues = {
                    'effect': Clue((cls.effect_time, 'apache_host'), effect_line, 40)
                }
        """)  # noqa
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testDedentingListComprehension(self):
    unformatted_code = textwrap.dedent("""\
        class Foo():
            def _pack_results_for_constraint_or():
                self.param_groups = dict(
                    (
                        key + 1, ParamGroup(groups[key], default_converter)
                    ) for key in six.moves.range(len(groups))
                )

                for combination in cls._clues_combinations(clues_lists):
                    if all(
                        cls._verify_constraint(combination, effect, constraint)
                        for constraint in constraints
                    ):
                        pass

                guessed_dict = dict(
                    (
                        key, guessed_pattern_matches[key]
                    ) for key in six.moves.range(len(guessed_pattern_matches))
                )

                content = "".join(
                    itertools.chain(
                        (first_line_fragment, ), lines_between, (last_line_fragment, )
                    )
                )

                rule = Rule(
                    [self.cause1, self.cause2, self.cause1, self.cause2], self.effect, constraints1,
                    Rule.LINKAGE_AND
                )

                assert sorted(log_type.files_to_parse) == [
                    ('localhost', os.path.join(path, 'node_1.log'), super_parser),
                    ('localhost', os.path.join(path, 'node_2.log'), super_parser)
                ]
        """)  # noqa
    expected_formatted_code = textwrap.dedent("""\
        class Foo():
            def _pack_results_for_constraint_or():
                self.param_groups = dict(
                    (key + 1, ParamGroup(groups[key], default_converter))
                    for key in six.moves.range(len(groups))
                )

                for combination in cls._clues_combinations(clues_lists):
                    if all(
                        cls._verify_constraint(combination, effect, constraint)
                        for constraint in constraints
                    ):
                        pass

                guessed_dict = dict(
                    (key, guessed_pattern_matches[key])
                    for key in six.moves.range(len(guessed_pattern_matches))
                )

                content = "".join(
                    itertools.chain(
                        (first_line_fragment, ), lines_between, (last_line_fragment, )
                    )
                )

                rule = Rule(
                    [self.cause1, self.cause2, self.cause1, self.cause2], self.effect,
                    constraints1, Rule.LINKAGE_AND
                )

                assert sorted(log_type.files_to_parse) == [
                    ('localhost', os.path.join(path, 'node_1.log'), super_parser),
                    ('localhost', os.path.join(path, 'node_2.log'), super_parser)
                ]
        """)  # noqa
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testMustSplitDedenting(self):
    code = textwrap.dedent("""\
        class _():
            def _():
                effect_line = FrontInput(
                    effect_line_offset, line_content,
                    LineSource('localhost', xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx)
                )
        """)  # noqa
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testDedentIfConditional(self):
    code = textwrap.dedent("""\
        class _():
            def _():
                if True:
                    if not self.frobbies and (
                        self.foobars.counters['db.cheeses'] != 1 or
                        self.foobars.counters['db.marshmellow_skins'] != 1
                    ):
                        pass
        """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testDedentSet(self):
    code = textwrap.dedent("""\
        class _():
            def _():
                assert set(self.constraint_links.get_links()) == set(
                    [
                        (2, 10, 100),
                        (2, 10, 200),
                        (2, 20, 100),
                        (2, 20, 200),
                    ]
                )
        """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testDedentingInnerScope(self):
    code = textwrap.dedent("""\
        class Foo():
            @classmethod
            def _pack_results_for_constraint_or(cls, combination, constraints):
                return cls._create_investigation_result(
                    (clue for clue in combination if not clue == Verifier.UNMATCHED),
                    constraints, InvestigationResult.OR
                )
        """)  # noqa
    llines = yapf_test_helper.ParseAndUnwrap(code)
    reformatted_code = reformatter.Reformat(llines)
    self.assertCodeEqual(code, reformatted_code)

    llines = yapf_test_helper.ParseAndUnwrap(reformatted_code)
    reformatted_code = reformatter.Reformat(llines)
    self.assertCodeEqual(code, reformatted_code)

  def testCommentWithNewlinesInPrefix(self):
    unformatted_code = textwrap.dedent("""\
        def foo():
            if 0:
                return False


            #a deadly comment
            elif 1:
                return True


        print(foo())
        """)
    expected_formatted_code = textwrap.dedent("""\
        def foo():
            if 0:
                return False

            #a deadly comment
            elif 1:
                return True


        print(foo())
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testIfStmtClosingBracket(self):
    unformatted_code = """\
if (isinstance(value  , (StopIteration  , StopAsyncIteration  )) and exc.__cause__ is value_asdfasdfasdfasdfsafsafsafdasfasdfs):
    return False
"""  # noqa
    expected_formatted_code = """\
if (
    isinstance(value, (StopIteration, StopAsyncIteration)) and
    exc.__cause__ is value_asdfasdfasdfasdfsafsafsafdasfasdfs
):
    return False
"""
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))


if __name__ == '__main__':
  unittest.main()
