# -*- coding: utf-8 -*-
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
"""Tests for yapf.style."""

import os
import shutil
import tempfile
import textwrap
import unittest

from yapf.yapflib import style

from yapftests import utils
from yapftests import yapf_test_helper


class UtilsTest(yapf_test_helper.YAPFTest):

  def testContinuationAlignStyleStringConverter(self):
    for cont_align_space in ('', 'space', '"space"', '\'space\''):
      self.assertEqual(
          style._ContinuationAlignStyleStringConverter(cont_align_space),
          'SPACE')
    for cont_align_fixed in ('fixed', '"fixed"', '\'fixed\''):
      self.assertEqual(
          style._ContinuationAlignStyleStringConverter(cont_align_fixed),
          'FIXED')
    for cont_align_valignright in (
        'valign-right',
        '"valign-right"',
        '\'valign-right\'',
        'valign_right',
        '"valign_right"',
        '\'valign_right\'',
    ):
      self.assertEqual(
          style._ContinuationAlignStyleStringConverter(cont_align_valignright),
          'VALIGN-RIGHT')
    with self.assertRaises(ValueError) as ctx:
      style._ContinuationAlignStyleStringConverter('blahblah')
    self.assertIn("unknown continuation align style: 'blahblah'",
                  str(ctx.exception))

  def testStringListConverter(self):
    self.assertEqual(style._StringListConverter('foo, bar'), ['foo', 'bar'])
    self.assertEqual(style._StringListConverter('foo,bar'), ['foo', 'bar'])
    self.assertEqual(style._StringListConverter('  foo'), ['foo'])
    self.assertEqual(
        style._StringListConverter('joe  ,foo,  bar'), ['joe', 'foo', 'bar'])

  def testBoolConverter(self):
    self.assertEqual(style._BoolConverter('true'), True)
    self.assertEqual(style._BoolConverter('1'), True)
    self.assertEqual(style._BoolConverter('false'), False)
    self.assertEqual(style._BoolConverter('0'), False)

  def testIntListConverter(self):
    self.assertEqual(style._IntListConverter('1, 2, 3'), [1, 2, 3])
    self.assertEqual(style._IntListConverter('[ 1, 2, 3 ]'), [1, 2, 3])
    self.assertEqual(style._IntListConverter('[ 1, 2, 3, ]'), [1, 2, 3])

  def testIntOrIntListConverter(self):
    self.assertEqual(style._IntOrIntListConverter('10'), 10)
    self.assertEqual(style._IntOrIntListConverter('1, 2, 3'), [1, 2, 3])


def _LooksLikeGoogleStyle(cfg):
  return cfg['COLUMN_LIMIT'] == 80 and cfg['SPLIT_COMPLEX_COMPREHENSION']


def _LooksLikePEP8Style(cfg):
  return cfg['COLUMN_LIMIT'] == 79


def _LooksLikeFacebookStyle(cfg):
  return cfg['DEDENT_CLOSING_BRACKETS']


def _LooksLikeYapfStyle(cfg):
  return cfg['SPLIT_BEFORE_DOT']


class PredefinedStylesByNameTest(yapf_test_helper.YAPFTest):

  @classmethod
  def setUpClass(cls):  # pylint: disable=g-missing-super-call
    style.SetGlobalStyle(style.CreatePEP8Style())

  def testDefault(self):
    # default is PEP8
    cfg = style.CreateStyleFromConfig(None)
    self.assertTrue(_LooksLikePEP8Style(cfg))

  def testPEP8ByName(self):
    for pep8_name in ('PEP8', 'pep8', 'Pep8'):
      cfg = style.CreateStyleFromConfig(pep8_name)
      self.assertTrue(_LooksLikePEP8Style(cfg))

  def testGoogleByName(self):
    for google_name in ('google', 'Google', 'GOOGLE'):
      cfg = style.CreateStyleFromConfig(google_name)
      self.assertTrue(_LooksLikeGoogleStyle(cfg))

  def testYapfByName(self):
    for yapf_name in ('yapf', 'YAPF'):
      cfg = style.CreateStyleFromConfig(yapf_name)
      self.assertTrue(_LooksLikeYapfStyle(cfg))

  def testFacebookByName(self):
    for fb_name in ('facebook', 'FACEBOOK', 'Facebook'):
      cfg = style.CreateStyleFromConfig(fb_name)
      self.assertTrue(_LooksLikeFacebookStyle(cfg))


class StyleFromFileTest(yapf_test_helper.YAPFTest):

  @classmethod
  def setUpClass(cls):  # pylint: disable=g-missing-super-call
    cls.test_tmpdir = tempfile.mkdtemp()
    style.SetGlobalStyle(style.CreatePEP8Style())

  @classmethod
  def tearDownClass(cls):  # pylint: disable=g-missing-super-call
    shutil.rmtree(cls.test_tmpdir)

  def testDefaultBasedOnStyle(self):
    cfg = textwrap.dedent(u'''\
        [style]
        continuation_indent_width = 20
        ''')
    with utils.TempFileContents(self.test_tmpdir, cfg) as filepath:
      cfg = style.CreateStyleFromConfig(filepath)
      self.assertTrue(_LooksLikePEP8Style(cfg))
      self.assertEqual(cfg['CONTINUATION_INDENT_WIDTH'], 20)

  def testDefaultBasedOnPEP8Style(self):
    cfg = textwrap.dedent(u'''\
        [style]
        based_on_style = pep8
        continuation_indent_width = 40
        ''')
    with utils.TempFileContents(self.test_tmpdir, cfg) as filepath:
      cfg = style.CreateStyleFromConfig(filepath)
      self.assertTrue(_LooksLikePEP8Style(cfg))
      self.assertEqual(cfg['CONTINUATION_INDENT_WIDTH'], 40)

  def testDefaultBasedOnGoogleStyle(self):
    cfg = textwrap.dedent(u'''\
        [style]
        based_on_style = google
        continuation_indent_width = 20
        ''')
    with utils.TempFileContents(self.test_tmpdir, cfg) as filepath:
      cfg = style.CreateStyleFromConfig(filepath)
      self.assertTrue(_LooksLikeGoogleStyle(cfg))
      self.assertEqual(cfg['CONTINUATION_INDENT_WIDTH'], 20)

  def testDefaultBasedOnFacebookStyle(self):
    cfg = textwrap.dedent(u'''\
        [style]
        based_on_style = facebook
        continuation_indent_width = 20
        ''')
    with utils.TempFileContents(self.test_tmpdir, cfg) as filepath:
      cfg = style.CreateStyleFromConfig(filepath)
      self.assertTrue(_LooksLikeFacebookStyle(cfg))
      self.assertEqual(cfg['CONTINUATION_INDENT_WIDTH'], 20)

  def testBoolOptionValue(self):
    cfg = textwrap.dedent(u'''\
        [style]
        based_on_style = pep8
        SPLIT_BEFORE_NAMED_ASSIGNS=False
        split_before_logical_operator = true
        ''')
    with utils.TempFileContents(self.test_tmpdir, cfg) as filepath:
      cfg = style.CreateStyleFromConfig(filepath)
      self.assertTrue(_LooksLikePEP8Style(cfg))
      self.assertEqual(cfg['SPLIT_BEFORE_NAMED_ASSIGNS'], False)
      self.assertEqual(cfg['SPLIT_BEFORE_LOGICAL_OPERATOR'], True)

  def testStringListOptionValue(self):
    cfg = textwrap.dedent(u'''\
        [style]
        based_on_style = pep8
        I18N_FUNCTION_CALL = N_, V_, T_
        ''')
    with utils.TempFileContents(self.test_tmpdir, cfg) as filepath:
      cfg = style.CreateStyleFromConfig(filepath)
      self.assertTrue(_LooksLikePEP8Style(cfg))
      self.assertEqual(cfg['I18N_FUNCTION_CALL'], ['N_', 'V_', 'T_'])

  def testErrorNoStyleFile(self):
    with self.assertRaisesRegex(style.StyleConfigError,
                                'is not a valid style or file path'):
      style.CreateStyleFromConfig('/8822/xyznosuchfile')

  def testErrorNoStyleSection(self):
    cfg = textwrap.dedent(u'''\
        [s]
        indent_width=2
        ''')
    with utils.TempFileContents(self.test_tmpdir, cfg) as filepath:
      with self.assertRaisesRegex(style.StyleConfigError,
                                  'Unable to find section'):
        style.CreateStyleFromConfig(filepath)

  def testErrorUnknownStyleOption(self):
    cfg = textwrap.dedent(u'''\
        [style]
        indent_width=2
        hummus=2
        ''')
    with utils.TempFileContents(self.test_tmpdir, cfg) as filepath:
      with self.assertRaisesRegex(style.StyleConfigError,
                                  'Unknown style option'):
        style.CreateStyleFromConfig(filepath)

  def testPyprojectTomlNoYapfSection(self):
    try:
      import toml
    except ImportError:
      return

    filepath = os.path.join(self.test_tmpdir, 'pyproject.toml')
    _ = open(filepath, 'w')
    with self.assertRaisesRegex(style.StyleConfigError,
                                'Unable to find section'):
      style.CreateStyleFromConfig(filepath)

  def testPyprojectTomlParseYapfSection(self):
    try:
      import toml
    except ImportError:
      return

    cfg = textwrap.dedent(u'''\
        [tool.yapf]
        based_on_style = "pep8"
        continuation_indent_width = 40
        ''')
    filepath = os.path.join(self.test_tmpdir, 'pyproject.toml')
    with open(filepath, 'w') as f:
      f.write(cfg)
    cfg = style.CreateStyleFromConfig(filepath)
    self.assertTrue(_LooksLikePEP8Style(cfg))
    self.assertEqual(cfg['CONTINUATION_INDENT_WIDTH'], 40)


class StyleFromDict(yapf_test_helper.YAPFTest):

  @classmethod
  def setUpClass(cls):  # pylint: disable=g-missing-super-call
    style.SetGlobalStyle(style.CreatePEP8Style())

  def testDefaultBasedOnStyle(self):
    config_dict = {
        'based_on_style': 'pep8',
        'indent_width': 2,
        'blank_line_before_nested_class_or_def': True
    }
    cfg = style.CreateStyleFromConfig(config_dict)
    self.assertTrue(_LooksLikePEP8Style(cfg))
    self.assertEqual(cfg['INDENT_WIDTH'], 2)

  def testDefaultBasedOnStyleBadDict(self):
    self.assertRaisesRegex(style.StyleConfigError, 'Unknown style option',
                           style.CreateStyleFromConfig,
                           {'based_on_styl': 'pep8'})
    self.assertRaisesRegex(style.StyleConfigError, 'not a valid',
                           style.CreateStyleFromConfig,
                           {'INDENT_WIDTH': 'FOUR'})


class StyleFromCommandLine(yapf_test_helper.YAPFTest):

  @classmethod
  def setUpClass(cls):  # pylint: disable=g-missing-super-call
    style.SetGlobalStyle(style.CreatePEP8Style())

  def testDefaultBasedOnStyle(self):
    cfg = style.CreateStyleFromConfig(
        '{based_on_style: pep8,'
        ' indent_width: 2,'
        ' blank_line_before_nested_class_or_def: True}')
    self.assertTrue(_LooksLikePEP8Style(cfg))
    self.assertEqual(cfg['INDENT_WIDTH'], 2)

  def testDefaultBasedOnStyleNotStrict(self):
    cfg = style.CreateStyleFromConfig(
        '{based_on_style : pep8'
        ' ,indent_width=2'
        ' blank_line_before_nested_class_or_def:True}')
    self.assertTrue(_LooksLikePEP8Style(cfg))
    self.assertEqual(cfg['INDENT_WIDTH'], 2)

  def testDefaultBasedOnExplicitlyUnicodeTypeString(self):
    cfg = style.CreateStyleFromConfig(u'{}')
    self.assertIsInstance(cfg, dict)

  def testDefaultBasedOnDetaultTypeString(self):
    cfg = style.CreateStyleFromConfig('{}')
    self.assertIsInstance(cfg, dict)

  def testDefaultBasedOnStyleBadString(self):
    self.assertRaisesRegex(style.StyleConfigError, 'Unknown style option',
                           style.CreateStyleFromConfig, '{based_on_styl: pep8}')
    self.assertRaisesRegex(style.StyleConfigError, 'not a valid',
                           style.CreateStyleFromConfig, '{INDENT_WIDTH: FOUR}')
    self.assertRaisesRegex(style.StyleConfigError, 'Invalid style dict',
                           style.CreateStyleFromConfig, '{based_on_style: pep8')


class StyleHelp(yapf_test_helper.YAPFTest):

  def testHelpKeys(self):
    settings = sorted(style.Help())
    expected = sorted(style._style)
    self.assertListEqual(settings, expected)


if __name__ == '__main__':
  unittest.main()
