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
"""Basic tests for yapf.reformatter."""

import textwrap
import unittest

from yapf.yapflib import py3compat
from yapf.yapflib import reformatter
from yapf.yapflib import style

from yapftests import yapf_test_helper


class BasicReformatterTest(yapf_test_helper.YAPFTest):

  @classmethod
  def setUpClass(cls):
    style.SetGlobalStyle(style.CreateYapfStyle())

  def testSplittingAllArgs(self):
    style.SetGlobalStyle(
        style.CreateStyleFromConfig(
            '{split_all_comma_separated_values: true, column_limit: 40}'))
    unformatted_code = textwrap.dedent("""\
          responseDict = {"timestamp": timestamp, "someValue":   value, "whatever": 120}
          """)  # noqa
    expected_formatted_code = textwrap.dedent("""\
          responseDict = {
              "timestamp": timestamp,
              "someValue": value,
              "whatever": 120
          }
          """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

    unformatted_code = textwrap.dedent("""\
          yes = { 'yes': 'no', 'no': 'yes', }
          """)
    expected_formatted_code = textwrap.dedent("""\
          yes = {
              'yes': 'no',
              'no': 'yes',
          }
          """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))
    unformatted_code = textwrap.dedent("""\
          def foo(long_arg, really_long_arg, really_really_long_arg, cant_keep_all_these_args):
                pass
          """)  # noqa
    expected_formatted_code = textwrap.dedent("""\
          def foo(long_arg,
                  really_long_arg,
                  really_really_long_arg,
                  cant_keep_all_these_args):
            pass
          """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))
    unformatted_code = textwrap.dedent("""\
          foo_tuple = [long_arg, really_long_arg, really_really_long_arg, cant_keep_all_these_args]
          """)  # noqa
    expected_formatted_code = textwrap.dedent("""\
          foo_tuple = [
              long_arg,
              really_long_arg,
              really_really_long_arg,
              cant_keep_all_these_args
          ]
          """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))
    unformatted_code = textwrap.dedent("""\
          foo_tuple = [short, arg]
          """)
    expected_formatted_code = textwrap.dedent("""\
          foo_tuple = [short, arg]
          """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))
    # There is a test for split_all_top_level_comma_separated_values, with
    # different expected value
    unformatted_code = textwrap.dedent("""\
          someLongFunction(this_is_a_very_long_parameter,
              abc=(a, this_will_just_fit_xxxxxxx))
          """)
    expected_formatted_code = textwrap.dedent("""\
          someLongFunction(
              this_is_a_very_long_parameter,
              abc=(a,
                   this_will_just_fit_xxxxxxx))
          """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testSplittingTopLevelAllArgs(self):
    style.SetGlobalStyle(
        style.CreateStyleFromConfig(
            '{split_all_top_level_comma_separated_values: true, '
            'column_limit: 40}'))
    # Works the same way as split_all_comma_separated_values
    unformatted_code = textwrap.dedent("""\
          responseDict = {"timestamp": timestamp, "someValue":   value, "whatever": 120}
          """)  # noqa
    expected_formatted_code = textwrap.dedent("""\
          responseDict = {
              "timestamp": timestamp,
              "someValue": value,
              "whatever": 120
          }
          """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))
    # Works the same way as split_all_comma_separated_values
    unformatted_code = textwrap.dedent("""\
          def foo(long_arg, really_long_arg, really_really_long_arg, cant_keep_all_these_args):
                pass
          """)  # noqa
    expected_formatted_code = textwrap.dedent("""\
          def foo(long_arg,
                  really_long_arg,
                  really_really_long_arg,
                  cant_keep_all_these_args):
            pass
          """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))
    # Works the same way as split_all_comma_separated_values
    unformatted_code = textwrap.dedent("""\
          foo_tuple = [long_arg, really_long_arg, really_really_long_arg, cant_keep_all_these_args]
          """)  # noqa
    expected_formatted_code = textwrap.dedent("""\
          foo_tuple = [
              long_arg,
              really_long_arg,
              really_really_long_arg,
              cant_keep_all_these_args
          ]
          """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))
    # Works the same way as split_all_comma_separated_values
    unformatted_code = textwrap.dedent("""\
          foo_tuple = [short, arg]
          """)
    expected_formatted_code = textwrap.dedent("""\
          foo_tuple = [short, arg]
          """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))
    # There is a test for split_all_comma_separated_values, with different
    # expected value
    unformatted_code = textwrap.dedent("""\
          someLongFunction(this_is_a_very_long_parameter,
              abc=(a, this_will_just_fit_xxxxxxx))
          """)
    expected_formatted_code = textwrap.dedent("""\
          someLongFunction(
              this_is_a_very_long_parameter,
              abc=(a, this_will_just_fit_xxxxxxx))
          """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    actual_formatted_code = reformatter.Reformat(llines)
    self.assertEqual(40, len(actual_formatted_code.splitlines()[-1]))
    self.assertCodeEqual(expected_formatted_code, actual_formatted_code)

    unformatted_code = textwrap.dedent("""\
          someLongFunction(this_is_a_very_long_parameter,
              abc=(a, this_will_not_fit_xxxxxxxxx))
          """)
    expected_formatted_code = textwrap.dedent("""\
          someLongFunction(
              this_is_a_very_long_parameter,
              abc=(a,
                   this_will_not_fit_xxxxxxxxx))
          """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

    # Exercise the case where there's no opening bracket (for a, b)
    unformatted_code = textwrap.dedent("""\
          a, b = f(
              a_very_long_parameter, yet_another_one, and_another)
          """)
    expected_formatted_code = textwrap.dedent("""\
          a, b = f(
              a_very_long_parameter, yet_another_one, and_another)
          """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

    # Don't require splitting before comments.
    unformatted_code = textwrap.dedent("""\
          KO = {
              'ABC': Abc, # abc
              'DEF': Def, # def
              'LOL': Lol, # wtf
              'GHI': Ghi,
              'JKL': Jkl,
          }
          """)
    expected_formatted_code = textwrap.dedent("""\
          KO = {
              'ABC': Abc,  # abc
              'DEF': Def,  # def
              'LOL': Lol,  # wtf
              'GHI': Ghi,
              'JKL': Jkl,
          }
          """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testSimpleFunctionsWithTrailingComments(self):
    unformatted_code = textwrap.dedent("""\
        def g():  # Trailing comment
          if (xxxxxxxxxxxx.yyyyyyyy(zzzzzzzzzzzzz[0]) == 'aaaaaaaaaaa' and
              xxxxxxxxxxxx.yyyyyyyy(zzzzzzzzzzzzz[0].mmmmmmmm[0]) == 'bbbbbbb'):
            pass

        def f(  # Intermediate comment
        ):
          if (xxxxxxxxxxxx.yyyyyyyy(zzzzzzzzzzzzz[0]) == 'aaaaaaaaaaa' and
              xxxxxxxxxxxx.yyyyyyyy(zzzzzzzzzzzzz[0].mmmmmmmm[0]) == 'bbbbbbb'):
            pass
        """)
    expected_formatted_code = textwrap.dedent("""\
        def g():  # Trailing comment
          if (xxxxxxxxxxxx.yyyyyyyy(zzzzzzzzzzzzz[0]) == 'aaaaaaaaaaa' and
              xxxxxxxxxxxx.yyyyyyyy(zzzzzzzzzzzzz[0].mmmmmmmm[0]) == 'bbbbbbb'):
            pass


        def f(  # Intermediate comment
        ):
          if (xxxxxxxxxxxx.yyyyyyyy(zzzzzzzzzzzzz[0]) == 'aaaaaaaaaaa' and
              xxxxxxxxxxxx.yyyyyyyy(zzzzzzzzzzzzz[0].mmmmmmmm[0]) == 'bbbbbbb'):
            pass
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testBlankLinesBetweenTopLevelImportsAndVariables(self):
    unformatted_code = textwrap.dedent("""\
        import foo as bar
        VAR = 'baz'
        """)
    expected_formatted_code = textwrap.dedent("""\
        import foo as bar

        VAR = 'baz'
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

    unformatted_code = textwrap.dedent("""\
        import foo as bar

        VAR = 'baz'
        """)
    expected_formatted_code = textwrap.dedent("""\
        import foo as bar


        VAR = 'baz'
        """)
    try:
      style.SetGlobalStyle(
          style.CreateStyleFromConfig(
              '{based_on_style: yapf, '
              'blank_lines_between_top_level_imports_and_variables: 2}'))
      llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
      self.assertCodeEqual(expected_formatted_code,
                           reformatter.Reformat(llines))
    finally:
      style.SetGlobalStyle(style.CreateYapfStyle())

    unformatted_code = textwrap.dedent("""\
        import foo as bar
        # Some comment
        """)
    expected_formatted_code = textwrap.dedent("""\
        import foo as bar
        # Some comment
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

    unformatted_code = textwrap.dedent("""\
        import foo as bar
        class Baz():
          pass
        """)
    expected_formatted_code = textwrap.dedent("""\
        import foo as bar


        class Baz():
          pass
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

    unformatted_code = textwrap.dedent("""\
        import foo as bar
        def foobar():
          pass
        """)
    expected_formatted_code = textwrap.dedent("""\
        import foo as bar


        def foobar():
          pass
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

    unformatted_code = textwrap.dedent("""\
        def foobar():
          from foo import Bar
          Bar.baz()
        """)
    expected_formatted_code = textwrap.dedent("""\
        def foobar():
          from foo import Bar
          Bar.baz()
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testBlankLinesAtEndOfFile(self):
    unformatted_code = textwrap.dedent("""\
        def foobar(): # foo
         pass



        """)
    expected_formatted_code = textwrap.dedent("""\
        def foobar():  # foo
          pass
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

    unformatted_code = textwrap.dedent("""\
        x = {  'a':37,'b':42,

        'c':927}

        """)
    expected_formatted_code = textwrap.dedent("""\
        x = {'a': 37, 'b': 42, 'c': 927}
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testIndentBlankLines(self):
    unformatted_code = textwrap.dedent("""\
        class foo(object):

          def foobar(self):

            pass

          def barfoo(self, x, y):  # bar

            if x:

              return y


        def bar():

          return 0
        """)
    expected_formatted_code = """\
class foo(object):\n  \n  def foobar(self):\n    \n    pass\n  \n  def barfoo(self, x, y):  # bar\n    \n    if x:\n      \n      return y\n\n\ndef bar():\n  \n  return 0
"""  # noqa

    try:
      style.SetGlobalStyle(
          style.CreateStyleFromConfig(
              '{based_on_style: yapf, indent_blank_lines: true}'))

      llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
      self.assertCodeEqual(expected_formatted_code,
                           reformatter.Reformat(llines))
    finally:
      style.SetGlobalStyle(style.CreateYapfStyle())

    unformatted_code, expected_formatted_code = (expected_formatted_code,
                                                 unformatted_code)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testMultipleUgliness(self):
    unformatted_code = textwrap.dedent("""\
        x = {  'a':37,'b':42,

        'c':927}

        y = 'hello ''world'
        z = 'hello '+'world'
        a = 'hello {}'.format('world')
        class foo  (     object  ):
          def f    (self   ):
            return       37*-+2
          def g(self, x,y=42):
              return y
        def f  (   a ) :
          return      37+-+a[42-x :  y**3]
        """)
    expected_formatted_code = textwrap.dedent("""\
        x = {'a': 37, 'b': 42, 'c': 927}

        y = 'hello ' 'world'
        z = 'hello ' + 'world'
        a = 'hello {}'.format('world')


        class foo(object):

          def f(self):
            return 37 * -+2

          def g(self, x, y=42):
            return y


        def f(a):
          return 37 + -+a[42 - x:y**3]
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testComments(self):
    unformatted_code = textwrap.dedent("""\
        class Foo(object):
          pass

        # Attached comment
        class Bar(object):
          pass

        global_assignment = 42

        # Comment attached to class with decorator.
        # Comment attached to class with decorator.
        @noop
        @noop
        class Baz(object):
          pass

        # Intermediate comment

        class Qux(object):
          pass
        """)
    expected_formatted_code = textwrap.dedent("""\
        class Foo(object):
          pass


        # Attached comment
        class Bar(object):
          pass


        global_assignment = 42


        # Comment attached to class with decorator.
        # Comment attached to class with decorator.
        @noop
        @noop
        class Baz(object):
          pass


        # Intermediate comment


        class Qux(object):
          pass
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testSingleComment(self):
    code = textwrap.dedent("""\
        # Thing 1
        """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testCommentsWithTrailingSpaces(self):
    unformatted_code = textwrap.dedent("""\
        # Thing 1    \n# Thing 2    \n""")
    expected_formatted_code = textwrap.dedent("""\
        # Thing 1
        # Thing 2
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testCommentsInDataLiteral(self):
    code = textwrap.dedent("""\
        def f():
          return collections.OrderedDict({
              # First comment.
              'fnord': 37,

              # Second comment.
              # Continuation of second comment.
              'bork': 42,

              # Ending comment.
          })
        """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testEndingWhitespaceAfterSimpleStatement(self):
    code = textwrap.dedent("""\
        import foo as bar
        # Thing 1
        # Thing 2
        """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testDocstrings(self):
    unformatted_code = textwrap.dedent('''\
        u"""Module-level docstring."""
        import os
        class Foo(object):

          """Class-level docstring."""
          # A comment for qux.
          def qux(self):


            """Function-level docstring.

            A multiline function docstring.
            """
            print('hello {}'.format('world'))
            return 42
        ''')
    expected_formatted_code = textwrap.dedent('''\
        u"""Module-level docstring."""
        import os


        class Foo(object):
          """Class-level docstring."""

          # A comment for qux.
          def qux(self):
            """Function-level docstring.

            A multiline function docstring.
            """
            print('hello {}'.format('world'))
            return 42
        ''')
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testDocstringAndMultilineComment(self):
    unformatted_code = textwrap.dedent('''\
        """Hello world"""
        # A multiline
        # comment
        class bar(object):
          """class docstring"""
          # class multiline
          # comment
          def foo(self):
            """Another docstring."""
            # Another multiline
            # comment
            pass
        ''')
    expected_formatted_code = textwrap.dedent('''\
        """Hello world"""


        # A multiline
        # comment
        class bar(object):
          """class docstring"""

          # class multiline
          # comment
          def foo(self):
            """Another docstring."""
            # Another multiline
            # comment
            pass
        ''')
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testMultilineDocstringAndMultilineComment(self):
    unformatted_code = textwrap.dedent('''\
        """Hello world

        RIP Dennis Richie.
        """
        # A multiline
        # comment
        class bar(object):
          """class docstring

          A classy class.
          """
          # class multiline
          # comment
          def foo(self):
            """Another docstring.

            A functional function.
            """
            # Another multiline
            # comment
            pass
        ''')
    expected_formatted_code = textwrap.dedent('''\
        """Hello world

        RIP Dennis Richie.
        """


        # A multiline
        # comment
        class bar(object):
          """class docstring

          A classy class.
          """

          # class multiline
          # comment
          def foo(self):
            """Another docstring.

            A functional function.
            """
            # Another multiline
            # comment
            pass
        ''')
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testTupleCommaBeforeLastParen(self):
    unformatted_code = textwrap.dedent("""\
        a = ( 1, )
        """)
    expected_formatted_code = textwrap.dedent("""\
        a = (1,)
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testNoBreakOutsideOfBracket(self):
    # FIXME(morbo): How this is formatted is not correct. But it's syntactically
    # correct.
    unformatted_code = textwrap.dedent("""\
        def f():
          assert port >= minimum, \
'Unexpected port %d when minimum was %d.' % (port, minimum)
        """)
    expected_formatted_code = textwrap.dedent("""\
        def f():
          assert port >= minimum, 'Unexpected port %d when minimum was %d.' % (port,
                                                                               minimum)
        """)  # noqa
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testBlankLinesBeforeDecorators(self):
    unformatted_code = textwrap.dedent("""\
        @foo()
        class A(object):
          @bar()
          @baz()
          def x(self):
            pass
        """)
    expected_formatted_code = textwrap.dedent("""\
        @foo()
        class A(object):

          @bar()
          @baz()
          def x(self):
            pass
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testCommentBetweenDecorators(self):
    unformatted_code = textwrap.dedent("""\
        @foo()
        # frob
        @bar
        def x  (self):
            pass
        """)
    expected_formatted_code = textwrap.dedent("""\
        @foo()
        # frob
        @bar
        def x(self):
          pass
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testListComprehension(self):
    unformatted_code = textwrap.dedent("""\
        def given(y):
            [k for k in ()
              if k in y]
        """)
    expected_formatted_code = textwrap.dedent("""\
        def given(y):
          [k for k in () if k in y]
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testListComprehensionPreferOneLine(self):
    unformatted_code = textwrap.dedent("""\
        def given(y):
            long_variable_name = [
                long_var_name + 1
                for long_var_name in ()
                if long_var_name == 2]
        """)
    expected_formatted_code = textwrap.dedent("""\
        def given(y):
          long_variable_name = [
              long_var_name + 1 for long_var_name in () if long_var_name == 2
          ]
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testListComprehensionPreferOneLineOverArithmeticSplit(self):
    unformatted_code = textwrap.dedent("""\
        def given(used_identifiers):
          return (sum(len(identifier)
                      for identifier in used_identifiers) / len(used_identifiers))
        """)  # noqa
    expected_formatted_code = textwrap.dedent("""\
        def given(used_identifiers):
          return (sum(len(identifier) for identifier in used_identifiers) /
                  len(used_identifiers))
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testListComprehensionPreferThreeLinesForLineWrap(self):
    unformatted_code = textwrap.dedent("""\
        def given(y):
            long_variable_name = [
                long_var_name + 1
                for long_var_name, number_two in ()
                if long_var_name == 2 and number_two == 3]
        """)
    expected_formatted_code = textwrap.dedent("""\
        def given(y):
          long_variable_name = [
              long_var_name + 1
              for long_var_name, number_two in ()
              if long_var_name == 2 and number_two == 3
          ]
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testListComprehensionPreferNoBreakForTrivialExpression(self):
    unformatted_code = textwrap.dedent("""\
        def given(y):
            long_variable_name = [
                long_var_name
                for long_var_name, number_two in ()
                if long_var_name == 2 and number_two == 3]
        """)
    expected_formatted_code = textwrap.dedent("""\
        def given(y):
          long_variable_name = [
              long_var_name for long_var_name, number_two in ()
              if long_var_name == 2 and number_two == 3
          ]
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testOpeningAndClosingBrackets(self):
    unformatted_code = """\
foo( (1, ) )
foo( ( 1, 2, 3  ) )
foo( ( 1, 2, 3, ) )
"""
    expected_formatted_code = """\
foo((1,))
foo((1, 2, 3))
foo((
    1,
    2,
    3,
))
"""
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testSingleLineFunctions(self):
    unformatted_code = textwrap.dedent("""\
        def foo():  return 42
        """)
    expected_formatted_code = textwrap.dedent("""\
        def foo():
          return 42
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testNoQueueSeletionInMiddleOfLine(self):
    # If the queue isn't properly constructed, then a token in the middle of the
    # line may be selected as the one with least penalty. The tokens after that
    # one are then splatted at the end of the line with no formatting.
    unformatted_code = """\
find_symbol(node.type) + "< " + " ".join(find_pattern(n) for n in node.child) + " >"
"""  # noqa
    expected_formatted_code = """\
find_symbol(node.type) + "< " + " ".join(
    find_pattern(n) for n in node.child) + " >"
"""
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testNoSpacesBetweenSubscriptsAndCalls(self):
    unformatted_code = textwrap.dedent("""\
        aaaaaaaaaa = bbbbbbbb.ccccccccc() [42] (a, 2)
        """)
    expected_formatted_code = textwrap.dedent("""\
        aaaaaaaaaa = bbbbbbbb.ccccccccc()[42](a, 2)
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testNoSpacesBetweenOpeningBracketAndStartingOperator(self):
    # Unary operator.
    unformatted_code = textwrap.dedent("""\
        aaaaaaaaaa = bbbbbbbb.ccccccccc[ -1 ]( -42 )
        """)
    expected_formatted_code = textwrap.dedent("""\
        aaaaaaaaaa = bbbbbbbb.ccccccccc[-1](-42)
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

    # Varargs and kwargs.
    unformatted_code = textwrap.dedent("""\
        aaaaaaaaaa = bbbbbbbb.ccccccccc( *varargs )
        aaaaaaaaaa = bbbbbbbb.ccccccccc( **kwargs )
        """)
    expected_formatted_code = textwrap.dedent("""\
        aaaaaaaaaa = bbbbbbbb.ccccccccc(*varargs)
        aaaaaaaaaa = bbbbbbbb.ccccccccc(**kwargs)
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testMultilineCommentReformatted(self):
    unformatted_code = textwrap.dedent("""\
        if True:
            # This is a multiline
            # comment.
            pass
        """)
    expected_formatted_code = textwrap.dedent("""\
        if True:
          # This is a multiline
          # comment.
          pass
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testDictionaryMakerFormatting(self):
    unformatted_code = textwrap.dedent("""\
        _PYTHON_STATEMENTS = frozenset({
            lambda x, y: 'simple_stmt': 'small_stmt', 'expr_stmt': 'print_stmt', 'del_stmt':
            'pass_stmt', lambda: 'break_stmt': 'continue_stmt', 'return_stmt': 'raise_stmt',
            'yield_stmt': 'import_stmt', lambda: 'global_stmt': 'exec_stmt', 'assert_stmt':
            'if_stmt', 'while_stmt': 'for_stmt',
        })
        """)  # noqa
    expected_formatted_code = textwrap.dedent("""\
        _PYTHON_STATEMENTS = frozenset({
            lambda x, y: 'simple_stmt': 'small_stmt',
            'expr_stmt': 'print_stmt',
            'del_stmt': 'pass_stmt',
            lambda: 'break_stmt': 'continue_stmt',
            'return_stmt': 'raise_stmt',
            'yield_stmt': 'import_stmt',
            lambda: 'global_stmt': 'exec_stmt',
            'assert_stmt': 'if_stmt',
            'while_stmt': 'for_stmt',
        })
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testSimpleMultilineCode(self):
    unformatted_code = textwrap.dedent("""\
        if True:
          aaaaaaaaaaaaaa.bbbbbbbbbbbbbb.ccccccc(zzzzzzzzzzzz, \
xxxxxxxxxxx, yyyyyyyyyyyy, vvvvvvvvv)
          aaaaaaaaaaaaaa.bbbbbbbbbbbbbb.ccccccc(zzzzzzzzzzzz, \
xxxxxxxxxxx, yyyyyyyyyyyy, vvvvvvvvv)
        """)
    expected_formatted_code = textwrap.dedent("""\
        if True:
          aaaaaaaaaaaaaa.bbbbbbbbbbbbbb.ccccccc(zzzzzzzzzzzz, xxxxxxxxxxx, yyyyyyyyyyyy,
                                                vvvvvvvvv)
          aaaaaaaaaaaaaa.bbbbbbbbbbbbbb.ccccccc(zzzzzzzzzzzz, xxxxxxxxxxx, yyyyyyyyyyyy,
                                                vvvvvvvvv)
        """)  # noqa
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testMultilineComment(self):
    code = textwrap.dedent("""\
        if Foo:
          # Hello world
          # Yo man.
          # Yo man.
          # Yo man.
          # Yo man.
          a = 42
        """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testSpaceBetweenStringAndParentheses(self):
    code = textwrap.dedent("""\
        b = '0' ('hello')
        """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testMultilineString(self):
    code = textwrap.dedent("""\
        code = textwrap.dedent('''\
            if Foo:
              # Hello world
              # Yo man.
              # Yo man.
              # Yo man.
              # Yo man.
              a = 42
            ''')
        """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

    unformatted_code = textwrap.dedent('''\
        def f():
            email_text += """<html>This is a really long docstring that goes over the column limit and is multi-line.<br><br>
        <b>Czar: </b>"""+despot["Nicholas"]+"""<br>
        <b>Minion: </b>"""+serf["Dmitri"]+"""<br>
        <b>Residence: </b>"""+palace["Winter"]+"""<br>
        </body>
        </html>"""
        ''')  # noqa
    expected_formatted_code = textwrap.dedent('''\
        def f():
          email_text += """<html>This is a really long docstring that goes over the column limit and is multi-line.<br><br>
        <b>Czar: </b>""" + despot["Nicholas"] + """<br>
        <b>Minion: </b>""" + serf["Dmitri"] + """<br>
        <b>Residence: </b>""" + palace["Winter"] + """<br>
        </body>
        </html>"""
        ''')  # noqa
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testSimpleMultilineWithComments(self):
    code = textwrap.dedent("""\
        if (  # This is the first comment
            a and  # This is the second comment
            # This is the third comment
            b):  # A trailing comment
          # Whoa! A normal comment!!
          pass  # Another trailing comment
        """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testMatchingParenSplittingMatching(self):
    unformatted_code = textwrap.dedent("""\
        def f():
          raise RuntimeError('unable to find insertion point for target node',
                             (target,))
        """)
    expected_formatted_code = textwrap.dedent("""\
        def f():
          raise RuntimeError('unable to find insertion point for target node',
                             (target,))
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testContinuationIndent(self):
    unformatted_code = textwrap.dedent('''\
        class F:
          def _ProcessArgLists(self, node):
            """Common method for processing argument lists."""
            for child in node.children:
              if isinstance(child, pytree.Leaf):
                self._SetTokenSubtype(
                    child, subtype=_ARGLIST_TOKEN_TO_SUBTYPE.get(
                        child.value, format_token.Subtype.NONE))
        ''')
    expected_formatted_code = textwrap.dedent('''\
        class F:

          def _ProcessArgLists(self, node):
            """Common method for processing argument lists."""
            for child in node.children:
              if isinstance(child, pytree.Leaf):
                self._SetTokenSubtype(
                    child,
                    subtype=_ARGLIST_TOKEN_TO_SUBTYPE.get(child.value,
                                                          format_token.Subtype.NONE))
        ''')  # noqa
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testTrailingCommaAndBracket(self):
    unformatted_code = textwrap.dedent('''\
        a = { 42, }
        b = ( 42, )
        c = [ 42, ]
        ''')
    expected_formatted_code = textwrap.dedent('''\
        a = {
            42,
        }
        b = (42,)
        c = [
            42,
        ]
        ''')
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testI18n(self):
    code = textwrap.dedent("""\
        N_('Some years ago - never mind how long precisely - having little or no money in my purse, and nothing particular to interest me on shore, I thought I would sail about a little and see the watery part of the world.')  # A comment is here.
        """)  # noqa
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

    code = textwrap.dedent("""\
        foo('Fake function call')  #. Some years ago - never mind how long precisely - having little or no money in my purse, and nothing particular to interest me on shore, I thought I would sail about a little and see the watery part of the world.
        """)  # noqa
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testI18nCommentsInDataLiteral(self):
    code = textwrap.dedent("""\
        def f():
          return collections.OrderedDict({
              #. First i18n comment.
              'bork': 'foo',

              #. Second i18n comment.
              'snork': 'bar#.*=\\\\0',
          })
        """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testClosingBracketIndent(self):
    code = textwrap.dedent('''\
        def f():

          def g():
            while (xxxxxxxxxxxxxxxxxxxxx(yyyyyyyyyyyyy[zzzzz]) == 'aaaaaaaaaaa' and
                   xxxxxxxxxxxxxxxxxxxxx(
                       yyyyyyyyyyyyy[zzzzz].aaaaaaaa[0]) == 'bbbbbbb'):
              pass
        ''')  # noqa
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testClosingBracketsInlinedInCall(self):
    unformatted_code = textwrap.dedent("""\
        class Foo(object):

          def bar(self):
            self.aaaaaaaa = xxxxxxxxxxxxxxxxxxx.yyyyyyyyyyyyy(
                self.cccccc.ddddddddd.eeeeeeee,
                options={
                    "forkforkfork": 1,
                    "borkborkbork": 2,
                    "corkcorkcork": 3,
                    "horkhorkhork": 4,
                    "porkporkpork": 5,
                    })
        """)
    expected_formatted_code = textwrap.dedent("""\
        class Foo(object):

          def bar(self):
            self.aaaaaaaa = xxxxxxxxxxxxxxxxxxx.yyyyyyyyyyyyy(
                self.cccccc.ddddddddd.eeeeeeee,
                options={
                    "forkforkfork": 1,
                    "borkborkbork": 2,
                    "corkcorkcork": 3,
                    "horkhorkhork": 4,
                    "porkporkpork": 5,
                })
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testLineWrapInForExpression(self):
    code = textwrap.dedent("""\
        class A:

          def x(self, node, name, n=1):
            for i, child in enumerate(
                itertools.ifilter(lambda c: pytree_utils.NodeName(c) == name,
                                  node.pre_order())):
              pass
        """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testFunctionCallContinuationLine(self):
    code = """\
class foo:

  def bar(self, node, name, n=1):
    if True:
      if True:
        return [(aaaaaaaaaa,
                 bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb(
                     cccc, ddddddddddddddddddddddddddddddddddddd))]
"""
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testI18nNonFormatting(self):
    code = textwrap.dedent("""\
        class F(object):

          def __init__(self, fieldname,
                       #. Error message indicating an invalid e-mail address.
                       message=N_('Please check your email address.'), **kwargs):
            pass
        """)  # noqa
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testNoSpaceBetweenUnaryOpAndOpeningParen(self):
    code = textwrap.dedent("""\
        if ~(a or b):
          pass
        """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testCommentBeforeFuncDef(self):
    code = textwrap.dedent("""\
        class Foo(object):

          a = 42

          # This is a comment.
          def __init__(self,
                       xxxxxxx,
                       yyyyy=0,
                       zzzzzzz=None,
                       aaaaaaaaaaaaaaaaaa=False,
                       bbbbbbbbbbbbbbb=False):
            pass
        """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testExcessLineCountWithDefaultKeywords(self):
    unformatted_code = textwrap.dedent("""\
        class Fnord(object):
          def Moo(self):
            aaaaaaaaaaaaaaaa = self._bbbbbbbbbbbbbbbbbbbbbbb(
                ccccccccccccc=ccccccccccccc, ddddddd=ddddddd, eeee=eeee,
                fffff=fffff, ggggggg=ggggggg, hhhhhhhhhhhhh=hhhhhhhhhhhhh,
                iiiiiii=iiiiiiiiiiiiii)
        """)
    expected_formatted_code = textwrap.dedent("""\
        class Fnord(object):

          def Moo(self):
            aaaaaaaaaaaaaaaa = self._bbbbbbbbbbbbbbbbbbbbbbb(
                ccccccccccccc=ccccccccccccc,
                ddddddd=ddddddd,
                eeee=eeee,
                fffff=fffff,
                ggggggg=ggggggg,
                hhhhhhhhhhhhh=hhhhhhhhhhhhh,
                iiiiiii=iiiiiiiiiiiiii)
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testSpaceAfterNotOperator(self):
    code = textwrap.dedent("""\
        if not (this and that):
          pass
        """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testNoPenaltySplitting(self):
    code = textwrap.dedent("""\
        def f():
          if True:
            if True:
              python_files.extend(
                  os.path.join(filename, f)
                  for f in os.listdir(filename)
                  if IsPythonFile(os.path.join(filename, f)))
        """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testExpressionPenalties(self):
    code = textwrap.dedent("""\
      def f():
        if ((left.value == '(' and right.value == ')') or
            (left.value == '[' and right.value == ']') or
            (left.value == '{' and right.value == '}')):
          return False
        """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testLineDepthOfSingleLineStatement(self):
    unformatted_code = textwrap.dedent("""\
        while True: continue
        for x in range(3): continue
        try: a = 42
        except: b = 42
        with open(a) as fd: a = fd.read()
        """)
    expected_formatted_code = textwrap.dedent("""\
        while True:
          continue
        for x in range(3):
          continue
        try:
          a = 42
        except:
          b = 42
        with open(a) as fd:
          a = fd.read()
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testSplitListWithTerminatingComma(self):
    unformatted_code = textwrap.dedent("""\
        FOO = ['bar', 'baz', 'mux', 'qux', 'quux', 'quuux', 'quuuux',
          'quuuuux', 'quuuuuux', 'quuuuuuux', lambda a, b: 37,]
        """)
    expected_formatted_code = textwrap.dedent("""\
        FOO = [
            'bar',
            'baz',
            'mux',
            'qux',
            'quux',
            'quuux',
            'quuuux',
            'quuuuux',
            'quuuuuux',
            'quuuuuuux',
            lambda a, b: 37,
        ]
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testSplitListWithInterspersedComments(self):
    code = textwrap.dedent("""\
        FOO = [
            'bar',  # bar
            'baz',  # baz
            'mux',  # mux
            'qux',  # qux
            'quux',  # quux
            'quuux',  # quuux
            'quuuux',  # quuuux
            'quuuuux',  # quuuuux
            'quuuuuux',  # quuuuuux
            'quuuuuuux',  # quuuuuuux
            lambda a, b: 37  # lambda
        ]
        """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testRelativeImportStatements(self):
    code = textwrap.dedent("""\
        from ... import bork
        """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testSingleLineList(self):
    # A list on a single line should prefer to remain contiguous.
    unformatted_code = textwrap.dedent("""\
        bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb = aaaaaaaaaaa(
            ("...", "."), "..",
            ".............................................."
        )
        """)
    expected_formatted_code = textwrap.dedent("""\
        bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb = aaaaaaaaaaa(
            ("...", "."), "..", "..............................................")
        """)  # noqa
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testBlankLinesBeforeFunctionsNotInColumnZero(self):
    unformatted_code = textwrap.dedent("""\
        import signal


        try:
          signal.SIGALRM
          # ..................................................................
          # ...............................................................


          def timeout(seconds=1):
            pass
        except:
          pass
        """)
    expected_formatted_code = textwrap.dedent("""\
        import signal

        try:
          signal.SIGALRM

          # ..................................................................
          # ...............................................................


          def timeout(seconds=1):
            pass
        except:
          pass
        """)  # noqa
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testNoKeywordArgumentBreakage(self):
    code = textwrap.dedent("""\
        class A(object):

          def b(self):
            if self.aaaaaaaaaaaaaaaaaaaa not in self.bbbbbbbbbb(
                cccccccccccccccccccc=True):
              pass
        """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testTrailerOnSingleLine(self):
    code = """\
urlpatterns = patterns('', url(r'^$', 'homepage_view'),
                       url(r'^/login/$', 'login_view'),
                       url(r'^/login/$', 'logout_view'),
                       url(r'^/user/(?P<username>\\w+)/$', 'profile_view'))
"""
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testIfConditionalParens(self):
    code = textwrap.dedent("""\
        class Foo:

          def bar():
            if True:
              if (child.type == grammar_token.NAME and
                  child.value in substatement_names):
                pass
        """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testContinuationMarkers(self):
    code = textwrap.dedent("""\
        text = "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Donec a diam lectus. "\\
               "Sed sit amet ipsum mauris. Maecenas congue ligula ac quam viverra nec consectetur "\\
               "ante hendrerit. Donec et mollis dolor. Praesent et diam eget libero egestas mattis "\\
               "sit amet vitae augue. Nam tincidunt congue enim, ut porta lorem lacinia consectetur. "\\
               "Donec ut libero sed arcu vehicula ultricies a non tortor. Lorem ipsum dolor sit amet"
        """)  # noqa
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

    code = textwrap.dedent("""\
        from __future__ import nested_scopes, generators, division, absolute_import, with_statement, \\
            print_function, unicode_literals
        """)  # noqa
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

    code = textwrap.dedent("""\
        if aaaaaaaaa == 42 and bbbbbbbbbbbbbb == 42 and \\
           cccccccc == 42:
          pass
        """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testCommentsWithContinuationMarkers(self):
    code = textwrap.dedent("""\
        def fn(arg):
          v = fn2(key1=True,
                  #c1
                  key2=arg)\\
                        .fn3()
        """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testMultipleContinuationMarkers(self):
    code = textwrap.dedent("""\
        xyz = \\
            \\
            some_thing()
        """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testContinuationMarkerAfterStringWithContinuation(self):
    code = """\
s = 'foo \\
    bar' \\
    .format()
"""
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testEmptyContainers(self):
    code = textwrap.dedent("""\
        flags.DEFINE_list(
            'output_dirs', [],
            'Lorem ipsum dolor sit amet, consetetur adipiscing elit. Donec a diam lectus. '
            'Sed sit amet ipsum mauris. Maecenas congue.')
        """)  # noqa
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testSplitStringsIfSurroundedByParens(self):
    unformatted_code = textwrap.dedent("""\
        a = foo.bar({'xxxxxxxxxxxxxxxxxxxxxxx' 'yyyyyyyyyyyyyyyyyyyyyyyyyy': baz[42]} + 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' 'bbbbbbbbbbbbbbbbbbbbbbbbbb' 'cccccccccccccccccccccccccccccccc' 'ddddddddddddddddddddddddddddd')
        """)  # noqa
    expected_formatted_code = textwrap.dedent("""\
        a = foo.bar({'xxxxxxxxxxxxxxxxxxxxxxx'
                     'yyyyyyyyyyyyyyyyyyyyyyyyyy': baz[42]} +
                    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
                    'bbbbbbbbbbbbbbbbbbbbbbbbbb'
                    'cccccccccccccccccccccccccccccccc'
                    'ddddddddddddddddddddddddddddd')
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

    code = textwrap.dedent("""\
        a = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' \
'bbbbbbbbbbbbbbbbbbbbbbbbbb' 'cccccccccccccccccccccccccccccccc' \
'ddddddddddddddddddddddddddddd'
        """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testMultilineShebang(self):
    code = textwrap.dedent("""\
        #!/bin/sh
        if "true" : '''\'
        then

        export FOO=123
        exec /usr/bin/env python "$0" "$@"

        exit 127
        fi
        '''

        import os

        assert os.environ['FOO'] == '123'
        """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testNoSplittingAroundTermOperators(self):
    code = textwrap.dedent("""\
        a_very_long_function_call_yada_yada_etc_etc_etc(long_arg1,
                                                        long_arg2 / long_arg3)
        """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testNoSplittingWithinSubscriptList(self):
    code = textwrap.dedent("""\
        somequitelongvariablename.somemember[(a, b)] = {
            'somelongkey': 1,
            'someotherlongkey': 2
        }
        """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testExcessCharacters(self):
    code = textwrap.dedent("""\
        class foo:

          def bar(self):
            self.write(s=[
                '%s%s %s' % ('many of really', 'long strings', '+ just makes up 81')
            ])
        """)  # noqa
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

    unformatted_code = textwrap.dedent("""\
        def _():
          if True:
            if True:
              if contract == allow_contract and attr_dict.get(if_attribute) == has_value:
                return True
        """)  # noqa
    expected_code = textwrap.dedent("""\
        def _():
          if True:
            if True:
              if contract == allow_contract and attr_dict.get(
                  if_attribute) == has_value:
                return True
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_code, reformatter.Reformat(llines))

  def testDictSetGenerator(self):
    code = textwrap.dedent("""\
        foo = {
            variable: 'hello world. How are you today?'
            for variable in fnord
            if variable != 37
        }
        """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testUnaryOpInDictionaryValue(self):
    code = textwrap.dedent("""\
        beta = "123"

        test = {'alpha': beta[-1]}

        print(beta[-1])
        """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testUnaryNotOperator(self):
    code = textwrap.dedent("""\
        if True:
          if True:
            if True:
              if True:
                remote_checksum = self.get_checksum(conn, tmp, dest, inject,
                                                    not directory_prepended, source)
        """)  # noqa
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testRelaxArraySubscriptAffinity(self):
    code = """\
class A(object):

  def f(self, aaaaaaaaa, bbbbbbbbbbbbb, row):
    if True:
      if True:
        if True:
          if True:
            if row[4] is None or row[5] is None:
              bbbbbbbbbbbbb[
                  '..............'] = row[5] if row[5] is not None else 5
"""
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testFunctionCallInDict(self):
    code = "a = {'a': b(c=d, **e)}\n"
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testFunctionCallInNestedDict(self):
    code = "a = {'a': {'a': {'a': b(c=d, **e)}}}\n"
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testUnbreakableNot(self):
    code = textwrap.dedent("""\
        def test():
          if not "Foooooooooooooooooooooooooooooo" or "Foooooooooooooooooooooooooooooo" == "Foooooooooooooooooooooooooooooo":
            pass
        """)  # noqa
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testSplitListWithComment(self):
    code = textwrap.dedent("""\
      a = [
          'a',
          'b',
          'c'  # hello world
      ]
      """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testOverColumnLimit(self):
    unformatted_code = textwrap.dedent("""\
      class Test:

        def testSomething(self):
          expected = {
              ('aaaaaaaaaaaaa', 'bbbb'): 'ccccccccccccccccccccccccccccccccccccccccccc',
              ('aaaaaaaaaaaaa', 'bbbb'): 'ccccccccccccccccccccccccccccccccccccccccccc',
              ('aaaaaaaaaaaaa', 'bbbb'): 'ccccccccccccccccccccccccccccccccccccccccccc',
          }
        """)  # noqa
    expected_formatted_code = textwrap.dedent("""\
      class Test:

        def testSomething(self):
          expected = {
              ('aaaaaaaaaaaaa', 'bbbb'):
                  'ccccccccccccccccccccccccccccccccccccccccccc',
              ('aaaaaaaaaaaaa', 'bbbb'):
                  'ccccccccccccccccccccccccccccccccccccccccccc',
              ('aaaaaaaaaaaaa', 'bbbb'):
                  'ccccccccccccccccccccccccccccccccccccccccccc',
          }
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testEndingComment(self):
    code = textwrap.dedent("""\
      a = f(
          a="something",
          b="something requiring comment which is quite long",  # comment about b (pushes line over 79)
          c="something else, about which comment doesn't make sense")
      """)  # noqa
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testContinuationSpaceRetention(self):
    code = textwrap.dedent("""\
      def fn():
        return module \\
               .method(Object(data,
                   fn2(arg)
               ))
      """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testIfExpressionWithFunctionCall(self):
    code = textwrap.dedent("""\
      if x or z.y(
          a,
          c,
          aaaaaaaaaaaaaaaaaaaaa=aaaaaaaaaaaaaaaaaa,
          bbbbbbbbbbbbbbbbbbbbb=bbbbbbbbbbbbbbbbbb):
        pass
      """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testUnformattedAfterMultilineString(self):
    code = textwrap.dedent("""\
      def foo():
        com_text = \\
      '''
      TEST
      ''' % (input_fname, output_fname)
      """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testNoSpacesAroundKeywordDefaultValues(self):
    code = textwrap.dedent("""\
      sources = {
          'json': request.get_json(silent=True) or {},
          'json2': request.get_json(silent=True),
      }
      json = request.get_json(silent=True) or {}
      """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testNoSplittingBeforeEndingSubscriptBracket(self):
    unformatted_code = textwrap.dedent("""\
        if True:
          if True:
            status = cf.describe_stacks(StackName=stackname)[u'Stacks'][0][u'StackStatus']
        """)  # noqa
    expected_formatted_code = textwrap.dedent("""\
        if True:
          if True:
            status = cf.describe_stacks(
                StackName=stackname)[u'Stacks'][0][u'StackStatus']
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testNoSplittingOnSingleArgument(self):
    unformatted_code = textwrap.dedent("""\
        xxxxxxxxxxxxxx = (re.search(r'(\\d+\\.\\d+\\.\\d+\\.)\\d+',
                                    aaaaaaa.bbbbbbbbbbbb).group(1) +
                          re.search(r'\\d+\\.\\d+\\.\\d+\\.(\\d+)',
                                    ccccccc).group(1))
        xxxxxxxxxxxxxx = (re.search(r'(\\d+\\.\\d+\\.\\d+\\.)\\d+',
                                    aaaaaaa.bbbbbbbbbbbb).group(a.b) +
                          re.search(r'\\d+\\.\\d+\\.\\d+\\.(\\d+)',
                                    ccccccc).group(c.d))
        """)
    expected_formatted_code = textwrap.dedent("""\
        xxxxxxxxxxxxxx = (
            re.search(r'(\\d+\\.\\d+\\.\\d+\\.)\\d+', aaaaaaa.bbbbbbbbbbbb).group(1) +
            re.search(r'\\d+\\.\\d+\\.\\d+\\.(\\d+)', ccccccc).group(1))
        xxxxxxxxxxxxxx = (
            re.search(r'(\\d+\\.\\d+\\.\\d+\\.)\\d+', aaaaaaa.bbbbbbbbbbbb).group(a.b) +
            re.search(r'\\d+\\.\\d+\\.\\d+\\.(\\d+)', ccccccc).group(c.d))
        """)  # noqa
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testSplittingArraysSensibly(self):
    unformatted_code = textwrap.dedent("""\
        while True:
          while True:
            aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa = list['bbbbbbbbbbbbbbbbbbbbbbbbb'].split(',')
            aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa = list('bbbbbbbbbbbbbbbbbbbbbbbbb').split(',')
        """)  # noqa
    expected_formatted_code = textwrap.dedent("""\
        while True:
          while True:
            aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa = list[
                'bbbbbbbbbbbbbbbbbbbbbbbbb'].split(',')
            aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa = list(
                'bbbbbbbbbbbbbbbbbbbbbbbbb').split(',')
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testComprehensionForAndIf(self):
    unformatted_code = textwrap.dedent("""\
        class f:

          def __repr__(self):
            tokens_repr = ','.join(['{0}({1!r})'.format(tok.name, tok.value) for tok in self._tokens])
        """)  # noqa
    expected_formatted_code = textwrap.dedent("""\
        class f:

          def __repr__(self):
            tokens_repr = ','.join(
                ['{0}({1!r})'.format(tok.name, tok.value) for tok in self._tokens])
        """)  # noqa
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testFunctionCallArguments(self):
    unformatted_code = textwrap.dedent("""\
        def f():
          if True:
            pytree_utils.InsertNodesBefore(_CreateCommentsFromPrefix(
                comment_prefix, comment_lineno, comment_column,
                standalone=True), ancestor_at_indent)
            pytree_utils.InsertNodesBefore(_CreateCommentsFromPrefix(
                comment_prefix, comment_lineno, comment_column,
                standalone=True))
        """)
    expected_formatted_code = textwrap.dedent("""\
        def f():
          if True:
            pytree_utils.InsertNodesBefore(
                _CreateCommentsFromPrefix(
                    comment_prefix, comment_lineno, comment_column, standalone=True),
                ancestor_at_indent)
            pytree_utils.InsertNodesBefore(
                _CreateCommentsFromPrefix(
                    comment_prefix, comment_lineno, comment_column, standalone=True))
        """)  # noqa
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testBinaryOperators(self):
    unformatted_code = textwrap.dedent("""\
        a = b ** 37
        c = (20 ** -3) / (_GRID_ROWS ** (code_length - 10))
        """)
    expected_formatted_code = textwrap.dedent("""\
        a = b**37
        c = (20**-3) / (_GRID_ROWS**(code_length - 10))
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

    code = textwrap.dedent("""\
      def f():
        if True:
          if (self.stack[-1].split_before_closing_bracket and
              # FIXME(morbo): Use the 'matching_bracket' instead of this.
              # FIXME(morbo): Don't forget about tuples!
              current.value in ']}'):
            pass
      """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testContiguousList(self):
    code = textwrap.dedent("""\
      [retval1, retval2] = a_very_long_function(argument_1, argument2, argument_3,
                                                argument_4)
      """)  # noqa
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testArgsAndKwargsFormatting(self):
    code = textwrap.dedent("""\
      a(a=aaaaaaaaaaaaaaaaaaaaa,
        b=aaaaaaaaaaaaaaaaaaaaaaaa,
        c=aaaaaaaaaaaaaaaaaa,
        *d,
        **e)
      """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

    code = textwrap.dedent("""\
      def foo():
        return [
            Bar(xxx='some string',
                yyy='another long string',
                zzz='a third long string')
        ]
      """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testCommentColumnLimitOverflow(self):
    code = textwrap.dedent("""\
      def f():
        if True:
          TaskManager.get_tags = MagicMock(
              name='get_tags_mock',
              return_value=[157031694470475],
              # side_effect=[(157031694470475), (157031694470475),],
          )
      """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testMultilineLambdas(self):
    unformatted_code = textwrap.dedent("""\
        class SomeClass(object):
          do_something = True

          def succeeded(self, dddddddddddddd):
            d = defer.succeed(None)

            if self.do_something:
              d.addCallback(lambda _: self.aaaaaa.bbbbbbbbbbbbbbbb.cccccccccccccccccccccccccccccccc(dddddddddddddd))
            return d
        """)  # noqa
    expected_formatted_code = textwrap.dedent("""\
        class SomeClass(object):
          do_something = True

          def succeeded(self, dddddddddddddd):
            d = defer.succeed(None)

            if self.do_something:
              d.addCallback(lambda _: self.aaaaaa.bbbbbbbbbbbbbbbb.
                            cccccccccccccccccccccccccccccccc(dddddddddddddd))
            return d
        """)

    try:
      style.SetGlobalStyle(
          style.CreateStyleFromConfig(
              '{based_on_style: yapf, allow_multiline_lambdas: true}'))
      llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
      self.assertCodeEqual(expected_formatted_code,
                           reformatter.Reformat(llines))
    finally:
      style.SetGlobalStyle(style.CreateYapfStyle())

  def testMultilineDictionaryKeys(self):
    unformatted_code = textwrap.dedent("""\
        MAP_WITH_LONG_KEYS = {
            ('lorem ipsum', 'dolor sit amet'):
                1,
            ('consectetur adipiscing elit.', 'Vestibulum mauris justo, ornare eget dolor eget'):
                2,
            ('vehicula convallis nulla. Vestibulum dictum nisl in malesuada finibus.',):
                3
        }
        """)  # noqa
    expected_formatted_code = textwrap.dedent("""\
        MAP_WITH_LONG_KEYS = {
            ('lorem ipsum', 'dolor sit amet'):
                1,
            ('consectetur adipiscing elit.',
             'Vestibulum mauris justo, ornare eget dolor eget'):
                2,
            ('vehicula convallis nulla. Vestibulum dictum nisl in malesuada finibus.',):
                3
        }
        """)  # noqa

    try:
      style.SetGlobalStyle(
          style.CreateStyleFromConfig('{based_on_style: yapf, '
                                      'allow_multiline_dictionary_keys: true}'))
      llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
      self.assertCodeEqual(expected_formatted_code,
                           reformatter.Reformat(llines))
    finally:
      style.SetGlobalStyle(style.CreateYapfStyle())

  def testStableDictionaryFormatting(self):
    code = textwrap.dedent("""\
        class A(object):

          def method(self):
            filters = {
                'expressions': [{
                    'field': {
                        'search_field': {
                            'user_field': 'latest_party__number_of_guests'
                        },
                    }
                }]
            }
        """)  # noqa

    try:
      style.SetGlobalStyle(
          style.CreateStyleFromConfig('{based_on_style: pep8, indent_width: 2, '
                                      'continuation_indent_width: 4, '
                                      'indent_dictionary_value: True}'))

      llines = yapf_test_helper.ParseAndUnwrap(code)
      reformatted_code = reformatter.Reformat(llines)
      self.assertCodeEqual(code, reformatted_code)

      llines = yapf_test_helper.ParseAndUnwrap(reformatted_code)
      reformatted_code = reformatter.Reformat(llines)
      self.assertCodeEqual(code, reformatted_code)
    finally:
      style.SetGlobalStyle(style.CreateYapfStyle())

  def testStableInlinedDictionaryFormatting(self):
    try:
      style.SetGlobalStyle(style.CreatePEP8Style())
      unformatted_code = textwrap.dedent("""\
          def _():
              url = "http://{0}/axis-cgi/admin/param.cgi?{1}".format(
                  value, urllib.urlencode({'action': 'update', 'parameter': value}))
          """)  # noqa
      expected_formatted_code = textwrap.dedent("""\
          def _():
              url = "http://{0}/axis-cgi/admin/param.cgi?{1}".format(
                  value, urllib.urlencode({
                      'action': 'update',
                      'parameter': value
                  }))
          """)

      llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
      reformatted_code = reformatter.Reformat(llines)
      self.assertCodeEqual(expected_formatted_code, reformatted_code)

      llines = yapf_test_helper.ParseAndUnwrap(reformatted_code)
      reformatted_code = reformatter.Reformat(llines)
      self.assertCodeEqual(expected_formatted_code, reformatted_code)
    finally:
      style.SetGlobalStyle(style.CreateYapfStyle())

  def testDontSplitKeywordValueArguments(self):
    unformatted_code = textwrap.dedent("""\
        def mark_game_scored(gid):
          _connect.execute(_games.update().where(_games.c.gid == gid).values(
              scored=True))
        """)
    expected_formatted_code = textwrap.dedent("""\
        def mark_game_scored(gid):
          _connect.execute(
              _games.update().where(_games.c.gid == gid).values(scored=True))
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testDontAddBlankLineAfterMultilineString(self):
    code = textwrap.dedent("""\
      query = '''SELECT id
      FROM table
      WHERE day in {}'''
      days = ",".join(days)
      """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testFormattingListComprehensions(self):
    code = textwrap.dedent("""\
      def a():
        if True:
          if True:
            if True:
              columns = [
                  x for x, y in self._heap_this_is_very_long if x.route[0] == choice
              ]
              self._heap = [x for x in self._heap if x.route and x.route[0] == choice]
      """)  # noqa
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testNoSplittingWhenBinPacking(self):
    code = textwrap.dedent("""\
        a_very_long_function_name(
            long_argument_name_1=1,
            long_argument_name_2=2,
            long_argument_name_3=3,
            long_argument_name_4=4,
        )

        a_very_long_function_name(
            long_argument_name_1=1, long_argument_name_2=2, long_argument_name_3=3,
            long_argument_name_4=4
        )
        """)  # noqa

    try:
      style.SetGlobalStyle(
          style.CreateStyleFromConfig(
              '{based_on_style: pep8, indent_width: 2, '
              'continuation_indent_width: 4, indent_dictionary_value: True, '
              'dedent_closing_brackets: True, '
              'split_before_named_assigns: False}'))

      llines = yapf_test_helper.ParseAndUnwrap(code)
      reformatted_code = reformatter.Reformat(llines)
      self.assertCodeEqual(code, reformatted_code)

      llines = yapf_test_helper.ParseAndUnwrap(reformatted_code)
      reformatted_code = reformatter.Reformat(llines)
      self.assertCodeEqual(code, reformatted_code)
    finally:
      style.SetGlobalStyle(style.CreateYapfStyle())

  def testNotSplittingAfterSubscript(self):
    unformatted_code = textwrap.dedent("""\
        if not aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.b(c == d[
                'eeeeee']).ffffff():
          pass
        """)
    expected_formatted_code = textwrap.dedent("""\
        if not aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.b(
            c == d['eeeeee']).ffffff():
          pass
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testSplittingOneArgumentList(self):
    unformatted_code = textwrap.dedent("""\
        def _():
          if True:
            if True:
              if True:
                if True:
                  if True:
                    boxes[id_] = np.concatenate((points.min(axis=0), qoints.max(axis=0)))
        """)  # noqa
    expected_formatted_code = textwrap.dedent("""\
        def _():
          if True:
            if True:
              if True:
                if True:
                  if True:
                    boxes[id_] = np.concatenate(
                        (points.min(axis=0), qoints.max(axis=0)))
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testSplittingBeforeFirstElementListArgument(self):
    unformatted_code = textwrap.dedent("""\
        class _():
          @classmethod
          def _pack_results_for_constraint_or(cls, combination, constraints):
            if True:
              if True:
                if True:
                  return cls._create_investigation_result(
                          (
                                  clue for clue in combination if not clue == Verifier.UNMATCHED
                          ), constraints, InvestigationResult.OR
                  )
        """)  # noqa
    expected_formatted_code = textwrap.dedent("""\
        class _():

          @classmethod
          def _pack_results_for_constraint_or(cls, combination, constraints):
            if True:
              if True:
                if True:
                  return cls._create_investigation_result(
                      (clue for clue in combination if not clue == Verifier.UNMATCHED),
                      constraints, InvestigationResult.OR)
        """)  # noqa
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testSplittingArgumentsTerminatedByComma(self):
    unformatted_code = textwrap.dedent("""\
        function_name(argument_name_1=1, argument_name_2=2, argument_name_3=3)

        function_name(argument_name_1=1, argument_name_2=2, argument_name_3=3,)

        a_very_long_function_name(long_argument_name_1=1, long_argument_name_2=2, long_argument_name_3=3, long_argument_name_4=4)

        a_very_long_function_name(long_argument_name_1, long_argument_name_2, long_argument_name_3, long_argument_name_4,)

        r =f0 (1,  2,3,)
        """)  # noqa
    expected_formatted_code = textwrap.dedent("""\
        function_name(argument_name_1=1, argument_name_2=2, argument_name_3=3)

        function_name(
            argument_name_1=1,
            argument_name_2=2,
            argument_name_3=3,
        )

        a_very_long_function_name(
            long_argument_name_1=1,
            long_argument_name_2=2,
            long_argument_name_3=3,
            long_argument_name_4=4)

        a_very_long_function_name(
            long_argument_name_1,
            long_argument_name_2,
            long_argument_name_3,
            long_argument_name_4,
        )

        r = f0(
            1,
            2,
            3,
        )
        """)

    try:
      style.SetGlobalStyle(
          style.CreateStyleFromConfig(
              '{based_on_style: yapf, '
              'split_arguments_when_comma_terminated: True}'))

      llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
      reformatted_code = reformatter.Reformat(llines)
      self.assertCodeEqual(expected_formatted_code, reformatted_code)

      llines = yapf_test_helper.ParseAndUnwrap(reformatted_code)
      reformatted_code = reformatter.Reformat(llines)
      self.assertCodeEqual(expected_formatted_code, reformatted_code)
    finally:
      style.SetGlobalStyle(style.CreateYapfStyle())

  def testImportAsList(self):
    code = textwrap.dedent("""\
        from toto import titi, tata, tutu  # noqa
        from toto import titi, tata, tutu
        from toto import (titi, tata, tutu)
        """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testDictionaryValuesOnOwnLines(self):
    unformatted_code = textwrap.dedent("""\
        a = {
        'aaaaaaaaaaaaaaaaaaaaaaaa':
            Check('ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ', '=', True),
        'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbb':
            Check('YYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYY', '=', True),
        'ccccccccccccccc':
            Check('XXXXXXXXXXXXXXXXXXX', '!=', 'SUSPENDED'),
        'dddddddddddddddddddddddddddddd':
            Check('WWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWW', '=', False),
        'eeeeeeeeeeeeeeeeeeeeeeeeeeeee':
            Check('VVVVVVVVVVVVVVVVVVVVVVVVVVVVVV', '=', False),
        'ffffffffffffffffffffffffff':
            Check('UUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUU', '=', True),
        'ggggggggggggggggg':
            Check('TTTTTTTTTTTTTTTTTTTTTTTTTTTTTT', '=', True),
        'hhhhhhhhhhhhhhhhhhhhhhhhhhhhhhh':
            Check('SSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSS', '=', True),
        'iiiiiiiiiiiiiiiiiiiiiiii':
            Check('RRRRRRRRRRRRRRRRRRRRRRRRRRR', '=', True),
        'jjjjjjjjjjjjjjjjjjjjjjjjjj':
            Check('QQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQ', '=', False),
        }
        """)
    expected_formatted_code = textwrap.dedent("""\
        a = {
            'aaaaaaaaaaaaaaaaaaaaaaaa':
                Check('ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ', '=', True),
            'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbb':
                Check('YYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYY', '=', True),
            'ccccccccccccccc':
                Check('XXXXXXXXXXXXXXXXXXX', '!=', 'SUSPENDED'),
            'dddddddddddddddddddddddddddddd':
                Check('WWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWW', '=', False),
            'eeeeeeeeeeeeeeeeeeeeeeeeeeeee':
                Check('VVVVVVVVVVVVVVVVVVVVVVVVVVVVVV', '=', False),
            'ffffffffffffffffffffffffff':
                Check('UUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUU', '=', True),
            'ggggggggggggggggg':
                Check('TTTTTTTTTTTTTTTTTTTTTTTTTTTTTT', '=', True),
            'hhhhhhhhhhhhhhhhhhhhhhhhhhhhhhh':
                Check('SSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSS', '=', True),
            'iiiiiiiiiiiiiiiiiiiiiiii':
                Check('RRRRRRRRRRRRRRRRRRRRRRRRRRR', '=', True),
            'jjjjjjjjjjjjjjjjjjjjjjjjjj':
                Check('QQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQ', '=', False),
        }
        """)  # noqa
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testDictionaryOnOwnLine(self):
    unformatted_code = textwrap.dedent("""\
        doc = test_utils.CreateTestDocumentViaController(
            content={ 'a': 'b' },
            branch_key=branch.key,
            collection_key=collection.key)
        """)
    expected_formatted_code = textwrap.dedent("""\
        doc = test_utils.CreateTestDocumentViaController(
            content={'a': 'b'}, branch_key=branch.key, collection_key=collection.key)
        """)  # noqa
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

    unformatted_code = textwrap.dedent("""\
        doc = test_utils.CreateTestDocumentViaController(
            content={ 'a': 'b' },
            branch_key=branch.key,
            collection_key=collection.key,
            collection_key2=collection.key2)
        """)
    expected_formatted_code = textwrap.dedent("""\
        doc = test_utils.CreateTestDocumentViaController(
            content={'a': 'b'},
            branch_key=branch.key,
            collection_key=collection.key,
            collection_key2=collection.key2)
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testNestedListsInDictionary(self):
    unformatted_code = textwrap.dedent("""\
        _A = {
            'cccccccccc': ('^^1',),
            'rrrrrrrrrrrrrrrrrrrrrrrrr': ('^7913',  # AAAAAAAAAAAAAA.
                                         ),
            'eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee': ('^6242',  # BBBBBBBBBBBBBBB.
                                                  ),
            'vvvvvvvvvvvvvvvvvvv': ('^27959',  # CCCCCCCCCCCCCCCCCC.
                                    '^19746',  # DDDDDDDDDDDDDDDDDDDDDDD.
                                    '^22907',  # EEEEEEEEEEEEEEEEEEEEEEEE.
                                    '^21098',  # FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF.
                                    '^22826',  # GGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGG.
                                    '^22769',  # HHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHH.
                                    '^22935',  # IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII.
                                    '^3982',  # JJJJJJJJJJJJJ.
                                   ),
            'uuuuuuuuuuuu': ('^19745',  # LLLLLLLLLLLLLLLLLLLLLLLLLL.
                             '^21324',  # MMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMM.
                             '^22831',  # NNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNN.
                             '^17081',  # OOOOOOOOOOOOOOOOOOOOO.
                            ),
            'eeeeeeeeeeeeee': (
                '^9416',  # Reporter email. Not necessarily the reporter.
                '^^3',  # This appears to be the raw email field.
            ),
            'cccccccccc': ('^21109',  # PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP.
                          ),
        }
        """)  # noqa
    expected_formatted_code = textwrap.dedent("""\
        _A = {
            'cccccccccc': ('^^1',),
            'rrrrrrrrrrrrrrrrrrrrrrrrr': (
                '^7913',  # AAAAAAAAAAAAAA.
            ),
            'eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee': (
                '^6242',  # BBBBBBBBBBBBBBB.
            ),
            'vvvvvvvvvvvvvvvvvvv': (
                '^27959',  # CCCCCCCCCCCCCCCCCC.
                '^19746',  # DDDDDDDDDDDDDDDDDDDDDDD.
                '^22907',  # EEEEEEEEEEEEEEEEEEEEEEEE.
                '^21098',  # FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF.
                '^22826',  # GGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGG.
                '^22769',  # HHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHH.
                '^22935',  # IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII.
                '^3982',  # JJJJJJJJJJJJJ.
            ),
            'uuuuuuuuuuuu': (
                '^19745',  # LLLLLLLLLLLLLLLLLLLLLLLLLL.
                '^21324',  # MMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMM.
                '^22831',  # NNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNN.
                '^17081',  # OOOOOOOOOOOOOOOOOOOOO.
            ),
            'eeeeeeeeeeeeee': (
                '^9416',  # Reporter email. Not necessarily the reporter.
                '^^3',  # This appears to be the raw email field.
            ),
            'cccccccccc': (
                '^21109',  # PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP.
            ),
        }
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testNestedDictionary(self):
    unformatted_code = textwrap.dedent("""\
        class _():
          def _():
            breadcrumbs = [{'name': 'Admin',
                            'url': url_for(".home")},
                           {'title': title},]
            breadcrumbs = [{'name': 'Admin',
                            'url': url_for(".home")},
                           {'title': title}]
        """)
    expected_formatted_code = textwrap.dedent("""\
        class _():
          def _():
            breadcrumbs = [
                {
                    'name': 'Admin',
                    'url': url_for(".home")
                },
                {
                    'title': title
                },
            ]
            breadcrumbs = [{'name': 'Admin', 'url': url_for(".home")}, {'title': title}]
        """)  # noqa
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testDictionaryElementsOnOneLine(self):
    code = textwrap.dedent("""\
        class _():

          @mock.patch.dict(
              os.environ,
              {'HTTP_' + xsrf._XSRF_TOKEN_HEADER.replace('-', '_'): 'atoken'})
          def _():
            pass


        AAAAAAAAAAAAAAAAAAAAAAAA = {
            Environment.XXXXXXXXXX: 'some text more text even more tex',
            Environment.YYYYYYY: 'some text more text even more text yet ag',
            Environment.ZZZZZZZZZZZ: 'some text more text even more text yet again tex',
        }
        """)  # noqa
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testNotInParams(self):
    unformatted_code = textwrap.dedent("""\
        list("a long line to break the line. a long line to break the brk a long lin", not True)
        """)  # noqa
    expected_code = textwrap.dedent("""\
        list("a long line to break the line. a long line to break the brk a long lin",
             not True)
        """)  # noqa
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_code, reformatter.Reformat(llines))

  def testNamedAssignNotAtEndOfLine(self):
    unformatted_code = textwrap.dedent("""\
        def _():
          if True:
            with py3compat.open_with_encoding(filename, mode='w',
                                              encoding=encoding) as fd:
              pass
        """)
    expected_code = textwrap.dedent("""\
        def _():
          if True:
            with py3compat.open_with_encoding(
                filename, mode='w', encoding=encoding) as fd:
              pass
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_code, reformatter.Reformat(llines))

  def testBlankLineBeforeClassDocstring(self):
    unformatted_code = textwrap.dedent('''\
        class A:

          """Does something.

          Also, here are some details.
          """

          def __init__(self):
            pass
        ''')
    expected_code = textwrap.dedent('''\
        class A:
          """Does something.

          Also, here are some details.
          """

          def __init__(self):
            pass
        ''')
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_code, reformatter.Reformat(llines))

    unformatted_code = textwrap.dedent('''\
        class A:

          """Does something.

          Also, here are some details.
          """

          def __init__(self):
            pass
        ''')
    expected_formatted_code = textwrap.dedent('''\
        class A:

          """Does something.

          Also, here are some details.
          """

          def __init__(self):
            pass
        ''')

    try:
      style.SetGlobalStyle(
          style.CreateStyleFromConfig(
              '{based_on_style: yapf, '
              'blank_line_before_class_docstring: True}'))

      llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
      self.assertCodeEqual(expected_formatted_code,
                           reformatter.Reformat(llines))
    finally:
      style.SetGlobalStyle(style.CreateYapfStyle())

  def testBlankLineBeforeModuleDocstring(self):
    unformatted_code = textwrap.dedent('''\
        #!/usr/bin/env python
        # -*- coding: utf-8 name> -*-

        """Some module docstring."""


        def foobar():
          pass
        ''')
    expected_code = textwrap.dedent('''\
        #!/usr/bin/env python
        # -*- coding: utf-8 name> -*-
        """Some module docstring."""


        def foobar():
          pass
        ''')
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_code, reformatter.Reformat(llines))

    unformatted_code = textwrap.dedent('''\
        #!/usr/bin/env python
        # -*- coding: utf-8 name> -*-
        """Some module docstring."""


        def foobar():
            pass
        ''')
    expected_formatted_code = textwrap.dedent('''\
        #!/usr/bin/env python
        # -*- coding: utf-8 name> -*-

        """Some module docstring."""


        def foobar():
            pass
        ''')

    try:
      style.SetGlobalStyle(
          style.CreateStyleFromConfig(
              '{based_on_style: pep8, '
              'blank_line_before_module_docstring: True}'))

      llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
      self.assertCodeEqual(expected_formatted_code,
                           reformatter.Reformat(llines))
    finally:
      style.SetGlobalStyle(style.CreateYapfStyle())

  def testTupleCohesion(self):
    unformatted_code = textwrap.dedent("""\
        def f():
          this_is_a_very_long_function_name(an_extremely_long_variable_name, (
              'a string that may be too long %s' % 'M15'))
        """)
    expected_code = textwrap.dedent("""\
        def f():
          this_is_a_very_long_function_name(
              an_extremely_long_variable_name,
              ('a string that may be too long %s' % 'M15'))
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_code, reformatter.Reformat(llines))

  def testSubscriptExpression(self):
    code = textwrap.dedent("""\
        foo = d[not a]
        """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testListWithFunctionCalls(self):
    unformatted_code = textwrap.dedent("""\
        def foo():
          return [
              Bar(
                  xxx='some string',
                  yyy='another long string',
                  zzz='a third long string'), Bar(
                      xxx='some string',
                      yyy='another long string',
                      zzz='a third long string')
          ]
        """)
    expected_code = textwrap.dedent("""\
        def foo():
          return [
              Bar(xxx='some string',
                  yyy='another long string',
                  zzz='a third long string'),
              Bar(xxx='some string',
                  yyy='another long string',
                  zzz='a third long string')
          ]
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_code, reformatter.Reformat(llines))

  def testEllipses(self):
    unformatted_code = textwrap.dedent("""\
        X=...
        Y = X if ... else X
        """)
    expected_code = textwrap.dedent("""\
        X = ...
        Y = X if ... else X
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_code, reformatter.Reformat(llines))

  def testPseudoParens(self):
    unformatted_code = """\
my_dict = {
    'key':  # Some comment about the key
        {'nested_key': 1, },
}
"""
    expected_code = """\
my_dict = {
    'key':  # Some comment about the key
        {
            'nested_key': 1,
        },
}
"""
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_code, reformatter.Reformat(llines))

  def testSplittingBeforeFirstArgumentOnFunctionCall(self):
    """Tests split_before_first_argument on a function call."""
    unformatted_code = textwrap.dedent("""\
        a_very_long_function_name("long string with formatting {0:s}".format(
            "mystring"))
        """)
    expected_formatted_code = textwrap.dedent("""\
        a_very_long_function_name(
            "long string with formatting {0:s}".format("mystring"))
        """)

    try:
      style.SetGlobalStyle(
          style.CreateStyleFromConfig(
              '{based_on_style: yapf, split_before_first_argument: True}'))

      llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
      self.assertCodeEqual(expected_formatted_code,
                           reformatter.Reformat(llines))
    finally:
      style.SetGlobalStyle(style.CreateYapfStyle())

  def testSplittingBeforeFirstArgumentOnFunctionDefinition(self):
    """Tests split_before_first_argument on a function definition."""
    unformatted_code = textwrap.dedent("""\
        def _GetNumberOfSecondsFromElements(year, month, day, hours,
                                            minutes, seconds, microseconds):
          return
        """)
    expected_formatted_code = textwrap.dedent("""\
        def _GetNumberOfSecondsFromElements(
            year, month, day, hours, minutes, seconds, microseconds):
          return
        """)

    try:
      style.SetGlobalStyle(
          style.CreateStyleFromConfig(
              '{based_on_style: yapf, split_before_first_argument: True}'))

      llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
      self.assertCodeEqual(expected_formatted_code,
                           reformatter.Reformat(llines))
    finally:
      style.SetGlobalStyle(style.CreateYapfStyle())

  def testSplittingBeforeFirstArgumentOnCompoundStatement(self):
    """Tests split_before_first_argument on a compound statement."""
    unformatted_code = textwrap.dedent("""\
        if (long_argument_name_1 == 1 or
            long_argument_name_2 == 2 or
            long_argument_name_3 == 3 or
            long_argument_name_4 == 4):
          pass
        """)
    expected_formatted_code = textwrap.dedent("""\
        if (long_argument_name_1 == 1 or long_argument_name_2 == 2 or
            long_argument_name_3 == 3 or long_argument_name_4 == 4):
          pass
        """)

    try:
      style.SetGlobalStyle(
          style.CreateStyleFromConfig(
              '{based_on_style: yapf, split_before_first_argument: True}'))

      llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
      self.assertCodeEqual(expected_formatted_code,
                           reformatter.Reformat(llines))
    finally:
      style.SetGlobalStyle(style.CreateYapfStyle())

  def testCoalesceBracketsOnDict(self):
    """Tests coalesce_brackets on a dictionary."""
    unformatted_code = textwrap.dedent("""\
        date_time_values = (
            {
                u'year': year,
                u'month': month,
                u'day_of_month': day_of_month,
                u'hours': hours,
                u'minutes': minutes,
                u'seconds': seconds
            }
        )
        """)
    expected_formatted_code = textwrap.dedent("""\
        date_time_values = ({
            u'year': year,
            u'month': month,
            u'day_of_month': day_of_month,
            u'hours': hours,
            u'minutes': minutes,
            u'seconds': seconds
        })
        """)

    try:
      style.SetGlobalStyle(
          style.CreateStyleFromConfig(
              '{based_on_style: yapf, coalesce_brackets: True}'))

      llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
      self.assertCodeEqual(expected_formatted_code,
                           reformatter.Reformat(llines))
    finally:
      style.SetGlobalStyle(style.CreateYapfStyle())

  def testSplitAfterComment(self):
    code = textwrap.dedent("""\
        if __name__ == "__main__":
          with another_resource:
            account = {
                "validUntil":
                    int(time() + (6 * 7 * 24 * 60 * 60))  # in 6 weeks time
            }
        """)

    try:
      style.SetGlobalStyle(
          style.CreateStyleFromConfig(
              '{based_on_style: yapf, coalesce_brackets: True, '
              'dedent_closing_brackets: true}'))
      llines = yapf_test_helper.ParseAndUnwrap(code)
      self.assertCodeEqual(code, reformatter.Reformat(llines))
    finally:
      style.SetGlobalStyle(style.CreateYapfStyle())

  @unittest.skipUnless(not py3compat.PY3, 'Requires Python 2.7')
  def testAsyncAsNonKeyword(self):
    try:
      style.SetGlobalStyle(style.CreatePEP8Style())

      # In Python 2, async may be used as a non-keyword identifier.
      code = textwrap.dedent("""\
          from util import async


          class A(object):

              def foo(self):
                  async.run()
          """)

      llines = yapf_test_helper.ParseAndUnwrap(code)
      self.assertCodeEqual(code, reformatter.Reformat(llines))
    finally:
      style.SetGlobalStyle(style.CreateYapfStyle())

  def testDisableEndingCommaHeuristic(self):
    code = textwrap.dedent("""\
        x = [1, 2, 3, 4, 5, 6, 7,]
        """)

    try:
      style.SetGlobalStyle(
          style.CreateStyleFromConfig('{based_on_style: yapf,'
                                      ' disable_ending_comma_heuristic: True}'))

      llines = yapf_test_helper.ParseAndUnwrap(code)
      self.assertCodeEqual(code, reformatter.Reformat(llines))
    finally:
      style.SetGlobalStyle(style.CreateYapfStyle())

  def testDedentClosingBracketsWithTypeAnnotationExceedingLineLength(self):
    unformatted_code = textwrap.dedent("""\
        def function(first_argument_xxxxxxxxxxxxxxxx=(0,), second_argument=None) -> None:
          pass


        def function(first_argument_xxxxxxxxxxxxxxxxxxxxxxx=(0,), second_argument=None) -> None:
          pass
        """)  # noqa
    expected_formatted_code = textwrap.dedent("""\
        def function(
            first_argument_xxxxxxxxxxxxxxxx=(0,), second_argument=None
        ) -> None:
          pass


        def function(
            first_argument_xxxxxxxxxxxxxxxxxxxxxxx=(0,), second_argument=None
        ) -> None:
          pass
        """)  # noqa

    try:
      style.SetGlobalStyle(
          style.CreateStyleFromConfig('{based_on_style: yapf,'
                                      ' dedent_closing_brackets: True}'))

      llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
      self.assertCodeEqual(expected_formatted_code,
                           reformatter.Reformat(llines))
    finally:
      style.SetGlobalStyle(style.CreateYapfStyle())

  def testIndentClosingBracketsWithTypeAnnotationExceedingLineLength(self):
    unformatted_code = textwrap.dedent("""\
        def function(first_argument_xxxxxxxxxxxxxxxx=(0,), second_argument=None) -> None:
          pass


        def function(first_argument_xxxxxxxxxxxxxxxxxxxxxxx=(0,), second_argument=None) -> None:
          pass
        """)  # noqa
    expected_formatted_code = textwrap.dedent("""\
        def function(
            first_argument_xxxxxxxxxxxxxxxx=(0,), second_argument=None
            ) -> None:
          pass


        def function(
            first_argument_xxxxxxxxxxxxxxxxxxxxxxx=(0,), second_argument=None
            ) -> None:
          pass
        """)  # noqa

    try:
      style.SetGlobalStyle(
          style.CreateStyleFromConfig('{based_on_style: yapf,'
                                      ' indent_closing_brackets: True}'))

      llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
      self.assertCodeEqual(expected_formatted_code,
                           reformatter.Reformat(llines))
    finally:
      style.SetGlobalStyle(style.CreateYapfStyle())

  def testIndentClosingBracketsInFunctionCall(self):
    unformatted_code = textwrap.dedent("""\
        def function(first_argument_xxxxxxxxxxxxxxxx=(0,), second_argument=None, third_and_final_argument=True):
          pass


        def function(first_argument_xxxxxxxxxxxxxxxxxxxxxxx=(0,), second_and_last_argument=None):
          pass
        """)  # noqa
    expected_formatted_code = textwrap.dedent("""\
        def function(
            first_argument_xxxxxxxxxxxxxxxx=(0,),
            second_argument=None,
            third_and_final_argument=True
            ):
          pass


        def function(
            first_argument_xxxxxxxxxxxxxxxxxxxxxxx=(0,), second_and_last_argument=None
            ):
          pass
        """)  # noqa

    try:
      style.SetGlobalStyle(
          style.CreateStyleFromConfig('{based_on_style: yapf,'
                                      ' indent_closing_brackets: True}'))

      llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
      self.assertCodeEqual(expected_formatted_code,
                           reformatter.Reformat(llines))
    finally:
      style.SetGlobalStyle(style.CreateYapfStyle())

  def testIndentClosingBracketsInTuple(self):
    unformatted_code = textwrap.dedent("""\
        def function():
          some_var = ('a long element', 'another long element', 'short element', 'really really long element')
          return True

        def function():
          some_var = ('a couple', 'small', 'elemens')
          return False
        """)  # noqa
    expected_formatted_code = textwrap.dedent("""\
        def function():
          some_var = (
              'a long element', 'another long element', 'short element',
              'really really long element'
              )
          return True


        def function():
          some_var = ('a couple', 'small', 'elemens')
          return False
        """)  # noqa

    try:
      style.SetGlobalStyle(
          style.CreateStyleFromConfig('{based_on_style: yapf,'
                                      ' indent_closing_brackets: True}'))

      llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
      self.assertCodeEqual(expected_formatted_code,
                           reformatter.Reformat(llines))
    finally:
      style.SetGlobalStyle(style.CreateYapfStyle())

  def testIndentClosingBracketsInList(self):
    unformatted_code = textwrap.dedent("""\
        def function():
          some_var = ['a long element', 'another long element', 'short element', 'really really long element']
          return True

        def function():
          some_var = ['a couple', 'small', 'elemens']
          return False
        """)  # noqa
    expected_formatted_code = textwrap.dedent("""\
        def function():
          some_var = [
              'a long element', 'another long element', 'short element',
              'really really long element'
              ]
          return True


        def function():
          some_var = ['a couple', 'small', 'elemens']
          return False
        """)

    try:
      style.SetGlobalStyle(
          style.CreateStyleFromConfig('{based_on_style: yapf,'
                                      ' indent_closing_brackets: True}'))

      llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
      self.assertCodeEqual(expected_formatted_code,
                           reformatter.Reformat(llines))
    finally:
      style.SetGlobalStyle(style.CreateYapfStyle())

  def testIndentClosingBracketsInDict(self):
    unformatted_code = textwrap.dedent("""\
        def function():
          some_var = {1: ('a long element', 'and another really really long element that is really really amazingly long'), 2: 'another long element', 3: 'short element', 4: 'really really long element'}
          return True

        def function():
          some_var = {1: 'a couple', 2: 'small', 3: 'elemens'}
          return False
        """)  # noqa
    expected_formatted_code = textwrap.dedent("""\
        def function():
          some_var = {
              1:
                  (
                      'a long element',
                      'and another really really long element that is really really amazingly long'
                      ),
              2: 'another long element',
              3: 'short element',
              4: 'really really long element'
              }
          return True


        def function():
          some_var = {1: 'a couple', 2: 'small', 3: 'elemens'}
          return False
        """)  # noqa

    try:
      style.SetGlobalStyle(
          style.CreateStyleFromConfig('{based_on_style: yapf,'
                                      ' indent_closing_brackets: True}'))

      llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
      self.assertCodeEqual(expected_formatted_code,
                           reformatter.Reformat(llines))
    finally:
      style.SetGlobalStyle(style.CreateYapfStyle())

  def testMultipleDictionariesInList(self):
    unformatted_code = textwrap.dedent("""\
        class A:
            def b():
                d = {
                    "123456": [
                        {
                            "12": "aa"
                        },
                        {
                            "12": "bb"
                        },
                        {
                            "12": "cc",
                            "1234567890": {
                                "1234567": [{
                                    "12": "dd",
                                    "12345": "text 1"
                                }, {
                                    "12": "ee",
                                    "12345": "text 2"
                                }]
                            }
                        }
                    ]
                }
        """)
    expected_formatted_code = textwrap.dedent("""\
        class A:

          def b():
            d = {
                "123456": [{
                    "12": "aa"
                }, {
                    "12": "bb"
                }, {
                    "12": "cc",
                    "1234567890": {
                        "1234567": [{
                            "12": "dd",
                            "12345": "text 1"
                        }, {
                            "12": "ee",
                            "12345": "text 2"
                        }]
                    }
                }]
            }
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testForceMultilineDict_True(self):
    try:
      style.SetGlobalStyle(
          style.CreateStyleFromConfig('{force_multiline_dict: true}'))
      unformatted_code = textwrap.dedent(
          "responseDict = {'childDict': {'spam': 'eggs'}}\n")
      llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
      actual = reformatter.Reformat(llines)
      expected = textwrap.dedent("""\
        responseDict = {
            'childDict': {
                'spam': 'eggs'
            }
        }
      """)
      self.assertCodeEqual(expected, actual)
    finally:
      style.SetGlobalStyle(style.CreateYapfStyle())

  def testForceMultilineDict_False(self):
    try:
      style.SetGlobalStyle(
          style.CreateStyleFromConfig('{force_multiline_dict: false}'))
      unformatted_code = textwrap.dedent("""\
        responseDict = {'childDict': {'spam': 'eggs'}}
      """)
      expected_formatted_code = unformatted_code
      llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
      self.assertCodeEqual(expected_formatted_code,
                           reformatter.Reformat(llines))
    finally:
      style.SetGlobalStyle(style.CreateYapfStyle())

  @unittest.skipUnless(py3compat.PY38, 'Requires Python 3.8')
  def testWalrus(self):
    unformatted_code = textwrap.dedent("""\
      if (x  :=  len([1]*1000)>100):
        print(f'{x} is pretty big' )
    """)
    expected = textwrap.dedent("""\
      if (x := len([1] * 1000) > 100):
        print(f'{x} is pretty big')
    """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected, reformatter.Reformat(llines))


if __name__ == '__main__':
  unittest.main()
