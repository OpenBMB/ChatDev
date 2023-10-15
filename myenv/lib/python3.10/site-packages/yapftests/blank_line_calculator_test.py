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
"""Tests for yapf.blank_line_calculator."""

import textwrap
import unittest

from yapf.yapflib import reformatter
from yapf.yapflib import style
from yapf.yapflib import yapf_api

from yapftests import yapf_test_helper


class BasicBlankLineCalculatorTest(yapf_test_helper.YAPFTest):

  @classmethod
  def setUpClass(cls):
    style.SetGlobalStyle(style.CreateYapfStyle())

  def testDecorators(self):
    unformatted_code = textwrap.dedent("""\
        @bork()

        def foo():
          pass
        """)
    expected_formatted_code = textwrap.dedent("""\
        @bork()
        def foo():
          pass
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testComplexDecorators(self):
    unformatted_code = textwrap.dedent("""\
        import sys
        @bork()

        def foo():
          pass
        @fork()

        class moo(object):
          @bar()
          @baz()

          def method(self):
            pass
        """)
    expected_formatted_code = textwrap.dedent("""\
        import sys


        @bork()
        def foo():
          pass


        @fork()
        class moo(object):

          @bar()
          @baz()
          def method(self):
            pass
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testCodeAfterFunctionsAndClasses(self):
    unformatted_code = textwrap.dedent("""\
        def foo():
          pass
        top_level_code = True
        class moo(object):
          def method_1(self):
            pass
          ivar_a = 42
          ivar_b = 13
          def method_2(self):
            pass
        try:
          raise Error
        except Error as error:
          pass
        """)
    expected_formatted_code = textwrap.dedent("""\
        def foo():
          pass


        top_level_code = True


        class moo(object):

          def method_1(self):
            pass

          ivar_a = 42
          ivar_b = 13

          def method_2(self):
            pass


        try:
          raise Error
        except Error as error:
          pass
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testCommentSpacing(self):
    unformatted_code = textwrap.dedent("""\
        # This is the first comment
        # And it's multiline

        # This is the second comment

        def foo():
          pass

        # multiline before a
        # class definition

        # This is the second comment

        class qux(object):
          pass


        # An attached comment.
        class bar(object):
          '''class docstring'''
          # Comment attached to
          # function
          def foo(self):
            '''Another docstring.'''
            # Another multiline
            # comment
            pass
        """)
    expected_formatted_code = textwrap.dedent("""\
        # This is the first comment
        # And it's multiline

        # This is the second comment


        def foo():
          pass


        # multiline before a
        # class definition

        # This is the second comment


        class qux(object):
          pass


        # An attached comment.
        class bar(object):
          '''class docstring'''

          # Comment attached to
          # function
          def foo(self):
            '''Another docstring.'''
            # Another multiline
            # comment
            pass
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testCommentBeforeMethod(self):
    code = textwrap.dedent("""\
        class foo(object):

          # pylint: disable=invalid-name
          def f(self):
            pass
        """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testCommentsBeforeClassDefs(self):
    code = textwrap.dedent('''\
        """Test."""

        # Comment


        class Foo(object):
          pass
        ''')
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testCommentsBeforeDecorator(self):
    code = textwrap.dedent("""\
        # The @foo operator adds bork to a().
        @foo()
        def a():
          pass
        """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

    code = textwrap.dedent("""\
        # Hello world


        @foo()
        def a():
          pass
        """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testCommentsAfterDecorator(self):
    code = textwrap.dedent("""\
        class _():

          def _():
            pass

          @pytest.mark.xfail(reason="#709 and #710")
          # also
          #@pytest.mark.xfail(setuptools.tests.is_ascii,
          #    reason="https://github.com/pypa/setuptools/issues/706")
          def test_unicode_filename_in_sdist(self, sdist_unicode, tmpdir, monkeypatch):
            pass
        """)  # noqa
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testInnerClasses(self):
    unformatted_code = textwrap.dedent("""\
      class DeployAPIClient(object):
          class Error(Exception): pass

          class TaskValidationError(Error): pass

          class DeployAPIHTTPError(Error): pass
        """)
    expected_formatted_code = textwrap.dedent("""\
      class DeployAPIClient(object):

        class Error(Exception):
          pass

        class TaskValidationError(Error):
          pass

        class DeployAPIHTTPError(Error):
          pass
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testLinesOnRangeBoundary(self):
    unformatted_code = textwrap.dedent(u"""\
        def A():
          pass

        def B():  # 4
          pass  # 5

        def C():
          pass
        def D():  # 9
          pass  # 10
        def E():
          pass
        """)
    expected_formatted_code = textwrap.dedent(u"""\
        def A():
          pass


        def B():  # 4
          pass  # 5

        def C():
          pass


        def D():  # 9
          pass  # 10
        def E():
          pass
        """)
    code, changed = yapf_api.FormatCode(
        unformatted_code, lines=[(4, 5), (9, 10)])
    self.assertCodeEqual(expected_formatted_code, code)
    self.assertTrue(changed)

  def testLinesRangeBoundaryNotOutside(self):
    unformatted_code = textwrap.dedent(u"""\
        def A():
          pass



        def B():  # 6
          pass  # 7



        def C():
          pass
        """)
    expected_formatted_code = textwrap.dedent(u"""\
        def A():
          pass



        def B():  # 6
          pass  # 7



        def C():
          pass
        """)
    code, changed = yapf_api.FormatCode(unformatted_code, lines=[(6, 7)])
    self.assertCodeEqual(expected_formatted_code, code)
    self.assertFalse(changed)

  def testLinesRangeRemove(self):
    unformatted_code = textwrap.dedent(u"""\
        def A():
          pass



        def B():  # 6
          pass  # 7




        def C():
          pass
        """)
    expected_formatted_code = textwrap.dedent(u"""\
        def A():
          pass


        def B():  # 6
          pass  # 7




        def C():
          pass
        """)
    code, changed = yapf_api.FormatCode(unformatted_code, lines=[(5, 9)])
    self.assertCodeEqual(expected_formatted_code, code)
    self.assertTrue(changed)

  def testLinesRangeRemoveSome(self):
    unformatted_code = textwrap.dedent(u"""\
        def A():
          pass




        def B():  # 7
          pass  # 8




        def C():
          pass
        """)
    expected_formatted_code = textwrap.dedent(u"""\
        def A():
          pass



        def B():  # 7
          pass  # 8




        def C():
          pass
        """)
    code, changed = yapf_api.FormatCode(unformatted_code, lines=[(6, 9)])
    self.assertCodeEqual(expected_formatted_code, code)
    self.assertTrue(changed)


if __name__ == '__main__':
  unittest.main()
