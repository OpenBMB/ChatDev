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
"""Tests for yapf.yapf."""

import io
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest

from lib2to3.pgen2 import tokenize

from yapf.yapflib import errors
from yapf.yapflib import py3compat
from yapf.yapflib import style
from yapf.yapflib import yapf_api

from yapftests import utils
from yapftests import yapf_test_helper

ROOT_DIR = os.path.dirname(os.path.abspath(os.path.dirname(__file__)))

# Verification is turned off by default, but want to enable it for testing.
YAPF_BINARY = [sys.executable, '-m', 'yapf', '--verify', '--no-local-style']


class FormatCodeTest(yapf_test_helper.YAPFTest):

  def _Check(self, unformatted_code, expected_formatted_code):
    formatted_code, _ = yapf_api.FormatCode(
        unformatted_code, style_config='yapf')
    self.assertCodeEqual(expected_formatted_code, formatted_code)

  def testSimple(self):
    unformatted_code = textwrap.dedent("""\
        print('foo')
        """)
    self._Check(unformatted_code, unformatted_code)

  def testNoEndingNewline(self):
    unformatted_code = textwrap.dedent("""\
        if True:
          pass""")
    expected_formatted_code = textwrap.dedent("""\
        if True:
          pass
        """)
    self._Check(unformatted_code, expected_formatted_code)

  @unittest.skipUnless(py3compat.PY36, 'Requires Python 3.6')
  def testPrintAfterPeriod(self):
    unformatted_code = textwrap.dedent("""a.print\n""")
    expected_formatted_code = textwrap.dedent("""a.print\n""")
    self._Check(unformatted_code, expected_formatted_code)


class FormatFileTest(unittest.TestCase):

  def setUp(self):  # pylint: disable=g-missing-super-call
    self.test_tmpdir = tempfile.mkdtemp()

  def tearDown(self):  # pylint: disable=g-missing-super-call
    shutil.rmtree(self.test_tmpdir)

  def assertCodeEqual(self, expected_code, code):
    if code != expected_code:
      msg = 'Code format mismatch:\n'
      msg += 'Expected:\n >'
      msg += '\n > '.join(expected_code.splitlines())
      msg += '\nActual:\n >'
      msg += '\n > '.join(code.splitlines())
      # TODO(sbc): maybe using difflib here to produce easy to read deltas?
      self.fail(msg)

  def testFormatFile(self):
    unformatted_code = textwrap.dedent(u"""\
        if True:
         pass
        """)
    expected_formatted_code_pep8 = textwrap.dedent(u"""\
        if True:
            pass
        """)
    expected_formatted_code_yapf = textwrap.dedent(u"""\
        if True:
          pass
        """)
    with utils.TempFileContents(self.test_tmpdir, unformatted_code) as filepath:
      formatted_code, _, _ = yapf_api.FormatFile(filepath, style_config='pep8')
      self.assertCodeEqual(expected_formatted_code_pep8, formatted_code)

      formatted_code, _, _ = yapf_api.FormatFile(filepath, style_config='yapf')
      self.assertCodeEqual(expected_formatted_code_yapf, formatted_code)

  def testDisableLinesPattern(self):
    unformatted_code = textwrap.dedent(u"""\
        if a:    b

        # yapf: disable
        if f:    g

        if h:    i
        """)
    expected_formatted_code = textwrap.dedent(u"""\
        if a: b

        # yapf: disable
        if f:    g

        if h:    i
        """)
    with utils.TempFileContents(self.test_tmpdir, unformatted_code) as filepath:
      formatted_code, _, _ = yapf_api.FormatFile(filepath, style_config='pep8')
      self.assertCodeEqual(expected_formatted_code, formatted_code)

  def testDisableAndReenableLinesPattern(self):
    unformatted_code = textwrap.dedent(u"""\
        if a:    b

        # yapf: disable
        if f:    g
        # yapf: enable

        if h:    i
        """)
    expected_formatted_code = textwrap.dedent(u"""\
        if a: b

        # yapf: disable
        if f:    g
        # yapf: enable

        if h: i
        """)
    with utils.TempFileContents(self.test_tmpdir, unformatted_code) as filepath:
      formatted_code, _, _ = yapf_api.FormatFile(filepath, style_config='pep8')
      self.assertCodeEqual(expected_formatted_code, formatted_code)

  def testDisablePartOfMultilineComment(self):
    unformatted_code = textwrap.dedent(u"""\
        if a:    b

        # This is a multiline comment that disables YAPF.
        # yapf: disable
        if f:    g
        # yapf: enable
        # This is a multiline comment that enables YAPF.

        if h:    i
        """)

    expected_formatted_code = textwrap.dedent(u"""\
        if a: b

        # This is a multiline comment that disables YAPF.
        # yapf: disable
        if f:    g
        # yapf: enable
        # This is a multiline comment that enables YAPF.

        if h: i
        """)
    with utils.TempFileContents(self.test_tmpdir, unformatted_code) as filepath:
      formatted_code, _, _ = yapf_api.FormatFile(filepath, style_config='pep8')
      self.assertCodeEqual(expected_formatted_code, formatted_code)

    code = textwrap.dedent(u"""\
      def foo_function():
          # some comment
          # yapf: disable

          foo(
          bar,
          baz
          )

          # yapf: enable
      """)
    with utils.TempFileContents(self.test_tmpdir, code) as filepath:
      formatted_code, _, _ = yapf_api.FormatFile(filepath, style_config='pep8')
      self.assertCodeEqual(code, formatted_code)

  def testEnabledDisabledSameComment(self):
    code = textwrap.dedent(u"""\
        # yapf: disable
        a(bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb, ccccccccccccccccccccccccccccccc, ddddddddddddddddddddddd, eeeeeeeeeeeeeeeeeeeeeeeeeee)
        # yapf: enable
        # yapf: disable
        a(bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb, ccccccccccccccccccccccccccccccc, ddddddddddddddddddddddd, eeeeeeeeeeeeeeeeeeeeeeeeeee)
        # yapf: enable
        """)  # noqa
    with utils.TempFileContents(self.test_tmpdir, code) as filepath:
      formatted_code, _, _ = yapf_api.FormatFile(filepath, style_config='pep8')
      self.assertCodeEqual(code, formatted_code)

  def testFormatFileLinesSelection(self):
    unformatted_code = textwrap.dedent(u"""\
        if a:    b

        if f:    g

        if h:    i
        """)
    expected_formatted_code_lines1and2 = textwrap.dedent(u"""\
        if a: b

        if f:    g

        if h:    i
        """)
    expected_formatted_code_lines3 = textwrap.dedent(u"""\
        if a:    b

        if f: g

        if h:    i
        """)
    with utils.TempFileContents(self.test_tmpdir, unformatted_code) as filepath:
      formatted_code, _, _ = yapf_api.FormatFile(
          filepath, style_config='pep8', lines=[(1, 2)])
      self.assertCodeEqual(expected_formatted_code_lines1and2, formatted_code)
      formatted_code, _, _ = yapf_api.FormatFile(
          filepath, style_config='pep8', lines=[(3, 3)])
      self.assertCodeEqual(expected_formatted_code_lines3, formatted_code)

  def testFormatFileDiff(self):
    unformatted_code = textwrap.dedent(u"""\
        if True:
         pass
        """)
    with utils.TempFileContents(self.test_tmpdir, unformatted_code) as filepath:
      diff, _, _ = yapf_api.FormatFile(filepath, print_diff=True)
      self.assertIn(u'+  pass', diff)

  def testFormatFileInPlace(self):
    unformatted_code = u'True==False\n'
    formatted_code = u'True == False\n'
    with utils.TempFileContents(self.test_tmpdir, unformatted_code) as filepath:
      result, _, _ = yapf_api.FormatFile(filepath, in_place=True)
      self.assertEqual(result, None)
      with open(filepath) as fd:
        if sys.version_info[0] <= 2:
          self.assertCodeEqual(formatted_code, fd.read().decode('ascii'))
        else:
          self.assertCodeEqual(formatted_code, fd.read())

      self.assertRaises(
          ValueError,
          yapf_api.FormatFile,
          filepath,
          in_place=True,
          print_diff=True)

  def testNoFile(self):
    stream = py3compat.StringIO()
    handler = logging.StreamHandler(stream)
    logger = logging.getLogger('mylogger')
    logger.addHandler(handler)
    self.assertRaises(
        IOError, yapf_api.FormatFile, 'not_a_file.py', logger=logger.error)
    self.assertEqual(stream.getvalue(),
                     "[Errno 2] No such file or directory: 'not_a_file.py'\n")

  def testCommentsUnformatted(self):
    code = textwrap.dedent(u"""\
        foo = [# A list of things
               # bork
            'one',
            # quark
            'two'] # yapf: disable
        """)
    with utils.TempFileContents(self.test_tmpdir, code) as filepath:
      formatted_code, _, _ = yapf_api.FormatFile(filepath, style_config='pep8')
      self.assertCodeEqual(code, formatted_code)

  def testDisabledHorizontalFormattingOnNewLine(self):
    code = textwrap.dedent(u"""\
        # yapf: disable
        a = [
        1]
        # yapf: enable
        """)
    with utils.TempFileContents(self.test_tmpdir, code) as filepath:
      formatted_code, _, _ = yapf_api.FormatFile(filepath, style_config='pep8')
      self.assertCodeEqual(code, formatted_code)

  def testSplittingSemicolonStatements(self):
    unformatted_code = textwrap.dedent(u"""\
        def f():
          x = y + 42 ; z = n * 42
          if True: a += 1 ; b += 1; c += 1
        """)
    expected_formatted_code = textwrap.dedent(u"""\
        def f():
            x = y + 42
            z = n * 42
            if True:
                a += 1
                b += 1
                c += 1
        """)
    with utils.TempFileContents(self.test_tmpdir, unformatted_code) as filepath:
      formatted_code, _, _ = yapf_api.FormatFile(filepath, style_config='pep8')
      self.assertCodeEqual(expected_formatted_code, formatted_code)

  def testSemicolonStatementsDisabled(self):
    unformatted_code = textwrap.dedent(u"""\
        def f():
          x = y + 42 ; z = n * 42  # yapf: disable
          if True: a += 1 ; b += 1; c += 1
        """)
    expected_formatted_code = textwrap.dedent(u"""\
        def f():
            x = y + 42 ; z = n * 42  # yapf: disable
            if True:
                a += 1
                b += 1
                c += 1
        """)
    with utils.TempFileContents(self.test_tmpdir, unformatted_code) as filepath:
      formatted_code, _, _ = yapf_api.FormatFile(filepath, style_config='pep8')
      self.assertCodeEqual(expected_formatted_code, formatted_code)

  def testDisabledSemiColonSeparatedStatements(self):
    code = textwrap.dedent(u"""\
        # yapf: disable
        if True: a ; b
        """)
    with utils.TempFileContents(self.test_tmpdir, code) as filepath:
      formatted_code, _, _ = yapf_api.FormatFile(filepath, style_config='pep8')
      self.assertCodeEqual(code, formatted_code)

  def testDisabledMultilineStringInDictionary(self):
    code = textwrap.dedent(u"""\
        # yapf: disable

        A = [
            {
                "aaaaaaaaaaaaaaaaaaa": '''
        bbbbbbbbbbb: "ccccccccccc"
        dddddddddddddd: 1
        eeeeeeee: 0
        ffffffffff: "ggggggg"
        ''',
            },
        ]
        """)
    with utils.TempFileContents(self.test_tmpdir, code) as filepath:
      formatted_code, _, _ = yapf_api.FormatFile(filepath, style_config='yapf')
      self.assertCodeEqual(code, formatted_code)

  def testDisabledWithPrecedingText(self):
    code = textwrap.dedent(u"""\
        # TODO(fix formatting): yapf: disable

        A = [
            {
                "aaaaaaaaaaaaaaaaaaa": '''
        bbbbbbbbbbb: "ccccccccccc"
        dddddddddddddd: 1
        eeeeeeee: 0
        ffffffffff: "ggggggg"
        ''',
            },
        ]
        """)
    with utils.TempFileContents(self.test_tmpdir, code) as filepath:
      formatted_code, _, _ = yapf_api.FormatFile(filepath, style_config='yapf')
      self.assertCodeEqual(code, formatted_code)

  def testCRLFLineEnding(self):
    code = u'class _():\r\n  pass\r\n'
    with utils.TempFileContents(self.test_tmpdir, code) as filepath:
      formatted_code, _, _ = yapf_api.FormatFile(filepath, style_config='yapf')
      self.assertCodeEqual(code, formatted_code)


class CommandLineTest(unittest.TestCase):
  """Test how calling yapf from the command line acts."""

  @classmethod
  def setUpClass(cls):  # pylint: disable=g-missing-super-call
    cls.test_tmpdir = tempfile.mkdtemp()

  @classmethod
  def tearDownClass(cls):  # pylint: disable=g-missing-super-call
    shutil.rmtree(cls.test_tmpdir)

  def assertYapfReformats(self,
                          unformatted,
                          expected,
                          extra_options=None,
                          env=None):
    """Check that yapf reformats the given code as expected.

    Invokes yapf in a subprocess, piping the unformatted code into its stdin.
    Checks that the formatted output is as expected.

    Arguments:
      unformatted: unformatted code - input to yapf
      expected: expected formatted code at the output of yapf
      extra_options: iterable of extra command-line options to pass to yapf
      env: dict of environment variables.
    """
    cmdline = YAPF_BINARY + (extra_options or [])
    p = subprocess.Popen(
        cmdline,
        stdout=subprocess.PIPE,
        stdin=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env)
    reformatted_code, stderrdata = p.communicate(
        unformatted.encode('utf-8-sig'))
    self.assertEqual(stderrdata, b'')
    self.assertMultiLineEqual(reformatted_code.decode('utf-8'), expected)

  @unittest.skipUnless(py3compat.PY36, 'Requires Python 3.6')
  def testUnicodeEncodingPipedToFile(self):
    unformatted_code = textwrap.dedent(u"""\
        def foo():
            print('⇒')
        """)
    with utils.NamedTempFile(
        dirname=self.test_tmpdir, suffix='.py') as (out, _):
      with utils.TempFileContents(
          self.test_tmpdir, unformatted_code, suffix='.py') as filepath:
        subprocess.check_call(YAPF_BINARY + ['--diff', filepath], stdout=out)

  def testInPlaceReformatting(self):
    unformatted_code = textwrap.dedent(u"""\
        def foo():
          x = 37
        """)
    expected_formatted_code = textwrap.dedent("""\
        def foo():
            x = 37
        """)
    with utils.TempFileContents(
        self.test_tmpdir, unformatted_code, suffix='.py') as filepath:
      p = subprocess.Popen(YAPF_BINARY + ['--in-place', filepath])
      p.wait()
      with io.open(filepath, mode='r', newline='') as fd:
        reformatted_code = fd.read()
    self.assertEqual(reformatted_code, expected_formatted_code)

  def testInPlaceReformattingBlank(self):
    unformatted_code = u'\n\n'
    expected_formatted_code = u'\n'
    with utils.TempFileContents(
        self.test_tmpdir, unformatted_code, suffix='.py') as filepath:
      p = subprocess.Popen(YAPF_BINARY + ['--in-place', filepath])
      p.wait()
      with io.open(filepath, mode='r', encoding='utf-8', newline='') as fd:
        reformatted_code = fd.read()
    self.assertEqual(reformatted_code, expected_formatted_code)

  def testInPlaceReformattingEmpty(self):
    unformatted_code = u''
    expected_formatted_code = u''
    with utils.TempFileContents(
        self.test_tmpdir, unformatted_code, suffix='.py') as filepath:
      p = subprocess.Popen(YAPF_BINARY + ['--in-place', filepath])
      p.wait()
      with io.open(filepath, mode='r', encoding='utf-8', newline='') as fd:
        reformatted_code = fd.read()
    self.assertEqual(reformatted_code, expected_formatted_code)

  def testReadFromStdin(self):
    unformatted_code = textwrap.dedent("""\
        def foo():
          x = 37
        """)
    expected_formatted_code = textwrap.dedent("""\
        def foo():
            x = 37
        """)
    self.assertYapfReformats(unformatted_code, expected_formatted_code)

  def testReadFromStdinWithEscapedStrings(self):
    unformatted_code = textwrap.dedent("""\
        s =   "foo\\nbar"
        """)
    expected_formatted_code = textwrap.dedent("""\
        s = "foo\\nbar"
        """)
    self.assertYapfReformats(unformatted_code, expected_formatted_code)

  def testSetYapfStyle(self):
    unformatted_code = textwrap.dedent("""\
        def foo(): # trail
            x = 37
        """)
    expected_formatted_code = textwrap.dedent("""\
        def foo():  # trail
          x = 37
        """)
    self.assertYapfReformats(
        unformatted_code,
        expected_formatted_code,
        extra_options=['--style=yapf'])

  def testSetCustomStyleBasedOnYapf(self):
    unformatted_code = textwrap.dedent("""\
        def foo(): # trail
            x = 37
        """)
    expected_formatted_code = textwrap.dedent("""\
        def foo():    # trail
          x = 37
        """)
    style_file = textwrap.dedent(u'''\
        [style]
        based_on_style = yapf
        spaces_before_comment = 4
        ''')
    with utils.TempFileContents(self.test_tmpdir, style_file) as stylepath:
      self.assertYapfReformats(
          unformatted_code,
          expected_formatted_code,
          extra_options=['--style={0}'.format(stylepath)])

  def testSetCustomStyleSpacesBeforeComment(self):
    unformatted_code = textwrap.dedent("""\
        a_very_long_statement_that_extends_way_beyond # Comment
        short # This is a shorter statement
        """)
    expected_formatted_code = textwrap.dedent("""\
        a_very_long_statement_that_extends_way_beyond # Comment
        short                                         # This is a shorter statement
        """)  # noqa
    style_file = textwrap.dedent(u'''\
        [style]
        spaces_before_comment = 15, 20
        ''')
    with utils.TempFileContents(self.test_tmpdir, style_file) as stylepath:
      self.assertYapfReformats(
          unformatted_code,
          expected_formatted_code,
          extra_options=['--style={0}'.format(stylepath)])

  def testReadSingleLineCodeFromStdin(self):
    unformatted_code = textwrap.dedent("""\
        if True: pass
        """)
    expected_formatted_code = textwrap.dedent("""\
        if True: pass
        """)
    self.assertYapfReformats(unformatted_code, expected_formatted_code)

  def testEncodingVerification(self):
    unformatted_code = textwrap.dedent(u"""\
        '''The module docstring.'''
        # -*- coding: utf-8 -*-
        def f():
            x = 37
        """)

    with utils.NamedTempFile(
        suffix='.py', dirname=self.test_tmpdir) as (out, _):
      with utils.TempFileContents(
          self.test_tmpdir, unformatted_code, suffix='.py') as filepath:
        try:
          subprocess.check_call(YAPF_BINARY + ['--diff', filepath], stdout=out)
        except subprocess.CalledProcessError as e:
          # Indicates the text changed.
          self.assertEqual(e.returncode, 1)  # pylint: disable=g-assert-in-except # noqa

  def testReformattingSpecificLines(self):
    unformatted_code = textwrap.dedent("""\
        def h():
            if (xxxxxxxxxxxx.yyyyyyyy(zzzzzzzzzzzzz[0]) == 'aaaaaaaaaaa' and xxxxxxxxxxxx.yyyyyyyy(zzzzzzzzzzzzz[0].mmmmmmmm[0]) == 'bbbbbbb'):
                pass


        def g():
            if (xxxxxxxxxxxx.yyyyyyyy(zzzzzzzzzzzzz[0]) == 'aaaaaaaaaaa' and xxxxxxxxxxxx.yyyyyyyy(zzzzzzzzzzzzz[0].mmmmmmmm[0]) == 'bbbbbbb'):
                pass
        """)  # noqa
    expected_formatted_code = textwrap.dedent("""\
        def h():
            if (xxxxxxxxxxxx.yyyyyyyy(zzzzzzzzzzzzz[0]) == 'aaaaaaaaaaa' and
                    xxxxxxxxxxxx.yyyyyyyy(zzzzzzzzzzzzz[0].mmmmmmmm[0]) == 'bbbbbbb'):
                pass


        def g():
            if (xxxxxxxxxxxx.yyyyyyyy(zzzzzzzzzzzzz[0]) == 'aaaaaaaaaaa' and xxxxxxxxxxxx.yyyyyyyy(zzzzzzzzzzzzz[0].mmmmmmmm[0]) == 'bbbbbbb'):
                pass
        """)  # noqa
    # TODO(ambv): the `expected_formatted_code` here is not PEP8 compliant,
    # raising "E129 visually indented line with same indent as next logical
    # line" with flake8.
    self.assertYapfReformats(
        unformatted_code,
        expected_formatted_code,
        extra_options=['--lines', '1-2'])

  def testOmitFormattingLinesBeforeDisabledFunctionComment(self):
    unformatted_code = textwrap.dedent("""\
        import sys

        # Comment
        def some_func(x):
            x = ["badly" , "formatted","line" ]
        """)
    expected_formatted_code = textwrap.dedent("""\
        import sys

        # Comment
        def some_func(x):
            x = ["badly", "formatted", "line"]
        """)
    self.assertYapfReformats(
        unformatted_code,
        expected_formatted_code,
        extra_options=['--lines', '5-5'])

  def testReformattingSkippingLines(self):
    unformatted_code = textwrap.dedent("""\
        def h():
            if (xxxxxxxxxxxx.yyyyyyyy(zzzzzzzzzzzzz[0]) == 'aaaaaaaaaaa' and xxxxxxxxxxxx.yyyyyyyy(zzzzzzzzzzzzz[0].mmmmmmmm[0]) == 'bbbbbbb'):
                pass

        # yapf: disable
        def g():
            if (xxxxxxxxxxxx.yyyyyyyy(zzzzzzzzzzzzz[0]) == 'aaaaaaaaaaa' and xxxxxxxxxxxx.yyyyyyyy(zzzzzzzzzzzzz[0].mmmmmmmm[0]) == 'bbbbbbb'):
                pass
        # yapf: enable
        """)  # noqa
    expected_formatted_code = textwrap.dedent("""\
        def h():
            if (xxxxxxxxxxxx.yyyyyyyy(zzzzzzzzzzzzz[0]) == 'aaaaaaaaaaa' and
                    xxxxxxxxxxxx.yyyyyyyy(zzzzzzzzzzzzz[0].mmmmmmmm[0]) == 'bbbbbbb'):
                pass


        # yapf: disable
        def g():
            if (xxxxxxxxxxxx.yyyyyyyy(zzzzzzzzzzzzz[0]) == 'aaaaaaaaaaa' and xxxxxxxxxxxx.yyyyyyyy(zzzzzzzzzzzzz[0].mmmmmmmm[0]) == 'bbbbbbb'):
                pass
        # yapf: enable
        """)  # noqa
    self.assertYapfReformats(unformatted_code, expected_formatted_code)

  def testReformattingSkippingToEndOfFile(self):
    unformatted_code = textwrap.dedent("""\
        def h():
            if (xxxxxxxxxxxx.yyyyyyyy(zzzzzzzzzzzzz[0]) == 'aaaaaaaaaaa' and xxxxxxxxxxxx.yyyyyyyy(zzzzzzzzzzzzz[0].mmmmmmmm[0]) == 'bbbbbbb'):
                pass

        # yapf: disable
        def g():
            if (xxxxxxxxxxxx.yyyyyyyy(zzzzzzzzzzzzz[0]) == 'aaaaaaaaaaa' and xxxxxxxxxxxx.yyyyyyyy(zzzzzzzzzzzzz[0].mmmmmmmm[0]) == 'bbbbbbb'):
                pass

        def f():
            def e():
                while (xxxxxxxxxxxxxxxxxxxxx(yyyyyyyyyyyyy[zzzzz]) == 'aaaaaaaaaaa' and
                       xxxxxxxxxxxxxxxxxxxxx(yyyyyyyyyyyyy[zzzzz].aaaaaaaa[0]) ==
                       'bbbbbbb'):
                    pass
        """)  # noqa
    expected_formatted_code = textwrap.dedent("""\
        def h():
            if (xxxxxxxxxxxx.yyyyyyyy(zzzzzzzzzzzzz[0]) == 'aaaaaaaaaaa' and
                    xxxxxxxxxxxx.yyyyyyyy(zzzzzzzzzzzzz[0].mmmmmmmm[0]) == 'bbbbbbb'):
                pass


        # yapf: disable
        def g():
            if (xxxxxxxxxxxx.yyyyyyyy(zzzzzzzzzzzzz[0]) == 'aaaaaaaaaaa' and xxxxxxxxxxxx.yyyyyyyy(zzzzzzzzzzzzz[0].mmmmmmmm[0]) == 'bbbbbbb'):
                pass

        def f():
            def e():
                while (xxxxxxxxxxxxxxxxxxxxx(yyyyyyyyyyyyy[zzzzz]) == 'aaaaaaaaaaa' and
                       xxxxxxxxxxxxxxxxxxxxx(yyyyyyyyyyyyy[zzzzz].aaaaaaaa[0]) ==
                       'bbbbbbb'):
                    pass
        """)  # noqa
    self.assertYapfReformats(unformatted_code, expected_formatted_code)

  def testReformattingSkippingSingleLine(self):
    unformatted_code = textwrap.dedent("""\
        def h():
            if (xxxxxxxxxxxx.yyyyyyyy(zzzzzzzzzzzzz[0]) == 'aaaaaaaaaaa' and xxxxxxxxxxxx.yyyyyyyy(zzzzzzzzzzzzz[0].mmmmmmmm[0]) == 'bbbbbbb'):
                pass

        def g():
            if (xxxxxxxxxxxx.yyyyyyyy(zzzzzzzzzzzzz[0]) == 'aaaaaaaaaaa' and xxxxxxxxxxxx.yyyyyyyy(zzzzzzzzzzzzz[0].mmmmmmmm[0]) == 'bbbbbbb'):  # yapf: disable
                pass
        """)  # noqa
    expected_formatted_code = textwrap.dedent("""\
        def h():
            if (xxxxxxxxxxxx.yyyyyyyy(zzzzzzzzzzzzz[0]) == 'aaaaaaaaaaa' and
                    xxxxxxxxxxxx.yyyyyyyy(zzzzzzzzzzzzz[0].mmmmmmmm[0]) == 'bbbbbbb'):
                pass


        def g():
            if (xxxxxxxxxxxx.yyyyyyyy(zzzzzzzzzzzzz[0]) == 'aaaaaaaaaaa' and xxxxxxxxxxxx.yyyyyyyy(zzzzzzzzzzzzz[0].mmmmmmmm[0]) == 'bbbbbbb'):  # yapf: disable
                pass
        """)  # noqa
    self.assertYapfReformats(unformatted_code, expected_formatted_code)

  def testDisableWholeDataStructure(self):
    unformatted_code = textwrap.dedent("""\
        A = set([
            'hello',
            'world',
        ])  # yapf: disable
        """)
    expected_formatted_code = textwrap.dedent("""\
        A = set([
            'hello',
            'world',
        ])  # yapf: disable
        """)
    self.assertYapfReformats(unformatted_code, expected_formatted_code)

  def testDisableButAdjustIndentations(self):
    unformatted_code = textwrap.dedent("""\
        class SplitPenaltyTest(unittest.TestCase):

          def testUnbreakable(self):
            self._CheckPenalties(tree, [
            ])  # yapf: disable
        """)
    expected_formatted_code = textwrap.dedent("""\
        class SplitPenaltyTest(unittest.TestCase):

            def testUnbreakable(self):
                self._CheckPenalties(tree, [
                ])  # yapf: disable
        """)
    self.assertYapfReformats(unformatted_code, expected_formatted_code)

  def testRetainingHorizontalWhitespace(self):
    unformatted_code = textwrap.dedent("""\
        def h():
            if (xxxxxxxxxxxx.yyyyyyyy(zzzzzzzzzzzzz[0]) == 'aaaaaaaaaaa' and xxxxxxxxxxxx.yyyyyyyy(zzzzzzzzzzzzz[0].mmmmmmmm[0]) == 'bbbbbbb'):
                pass

        def g():
            if (xxxxxxxxxxxx.yyyyyyyy        (zzzzzzzzzzzzz  [0]) ==     'aaaaaaaaaaa' and    xxxxxxxxxxxx.yyyyyyyy(zzzzzzzzzzzzz[0].mmmmmmmm[0]) == 'bbbbbbb'):  # yapf: disable
                pass
        """)  # noqa
    expected_formatted_code = textwrap.dedent("""\
        def h():
            if (xxxxxxxxxxxx.yyyyyyyy(zzzzzzzzzzzzz[0]) == 'aaaaaaaaaaa' and
                    xxxxxxxxxxxx.yyyyyyyy(zzzzzzzzzzzzz[0].mmmmmmmm[0]) == 'bbbbbbb'):
                pass


        def g():
            if (xxxxxxxxxxxx.yyyyyyyy        (zzzzzzzzzzzzz  [0]) ==     'aaaaaaaaaaa' and    xxxxxxxxxxxx.yyyyyyyy(zzzzzzzzzzzzz[0].mmmmmmmm[0]) == 'bbbbbbb'):  # yapf: disable
                pass
        """)  # noqa
    self.assertYapfReformats(unformatted_code, expected_formatted_code)

  def testRetainingVerticalWhitespace(self):
    unformatted_code = textwrap.dedent("""\
        def h():
            if (xxxxxxxxxxxx.yyyyyyyy(zzzzzzzzzzzzz[0]) == 'aaaaaaaaaaa' and xxxxxxxxxxxx.yyyyyyyy(zzzzzzzzzzzzz[0].mmmmmmmm[0]) == 'bbbbbbb'):
                pass

        def g():


            if (xxxxxxxxxxxx.yyyyyyyy(zzzzzzzzzzzzz[0]) == 'aaaaaaaaaaa' and xxxxxxxxxxxx.yyyyyyyy(zzzzzzzzzzzzz[0].mmmmmmmm[0]) == 'bbbbbbb'):

                pass
        """)  # noqa
    expected_formatted_code = textwrap.dedent("""\
        def h():
            if (xxxxxxxxxxxx.yyyyyyyy(zzzzzzzzzzzzz[0]) == 'aaaaaaaaaaa' and
                    xxxxxxxxxxxx.yyyyyyyy(zzzzzzzzzzzzz[0].mmmmmmmm[0]) == 'bbbbbbb'):
                pass

        def g():


            if (xxxxxxxxxxxx.yyyyyyyy(zzzzzzzzzzzzz[0]) == 'aaaaaaaaaaa' and xxxxxxxxxxxx.yyyyyyyy(zzzzzzzzzzzzz[0].mmmmmmmm[0]) == 'bbbbbbb'):

                pass
        """)  # noqa
    self.assertYapfReformats(
        unformatted_code,
        expected_formatted_code,
        extra_options=['--lines', '1-2'])

    unformatted_code = textwrap.dedent("""\


        if a:     b


        if c:
            to_much      + indent

            same



        #comment

        #   trailing whitespace
        """)
    expected_formatted_code = textwrap.dedent("""\
        if a: b


        if c:
            to_much      + indent

            same



        #comment

        #   trailing whitespace
        """)
    self.assertYapfReformats(
        unformatted_code,
        expected_formatted_code,
        extra_options=['--lines', '3-3', '--lines', '13-13'])

    unformatted_code = textwrap.dedent("""\
        '''
        docstring

        '''

        import blah
        """)

    self.assertYapfReformats(
        unformatted_code, unformatted_code, extra_options=['--lines', '2-2'])

  def testVerticalSpacingWithCommentWithContinuationMarkers(self):
    unformatted_code = """\
# \\
# \\
# \\

x = {
}
"""
    expected_formatted_code = """\
# \\
# \\
# \\

x = {
}
"""
    self.assertYapfReformats(
        unformatted_code,
        expected_formatted_code,
        extra_options=['--lines', '1-1'])

  def testRetainingSemicolonsWhenSpecifyingLines(self):
    unformatted_code = textwrap.dedent("""\
        a = line_to_format
        def f():
            x = y + 42; z = n * 42
            if True: a += 1 ; b += 1 ; c += 1
        """)
    expected_formatted_code = textwrap.dedent("""\
        a = line_to_format
        def f():
            x = y + 42; z = n * 42
            if True: a += 1 ; b += 1 ; c += 1
        """)
    self.assertYapfReformats(
        unformatted_code,
        expected_formatted_code,
        extra_options=['--lines', '1-1'])

  def testDisabledMultilineStrings(self):
    unformatted_code = textwrap.dedent('''\
        foo=42
        def f():
            email_text += """<html>This is a really long docstring that goes over the column limit and is multi-line.<br><br>
        <b>Czar: </b>"""+despot["Nicholas"]+"""<br>
        <b>Minion: </b>"""+serf["Dmitri"]+"""<br>
        <b>Residence: </b>"""+palace["Winter"]+"""<br>
        </body>
        </html>"""
        ''')  # noqa
    expected_formatted_code = textwrap.dedent('''\
        foo = 42
        def f():
            email_text += """<html>This is a really long docstring that goes over the column limit and is multi-line.<br><br>
        <b>Czar: </b>"""+despot["Nicholas"]+"""<br>
        <b>Minion: </b>"""+serf["Dmitri"]+"""<br>
        <b>Residence: </b>"""+palace["Winter"]+"""<br>
        </body>
        </html>"""
        ''')  # noqa
    self.assertYapfReformats(
        unformatted_code,
        expected_formatted_code,
        extra_options=['--lines', '1-1'])

  def testDisableWhenSpecifyingLines(self):
    unformatted_code = textwrap.dedent("""\
        # yapf: disable
        A = set([
            'hello',
            'world',
        ])
        # yapf: enable
        B = set([
            'hello',
            'world',
        ])  # yapf: disable
        """)
    expected_formatted_code = textwrap.dedent("""\
        # yapf: disable
        A = set([
            'hello',
            'world',
        ])
        # yapf: enable
        B = set([
            'hello',
            'world',
        ])  # yapf: disable
        """)
    self.assertYapfReformats(
        unformatted_code,
        expected_formatted_code,
        extra_options=['--lines', '1-10'])

  def testDisableFormattingInDataLiteral(self):
    unformatted_code = textwrap.dedent("""\
        def horrible():
          oh_god()
          why_would_you()
          [
             'do',

              'that',
          ]

        def still_horrible():
            oh_god()
            why_would_you()
            [
                'do',

                'that'
            ]
        """)
    expected_formatted_code = textwrap.dedent("""\
        def horrible():
            oh_god()
            why_would_you()
            [
               'do',

                'that',
            ]

        def still_horrible():
            oh_god()
            why_would_you()
            ['do', 'that']
        """)
    self.assertYapfReformats(
        unformatted_code,
        expected_formatted_code,
        extra_options=['--lines', '14-15'])

  def testRetainVerticalFormattingBetweenDisabledAndEnabledLines(self):
    unformatted_code = textwrap.dedent("""\
        class A(object):
            def aaaaaaaaaaaaa(self):
                c = bbbbbbbbb.ccccccccc('challenge', 0, 1, 10)
                self.assertEqual(
                    ('ddddddddddddddddddddddddd',
             'eeeeeeeeeeeeeeeeeeeeeeeee.%s' %
                     c.ffffffffffff),
             gggggggggggg.hhhhhhhhh(c, c.ffffffffffff))
                iiiii = jjjjjjjjjjjjjj.iiiii
        """)
    expected_formatted_code = textwrap.dedent("""\
        class A(object):
            def aaaaaaaaaaaaa(self):
                c = bbbbbbbbb.ccccccccc('challenge', 0, 1, 10)
                self.assertEqual(('ddddddddddddddddddddddddd',
                                  'eeeeeeeeeeeeeeeeeeeeeeeee.%s' % c.ffffffffffff),
                                 gggggggggggg.hhhhhhhhh(c, c.ffffffffffff))
                iiiii = jjjjjjjjjjjjjj.iiiii
        """)  # noqa
    self.assertYapfReformats(
        unformatted_code,
        expected_formatted_code,
        extra_options=['--lines', '4-7'])

  def testRetainVerticalFormattingBetweenDisabledLines(self):
    unformatted_code = textwrap.dedent("""\
        class A(object):
            def aaaaaaaaaaaaa(self):
                pass


            def bbbbbbbbbbbbb(self):  # 5
                pass
        """)
    expected_formatted_code = textwrap.dedent("""\
        class A(object):
            def aaaaaaaaaaaaa(self):
                pass


            def bbbbbbbbbbbbb(self):  # 5
                pass
        """)
    self.assertYapfReformats(
        unformatted_code,
        expected_formatted_code,
        extra_options=['--lines', '4-4'])

  def testFormatLinesSpecifiedInMiddleOfExpression(self):
    unformatted_code = textwrap.dedent("""\
        class A(object):
            def aaaaaaaaaaaaa(self):
                c = bbbbbbbbb.ccccccccc('challenge', 0, 1, 10)
                self.assertEqual(
                    ('ddddddddddddddddddddddddd',
             'eeeeeeeeeeeeeeeeeeeeeeeee.%s' %
                     c.ffffffffffff),
             gggggggggggg.hhhhhhhhh(c, c.ffffffffffff))
                iiiii = jjjjjjjjjjjjjj.iiiii
        """)
    expected_formatted_code = textwrap.dedent("""\
        class A(object):
            def aaaaaaaaaaaaa(self):
                c = bbbbbbbbb.ccccccccc('challenge', 0, 1, 10)
                self.assertEqual(('ddddddddddddddddddddddddd',
                                  'eeeeeeeeeeeeeeeeeeeeeeeee.%s' % c.ffffffffffff),
                                 gggggggggggg.hhhhhhhhh(c, c.ffffffffffff))
                iiiii = jjjjjjjjjjjjjj.iiiii
        """)  # noqa
    self.assertYapfReformats(
        unformatted_code,
        expected_formatted_code,
        extra_options=['--lines', '5-6'])

  def testCommentFollowingMultilineString(self):
    unformatted_code = textwrap.dedent("""\
        def foo():
            '''First line.
            Second line.
            '''  # comment
            x = '''hello world'''  # second comment
            return 42  # another comment
        """)
    expected_formatted_code = textwrap.dedent("""\
        def foo():
            '''First line.
            Second line.
            '''  # comment
            x = '''hello world'''  # second comment
            return 42  # another comment
        """)
    self.assertYapfReformats(
        unformatted_code,
        expected_formatted_code,
        extra_options=['--lines', '1-1'])

  def testDedentClosingBracket(self):
    # no line-break on the first argument, not dedenting closing brackets
    unformatted_code = textwrap.dedent("""\
      def overly_long_function_name(first_argument_on_the_same_line,
      second_argument_makes_the_line_too_long):
        pass
    """)
    expected_formatted_code = textwrap.dedent("""\
      def overly_long_function_name(first_argument_on_the_same_line,
                                    second_argument_makes_the_line_too_long):
          pass
    """)
    self.assertYapfReformats(
        unformatted_code,
        expected_formatted_code,
        extra_options=['--style=pep8'])

    # TODO(ambv): currently the following produces the closing bracket on a new
    # line but indented to the opening bracket which is the worst of both
    # worlds. Expected behaviour would be to format as --style=pep8 does in
    # this case.
    # self.assertYapfReformats(unformatted_code, expected_formatted_code,
    #                          extra_options=['--style=facebook'])

    # line-break before the first argument, dedenting closing brackets if set
    unformatted_code = textwrap.dedent("""\
      def overly_long_function_name(
        first_argument_on_the_same_line,
        second_argument_makes_the_line_too_long):
        pass
    """)
    # expected_formatted_pep8_code = textwrap.dedent("""\
    #   def overly_long_function_name(
    #           first_argument_on_the_same_line,
    #           second_argument_makes_the_line_too_long):
    #       pass
    # """)
    expected_formatted_fb_code = textwrap.dedent("""\
      def overly_long_function_name(
          first_argument_on_the_same_line, second_argument_makes_the_line_too_long
      ):
          pass
    """)  # noqa
    self.assertYapfReformats(
        unformatted_code,
        expected_formatted_fb_code,
        extra_options=['--style=facebook'])
    # TODO(ambv): currently the following produces code that is not PEP8
    # compliant, raising "E125 continuation line with same indent as next
    # logical line" with flake8. Expected behaviour for PEP8 would be to use
    # double-indentation here.
    # self.assertYapfReformats(unformatted_code, expected_formatted_pep8_code,
    #                          extra_options=['--style=pep8'])

  def testCoalesceBrackets(self):
    unformatted_code = textwrap.dedent("""\
       some_long_function_name_foo(
           {
               'first_argument_of_the_thing': id,
               'second_argument_of_the_thing': "some thing"
           }
       )""")
    expected_formatted_code = textwrap.dedent("""\
       some_long_function_name_foo({
           'first_argument_of_the_thing': id,
           'second_argument_of_the_thing': "some thing"
       })
       """)
    with utils.NamedTempFile(dirname=self.test_tmpdir, mode='w') as (f, name):
      f.write(
          textwrap.dedent(u'''\
          [style]
          column_limit=82
          coalesce_brackets = True
          '''))
      f.flush()
      self.assertYapfReformats(
          unformatted_code,
          expected_formatted_code,
          extra_options=['--style={0}'.format(name)])

  def testPseudoParenSpaces(self):
    unformatted_code = textwrap.dedent("""\
        def   foo():
          def bar():
            return {msg_id: author for author, msg_id in reader}
        """)
    expected_formatted_code = textwrap.dedent("""\
        def foo():
          def bar():
            return {msg_id: author for author, msg_id in reader}
        """)
    self.assertYapfReformats(
        unformatted_code,
        expected_formatted_code,
        extra_options=['--lines', '1-1', '--style', 'yapf'])

  def testMultilineCommentFormattingDisabled(self):
    unformatted_code = textwrap.dedent("""\
        # This is a comment
        FOO = {
            aaaaaaaa.ZZZ: [
                bbbbbbbbbb.Pop(),
                # Multiline comment.
                # Line two.
                bbbbbbbbbb.Pop(),
            ],
            'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx':
                ('yyyyy', zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz),
            '#': lambda x: x  # do nothing
        }
        """)
    expected_formatted_code = textwrap.dedent("""\
        # This is a comment
        FOO = {
            aaaaaaaa.ZZZ: [
                bbbbbbbbbb.Pop(),
                # Multiline comment.
                # Line two.
                bbbbbbbbbb.Pop(),
            ],
            'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx':
                ('yyyyy', zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz),
            '#': lambda x: x  # do nothing
        }
        """)
    self.assertYapfReformats(
        unformatted_code,
        expected_formatted_code,
        extra_options=['--lines', '1-1', '--style', 'yapf'])

  def testTrailingCommentsWithDisabledFormatting(self):
    unformatted_code = textwrap.dedent("""\
        import os

        SCOPES = [
            'hello world'  # This is a comment.
        ]
        """)
    expected_formatted_code = textwrap.dedent("""\
        import os

        SCOPES = [
            'hello world'  # This is a comment.
        ]
        """)
    self.assertYapfReformats(
        unformatted_code,
        expected_formatted_code,
        extra_options=['--lines', '1-1', '--style', 'yapf'])

  def testUseTabs(self):
    unformatted_code = """\
def foo_function():
 if True:
  pass
"""
    expected_formatted_code = """\
def foo_function():
	if True:
		pass
"""  # noqa: W191,E101
    style_contents = u"""\
[style]
based_on_style = yapf
USE_TABS = true
INDENT_WIDTH=1
"""
    with utils.TempFileContents(self.test_tmpdir, style_contents) as stylepath:
      self.assertYapfReformats(
          unformatted_code,
          expected_formatted_code,
          extra_options=['--style={0}'.format(stylepath)])

  def testUseTabsWith(self):
    unformatted_code = """\
def f():
  return ['hello', 'world',]
"""
    expected_formatted_code = """\
def f():
	return [
	    'hello',
	    'world',
	]
"""  # noqa: W191,E101
    style_contents = u"""\
[style]
based_on_style = yapf
USE_TABS = true
INDENT_WIDTH=1
"""
    with utils.TempFileContents(self.test_tmpdir, style_contents) as stylepath:
      self.assertYapfReformats(
          unformatted_code,
          expected_formatted_code,
          extra_options=['--style={0}'.format(stylepath)])

  def testUseTabsContinuationAlignStyleFixed(self):
    unformatted_code = """\
def foo_function(arg1, arg2, arg3):
  return ['hello', 'world',]
"""
    expected_formatted_code = """\
def foo_function(
		arg1, arg2, arg3):
	return [
			'hello',
			'world',
	]
"""  # noqa: W191,E101
    style_contents = u"""\
[style]
based_on_style = yapf
USE_TABS = true
COLUMN_LIMIT=32
INDENT_WIDTH=4
CONTINUATION_INDENT_WIDTH=8
CONTINUATION_ALIGN_STYLE = fixed
"""
    with utils.TempFileContents(self.test_tmpdir, style_contents) as stylepath:
      self.assertYapfReformats(
          unformatted_code,
          expected_formatted_code,
          extra_options=['--style={0}'.format(stylepath)])

  def testUseTabsContinuationAlignStyleVAlignRight(self):
    unformatted_code = """\
def foo_function(arg1, arg2, arg3):
  return ['hello', 'world',]
"""
    expected_formatted_code = """\
def foo_function(arg1, arg2,
					arg3):
	return [
			'hello',
			'world',
	]
"""  # noqa: W191,E101
    style_contents = u"""\
[style]
based_on_style = yapf
USE_TABS = true
COLUMN_LIMIT=32
INDENT_WIDTH=4
CONTINUATION_INDENT_WIDTH=8
CONTINUATION_ALIGN_STYLE = valign-right
"""
    with utils.TempFileContents(self.test_tmpdir, style_contents) as stylepath:
      self.assertYapfReformats(
          unformatted_code,
          expected_formatted_code,
          extra_options=['--style={0}'.format(stylepath)])

  def testUseSpacesContinuationAlignStyleFixed(self):
    unformatted_code = """\
def foo_function(arg1, arg2, arg3):
  return ['hello', 'world',]
"""
    expected_formatted_code = """\
def foo_function(
        arg1, arg2, arg3):
    return [
            'hello',
            'world',
    ]
"""
    style_contents = u"""\
[style]
based_on_style = yapf
COLUMN_LIMIT=32
INDENT_WIDTH=4
CONTINUATION_INDENT_WIDTH=8
CONTINUATION_ALIGN_STYLE = fixed
"""
    with utils.TempFileContents(self.test_tmpdir, style_contents) as stylepath:
      self.assertYapfReformats(
          unformatted_code,
          expected_formatted_code,
          extra_options=['--style={0}'.format(stylepath)])

  def testUseSpacesContinuationAlignStyleVAlignRight(self):
    unformatted_code = """\
def foo_function(arg1, arg2, arg3):
  return ['hello', 'world',]
"""
    expected_formatted_code = """\
def foo_function(arg1, arg2,
                    arg3):
    return [
            'hello',
            'world',
    ]
"""
    style_contents = u"""\
[style]
based_on_style = yapf
COLUMN_LIMIT=32
INDENT_WIDTH=4
CONTINUATION_INDENT_WIDTH=8
CONTINUATION_ALIGN_STYLE = valign-right
"""
    with utils.TempFileContents(self.test_tmpdir, style_contents) as stylepath:
      self.assertYapfReformats(
          unformatted_code,
          expected_formatted_code,
          extra_options=['--style={0}'.format(stylepath)])

  def testStyleOutputRoundTrip(self):
    unformatted_code = textwrap.dedent("""\
        def foo_function():
          pass
        """)
    expected_formatted_code = textwrap.dedent("""\
        def foo_function():
            pass
        """)

    with utils.NamedTempFile(dirname=self.test_tmpdir) as (stylefile,
                                                           stylepath):
      p = subprocess.Popen(
          YAPF_BINARY + ['--style-help'],
          stdout=stylefile,
          stdin=subprocess.PIPE,
          stderr=subprocess.PIPE)
      _, stderrdata = p.communicate()
      self.assertEqual(stderrdata, b'')
      self.assertYapfReformats(
          unformatted_code,
          expected_formatted_code,
          extra_options=['--style={0}'.format(stylepath)])

  def testSpacingBeforeComments(self):
    unformatted_code = textwrap.dedent("""\
        A = 42


        # A comment
        def x():
            pass
        def _():
            pass
        """)
    expected_formatted_code = textwrap.dedent("""\
        A = 42


        # A comment
        def x():
            pass
        def _():
            pass
        """)
    self.assertYapfReformats(
        unformatted_code,
        expected_formatted_code,
        extra_options=['--lines', '1-2'])

  def testSpacingBeforeCommentsInDicts(self):
    unformatted_code = textwrap.dedent("""\
        A=42

        X = {
            # 'Valid' statuses.
            PASSED:  # Passed
                'PASSED',
            FAILED:  # Failed
                'FAILED',
            TIMED_OUT:  # Timed out.
                'FAILED',
            BORKED:  # Broken.
                'BROKEN'
        }
        """)
    expected_formatted_code = textwrap.dedent("""\
        A = 42

        X = {
            # 'Valid' statuses.
            PASSED:  # Passed
                'PASSED',
            FAILED:  # Failed
                'FAILED',
            TIMED_OUT:  # Timed out.
                'FAILED',
            BORKED:  # Broken.
                'BROKEN'
        }
        """)
    self.assertYapfReformats(
        unformatted_code,
        expected_formatted_code,
        extra_options=['--style', 'yapf', '--lines', '1-1'])

  def testDisableWithLinesOption(self):
    unformatted_code = textwrap.dedent("""\
        # yapf_lines_bug.py
        # yapf: disable
        def outer_func():
            def inner_func():
                return
            return
        # yapf: enable
        """)
    expected_formatted_code = textwrap.dedent("""\
        # yapf_lines_bug.py
        # yapf: disable
        def outer_func():
            def inner_func():
                return
            return
        # yapf: enable
        """)
    self.assertYapfReformats(
        unformatted_code,
        expected_formatted_code,
        extra_options=['--lines', '1-8'])

  @unittest.skipUnless(py3compat.PY36, 'Requires Python 3.6')
  def testNoSpacesAroundBinaryOperators(self):
    unformatted_code = """\
a = 4-b/c@d**37
"""
    expected_formatted_code = """\
a = 4-b / c@d**37
"""
    self.assertYapfReformats(
        unformatted_code,
        expected_formatted_code,
        extra_options=[
            '--style',
            '{based_on_style: pep8, '
            'no_spaces_around_selected_binary_operators: "@,**,-"}',
        ])

  @unittest.skipUnless(py3compat.PY36, 'Requires Python 3.6')
  def testCP936Encoding(self):
    unformatted_code = 'print("中文")\n'
    expected_formatted_code = 'print("中文")\n'
    self.assertYapfReformats(
        unformatted_code,
        expected_formatted_code,
        env={'PYTHONIOENCODING': 'cp936'})

  def testDisableWithLineRanges(self):
    unformatted_code = """\
# yapf: disable
a = [
    1,
    2,

    3
]
"""
    expected_formatted_code = """\
# yapf: disable
a = [
    1,
    2,

    3
]
"""
    self.assertYapfReformats(
        unformatted_code,
        expected_formatted_code,
        extra_options=['--style', 'yapf', '--lines', '1-100'])


class BadInputTest(unittest.TestCase):
  """Test yapf's behaviour when passed bad input."""

  def testBadSyntax(self):
    code = '  a = 1\n'
    self.assertRaises(errors.YapfError, yapf_api.FormatCode, code)

  def testBadCode(self):
    code = 'x = """hello\n'
    self.assertRaises(errors.YapfError, yapf_api.FormatCode, code)


class DiffIndentTest(unittest.TestCase):

  @staticmethod
  def _OwnStyle():
    my_style = style.CreatePEP8Style()
    my_style['INDENT_WIDTH'] = 3
    my_style['CONTINUATION_INDENT_WIDTH'] = 3
    return my_style

  def _Check(self, unformatted_code, expected_formatted_code):
    formatted_code, _ = yapf_api.FormatCode(
        unformatted_code, style_config=style.SetGlobalStyle(self._OwnStyle()))
    self.assertEqual(expected_formatted_code, formatted_code)

  def testSimple(self):
    unformatted_code = textwrap.dedent("""\
        for i in range(5):
         print('bar')
         """)
    expected_formatted_code = textwrap.dedent("""\
        for i in range(5):
           print('bar')
           """)
    self._Check(unformatted_code, expected_formatted_code)


class HorizontallyAlignedTrailingCommentsTest(yapf_test_helper.YAPFTest):

  @staticmethod
  def _OwnStyle():
    my_style = style.CreatePEP8Style()
    my_style['SPACES_BEFORE_COMMENT'] = [
        15,
        25,
        35,
    ]
    return my_style

  def _Check(self, unformatted_code, expected_formatted_code):
    formatted_code, _ = yapf_api.FormatCode(
        unformatted_code, style_config=style.SetGlobalStyle(self._OwnStyle()))
    self.assertCodeEqual(expected_formatted_code, formatted_code)

  def testSimple(self):
    unformatted_code = textwrap.dedent("""\
        foo = '1' # Aligned at first list value

        foo = '2__<15>' # Aligned at second list value

        foo = '3____________<25>' # Aligned at third list value

        foo = '4______________________<35>' # Aligned beyond list values
        """)
    expected_formatted_code = textwrap.dedent("""\
        foo = '1'     # Aligned at first list value

        foo = '2__<15>'         # Aligned at second list value

        foo = '3____________<25>'         # Aligned at third list value

        foo = '4______________________<35>' # Aligned beyond list values
        """)
    self._Check(unformatted_code, expected_formatted_code)

  def testBlock(self):
    unformatted_code = textwrap.dedent("""\
        func(1)     # Line 1
        func(2) # Line 2
        # Line 3
        func(3)                             # Line 4
                                            # Line 5
                                            # Line 6
        """)
    expected_formatted_code = textwrap.dedent("""\
        func(1)       # Line 1
        func(2)       # Line 2
                      # Line 3
        func(3)       # Line 4
                      # Line 5
                      # Line 6
        """)
    self._Check(unformatted_code, expected_formatted_code)

  def testBlockWithLongLine(self):
    unformatted_code = textwrap.dedent("""\
        func(1)     # Line 1
        func___________________(2) # Line 2
        # Line 3
        func(3)                             # Line 4
                                            # Line 5
                                            # Line 6
        """)
    expected_formatted_code = textwrap.dedent("""\
        func(1)                           # Line 1
        func___________________(2)        # Line 2
                                          # Line 3
        func(3)                           # Line 4
                                          # Line 5
                                          # Line 6
        """)
    self._Check(unformatted_code, expected_formatted_code)

  def testBlockFuncSuffix(self):
    unformatted_code = textwrap.dedent("""\
        func(1)     # Line 1
        func(2) # Line 2
        # Line 3
        func(3)                             # Line 4
                                        # Line 5
                                    # Line 6

        def Func():
            pass
        """)
    expected_formatted_code = textwrap.dedent("""\
        func(1)       # Line 1
        func(2)       # Line 2
                      # Line 3
        func(3)       # Line 4
                      # Line 5
                      # Line 6


        def Func():
            pass
        """)
    self._Check(unformatted_code, expected_formatted_code)

  def testBlockCommentSuffix(self):
    unformatted_code = textwrap.dedent("""\
        func(1)     # Line 1
        func(2) # Line 2
        # Line 3
        func(3)                             # Line 4
                                        # Line 5 - SpliceComments makes this part of the previous block
                                    # Line 6

                                            # Aligned with prev comment block
        """)  # noqa
    expected_formatted_code = textwrap.dedent("""\
        func(1)       # Line 1
        func(2)       # Line 2
                      # Line 3
        func(3)       # Line 4
                      # Line 5 - SpliceComments makes this part of the previous block
                      # Line 6

                      # Aligned with prev comment block
        """)  # noqa
    self._Check(unformatted_code, expected_formatted_code)

  def testBlockIndentedFuncSuffix(self):
    unformatted_code = textwrap.dedent("""\
        if True:
            func(1)     # Line 1
            func(2) # Line 2
            # Line 3
            func(3)                             # Line 4
                                                # Line 5 - SpliceComments makes this a new block
                                                # Line 6

                                                # Aligned with Func

            def Func():
                pass
        """)  # noqa
    expected_formatted_code = textwrap.dedent("""\
        if True:
            func(1)   # Line 1
            func(2)   # Line 2
                      # Line 3
            func(3)   # Line 4

            # Line 5 - SpliceComments makes this a new block
            # Line 6

            # Aligned with Func


            def Func():
                pass
        """)
    self._Check(unformatted_code, expected_formatted_code)

  def testBlockIndentedCommentSuffix(self):
    unformatted_code = textwrap.dedent("""\
        if True:
            func(1)     # Line 1
            func(2) # Line 2
            # Line 3
            func(3)                             # Line 4
                                                # Line 5
                                                # Line 6

                                                # Not aligned
        """)
    expected_formatted_code = textwrap.dedent("""\
        if True:
            func(1)   # Line 1
            func(2)   # Line 2
                      # Line 3
            func(3)   # Line 4
                      # Line 5
                      # Line 6

            # Not aligned
        """)
    self._Check(unformatted_code, expected_formatted_code)

  def testBlockMultiIndented(self):
    unformatted_code = textwrap.dedent("""\
        if True:
            if True:
                if True:
                    func(1)     # Line 1
                    func(2) # Line 2
                    # Line 3
                    func(3)                             # Line 4
                                                        # Line 5
                                                        # Line 6

                                                        # Not aligned
        """)  # noqa
    expected_formatted_code = textwrap.dedent("""\
        if True:
            if True:
                if True:
                    func(1)     # Line 1
                    func(2)     # Line 2
                                # Line 3
                    func(3)     # Line 4
                                # Line 5
                                # Line 6

                    # Not aligned
        """)
    self._Check(unformatted_code, expected_formatted_code)

  def testArgs(self):
    unformatted_code = textwrap.dedent("""\
        def MyFunc(
            arg1,   # Desc 1
            arg2,   # Desc 2
            a_longer_var_name,  # Desc 3
            arg4,
            arg5,   # Desc 5
            arg6,
        ):
            pass
        """)
    expected_formatted_code = textwrap.dedent("""\
        def MyFunc(
            arg1,               # Desc 1
            arg2,               # Desc 2
            a_longer_var_name,  # Desc 3
            arg4,
            arg5,               # Desc 5
            arg6,
        ):
            pass
        """)
    self._Check(unformatted_code, expected_formatted_code)

  def testDisableBlock(self):
    unformatted_code = textwrap.dedent("""\
        a() # comment 1
        b() # comment 2

        # yapf: disable
        c() # comment 3
        d()   # comment 4
        # yapf: enable

        e() # comment 5
        f() # comment 6
        """)
    expected_formatted_code = textwrap.dedent("""\
        a()           # comment 1
        b()           # comment 2

        # yapf: disable
        c() # comment 3
        d()   # comment 4
        # yapf: enable

        e()           # comment 5
        f()           # comment 6
        """)
    self._Check(unformatted_code, expected_formatted_code)

  def testDisabledLine(self):
    unformatted_code = textwrap.dedent("""\
        short # comment 1
        do_not_touch1 # yapf: disable
        do_not_touch2   # yapf: disable
        a_longer_statement # comment 2
        """)
    expected_formatted_code = textwrap.dedent("""\
        short                   # comment 1
        do_not_touch1 # yapf: disable
        do_not_touch2   # yapf: disable
        a_longer_statement      # comment 2
        """)
    self._Check(unformatted_code, expected_formatted_code)


class _SpacesAroundDictListTupleTestImpl(unittest.TestCase):

  @staticmethod
  def _OwnStyle():
    my_style = style.CreatePEP8Style()
    my_style['DISABLE_ENDING_COMMA_HEURISTIC'] = True
    my_style['SPLIT_ALL_COMMA_SEPARATED_VALUES'] = False
    my_style['SPLIT_ARGUMENTS_WHEN_COMMA_TERMINATED'] = False
    return my_style

  def _Check(self, unformatted_code, expected_formatted_code):
    formatted_code, _ = yapf_api.FormatCode(
        unformatted_code, style_config=style.SetGlobalStyle(self._OwnStyle()))
    self.assertEqual(expected_formatted_code, formatted_code)

  def setUp(self):
    self.maxDiff = None


class SpacesAroundDictTest(_SpacesAroundDictListTupleTestImpl):

  @classmethod
  def _OwnStyle(cls):
    style = super(SpacesAroundDictTest, cls)._OwnStyle()
    style['SPACES_AROUND_DICT_DELIMITERS'] = True

    return style

  def testStandard(self):
    unformatted_code = textwrap.dedent("""\
      {1 : 2}
      {k:v for k, v in other.items()}
      {k for k in [1, 2, 3]}

      # The following statements should not change
      {}
      {1 : 2} # yapf: disable

      # yapf: disable
      {1 : 2}
      # yapf: enable

      # Dict settings should not impact lists or tuples
      [1, 2]
      (3, 4)
      """)
    expected_formatted_code = textwrap.dedent("""\
      { 1: 2 }
      { k: v for k, v in other.items() }
      { k for k in [1, 2, 3] }

      # The following statements should not change
      {}
      {1 : 2} # yapf: disable

      # yapf: disable
      {1 : 2}
      # yapf: enable

      # Dict settings should not impact lists or tuples
      [1, 2]
      (3, 4)
      """)

    self._Check(unformatted_code, expected_formatted_code)


class SpacesAroundListTest(_SpacesAroundDictListTupleTestImpl):

  @classmethod
  def _OwnStyle(cls):
    style = super(SpacesAroundListTest, cls)._OwnStyle()
    style['SPACES_AROUND_LIST_DELIMITERS'] = True

    return style

  def testStandard(self):
    unformatted_code = textwrap.dedent("""\
      [a,b,c]
      [4,5,]
      [6, [7, 8], 9]
      [v for v in [1,2,3] if v & 1]

      # The following statements should not change
      index[0]
      index[a, b]
      []
      [v for v in [1,2,3] if v & 1] # yapf: disable

      # yapf: disable
      [a,b,c]
      [4,5,]
      # yapf: enable

      # List settings should not impact dicts or tuples
      {a: b}
      (1, 2)
      """)
    expected_formatted_code = textwrap.dedent("""\
      [ a, b, c ]
      [ 4, 5, ]
      [ 6, [ 7, 8 ], 9 ]
      [ v for v in [ 1, 2, 3 ] if v & 1 ]

      # The following statements should not change
      index[0]
      index[a, b]
      []
      [v for v in [1,2,3] if v & 1] # yapf: disable

      # yapf: disable
      [a,b,c]
      [4,5,]
      # yapf: enable

      # List settings should not impact dicts or tuples
      {a: b}
      (1, 2)
      """)

    self._Check(unformatted_code, expected_formatted_code)


class SpacesAroundTupleTest(_SpacesAroundDictListTupleTestImpl):

  @classmethod
  def _OwnStyle(cls):
    style = super(SpacesAroundTupleTest, cls)._OwnStyle()
    style['SPACES_AROUND_TUPLE_DELIMITERS'] = True

    return style

  def testStandard(self):
    unformatted_code = textwrap.dedent("""\
      (0, 1)
      (2, 3)
      (4, 5, 6,)
      func((7, 8), 9)

      # The following statements should not change
      func(1, 2)
      (this_func or that_func)(3, 4)
      if (True and False): pass
      ()

      (0, 1) # yapf: disable

      # yapf: disable
      (0, 1)
      (2, 3)
      # yapf: enable

      # Tuple settings should not impact dicts or lists
      {a: b}
      [3, 4]
      """)
    expected_formatted_code = textwrap.dedent("""\
      ( 0, 1 )
      ( 2, 3 )
      ( 4, 5, 6, )
      func(( 7, 8 ), 9)

      # The following statements should not change
      func(1, 2)
      (this_func or that_func)(3, 4)
      if (True and False): pass
      ()

      (0, 1) # yapf: disable

      # yapf: disable
      (0, 1)
      (2, 3)
      # yapf: enable

      # Tuple settings should not impact dicts or lists
      {a: b}
      [3, 4]
      """)

    self._Check(unformatted_code, expected_formatted_code)


if __name__ == '__main__':
  unittest.main()
