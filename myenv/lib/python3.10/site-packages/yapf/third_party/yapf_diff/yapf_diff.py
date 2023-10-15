# Modified copy of clang-format-diff.py that works with yapf.
#
# Licensed under the Apache License, Version 2.0 (the "License") with LLVM
# Exceptions; you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://llvm.org/LICENSE.txt
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
This script reads input from a unified diff and reformats all the changed
lines. This is useful to reformat all the lines touched by a specific patch.
Example usage for git/svn users:

  git diff -U0 --no-color --relative HEAD^ | yapf-diff -i
  svn diff --diff-cmd=diff -x-U0 | yapf-diff -p0 -i

It should be noted that the filename contained in the diff is used unmodified
to determine the source file to update. Users calling this script directly
should be careful to ensure that the path in the diff is correct relative to the
current working directory.
"""
from __future__ import absolute_import, division, print_function

import argparse
import difflib
import re
import subprocess
import sys

if sys.version_info.major >= 3:
  from io import StringIO
else:
  from io import BytesIO as StringIO


def main():
  parser = argparse.ArgumentParser(
      description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
  parser.add_argument(
      '-i',
      '--in-place',
      action='store_true',
      default=False,
      help='apply edits to files instead of displaying a diff')
  parser.add_argument(
      '-p',
      '--prefix',
      metavar='NUM',
      default=1,
      help='strip the smallest prefix containing P slashes')
  parser.add_argument(
      '--regex',
      metavar='PATTERN',
      default=None,
      help='custom pattern selecting file paths to reformat '
      '(case sensitive, overrides -iregex)')
  parser.add_argument(
      '--iregex',
      metavar='PATTERN',
      default=r'.*\.(py)',
      help='custom pattern selecting file paths to reformat '
      '(case insensitive, overridden by -regex)')
  parser.add_argument(
      '-v',
      '--verbose',
      action='store_true',
      help='be more verbose, ineffective without -i')
  parser.add_argument(
      '--style',
      help='specify formatting style: either a style name (for '
      'example "pep8" or "google"), or the name of a file with '
      'style settings. The default is pep8 unless a '
      '.style.yapf or setup.cfg file located in one of the '
      'parent directories of the source file (or current '
      'directory for stdin)')
  parser.add_argument(
      '--binary', default='yapf', help='location of binary to use for yapf')
  args = parser.parse_args()

  # Extract changed lines for each file.
  filename = None
  lines_by_file = {}
  for line in sys.stdin:
    match = re.search(r'^\+\+\+\ (.*?/){%s}(\S*)' % args.prefix, line)
    if match:
      filename = match.group(2)
    if filename is None:
      continue

    if args.regex is not None:
      if not re.match('^%s$' % args.regex, filename):
        continue
    elif not re.match('^%s$' % args.iregex, filename, re.IGNORECASE):
      continue

    match = re.search(r'^@@.*\+(\d+)(,(\d+))?', line)
    if match:
      start_line = int(match.group(1))
      line_count = 1
      if match.group(3):
        line_count = int(match.group(3))
      if line_count == 0:
        continue
      end_line = start_line + line_count - 1
      lines_by_file.setdefault(filename, []).extend(
          ['--lines', str(start_line) + '-' + str(end_line)])

  # Reformat files containing changes in place.
  for filename, lines in lines_by_file.items():
    if args.in_place and args.verbose:
      print('Formatting {}'.format(filename))
    command = [args.binary, filename]
    if args.in_place:
      command.append('-i')
    command.extend(lines)
    if args.style:
      command.extend(['--style', args.style])
    p = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=None,
        stdin=subprocess.PIPE,
        universal_newlines=True)
    stdout, stderr = p.communicate()
    if p.returncode != 0:
      sys.exit(p.returncode)

    if not args.in_place:
      with open(filename) as f:
        code = f.readlines()
      formatted_code = StringIO(stdout).readlines()
      diff = difflib.unified_diff(code, formatted_code, filename, filename,
                                  '(before formatting)', '(after formatting)')
      diff_string = ''.join(diff)
      if len(diff_string) > 0:
        sys.stdout.write(diff_string)


if __name__ == '__main__':
  main()
