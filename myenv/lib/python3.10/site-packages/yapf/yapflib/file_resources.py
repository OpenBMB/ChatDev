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
"""Interface to file resources.

This module provides functions for interfacing with files: opening, writing, and
querying.
"""

import fnmatch
import os
import re

from lib2to3.pgen2 import tokenize

from yapf.yapflib import errors
from yapf.yapflib import py3compat
from yapf.yapflib import style

CR = '\r'
LF = '\n'
CRLF = '\r\n'


def _GetExcludePatternsFromYapfIgnore(filename):
  """Get a list of file patterns to ignore from .yapfignore."""
  ignore_patterns = []
  if os.path.isfile(filename) and os.access(filename, os.R_OK):
    with open(filename, 'r') as fd:
      for line in fd:
        if line.strip() and not line.startswith('#'):
          ignore_patterns.append(line.strip())

    if any(e.startswith('./') for e in ignore_patterns):
      raise errors.YapfError('path in .yapfignore should not start with ./')

  return ignore_patterns


def _GetExcludePatternsFromPyprojectToml(filename):
  """Get a list of file patterns to ignore from pyproject.toml."""
  ignore_patterns = []
  try:
    import toml
  except ImportError:
    raise errors.YapfError(
        "toml package is needed for using pyproject.toml as a "
        "configuration file")

  if os.path.isfile(filename) and os.access(filename, os.R_OK):
    pyproject_toml = toml.load(filename)
    ignore_patterns = pyproject_toml.get('tool',
                                         {}).get('yapfignore',
                                                 {}).get('ignore_patterns', [])
    if any(e.startswith('./') for e in ignore_patterns):
      raise errors.YapfError('path in pyproject.toml should not start with ./')

  return ignore_patterns


def GetExcludePatternsForDir(dirname):
  """Return patterns of files to exclude from ignorefile in a given directory.

  Looks for .yapfignore in the directory dirname.

  Arguments:
    dirname: (unicode) The name of the directory.

  Returns:
    A List of file patterns to exclude if ignore file is found, otherwise empty
    List.
  """
  ignore_patterns = []

  yapfignore_file = os.path.join(dirname, '.yapfignore')
  if os.path.exists(yapfignore_file):
    ignore_patterns += _GetExcludePatternsFromYapfIgnore(yapfignore_file)

  pyproject_toml_file = os.path.join(dirname, 'pyproject.toml')
  if os.path.exists(pyproject_toml_file):
    ignore_patterns += _GetExcludePatternsFromPyprojectToml(pyproject_toml_file)
  return ignore_patterns


def GetDefaultStyleForDir(dirname, default_style=style.DEFAULT_STYLE):
  """Return default style name for a given directory.

  Looks for .style.yapf or setup.cfg or pyproject.toml in the parent
  directories.

  Arguments:
    dirname: (unicode) The name of the directory.
    default_style: The style to return if nothing is found. Defaults to the
                   global default style ('pep8') unless otherwise specified.

  Returns:
    The filename if found, otherwise return the default style.
  """
  dirname = os.path.abspath(dirname)
  while True:
    # See if we have a .style.yapf file.
    style_file = os.path.join(dirname, style.LOCAL_STYLE)
    if os.path.exists(style_file):
      return style_file

    # See if we have a setup.cfg file with a '[yapf]' section.
    config_file = os.path.join(dirname, style.SETUP_CONFIG)
    try:
      fd = open(config_file)
    except IOError:
      pass  # It's okay if it's not there.
    else:
      with fd:
        config = py3compat.ConfigParser()
        config.read_file(fd)
        if config.has_section('yapf'):
          return config_file

    # See if we have a pyproject.toml file with a '[tool.yapf]'  section.
    config_file = os.path.join(dirname, style.PYPROJECT_TOML)
    try:
      fd = open(config_file)
    except IOError:
      pass  # It's okay if it's not there.
    else:
      with fd:
        try:
          import toml
        except ImportError:
          raise errors.YapfError(
              "toml package is needed for using pyproject.toml as a "
              "configuration file")

        pyproject_toml = toml.load(config_file)
        style_dict = pyproject_toml.get('tool', {}).get('yapf', None)
        if style_dict is not None:
          return config_file

    if (not dirname or not os.path.basename(dirname) or
        dirname == os.path.abspath(os.path.sep)):
      break
    dirname = os.path.dirname(dirname)

  global_file = os.path.expanduser(style.GLOBAL_STYLE)
  if os.path.exists(global_file):
    return global_file

  return default_style


def GetCommandLineFiles(command_line_file_list, recursive, exclude):
  """Return the list of files specified on the command line."""
  return _FindPythonFiles(command_line_file_list, recursive, exclude)


def WriteReformattedCode(filename,
                         reformatted_code,
                         encoding='',
                         in_place=False):
  """Emit the reformatted code.

  Write the reformatted code into the file, if in_place is True. Otherwise,
  write to stdout.

  Arguments:
    filename: (unicode) The name of the unformatted file.
    reformatted_code: (unicode) The reformatted code.
    encoding: (unicode) The encoding of the file.
    in_place: (bool) If True, then write the reformatted code to the file.
  """
  if in_place:
    with py3compat.open_with_encoding(
        filename, mode='w', encoding=encoding, newline='') as fd:
      fd.write(reformatted_code)
  else:
    py3compat.EncodeAndWriteToStdout(reformatted_code)


def LineEnding(lines):
  """Retrieve the line ending of the original source."""
  endings = {CRLF: 0, CR: 0, LF: 0}
  for line in lines:
    if line.endswith(CRLF):
      endings[CRLF] += 1
    elif line.endswith(CR):
      endings[CR] += 1
    elif line.endswith(LF):
      endings[LF] += 1
  return (sorted(endings, key=endings.get, reverse=True) or [LF])[0]


def _FindPythonFiles(filenames, recursive, exclude):
  """Find all Python files."""
  if exclude and any(e.startswith('./') for e in exclude):
    raise errors.YapfError("path in '--exclude' should not start with ./")
  exclude = exclude and [e.rstrip("/" + os.path.sep) for e in exclude]

  python_files = []
  for filename in filenames:
    if filename != '.' and exclude and IsIgnored(filename, exclude):
      continue
    if os.path.isdir(filename):
      if not recursive:
        raise errors.YapfError(
            "directory specified without '--recursive' flag: %s" % filename)

      # TODO(morbo): Look into a version of os.walk that can handle recursion.
      excluded_dirs = []
      for dirpath, dirnames, filelist in os.walk(filename):
        if dirpath != '.' and exclude and IsIgnored(dirpath, exclude):
          excluded_dirs.append(dirpath)
          continue
        elif any(dirpath.startswith(e) for e in excluded_dirs):
          continue
        for f in filelist:
          filepath = os.path.join(dirpath, f)
          if exclude and IsIgnored(filepath, exclude):
            continue
          if IsPythonFile(filepath):
            python_files.append(filepath)
        # To prevent it from scanning the contents excluded folders, os.walk()
        # lets you amend its list of child dirs `dirnames`. These edits must be
        # made in-place instead of creating a modified copy of `dirnames`.
        # list.remove() is slow and list.pop() is a headache. Instead clear
        # `dirnames` then repopulate it.
        dirnames_ = [dirnames.pop(0) for i in range(len(dirnames))]
        for dirname in dirnames_:
          dir_ = os.path.join(dirpath, dirname)
          if IsIgnored(dir_, exclude):
            excluded_dirs.append(dir_)
          else:
            dirnames.append(dirname)

    elif os.path.isfile(filename):
      python_files.append(filename)

  return python_files


def IsIgnored(path, exclude):
  """Return True if filename matches any patterns in exclude."""
  if exclude is None:
    return False
  path = path.lstrip(os.path.sep)
  while path.startswith('.' + os.path.sep):
    path = path[2:]
  return any(fnmatch.fnmatch(path, e.rstrip(os.path.sep)) for e in exclude)


def IsPythonFile(filename):
  """Return True if filename is a Python file."""
  if os.path.splitext(filename)[1] == '.py':
    return True

  try:
    with open(filename, 'rb') as fd:
      encoding = tokenize.detect_encoding(fd.readline)[0]

    # Check for correctness of encoding.
    with py3compat.open_with_encoding(
        filename, mode='r', encoding=encoding) as fd:
      fd.read()
  except UnicodeDecodeError:
    encoding = 'latin-1'
  except (IOError, SyntaxError):
    # If we fail to detect encoding (or the encoding cookie is incorrect - which
    # will make detect_encoding raise SyntaxError), assume it's not a Python
    # file.
    return False

  try:
    with py3compat.open_with_encoding(
        filename, mode='r', encoding=encoding) as fd:
      first_line = fd.readline(256)
  except IOError:
    return False

  return re.match(r'^#!.*\bpython[23]?\b', first_line)


def FileEncoding(filename):
  """Return the file's encoding."""
  with open(filename, 'rb') as fd:
    return tokenize.detect_encoding(fd.readline)[0]
