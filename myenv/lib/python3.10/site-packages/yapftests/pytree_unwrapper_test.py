# Copyright 2015 Google Inc. All Rights Reserved.
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
"""Tests for yapf.pytree_unwrapper."""

import textwrap
import unittest

from yapf.yapflib import pytree_utils

from yapftests import yapf_test_helper


class PytreeUnwrapperTest(yapf_test_helper.YAPFTest):

  def _CheckLogicalLines(self, llines, list_of_expected):
    """Check that the given LogicalLines match expectations.

    Args:
      llines: list of LogicalLine
      list_of_expected: list of (depth, values) pairs. Non-semantic tokens are
        filtered out from the expected values.
    """
    actual = []
    for lline in llines:
      filtered_values = [
          ft.value
          for ft in lline.tokens
          if ft.name not in pytree_utils.NONSEMANTIC_TOKENS
      ]
      actual.append((lline.depth, filtered_values))

    self.assertEqual(list_of_expected, actual)

  def testSimpleFileScope(self):
    code = textwrap.dedent(r"""
      x = 1
      # a comment
      y = 2
      """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self._CheckLogicalLines(llines, [
        (0, ['x', '=', '1']),
        (0, ['# a comment']),
        (0, ['y', '=', '2']),
    ])

  def testSimpleMultilineStatement(self):
    code = textwrap.dedent(r"""
      y = (1 +
           x)
      """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self._CheckLogicalLines(llines, [
        (0, ['y', '=', '(', '1', '+', 'x', ')']),
    ])

  def testFileScopeWithInlineComment(self):
    code = textwrap.dedent(r"""
      x = 1    # a comment
      y = 2
      """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self._CheckLogicalLines(llines, [
        (0, ['x', '=', '1', '# a comment']),
        (0, ['y', '=', '2']),
    ])

  def testSimpleIf(self):
    code = textwrap.dedent(r"""
      if foo:
          x = 1
          y = 2
      """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self._CheckLogicalLines(llines, [
        (0, ['if', 'foo', ':']),
        (1, ['x', '=', '1']),
        (1, ['y', '=', '2']),
    ])

  def testSimpleIfWithComments(self):
    code = textwrap.dedent(r"""
      # c1
      if foo: # c2
          x = 1
          y = 2
      """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self._CheckLogicalLines(llines, [
        (0, ['# c1']),
        (0, ['if', 'foo', ':', '# c2']),
        (1, ['x', '=', '1']),
        (1, ['y', '=', '2']),
    ])

  def testIfWithCommentsInside(self):
    code = textwrap.dedent(r"""
      if foo:
          # c1
          x = 1 # c2
          # c3
          y = 2
      """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self._CheckLogicalLines(llines, [
        (0, ['if', 'foo', ':']),
        (1, ['# c1']),
        (1, ['x', '=', '1', '# c2']),
        (1, ['# c3']),
        (1, ['y', '=', '2']),
    ])

  def testIfElifElse(self):
    code = textwrap.dedent(r"""
       if x:
         x = 1 # c1
       elif y: # c2
         y = 1
       else:
         # c3
         z = 1
      """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self._CheckLogicalLines(llines, [
        (0, ['if', 'x', ':']),
        (1, ['x', '=', '1', '# c1']),
        (0, ['elif', 'y', ':', '# c2']),
        (1, ['y', '=', '1']),
        (0, ['else', ':']),
        (1, ['# c3']),
        (1, ['z', '=', '1']),
    ])

  def testNestedCompoundTwoLevel(self):
    code = textwrap.dedent(r"""
       if x:
         x = 1 # c1
         while t:
           # c2
           j = 1
         k = 1
      """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self._CheckLogicalLines(llines, [
        (0, ['if', 'x', ':']),
        (1, ['x', '=', '1', '# c1']),
        (1, ['while', 't', ':']),
        (2, ['# c2']),
        (2, ['j', '=', '1']),
        (1, ['k', '=', '1']),
    ])

  def testSimpleWhile(self):
    code = textwrap.dedent(r"""
       while x > 1: # c1
          # c2
          x = 1
      """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self._CheckLogicalLines(llines, [
        (0, ['while', 'x', '>', '1', ':', '# c1']),
        (1, ['# c2']),
        (1, ['x', '=', '1']),
    ])

  def testSimpleTry(self):
    code = textwrap.dedent(r"""
      try:
        pass
      except:
        pass
      except:
        pass
      else:
        pass
      finally:
        pass
      """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self._CheckLogicalLines(llines, [
        (0, ['try', ':']),
        (1, ['pass']),
        (0, ['except', ':']),
        (1, ['pass']),
        (0, ['except', ':']),
        (1, ['pass']),
        (0, ['else', ':']),
        (1, ['pass']),
        (0, ['finally', ':']),
        (1, ['pass']),
    ])

  def testSimpleFuncdef(self):
    code = textwrap.dedent(r"""
      def foo(x): # c1
        # c2
        return x
      """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self._CheckLogicalLines(llines, [
        (0, ['def', 'foo', '(', 'x', ')', ':', '# c1']),
        (1, ['# c2']),
        (1, ['return', 'x']),
    ])

  def testTwoFuncDefs(self):
    code = textwrap.dedent(r"""
      def foo(x): # c1
        # c2
        return x

      def bar(): # c3
        # c4
        return x
      """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self._CheckLogicalLines(llines, [
        (0, ['def', 'foo', '(', 'x', ')', ':', '# c1']),
        (1, ['# c2']),
        (1, ['return', 'x']),
        (0, ['def', 'bar', '(', ')', ':', '# c3']),
        (1, ['# c4']),
        (1, ['return', 'x']),
    ])

  def testSimpleClassDef(self):
    code = textwrap.dedent(r"""
      class Klass: # c1
        # c2
        p = 1
      """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self._CheckLogicalLines(llines, [
        (0, ['class', 'Klass', ':', '# c1']),
        (1, ['# c2']),
        (1, ['p', '=', '1']),
    ])

  def testSingleLineStmtInFunc(self):
    code = textwrap.dedent(r"""
        def f(): return 37
      """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self._CheckLogicalLines(llines, [
        (0, ['def', 'f', '(', ')', ':']),
        (1, ['return', '37']),
    ])

  def testMultipleComments(self):
    code = textwrap.dedent(r"""
        # Comment #1

        # Comment #2
        def f():
          pass
      """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self._CheckLogicalLines(llines, [
        (0, ['# Comment #1']),
        (0, ['# Comment #2']),
        (0, ['def', 'f', '(', ')', ':']),
        (1, ['pass']),
    ])

  def testSplitListWithComment(self):
    code = textwrap.dedent(r"""
      a = [
          'a',
          'b',
          'c',  # hello world
      ]
      """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self._CheckLogicalLines(llines, [(0, [
        'a', '=', '[', "'a'", ',', "'b'", ',', "'c'", ',', '# hello world', ']'
    ])])


class MatchBracketsTest(yapf_test_helper.YAPFTest):

  def _CheckMatchingBrackets(self, llines, list_of_expected):
    """Check that the tokens have the expected matching bracket.

    Arguments:
      llines: list of LogicalLine.
      list_of_expected: list of (index, index) pairs. The matching brackets at
        the indexes need to match. Non-semantic tokens are filtered out from the
        expected values.
    """
    actual = []
    for lline in llines:
      filtered_values = [(ft, ft.matching_bracket)
                         for ft in lline.tokens
                         if ft.name not in pytree_utils.NONSEMANTIC_TOKENS]
      if filtered_values:
        actual.append(filtered_values)

    for index, bracket_list in enumerate(list_of_expected):
      lline = actual[index]
      if not bracket_list:
        for value in lline:
          self.assertIsNone(value[1])
      else:
        for open_bracket, close_bracket in bracket_list:
          self.assertEqual(lline[open_bracket][0], lline[close_bracket][1])
          self.assertEqual(lline[close_bracket][0], lline[open_bracket][1])

  def testFunctionDef(self):
    code = textwrap.dedent("""\
        def foo(a, b=['w','d'], c=[42, 37]):
          pass
        """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self._CheckMatchingBrackets(llines, [
        [(2, 20), (7, 11), (15, 19)],
        [],
    ])

  def testDecorator(self):
    code = textwrap.dedent("""\
        @bar()
        def foo(a, b, c):
          pass
        """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self._CheckMatchingBrackets(llines, [
        [(2, 3)],
        [(2, 8)],
        [],
    ])

  def testClassDef(self):
    code = textwrap.dedent("""\
        class A(B, C, D):
          pass
        """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self._CheckMatchingBrackets(llines, [
        [(2, 8)],
        [],
    ])


if __name__ == '__main__':
  unittest.main()
