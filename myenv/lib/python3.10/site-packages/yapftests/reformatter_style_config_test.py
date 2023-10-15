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
"""Style config tests for yapf.reformatter."""

import textwrap
import unittest

from yapf.yapflib import reformatter
from yapf.yapflib import style

from yapftests import yapf_test_helper


class TestsForStyleConfig(yapf_test_helper.YAPFTest):

  def setUp(self):
    self.current_style = style.DEFAULT_STYLE

  def testSetGlobalStyle(self):
    try:
      style.SetGlobalStyle(style.CreateYapfStyle())
      unformatted_code = textwrap.dedent(u"""\
          for i in range(5):
           print('bar')
          """)
      expected_formatted_code = textwrap.dedent(u"""\
          for i in range(5):
            print('bar')
          """)
      llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
      self.assertCodeEqual(expected_formatted_code,
                           reformatter.Reformat(llines))
    finally:
      style.SetGlobalStyle(style.CreatePEP8Style())
      style.DEFAULT_STYLE = self.current_style

    unformatted_code = textwrap.dedent(u"""\
        for i in range(5):
         print('bar')
        """)
    expected_formatted_code = textwrap.dedent(u"""\
        for i in range(5):
            print('bar')
        """)
    llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
    self.assertCodeEqual(expected_formatted_code, reformatter.Reformat(llines))

  def testOperatorNoSpaceStyle(self):
    try:
      sympy_style = style.CreatePEP8Style()
      sympy_style['NO_SPACES_AROUND_SELECTED_BINARY_OPERATORS'] = \
        style._StringSetConverter('*,/')
      style.SetGlobalStyle(sympy_style)
      unformatted_code = textwrap.dedent("""\
          a = 1+2 * 3 - 4 / 5
          b = '0' * 1
          """)
      expected_formatted_code = textwrap.dedent("""\
          a = 1 + 2*3 - 4/5
          b = '0'*1
          """)

      llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
      self.assertCodeEqual(expected_formatted_code,
                           reformatter.Reformat(llines))
    finally:
      style.SetGlobalStyle(style.CreatePEP8Style())
      style.DEFAULT_STYLE = self.current_style

  def testOperatorPrecedenceStyle(self):
    try:
      pep8_with_precedence = style.CreatePEP8Style()
      pep8_with_precedence['ARITHMETIC_PRECEDENCE_INDICATION'] = True
      style.SetGlobalStyle(pep8_with_precedence)
      unformatted_code = textwrap.dedent("""\
          1+2
          (1 + 2) * (3 - (4 / 5))
          a = 1 * 2 + 3 / 4
          b = 1 / 2 - 3 * 4
          c = (1 + 2) * (3 - 4)
          d = (1 - 2) / (3 + 4)
          e = 1 * 2 - 3
          f = 1 + 2 + 3 + 4
          g = 1 * 2 * 3 * 4
          h = 1 + 2 - 3 + 4
          i = 1 * 2 / 3 * 4
          j = (1 * 2 - 3) + 4
          k = (1 * 2 * 3) + (4 * 5 * 6 * 7 * 8)
          """)
      expected_formatted_code = textwrap.dedent("""\
          1 + 2
          (1+2) * (3 - (4/5))
          a = 1*2 + 3/4
          b = 1/2 - 3*4
          c = (1+2) * (3-4)
          d = (1-2) / (3+4)
          e = 1*2 - 3
          f = 1 + 2 + 3 + 4
          g = 1 * 2 * 3 * 4
          h = 1 + 2 - 3 + 4
          i = 1 * 2 / 3 * 4
          j = (1*2 - 3) + 4
          k = (1*2*3) + (4*5*6*7*8)
          """)

      llines = yapf_test_helper.ParseAndUnwrap(unformatted_code)
      self.assertCodeEqual(expected_formatted_code,
                           reformatter.Reformat(llines))
    finally:
      style.SetGlobalStyle(style.CreatePEP8Style())
      style.DEFAULT_STYLE = self.current_style

  def testNoSplitBeforeFirstArgumentStyle1(self):
    try:
      pep8_no_split_before_first = style.CreatePEP8Style()
      pep8_no_split_before_first['SPLIT_BEFORE_FIRST_ARGUMENT'] = False
      pep8_no_split_before_first['SPLIT_BEFORE_NAMED_ASSIGNS'] = False
      style.SetGlobalStyle(pep8_no_split_before_first)
      formatted_code = textwrap.dedent("""\
          # Example from in-code MustSplit comments
          foo = outer_function_call(fitting_inner_function_call(inner_arg1, inner_arg2),
                                    outer_arg1, outer_arg2)

          foo = outer_function_call(
              not_fitting_inner_function_call(inner_arg1, inner_arg2), outer_arg1,
              outer_arg2)

          # Examples Issue#424
          a_super_long_version_of_print(argument1, argument2, argument3, argument4,
                                        argument5, argument6, argument7)

          CREDS_FILE = os.path.join(os.path.expanduser('~'),
                                    'apis/super-secret-admin-creds.json')

          # Examples Issue#556
          i_take_a_lot_of_params(arg1, param1=very_long_expression1(),
                                 param2=very_long_expression2(),
                                 param3=very_long_expression3(),
                                 param4=very_long_expression4())

          # Examples Issue#590
          plt.plot(numpy.linspace(0, 1, 10), numpy.linspace(0, 1, 10), marker="x",
                   color="r")

          plt.plot(veryverylongvariablename, veryverylongvariablename, marker="x",
                   color="r")
          """)  # noqa
      llines = yapf_test_helper.ParseAndUnwrap(formatted_code)
      self.assertCodeEqual(formatted_code, reformatter.Reformat(llines))
    finally:
      style.SetGlobalStyle(style.CreatePEP8Style())
      style.DEFAULT_STYLE = self.current_style

  def testNoSplitBeforeFirstArgumentStyle2(self):
    try:
      pep8_no_split_before_first = style.CreatePEP8Style()
      pep8_no_split_before_first['SPLIT_BEFORE_FIRST_ARGUMENT'] = False
      pep8_no_split_before_first['SPLIT_BEFORE_NAMED_ASSIGNS'] = True
      style.SetGlobalStyle(pep8_no_split_before_first)
      formatted_code = textwrap.dedent("""\
          # Examples Issue#556
          i_take_a_lot_of_params(arg1,
                                 param1=very_long_expression1(),
                                 param2=very_long_expression2(),
                                 param3=very_long_expression3(),
                                 param4=very_long_expression4())

          # Examples Issue#590
          plt.plot(numpy.linspace(0, 1, 10),
                   numpy.linspace(0, 1, 10),
                   marker="x",
                   color="r")

          plt.plot(veryverylongvariablename,
                   veryverylongvariablename,
                   marker="x",
                   color="r")
          """)
      llines = yapf_test_helper.ParseAndUnwrap(formatted_code)
      self.assertCodeEqual(formatted_code, reformatter.Reformat(llines))
    finally:
      style.SetGlobalStyle(style.CreatePEP8Style())
      style.DEFAULT_STYLE = self.current_style


if __name__ == '__main__':
  unittest.main()
