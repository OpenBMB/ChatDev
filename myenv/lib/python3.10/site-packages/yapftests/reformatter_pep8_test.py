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
"""PEP8 tests for yapf.reformatter."""

import textwrap
import unittest

from yapf.yapflib import py3compat
from yapf.yapflib import reformatter
from yapf.yapflib import style

from yapftests import yapf_test_helper


class TestsForPEP8Style(yapf_test_helper.YAPFTest):

  @classmethod
  def setUpClass(cls):  # pylint: disable=g-missing-super-call
    style.SetGlobalStyle(style.CreatePEP8Style())

  def testIndent4(self):
    unformatted_code = textwrap.dedent("""\
        if a+b:
          pass
        """)
    expected_formatted_code = textwrap.dedent("""\
        if a + b:
            pass
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testSingleLineIfStatements(self):
    code = textwrap.dedent("""\
        if True: a = 42
        elif False: b = 42
        else: c = 42
        """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testBlankBetweenClassAndDef(self):
    unformatted_code = textwrap.dedent("""\
        class Foo:
          def joe():
            pass
        """)
    expected_formatted_code = textwrap.dedent("""\
        class Foo:

            def joe():
                pass
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testBlankBetweenDefsInClass(self):
    unformatted_code = textwrap.dedent('''\
        class TestClass:
            def __init__(self):
                self.running = False
            def run(self):
                """Override in subclass"""
            def is_running(self):
                return self.running
        ''')
    expected_formatted_code = textwrap.dedent('''\
        class TestClass:

            def __init__(self):
                self.running = False

            def run(self):
                """Override in subclass"""

            def is_running(self):
                return self.running
        ''')
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testSingleWhiteBeforeTrailingComment(self):
    unformatted_code = textwrap.dedent("""\
        if a+b: # comment
          pass
        """)
    expected_formatted_code = textwrap.dedent("""\
        if a + b:  # comment
            pass
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testSpaceBetweenEndingCommandAndClosingBracket(self):
    unformatted_code = textwrap.dedent("""\
        a = (
            1,
        )
        """)
    expected_formatted_code = textwrap.dedent("""\
        a = (1, )
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testContinuedNonOutdentedLine(self):
    code = textwrap.dedent("""\
        class eld(d):
            if str(geom.geom_type).upper(
            ) != self.geom_type and not self.geom_type == 'GEOMETRY':
                ror(code='om_type')
        """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testWrappingPercentExpressions(self):
    unformatted_code = textwrap.dedent("""\
        def f():
            if True:
                zzzzz = '%s-%s' % (xxxxxxxxxxxxxxxxxxxxxxxxxx + 1, xxxxxxxxxxxxxxxxx.yyy + 1)
                zzzzz = '%s-%s'.ww(xxxxxxxxxxxxxxxxxxxxxxxxxx + 1, xxxxxxxxxxxxxxxxx.yyy + 1)
                zzzzz = '%s-%s' % (xxxxxxxxxxxxxxxxxxxxxxx + 1, xxxxxxxxxxxxxxxxxxxxx + 1)
                zzzzz = '%s-%s'.ww(xxxxxxxxxxxxxxxxxxxxxxx + 1, xxxxxxxxxxxxxxxxxxxxx + 1)
        """)  # noqa
    expected_formatted_code = textwrap.dedent("""\
        def f():
            if True:
                zzzzz = '%s-%s' % (xxxxxxxxxxxxxxxxxxxxxxxxxx + 1,
                                   xxxxxxxxxxxxxxxxx.yyy + 1)
                zzzzz = '%s-%s'.ww(xxxxxxxxxxxxxxxxxxxxxxxxxx + 1,
                                   xxxxxxxxxxxxxxxxx.yyy + 1)
                zzzzz = '%s-%s' % (xxxxxxxxxxxxxxxxxxxxxxx + 1,
                                   xxxxxxxxxxxxxxxxxxxxx + 1)
                zzzzz = '%s-%s'.ww(xxxxxxxxxxxxxxxxxxxxxxx + 1,
                                   xxxxxxxxxxxxxxxxxxxxx + 1)
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testAlignClosingBracketWithVisualIndentation(self):
    unformatted_code = textwrap.dedent("""\
        TEST_LIST = ('foo', 'bar',  # first comment
                     'baz'  # second comment
                    )
        """)
    expected_formatted_code = textwrap.dedent("""\
        TEST_LIST = (
            'foo',
            'bar',  # first comment
            'baz'  # second comment
        )
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

    unformatted_code = textwrap.dedent("""\
        def f():

          def g():
            while (xxxxxxxxxxxxxxxxxxxx(yyyyyyyyyyyyy[zzzzz]) == 'aaaaaaaaaaa' and
                   xxxxxxxxxxxxxxxxxxxx(yyyyyyyyyyyyy[zzzzz].aaaaaaaa[0]) == 'bbbbbbb'
                  ):
              pass
        """)  # noqa
    expected_formatted_code = textwrap.dedent("""\
        def f():

            def g():
                while (xxxxxxxxxxxxxxxxxxxx(yyyyyyyyyyyyy[zzzzz]) == 'aaaaaaaaaaa'
                       and xxxxxxxxxxxxxxxxxxxx(
                           yyyyyyyyyyyyy[zzzzz].aaaaaaaa[0]) == 'bbbbbbb'):
                    pass
        """)  # noqa
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testIndentSizeChanging(self):
    unformatted_code = textwrap.dedent("""\
        if True:
          runtime_mins = (program_end_time - program_start_time).total_seconds() / 60.0
        """)  # noqa
    expected_formatted_code = textwrap.dedent("""\
        if True:
            runtime_mins = (program_end_time -
                            program_start_time).total_seconds() / 60.0
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testHangingIndentCollision(self):
    unformatted_code = textwrap.dedent("""\
        if (aaaaaaaaaaaaaa + bbbbbbbbbbbbbbbb == ccccccccccccccccc and xxxxxxxxxxxxx or yyyyyyyyyyyyyyyyy):
            pass
        elif (xxxxxxxxxxxxxxx(aaaaaaaaaaa, bbbbbbbbbbbbbb, cccccccccccc, dddddddddd=None)):
            pass


        def h():
            if (xxxxxxxxxxxx.yyyyyyyy(zzzzzzzzzzzzz[0]) == 'aaaaaaaaaaa' and xxxxxxxxxxxx.yyyyyyyy(zzzzzzzzzzzzz[0].mmmmmmmm[0]) == 'bbbbbbb'):
                pass

            for connection in itertools.chain(branch.contact, branch.address, morestuff.andmore.andmore.andmore.andmore.andmore.andmore.andmore):
                dosomething(connection)
        """)  # noqa
    expected_formatted_code = textwrap.dedent("""\
        if (aaaaaaaaaaaaaa + bbbbbbbbbbbbbbbb == ccccccccccccccccc and xxxxxxxxxxxxx
                or yyyyyyyyyyyyyyyyy):
            pass
        elif (xxxxxxxxxxxxxxx(aaaaaaaaaaa,
                              bbbbbbbbbbbbbb,
                              cccccccccccc,
                              dddddddddd=None)):
            pass


        def h():
            if (xxxxxxxxxxxx.yyyyyyyy(zzzzzzzzzzzzz[0]) == 'aaaaaaaaaaa' and
                    xxxxxxxxxxxx.yyyyyyyy(zzzzzzzzzzzzz[0].mmmmmmmm[0]) == 'bbbbbbb'):
                pass

            for connection in itertools.chain(
                    branch.contact, branch.address,
                    morestuff.andmore.andmore.andmore.andmore.andmore.andmore.andmore):
                dosomething(connection)
        """)  # noqa
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testSplittingBeforeLogicalOperator(self):
    try:
      style.SetGlobalStyle(
          style.CreateStyleFromConfig(
              '{based_on_style: pep8, split_before_logical_operator: True}'))
      unformatted_code = textwrap.dedent("""\
          def foo():
              return bool(update.message.new_chat_member or update.message.left_chat_member or
                          update.message.new_chat_title or update.message.new_chat_photo or
                          update.message.delete_chat_photo or update.message.group_chat_created or
                          update.message.supergroup_chat_created or update.message.channel_chat_created
                          or update.message.migrate_to_chat_id or update.message.migrate_from_chat_id or
                          update.message.pinned_message)
          """)  # noqa
      expected_formatted_code = textwrap.dedent("""\
          def foo():
              return bool(
                  update.message.new_chat_member or update.message.left_chat_member
                  or update.message.new_chat_title or update.message.new_chat_photo
                  or update.message.delete_chat_photo
                  or update.message.group_chat_created
                  or update.message.supergroup_chat_created
                  or update.message.channel_chat_created
                  or update.message.migrate_to_chat_id
                  or update.message.migrate_from_chat_id
                  or update.message.pinned_message)
          """)  # noqa
      llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
      self.assertCodeEqual(expected_formatted_code,
                           reformatter.Reformat(llines))
    finally:
      style.SetGlobalStyle(style.CreatePEP8Style())

  def testContiguousListEndingWithComment(self):
    unformatted_code = textwrap.dedent("""\
        if True:
            if True:
                keys.append(aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa)  # may be unassigned.
        """)  # noqa
    expected_formatted_code = textwrap.dedent("""\
        if True:
            if True:
                keys.append(
                    aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa)  # may be unassigned.
        """)  # noqa
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testSplittingBeforeFirstArgument(self):
    try:
      style.SetGlobalStyle(
          style.CreateStyleFromConfig(
              '{based_on_style: pep8, split_before_first_argument: True}'))
      unformatted_code = textwrap.dedent("""\
          a_very_long_function_name(long_argument_name_1=1, long_argument_name_2=2,
                                    long_argument_name_3=3, long_argument_name_4=4)
          """)  # noqa
      expected_formatted_code = textwrap.dedent("""\
          a_very_long_function_name(
              long_argument_name_1=1,
              long_argument_name_2=2,
              long_argument_name_3=3,
              long_argument_name_4=4)
          """)
      llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
      self.assertCodeEqual(expected_formatted_code,
                           reformatter.Reformat(llines))
    finally:
      style.SetGlobalStyle(style.CreatePEP8Style())

  def testSplittingExpressionsInsideSubscripts(self):
    unformatted_code = textwrap.dedent("""\
        def foo():
            df = df[(df['campaign_status'] == 'LIVE') & (df['action_status'] == 'LIVE')]
        """)  # noqa
    expected_formatted_code = textwrap.dedent("""\
        def foo():
            df = df[(df['campaign_status'] == 'LIVE')
                    & (df['action_status'] == 'LIVE')]
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testSplitListsAndDictSetMakersIfCommaTerminated(self):
    unformatted_code = textwrap.dedent("""\
        DJANGO_TEMPLATES_OPTIONS = {"context_processors": []}
        DJANGO_TEMPLATES_OPTIONS = {"context_processors": [],}
        x = ["context_processors"]
        x = ["context_processors",]
        """)
    expected_formatted_code = textwrap.dedent("""\
        DJANGO_TEMPLATES_OPTIONS = {"context_processors": []}
        DJANGO_TEMPLATES_OPTIONS = {
            "context_processors": [],
        }
        x = ["context_processors"]
        x = [
            "context_processors",
        ]
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testSplitAroundNamedAssigns(self):
    unformatted_code = textwrap.dedent("""\
        class a():

            def a(): return a(
             aaaaaaaaaa=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa)
        """)
    expected_formatted_code = textwrap.dedent("""\
        class a():

            def a():
                return a(
                    aaaaaaaaaa=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
                )
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testUnaryOperator(self):
    unformatted_code = textwrap.dedent("""\
        if not -3 < x < 3:
          pass
        if -3 < x < 3:
          pass
        """)
    expected_formatted_code = textwrap.dedent("""\
        if not -3 < x < 3:
            pass
        if -3 < x < 3:
            pass
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testNoSplitBeforeDictValue(self):
    try:
      style.SetGlobalStyle(
          style.CreateStyleFromConfig('{based_on_style: pep8, '
                                      'allow_split_before_dict_value: false, '
                                      'coalesce_brackets: true, '
                                      'dedent_closing_brackets: true, '
                                      'each_dict_entry_on_separate_line: true, '
                                      'split_before_logical_operator: true}'))

      unformatted_code = textwrap.dedent("""\
          some_dict = {
              'title': _("I am example data"),
              'description': _("Lorem ipsum dolor met sit amet elit, si vis pacem para bellum "
                               "elites nihi very long string."),
          }
          """)  # noqa
      expected_formatted_code = textwrap.dedent("""\
          some_dict = {
              'title': _("I am example data"),
              'description': _(
                  "Lorem ipsum dolor met sit amet elit, si vis pacem para bellum "
                  "elites nihi very long string."
              ),
          }
          """)  # noqa
      llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
      self.assertCodeEqual(expected_formatted_code,
                           reformatter.Reformat(llines))

      unformatted_code = textwrap.dedent("""\
          X = {'a': 1, 'b': 2, 'key': this_is_a_function_call_that_goes_over_the_column_limit_im_pretty_sure()}
          """)  # noqa
      expected_formatted_code = textwrap.dedent("""\
          X = {
              'a': 1,
              'b': 2,
              'key': this_is_a_function_call_that_goes_over_the_column_limit_im_pretty_sure()
          }
          """)  # noqa
      llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
      self.assertCodeEqual(expected_formatted_code,
                           reformatter.Reformat(llines))

      unformatted_code = textwrap.dedent("""\
          attrs = {
              'category': category,
              'role': forms.ModelChoiceField(label=_("Role"), required=False, queryset=category_roles, initial=selected_role, empty_label=_("No access"),),
          }
          """)  # noqa
      expected_formatted_code = textwrap.dedent("""\
          attrs = {
              'category': category,
              'role': forms.ModelChoiceField(
                  label=_("Role"),
                  required=False,
                  queryset=category_roles,
                  initial=selected_role,
                  empty_label=_("No access"),
              ),
          }
          """)
      llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
      self.assertCodeEqual(expected_formatted_code,
                           reformatter.Reformat(llines))

      unformatted_code = textwrap.dedent("""\
          css_class = forms.CharField(
              label=_("CSS class"),
              required=False,
              help_text=_("Optional CSS class used to customize this category appearance from templates."),
          )
          """)  # noqa
      expected_formatted_code = textwrap.dedent("""\
          css_class = forms.CharField(
              label=_("CSS class"),
              required=False,
              help_text=_(
                  "Optional CSS class used to customize this category appearance from templates."
              ),
          )
          """)  # noqa
      llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
      self.assertCodeEqual(expected_formatted_code,
                           reformatter.Reformat(llines))
    finally:
      style.SetGlobalStyle(style.CreatePEP8Style())

  def testBitwiseOperandSplitting(self):
    unformatted_code = """\
def _():
    include_values = np.where(
                (cdffile['Quality_Flag'][:] >= 5) & (
                cdffile['Day_Night_Flag'][:] == 1) & (
                cdffile['Longitude'][:] >= select_lon - radius) & (
                cdffile['Longitude'][:] <= select_lon + radius) & (
                cdffile['Latitude'][:] >= select_lat - radius) & (
                cdffile['Latitude'][:] <= select_lat + radius))
"""
    expected_code = """\
def _():
    include_values = np.where(
        (cdffile['Quality_Flag'][:] >= 5) & (cdffile['Day_Night_Flag'][:] == 1)
        & (cdffile['Longitude'][:] >= select_lon - radius)
        & (cdffile['Longitude'][:] <= select_lon + radius)
        & (cdffile['Latitude'][:] >= select_lat - radius)
        & (cdffile['Latitude'][:] <= select_lat + radius))
"""
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertEqual(expected_code, reformatter.Reformat(llines))

  def testNoBlankLinesOnlyForFirstNestedObject(self):
    unformatted_code = '''\
class Demo:
    """
    Demo docs
    """
    def foo(self):
        """
        foo docs
        """
    def bar(self):
        """
        bar docs
        """
'''
    expected_code = '''\
class Demo:
    """
    Demo docs
    """

    def foo(self):
        """
        foo docs
        """

    def bar(self):
        """
        bar docs
        """
'''
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertEqual(expected_code, reformatter.Reformat(llines))

  def testSplitBeforeArithmeticOperators(self):
    try:
      style.SetGlobalStyle(
          style.CreateStyleFromConfig(
              '{based_on_style: pep8, split_before_arithmetic_operator: true}'))

      unformatted_code = """\
def _():
    raise ValueError('This is a long message that ends with an argument: ' + str(42))
"""  # noqa
      expected_formatted_code = """\
def _():
    raise ValueError('This is a long message that ends with an argument: '
                     + str(42))
"""
      llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
      self.assertCodeEqual(expected_formatted_code,
                           reformatter.Reformat(llines))
    finally:
      style.SetGlobalStyle(style.CreatePEP8Style())

  def testListSplitting(self):
    unformatted_code = """\
foo([(1,1), (1,1), (1,1), (1,1), (1,1), (1,1), (1,1),
     (1,1), (1,1), (1,1), (1,1), (1,1), (1,1), (1,1),
     (1,10), (1,11), (1, 10), (1,11), (10,11)])
"""
    expected_code = """\
foo([(1, 1), (1, 1), (1, 1), (1, 1), (1, 1), (1, 1), (1, 1), (1, 1), (1, 1),
     (1, 1), (1, 1), (1, 1), (1, 1), (1, 1), (1, 10), (1, 11), (1, 10),
     (1, 11), (10, 11)])
"""
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_code, reformatter.Reformat(llines))

  def testNoBlankLineBeforeNestedFuncOrClass(self):
    try:
      style.SetGlobalStyle(
          style.CreateStyleFromConfig(
              '{based_on_style: pep8, '
              'blank_line_before_nested_class_or_def: false}'))

      unformatted_code = '''\
def normal_function():
    """Return the nested function."""

    def nested_function():
        """Do nothing just nest within."""

        @nested(klass)
        class nested_class():
            pass

        pass

    return nested_function
'''
      expected_formatted_code = '''\
def normal_function():
    """Return the nested function."""
    def nested_function():
        """Do nothing just nest within."""
        @nested(klass)
        class nested_class():
            pass

        pass

    return nested_function
'''
      llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
      self.assertCodeEqual(expected_formatted_code,
                           reformatter.Reformat(llines))
    finally:
      style.SetGlobalStyle(style.CreatePEP8Style())

  def testParamListIndentationCollision1(self):
    unformatted_code = textwrap.dedent("""\
class _():

    def __init__(self, title: Optional[str], diffs: Collection[BinaryDiff] = (), charset: Union[Type[AsciiCharset], Type[LineCharset]] = AsciiCharset, preprocess: Callable[[str], str] = identity,
            # TODO(somebody): Make this a Literal type.
            justify: str = 'rjust'):
        self._cs = charset
        self._preprocess = preprocess
        """)  # noqa
    expected_formatted_code = textwrap.dedent("""\
class _():

    def __init__(
            self,
            title: Optional[str],
            diffs: Collection[BinaryDiff] = (),
            charset: Union[Type[AsciiCharset],
                           Type[LineCharset]] = AsciiCharset,
            preprocess: Callable[[str], str] = identity,
            # TODO(somebody): Make this a Literal type.
            justify: str = 'rjust'):
        self._cs = charset
        self._preprocess = preprocess
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testParamListIndentationCollision2(self):
    code = textwrap.dedent("""\
        def simple_pass_function_with_an_extremely_long_name_and_some_arguments(
                argument0, argument1):
            pass
        """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testParamListIndentationCollision3(self):
    code = textwrap.dedent("""\
        def func1(
            arg1,
            arg2,
        ) -> None:
            pass


        def func2(
            arg1,
            arg2,
        ):
            pass
        """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines))

  def testTwoWordComparisonOperators(self):
    unformatted_code = textwrap.dedent("""\
        _ = (klsdfjdklsfjksdlfjdklsfjdslkfjsdkl is not ksldfjsdklfjdklsfjdklsfjdklsfjdsklfjdklsfj)
        _ = (klsdfjdklsfjksdlfjdklsfjdslkfjsdkl not in {ksldfjsdklfjdklsfjdklsfjdklsfjdsklfjdklsfj})
        """)  # noqa
    expected_formatted_code = textwrap.dedent("""\
        _ = (klsdfjdklsfjksdlfjdklsfjdslkfjsdkl
             is not ksldfjsdklfjdklsfjdklsfjdklsfjdsklfjdklsfj)
        _ = (klsdfjdklsfjksdlfjdklsfjdslkfjsdkl
             not in {ksldfjsdklfjdklsfjdklsfjdklsfjdsklfjdklsfj})
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  @unittest.skipUnless(not py3compat.PY3, 'Requires Python 2.7')
  def testAsyncAsNonKeyword(self):
    # In Python 2, async may be used as a non-keyword identifier.
    code = textwrap.dedent("""\
        from util import async


        class A(object):

            def foo(self):
                async.run()

            def bar(self):
                pass
        """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines, verify=False))

  def testStableInlinedDictionaryFormatting(self):
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

  @unittest.skipUnless(py3compat.PY36, 'Requires Python 3.6')
  def testSpaceBetweenColonAndElipses(self):
    style.SetGlobalStyle(style.CreatePEP8Style())
    code = textwrap.dedent("""\
      class MyClass(ABC):

          place: ...
    """)
    llines = yapf_test_helper.ParseAndUnwrap(code)
    self.assertCodeEqual(code, reformatter.Reformat(llines, verify=False))

  @unittest.skipUnless(py3compat.PY36, 'Requires Python 3.6')
  def testSpaceBetweenDictColonAndElipses(self):
    style.SetGlobalStyle(style.CreatePEP8Style())
    unformatted_code = textwrap.dedent("""\
      {0:"...", 1:...}
    """)
    expected_formatted_code = textwrap.dedent("""\
      {0: "...", 1: ...}
    """)

    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))


class TestsForSpacesInsideBrackets(yapf_test_helper.YAPFTest):
  """Test the SPACE_INSIDE_BRACKETS style option."""
  unformatted_code = textwrap.dedent("""\
    foo()
    foo(1)
    foo(1,2)
    foo((1,))
    foo((1, 2))
    foo((1, 2,))
    foo(bar['baz'][0])
    set1 = {1, 2, 3}
    dict1 = {1: 1, foo: 2, 3: bar}
    dict2 = {
        1: 1,
        foo: 2,
        3: bar,
    }
    dict3[3][1][get_index(*args,**kwargs)]
    dict4[3][1][get_index(**kwargs)]
    x = dict5[4](foo(*args))
    a = list1[:]
    b = list2[slice_start:]
    c = list3[slice_start:slice_end]
    d = list4[slice_start:slice_end:]
    e = list5[slice_start:slice_end:slice_step]
    # Print gets special handling
    print(set2)
    compound = ((10+3)/(5-2**(6+x)))
    string_idx = "mystring"[3]
    """)

  def testEnabled(self):
    style.SetGlobalStyle(
        style.CreateStyleFromConfig('{space_inside_brackets: True}'))

    expected_formatted_code = textwrap.dedent("""\
      foo()
      foo( 1 )
      foo( 1, 2 )
      foo( ( 1, ) )
      foo( ( 1, 2 ) )
      foo( (
          1,
          2,
      ) )
      foo( bar[ 'baz' ][ 0 ] )
      set1 = { 1, 2, 3 }
      dict1 = { 1: 1, foo: 2, 3: bar }
      dict2 = {
          1: 1,
          foo: 2,
          3: bar,
      }
      dict3[ 3 ][ 1 ][ get_index( *args, **kwargs ) ]
      dict4[ 3 ][ 1 ][ get_index( **kwargs ) ]
      x = dict5[ 4 ]( foo( *args ) )
      a = list1[ : ]
      b = list2[ slice_start: ]
      c = list3[ slice_start:slice_end ]
      d = list4[ slice_start:slice_end: ]
      e = list5[ slice_start:slice_end:slice_step ]
      # Print gets special handling
      print( set2 )
      compound = ( ( 10 + 3 ) / ( 5 - 2**( 6 + x ) ) )
      string_idx = "mystring"[ 3 ]
      """)

    llines = yapf_test_helper.ParseAndUnwrap(self.unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testDefault(self):
    style.SetGlobalStyle(style.CreatePEP8Style())

    expected_formatted_code = textwrap.dedent("""\
      foo()
      foo(1)
      foo(1, 2)
      foo((1, ))
      foo((1, 2))
      foo((
          1,
          2,
      ))
      foo(bar['baz'][0])
      set1 = {1, 2, 3}
      dict1 = {1: 1, foo: 2, 3: bar}
      dict2 = {
          1: 1,
          foo: 2,
          3: bar,
      }
      dict3[3][1][get_index(*args, **kwargs)]
      dict4[3][1][get_index(**kwargs)]
      x = dict5[4](foo(*args))
      a = list1[:]
      b = list2[slice_start:]
      c = list3[slice_start:slice_end]
      d = list4[slice_start:slice_end:]
      e = list5[slice_start:slice_end:slice_step]
      # Print gets special handling
      print(set2)
      compound = ((10 + 3) / (5 - 2**(6 + x)))
      string_idx = "mystring"[3]
      """)

    llines = yapf_test_helper.ParseAndUnwrap(self.unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  @unittest.skipUnless(py3compat.PY36, 'Requires Python 3.6')
  def testAwait(self):
    style.SetGlobalStyle(
        style.CreateStyleFromConfig('{space_inside_brackets: True}'))
    unformatted_code = textwrap.dedent("""\
      import asyncio
      import time

      @print_args
      async def slow_operation():
        await asyncio.sleep(1)
        # print("Slow operation {} complete".format(n))
        async def main():
          start = time.time()
          if (await get_html()):
            pass
      """)
    expected_formatted_code = textwrap.dedent("""\
      import asyncio
      import time


      @print_args
      async def slow_operation():
          await asyncio.sleep( 1 )

          # print("Slow operation {} complete".format(n))
          async def main():
              start = time.time()
              if ( await get_html() ):
                  pass
      """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))


class TestsForSpacesAroundSubscriptColon(yapf_test_helper.YAPFTest):
  """Test the SPACES_AROUND_SUBSCRIPT_COLON style option."""
  unformatted_code = textwrap.dedent("""\
    a = list1[ : ]
    b = list2[ slice_start: ]
    c = list3[ slice_start:slice_end ]
    d = list4[ slice_start:slice_end: ]
    e = list5[ slice_start:slice_end:slice_step ]
    a1 = list1[ : ]
    b1 = list2[ 1: ]
    c1 = list3[ 1:20 ]
    d1 = list4[ 1:20: ]
    e1 = list5[ 1:20:3 ]
  """)

  def testEnabled(self):
    style.SetGlobalStyle(
        style.CreateStyleFromConfig('{spaces_around_subscript_colon: True}'))
    expected_formatted_code = textwrap.dedent("""\
      a = list1[:]
      b = list2[slice_start :]
      c = list3[slice_start : slice_end]
      d = list4[slice_start : slice_end :]
      e = list5[slice_start : slice_end : slice_step]
      a1 = list1[:]
      b1 = list2[1 :]
      c1 = list3[1 : 20]
      d1 = list4[1 : 20 :]
      e1 = list5[1 : 20 : 3]
    """)
    llines = yapf_test_helper.ParseAndUnwrap(self.unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testWithSpaceInsideBrackets(self):
    style.SetGlobalStyle(
        style.CreateStyleFromConfig('{'
                                    'spaces_around_subscript_colon: true, '
                                    'space_inside_brackets: true,'
                                    '}'))
    expected_formatted_code = textwrap.dedent("""\
      a = list1[ : ]
      b = list2[ slice_start : ]
      c = list3[ slice_start : slice_end ]
      d = list4[ slice_start : slice_end : ]
      e = list5[ slice_start : slice_end : slice_step ]
      a1 = list1[ : ]
      b1 = list2[ 1 : ]
      c1 = list3[ 1 : 20 ]
      d1 = list4[ 1 : 20 : ]
      e1 = list5[ 1 : 20 : 3 ]
    """)
    llines = yapf_test_helper.ParseAndUnwrap(self.unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testDefault(self):
    style.SetGlobalStyle(style.CreatePEP8Style())
    expected_formatted_code = textwrap.dedent("""\
      a = list1[:]
      b = list2[slice_start:]
      c = list3[slice_start:slice_end]
      d = list4[slice_start:slice_end:]
      e = list5[slice_start:slice_end:slice_step]
      a1 = list1[:]
      b1 = list2[1:]
      c1 = list3[1:20]
      d1 = list4[1:20:]
      e1 = list5[1:20:3]
    """)
    llines = yapf_test_helper.ParseAndUnwrap(self.unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))


if __name__ == '__main__':
  unittest.main()
