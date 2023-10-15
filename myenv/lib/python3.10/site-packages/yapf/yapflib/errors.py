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
"""YAPF error objects."""

from lib2to3.pgen2 import tokenize


def FormatErrorMsg(e):
  """Convert an exception into a standard format.

  The standard error message format is:

      <filename>:<lineno>:<column>: <msg>

  Arguments:
    e: An exception.

  Returns:
    A properly formatted error message string.
  """
  if isinstance(e, SyntaxError):
    return '{}:{}:{}: {}'.format(e.filename, e.lineno, e.offset, e.msg)
  if isinstance(e, tokenize.TokenError):
    return '{}:{}:{}: {}'.format(e.filename, e.args[1][0], e.args[1][1],
                                 e.args[0])
  return '{}:{}:{}: {}'.format(e.args[1][0], e.args[1][1], e.args[1][2], e.msg)


class YapfError(Exception):
  """Parent class for user errors or input errors.

  Exceptions of this type are handled by the command line tool
  and result in clear error messages, as opposed to backtraces.
  """
  pass
