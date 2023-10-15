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
"""Tests for yapf.logical_line."""

import textwrap
import unittest

from lib2to3 import pytree
from lib2to3.pgen2 import token

from yapf.yapflib import format_token
from yapf.yapflib import logical_line
from yapf.yapflib import split_penalty

from yapftests import yapf_test_helper


class LogicalLineBasicTest(unittest.TestCase):

  def testConstruction(self):
    toks = _MakeFormatTokenList([(token.DOT, '.'), (token.VBAR, '|')])
    lline = logical_line.LogicalLine(20, toks)
    self.assertEqual(20, lline.depth)
    self.assertEqual(['DOT', 'VBAR'], [tok.name for tok in lline.tokens])

  def testFirstLast(self):
    toks = _MakeFormatTokenList([(token.DOT, '.'), (token.LPAR, '('),
                                 (token.VBAR, '|')])
    lline = logical_line.LogicalLine(20, toks)
    self.assertEqual(20, lline.depth)
    self.assertEqual('DOT', lline.first.name)
    self.assertEqual('VBAR', lline.last.name)

  def testAsCode(self):
    toks = _MakeFormatTokenList([(token.DOT, '.'), (token.LPAR, '('),
                                 (token.VBAR, '|')])
    lline = logical_line.LogicalLine(2, toks)
    self.assertEqual('    . ( |', lline.AsCode())

  def testAppendToken(self):
    lline = logical_line.LogicalLine(0)
    lline.AppendToken(_MakeFormatTokenLeaf(token.LPAR, '('))
    lline.AppendToken(_MakeFormatTokenLeaf(token.RPAR, ')'))
    self.assertEqual(['LPAR', 'RPAR'], [tok.name for tok in lline.tokens])

  def testAppendNode(self):
    lline = logical_line.LogicalLine(0)
    lline.AppendNode(pytree.Leaf(token.LPAR, '('))
    lline.AppendNode(pytree.Leaf(token.RPAR, ')'))
    self.assertEqual(['LPAR', 'RPAR'], [tok.name for tok in lline.tokens])


class LogicalLineFormattingInformationTest(yapf_test_helper.YAPFTest):

  def testFuncDef(self):
    code = textwrap.dedent(r"""
        def f(a, b):
          pass
        """)
    llines = yapf_test_helper.ParseAndUnwrap(code)

    f = llines[0].tokens[1]
    self.assertFalse(f.can_break_before)
    self.assertFalse(f.must_break_before)
    self.assertEqual(f.split_penalty, split_penalty.UNBREAKABLE)

    lparen = llines[0].tokens[2]
    self.assertFalse(lparen.can_break_before)
    self.assertFalse(lparen.must_break_before)
    self.assertEqual(lparen.split_penalty, split_penalty.UNBREAKABLE)


def _MakeFormatTokenLeaf(token_type, token_value):
  return format_token.FormatToken(pytree.Leaf(token_type, token_value))


def _MakeFormatTokenList(token_type_values):
  return [
      _MakeFormatTokenLeaf(token_type, token_value)
      for token_type, token_value in token_type_values
  ]


if __name__ == '__main__':
  unittest.main()
