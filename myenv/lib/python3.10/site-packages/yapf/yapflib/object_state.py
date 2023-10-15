# Copyright 2017 Google Inc. All Rights Reserved.
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
"""Represents the state of Python objects being formatted.

Objects (e.g., list comprehensions, dictionaries, etc.) have specific
requirements on how they're formatted. These state objects keep track of these
requirements.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from yapf.yapflib import format_token
from yapf.yapflib import py3compat
from yapf.yapflib import style
from yapf.yapflib import subtypes


class ComprehensionState(object):
  """Maintains the state of list comprehension formatting decisions.

  A stack of ComprehensionState objects are kept to ensure that list
  comprehensions are wrapped with well-defined rules.

  Attributes:
    expr_token: The first token in the comprehension.
    for_token: The first 'for' token of the comprehension.
    opening_bracket: The opening bracket of the list comprehension.
    closing_bracket: The closing bracket of the list comprehension.
    has_split_at_for: Whether there is a newline immediately before the
      for_token.
    has_interior_split: Whether there is a newline within the comprehension.
      That is, a split somewhere after expr_token or before closing_bracket.
  """

  def __init__(self, expr_token):
    self.expr_token = expr_token
    self.for_token = None
    self.has_split_at_for = False
    self.has_interior_split = False

  def HasTrivialExpr(self):
    """Returns whether the comp_expr is "trivial" i.e. is a single token."""
    return self.expr_token.next_token.value == 'for'

  @property
  def opening_bracket(self):
    return self.expr_token.previous_token

  @property
  def closing_bracket(self):
    return self.opening_bracket.matching_bracket

  def Clone(self):
    clone = ComprehensionState(self.expr_token)
    clone.for_token = self.for_token
    clone.has_split_at_for = self.has_split_at_for
    clone.has_interior_split = self.has_interior_split
    return clone

  def __repr__(self):
    return ('[opening_bracket::%s, for_token::%s, has_split_at_for::%s,'
            ' has_interior_split::%s, has_trivial_expr::%s]' %
            (self.opening_bracket, self.for_token, self.has_split_at_for,
             self.has_interior_split, self.HasTrivialExpr()))

  def __eq__(self, other):
    return hash(self) == hash(other)

  def __ne__(self, other):
    return not self == other

  def __hash__(self, *args, **kwargs):
    return hash((self.expr_token, self.for_token, self.has_split_at_for,
                 self.has_interior_split))


class ParameterListState(object):
  """Maintains the state of function parameter list formatting decisions.

  Attributes:
    opening_bracket: The opening bracket of the parameter list.
    closing_bracket: The closing bracket of the parameter list.
    has_typed_return: True if the function definition has a typed return.
    ends_in_comma: True if the parameter list ends in a comma.
    last_token: Returns the last token of the function declaration.
    has_default_values: True if the parameters have default values.
    has_split_before_first_param: Whether there is a newline before the first
      parameter.
    opening_column: The position of the opening parameter before a newline.
    parameters: A list of parameter objects (Parameter).
    split_before_closing_bracket: Split before the closing bracket. Sometimes
      needed if the indentation would collide.
  """

  def __init__(self, opening_bracket, newline, opening_column):
    self.opening_bracket = opening_bracket
    self.has_split_before_first_param = newline
    self.opening_column = opening_column
    self.parameters = opening_bracket.parameters
    self.split_before_closing_bracket = False

  @property
  def closing_bracket(self):
    return self.opening_bracket.matching_bracket

  @property
  def has_typed_return(self):
    return self.closing_bracket.next_token.value == '->'

  @property
  @py3compat.lru_cache()
  def has_default_values(self):
    return any(param.has_default_value for param in self.parameters)

  @property
  @py3compat.lru_cache()
  def ends_in_comma(self):
    if not self.parameters:
      return False
    return self.parameters[-1].last_token.next_token.value == ','

  @property
  @py3compat.lru_cache()
  def last_token(self):
    token = self.opening_bracket.matching_bracket
    while not token.is_comment and token.next_token:
      token = token.next_token
    return token

  @py3compat.lru_cache()
  def LastParamFitsOnLine(self, indent):
    """Return true if the last parameter fits on a single line."""
    if not self.has_typed_return:
      return False
    if not self.parameters:
      return True
    total_length = self.last_token.total_length
    last_param = self.parameters[-1].first_token
    total_length -= last_param.total_length - len(last_param.value)
    return total_length + indent <= style.Get('COLUMN_LIMIT')

  @py3compat.lru_cache()
  def SplitBeforeClosingBracket(self, indent):
    """Return true if there's a split before the closing bracket."""
    if style.Get('DEDENT_CLOSING_BRACKETS'):
      return True
    if self.ends_in_comma:
      return True
    if not self.parameters:
      return False
    total_length = self.last_token.total_length
    last_param = self.parameters[-1].first_token
    total_length -= last_param.total_length - len(last_param.value)
    return total_length + indent > style.Get('COLUMN_LIMIT')

  def Clone(self):
    clone = ParameterListState(self.opening_bracket,
                               self.has_split_before_first_param,
                               self.opening_column)
    clone.split_before_closing_bracket = self.split_before_closing_bracket
    clone.parameters = [param.Clone() for param in self.parameters]
    return clone

  def __repr__(self):
    return ('[opening_bracket::%s, has_split_before_first_param::%s, '
            'opening_column::%d]' %
            (self.opening_bracket, self.has_split_before_first_param,
             self.opening_column))

  def __eq__(self, other):
    return hash(self) == hash(other)

  def __ne__(self, other):
    return not self == other

  def __hash__(self, *args, **kwargs):
    return hash(
        (self.opening_bracket, self.has_split_before_first_param,
         self.opening_column, (hash(param) for param in self.parameters)))


class Parameter(object):
  """A parameter in a parameter list.

  Attributes:
    first_token: (format_token.FormatToken) First token of parameter.
    last_token: (format_token.FormatToken) Last token of parameter.
    has_default_value: (boolean) True if the parameter has a default value
  """

  def __init__(self, first_token, last_token):
    self.first_token = first_token
    self.last_token = last_token

  @property
  @py3compat.lru_cache()
  def has_default_value(self):
    """Returns true if the parameter has a default value."""
    tok = self.first_token
    while tok != self.last_token:
      if subtypes.DEFAULT_OR_NAMED_ASSIGN in tok.subtypes:
        return True
      tok = tok.matching_bracket if tok.OpensScope() else tok.next_token
    return False

  def Clone(self):
    return Parameter(self.first_token, self.last_token)

  def __repr__(self):
    return '[first_token::%s, last_token:%s]' % (self.first_token,
                                                 self.last_token)

  def __eq__(self, other):
    return hash(self) == hash(other)

  def __ne__(self, other):
    return not self == other

  def __hash__(self, *args, **kwargs):
    return hash((self.first_token, self.last_token))
