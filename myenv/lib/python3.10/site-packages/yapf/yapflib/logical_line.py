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
"""LogicalLine primitive for formatting.

A logical line is the containing data structure produced by the parser. It
collects all nodes (stored in FormatToken objects) that could appear on a single
line if there were no line length restrictions. It's then used by the parser to
perform the wrapping required to comply with the style guide.
"""

from yapf.yapflib import format_token
from yapf.yapflib import py3compat
from yapf.yapflib import pytree_utils
from yapf.yapflib import split_penalty
from yapf.yapflib import style
from yapf.yapflib import subtypes

from lib2to3.fixer_util import syms as python_symbols


class LogicalLine(object):
  """Represents a single logical line in the output.

  Attributes:
    depth: indentation depth of this line. This is just a numeric value used to
      distinguish lines that are more deeply nested than others. It is not the
      actual amount of spaces, which is style-dependent.
  """

  def __init__(self, depth, tokens=None):
    """Constructor.

    Creates a new logical line with the given depth an initial list of tokens.
    Constructs the doubly-linked lists for format tokens using their built-in
    next_token and previous_token attributes.

    Arguments:
      depth: indentation depth of this line
      tokens: initial list of tokens
    """
    self.depth = depth
    self._tokens = tokens or []
    self.disable = False

    if self._tokens:
      # Set up a doubly linked list.
      for index, tok in enumerate(self._tokens[1:]):
        # Note, 'index' is the index to the previous token.
        tok.previous_token = self._tokens[index]
        self._tokens[index].next_token = tok

  def CalculateFormattingInformation(self):
    """Calculate the split penalty and total length for the tokens."""
    # Say that the first token in the line should have a space before it. This
    # means only that if this logical line is joined with a predecessor line,
    # then there will be a space between them.
    self.first.spaces_required_before = 1
    self.first.total_length = len(self.first.value)

    prev_token = self.first
    prev_length = self.first.total_length
    for token in self._tokens[1:]:
      if (token.spaces_required_before == 0 and
          _SpaceRequiredBetween(prev_token, token, self.disable)):
        token.spaces_required_before = 1

      tok_len = len(token.value) if not token.is_pseudo else 0

      spaces_required_before = token.spaces_required_before
      if isinstance(spaces_required_before, list):
        assert token.is_comment, token

        # If here, we are looking at a comment token that appears on a line
        # with other tokens (but because it is a comment, it is always the last
        # token).  Rather than specifying the actual number of spaces here,
        # hard code a value of 0 and then set it later. This logic only works
        # because this comment token is guaranteed to be the last token in the
        # list.
        spaces_required_before = 0

      token.total_length = prev_length + tok_len + spaces_required_before

      # The split penalty has to be computed before {must|can}_break_before,
      # because these may use it for their decision.
      token.split_penalty += _SplitPenalty(prev_token, token)
      token.must_break_before = _MustBreakBefore(prev_token, token)
      token.can_break_before = (
          token.must_break_before or _CanBreakBefore(prev_token, token))

      prev_length = token.total_length
      prev_token = token

  def Split(self):
    """Split the line at semicolons."""
    if not self.has_semicolon or self.disable:
      return [self]

    llines = []
    lline = LogicalLine(self.depth)
    for tok in self._tokens:
      if tok.value == ';':
        llines.append(lline)
        lline = LogicalLine(self.depth)
      else:
        lline.AppendToken(tok)

    if lline.tokens:
      llines.append(lline)

    for lline in llines:
      lline.first.previous_token = None
      lline.last.next_token = None

    return llines

  ############################################################################
  # Token Access and Manipulation Methods                                    #
  ############################################################################

  def AppendToken(self, token):
    """Append a new FormatToken to the tokens contained in this line."""
    if self._tokens:
      token.previous_token = self.last
      self.last.next_token = token
    self._tokens.append(token)

  def AppendNode(self, node):
    """Convenience method to append a pytree node directly.

    Wraps the node with a FormatToken.

    Arguments:
      node: the node to append
    """
    self.AppendToken(format_token.FormatToken(node))

  @property
  def first(self):
    """Returns the first non-whitespace token."""
    return self._tokens[0]

  @property
  def last(self):
    """Returns the last non-whitespace token."""
    return self._tokens[-1]

  ############################################################################
  # Token -> String Methods                                                  #
  ############################################################################

  def AsCode(self, indent_per_depth=2):
    """Return a "code" representation of this line.

    The code representation shows how the line would be printed out as code.

    TODO(eliben): for now this is rudimentary for debugging - once we add
    formatting capabilities, this method will have other uses (not all tokens
    have spaces around them, for example).

    Arguments:
      indent_per_depth: how much spaces to indend per depth level.

    Returns:
      A string representing the line as code.
    """
    indent = ' ' * indent_per_depth * self.depth
    tokens_str = ' '.join(tok.value for tok in self._tokens)
    return indent + tokens_str

  def __str__(self):  # pragma: no cover
    return self.AsCode()

  def __repr__(self):  # pragma: no cover
    tokens_repr = ','.join(
        '{0}({1!r})'.format(tok.name, tok.value) for tok in self._tokens)
    return 'LogicalLine(depth={0}, tokens=[{1}])'.format(
        self.depth, tokens_repr)

  ############################################################################
  # Properties                                                               #
  ############################################################################

  @property
  def tokens(self):
    """Access the tokens contained within this line.

    The caller must not modify the tokens list returned by this method.

    Returns:
      List of tokens in this line.
    """
    return self._tokens

  @property
  def lineno(self):
    """Return the line number of this logical line.

    Returns:
      The line number of the first token in this logical line.
    """
    return self.first.lineno

  @property
  def start(self):
    """The start of the logical line.

    Returns:
      A tuple of the starting line number and column.
    """
    return (self.first.lineno, self.first.column)

  @property
  def end(self):
    """The end of the logical line.

    Returns:
      A tuple of the ending line number and column.
    """
    return (self.last.lineno, self.last.column + len(self.last.value))

  @property
  def is_comment(self):
    return self.first.is_comment

  @property
  def has_semicolon(self):
    return any(tok.value == ';' for tok in self._tokens)


def _IsIdNumberStringToken(tok):
  return tok.is_keyword or tok.is_name or tok.is_number or tok.is_string


def _IsUnaryOperator(tok):
  return subtypes.UNARY_OPERATOR in tok.subtypes


def _HasPrecedence(tok):
  """Whether a binary operation has precedence within its context."""
  node = tok.node

  # We let ancestor be the statement surrounding the operation that tok is the
  # operator in.
  ancestor = node.parent.parent

  while ancestor is not None:
    # Search through the ancestor nodes in the parse tree for operators with
    # lower precedence.
    predecessor_type = pytree_utils.NodeName(ancestor)
    if predecessor_type in ['arith_expr', 'term']:
      # An ancestor "arith_expr" or "term" means we have found an operator
      # with lower precedence than our tok.
      return True
    if predecessor_type != 'atom':
      # We understand the context to look for precedence within as an
      # arbitrary nesting of "arith_expr", "term", and "atom" nodes. If we
      # leave this context we have not found a lower precedence operator.
      return False
    # Under normal usage we expect a complete parse tree to be available and
    # we will return before we get an AttributeError from the root.
    ancestor = ancestor.parent


def _PriorityIndicatingNoSpace(tok):
  """Whether to remove spaces around an operator due to precedence."""
  if not tok.is_arithmetic_op or not tok.is_simple_expr:
    # Limit space removal to highest priority arithmetic operators
    return False
  return _HasPrecedence(tok)


def _IsSubscriptColonAndValuePair(token1, token2):
  return (token1.is_number or token1.is_name) and token2.is_subscript_colon


def _SpaceRequiredBetween(left, right, is_line_disabled):
  """Return True if a space is required between the left and right token."""
  lval = left.value
  rval = right.value
  if (left.is_pseudo and _IsIdNumberStringToken(right) and
      left.previous_token and _IsIdNumberStringToken(left.previous_token)):
    # Space between keyword... tokens and pseudo parens.
    return True
  if left.is_pseudo or right.is_pseudo:
    # There should be a space after the ':' in a dictionary.
    if left.OpensScope():
      return True
    # The closing pseudo-paren shouldn't affect spacing.
    return False
  if left.is_continuation or right.is_continuation:
    # The continuation node's value has all of the spaces it needs.
    return False
  if right.name in pytree_utils.NONSEMANTIC_TOKENS:
    # No space before a non-semantic token.
    return False
  if _IsIdNumberStringToken(left) and _IsIdNumberStringToken(right):
    # Spaces between keyword, string, number, and identifier tokens.
    return True
  if lval == ',' and rval == ':':
    # We do want a space between a comma and colon.
    return True
  if style.Get('SPACE_INSIDE_BRACKETS'):
    # Supersede the "no space before a colon or comma" check.
    if lval in pytree_utils.OPENING_BRACKETS and rval == ':':
      return True
    if rval in pytree_utils.CLOSING_BRACKETS and lval == ':':
      return True
  if (style.Get('SPACES_AROUND_SUBSCRIPT_COLON') and
      (_IsSubscriptColonAndValuePair(left, right) or
       _IsSubscriptColonAndValuePair(right, left))):
    # Supersede the "never want a space before a colon or comma" check.
    return True
  if rval in ':,':
    # Otherwise, we never want a space before a colon or comma.
    return False
  if lval == ',' and rval in ']})':
    # Add a space between ending ',' and closing bracket if requested.
    return style.Get('SPACE_BETWEEN_ENDING_COMMA_AND_CLOSING_BRACKET')
  if lval == ',':
    # We want a space after a comma.
    return True
  if lval == 'from' and rval == '.':
    # Space before the '.' in an import statement.
    return True
  if lval == '.' and rval == 'import':
    # Space after the '.' in an import statement.
    return True
  if (lval == '=' and rval in {'.', ',,,'} and
      subtypes.DEFAULT_OR_NAMED_ASSIGN not in left.subtypes):
    # Space between equal and '.' as in "X = ...".
    return True
  if lval == ':' and rval in {'.', '...'}:
    # Space between : and ...
    return True
  if ((right.is_keyword or right.is_name) and
      (left.is_keyword or left.is_name)):
    # Don't merge two keywords/identifiers.
    return True
  if (subtypes.SUBSCRIPT_COLON in left.subtypes or
      subtypes.SUBSCRIPT_COLON in right.subtypes):
    # A subscript shouldn't have spaces separating its colons.
    return False
  if (subtypes.TYPED_NAME in left.subtypes or
      subtypes.TYPED_NAME in right.subtypes):
    # A typed argument should have a space after the colon.
    return True
  if left.is_string:
    if (rval == '=' and
        subtypes.DEFAULT_OR_NAMED_ASSIGN_ARG_LIST in right.subtypes):
      # If there is a type hint, then we don't want to add a space between the
      # equal sign and the hint.
      return False
    if rval not in '[)]}.' and not right.is_binary_op:
      # A string followed by something other than a subscript, closing bracket,
      # dot, or a binary op should have a space after it.
      return True
    if rval in pytree_utils.CLOSING_BRACKETS:
      # A string followed by closing brackets should have a space after it
      # depending on SPACE_INSIDE_BRACKETS.  A string followed by opening
      # brackets, however, should not.
      return style.Get('SPACE_INSIDE_BRACKETS')
    if subtypes.SUBSCRIPT_BRACKET in right.subtypes:
      # It's legal to do this in Python: 'hello'[a]
      return False
  if left.is_binary_op and lval != '**' and _IsUnaryOperator(right):
    # Space between the binary operator and the unary operator.
    return True
  if left.is_keyword and _IsUnaryOperator(right):
    # Handle things like "not -3 < x".
    return True
  if _IsUnaryOperator(left) and _IsUnaryOperator(right):
    # No space between two unary operators.
    return False
  if left.is_binary_op or right.is_binary_op:
    if lval == '**' or rval == '**':
      # Space around the "power" operator.
      return style.Get('SPACES_AROUND_POWER_OPERATOR')
    # Enforce spaces around binary operators except the blocked ones.
    block_list = style.Get('NO_SPACES_AROUND_SELECTED_BINARY_OPERATORS')
    if lval in block_list or rval in block_list:
      return False
    if style.Get('ARITHMETIC_PRECEDENCE_INDICATION'):
      if _PriorityIndicatingNoSpace(left) or _PriorityIndicatingNoSpace(right):
        return False
      else:
        return True
    else:
      return True
  if (_IsUnaryOperator(left) and lval != 'not' and
      (right.is_name or right.is_number or rval == '(')):
    # The previous token was a unary op. No space is desired between it and
    # the current token.
    return False
  if (subtypes.DEFAULT_OR_NAMED_ASSIGN in left.subtypes and
      subtypes.TYPED_NAME not in right.subtypes):
    # A named argument or default parameter shouldn't have spaces around it.
    return style.Get('SPACES_AROUND_DEFAULT_OR_NAMED_ASSIGN')
  if (subtypes.DEFAULT_OR_NAMED_ASSIGN in right.subtypes and
      subtypes.TYPED_NAME not in left.subtypes):
    # A named argument or default parameter shouldn't have spaces around it.
    return style.Get('SPACES_AROUND_DEFAULT_OR_NAMED_ASSIGN')
  if (subtypes.VARARGS_LIST in left.subtypes or
      subtypes.VARARGS_LIST in right.subtypes):
    return False
  if (subtypes.VARARGS_STAR in left.subtypes or
      subtypes.KWARGS_STAR_STAR in left.subtypes):
    # Don't add a space after a vararg's star or a keyword's star-star.
    return False
  if lval == '@' and subtypes.DECORATOR in left.subtypes:
    # Decorators shouldn't be separated from the 'at' sign.
    return False
  if left.is_keyword and rval == '.':
    # Add space between keywords and dots.
    return lval not in {'None', 'print'}
  if lval == '.' and right.is_keyword:
    # Add space between keywords and dots.
    return rval not in {'None', 'print'}
  if lval == '.' or rval == '.':
    # Don't place spaces between dots.
    return False
  if ((lval == '(' and rval == ')') or (lval == '[' and rval == ']') or
      (lval == '{' and rval == '}')):
    # Empty objects shouldn't be separated by spaces.
    return False
  if not is_line_disabled and (left.OpensScope() or right.ClosesScope()):
    if (style.GetOrDefault('SPACES_AROUND_DICT_DELIMITERS', False) and (
        (lval == '{' and _IsDictListTupleDelimiterTok(left, is_opening=True)) or
        (rval == '}' and
         _IsDictListTupleDelimiterTok(right, is_opening=False)))):
      return True
    if (style.GetOrDefault('SPACES_AROUND_LIST_DELIMITERS', False) and (
        (lval == '[' and _IsDictListTupleDelimiterTok(left, is_opening=True)) or
        (rval == ']' and
         _IsDictListTupleDelimiterTok(right, is_opening=False)))):
      return True
    if (style.GetOrDefault('SPACES_AROUND_TUPLE_DELIMITERS', False) and (
        (lval == '(' and _IsDictListTupleDelimiterTok(left, is_opening=True)) or
        (rval == ')' and
         _IsDictListTupleDelimiterTok(right, is_opening=False)))):
      return True
  if (lval in pytree_utils.OPENING_BRACKETS and
      rval in pytree_utils.OPENING_BRACKETS):
    # Nested objects' opening brackets shouldn't be separated, unless enabled
    # by SPACE_INSIDE_BRACKETS.
    return style.Get('SPACE_INSIDE_BRACKETS')
  if (lval in pytree_utils.CLOSING_BRACKETS and
      rval in pytree_utils.CLOSING_BRACKETS):
    # Nested objects' closing brackets shouldn't be separated, unless enabled
    # by SPACE_INSIDE_BRACKETS.
    return style.Get('SPACE_INSIDE_BRACKETS')
  if lval in pytree_utils.CLOSING_BRACKETS and rval in '([':
    # A call, set, dictionary, or subscript that has a call or subscript after
    # it shouldn't have a space between them.
    return False
  if lval in pytree_utils.OPENING_BRACKETS and _IsIdNumberStringToken(right):
    # Don't separate the opening bracket from the first item, unless enabled
    # by SPACE_INSIDE_BRACKETS.
    return style.Get('SPACE_INSIDE_BRACKETS')
  if left.is_name and rval in '([':
    # Don't separate a call or array access from the name.
    return False
  if rval in pytree_utils.CLOSING_BRACKETS:
    # Don't separate the closing bracket from the last item, unless enabled
    # by SPACE_INSIDE_BRACKETS.
    # FIXME(morbo): This might be too permissive.
    return style.Get('SPACE_INSIDE_BRACKETS')
  if lval == 'print' and rval == '(':
    # Special support for the 'print' function.
    return False
  if lval in pytree_utils.OPENING_BRACKETS and _IsUnaryOperator(right):
    # Don't separate a unary operator from the opening bracket, unless enabled
    # by SPACE_INSIDE_BRACKETS.
    return style.Get('SPACE_INSIDE_BRACKETS')
  if (lval in pytree_utils.OPENING_BRACKETS and
      (subtypes.VARARGS_STAR in right.subtypes or
       subtypes.KWARGS_STAR_STAR in right.subtypes)):
    # Don't separate a '*' or '**' from the opening bracket, unless enabled
    # by SPACE_INSIDE_BRACKETS.
    return style.Get('SPACE_INSIDE_BRACKETS')
  if rval == ';':
    # Avoid spaces before a semicolon. (Why is there a semicolon?!)
    return False
  if lval == '(' and rval == 'await':
    # Special support for the 'await' keyword. Don't separate the 'await'
    # keyword from an opening paren, unless enabled by SPACE_INSIDE_BRACKETS.
    return style.Get('SPACE_INSIDE_BRACKETS')
  return True


def _MustBreakBefore(prev_token, cur_token):
  """Return True if a line break is required before the current token."""
  if prev_token.is_comment or (prev_token.previous_token and
                               prev_token.is_pseudo and
                               prev_token.previous_token.is_comment):
    # Must break if the previous token was a comment.
    return True
  if (cur_token.is_string and prev_token.is_string and
      IsSurroundedByBrackets(cur_token)):
    # We want consecutive strings to be on separate lines. This is a
    # reasonable assumption, because otherwise they should have written them
    # all on the same line, or with a '+'.
    return True
  return cur_token.must_break_before


def _CanBreakBefore(prev_token, cur_token):
  """Return True if a line break may occur before the current token."""
  pval = prev_token.value
  cval = cur_token.value
  if py3compat.PY3:
    if pval == 'yield' and cval == 'from':
      # Don't break before a yield argument.
      return False
    if pval in {'async', 'await'} and cval in {'def', 'with', 'for'}:
      # Don't break after sync keywords.
      return False
  if cur_token.split_penalty >= split_penalty.UNBREAKABLE:
    return False
  if pval == '@':
    # Don't break right after the beginning of a decorator.
    return False
  if cval == ':':
    # Don't break before the start of a block of code.
    return False
  if cval == ',':
    # Don't break before a comma.
    return False
  if prev_token.is_name and cval == '(':
    # Don't break in the middle of a function definition or call.
    return False
  if prev_token.is_name and cval == '[':
    # Don't break in the middle of an array dereference.
    return False
  if cur_token.is_comment and prev_token.lineno == cur_token.lineno:
    # Don't break a comment at the end of the line.
    return False
  if subtypes.UNARY_OPERATOR in prev_token.subtypes:
    # Don't break after a unary token.
    return False
  if not style.Get('ALLOW_SPLIT_BEFORE_DEFAULT_OR_NAMED_ASSIGNS'):
    if (subtypes.DEFAULT_OR_NAMED_ASSIGN in cur_token.subtypes or
        subtypes.DEFAULT_OR_NAMED_ASSIGN in prev_token.subtypes):
      return False
  return True


def IsSurroundedByBrackets(tok):
  """Return True if the token is surrounded by brackets."""
  paren_count = 0
  brace_count = 0
  sq_bracket_count = 0
  previous_token = tok.previous_token
  while previous_token:
    if previous_token.value == ')':
      paren_count -= 1
    elif previous_token.value == '}':
      brace_count -= 1
    elif previous_token.value == ']':
      sq_bracket_count -= 1

    if previous_token.value == '(':
      if paren_count == 0:
        return previous_token
      paren_count += 1
    elif previous_token.value == '{':
      if brace_count == 0:
        return previous_token
      brace_count += 1
    elif previous_token.value == '[':
      if sq_bracket_count == 0:
        return previous_token
      sq_bracket_count += 1

    previous_token = previous_token.previous_token
  return None


def _IsDictListTupleDelimiterTok(tok, is_opening):
  assert tok

  if tok.matching_bracket is None:
    return False

  if is_opening:
    open_tok = tok
    close_tok = tok.matching_bracket
  else:
    open_tok = tok.matching_bracket
    close_tok = tok

  # There must be something in between the tokens
  if open_tok.next_token == close_tok:
    return False

  assert open_tok.next_token.node
  assert open_tok.next_token.node.parent

  return open_tok.next_token.node.parent.type in [
      python_symbols.dictsetmaker,
      python_symbols.listmaker,
      python_symbols.testlist_gexp,
  ]


_LOGICAL_OPERATORS = frozenset({'and', 'or'})
_BITWISE_OPERATORS = frozenset({'&', '|', '^'})
_ARITHMETIC_OPERATORS = frozenset({'+', '-', '*', '/', '%', '//', '@'})


def _SplitPenalty(prev_token, cur_token):
  """Return the penalty for breaking the line before the current token."""
  pval = prev_token.value
  cval = cur_token.value
  if pval == 'not':
    return split_penalty.UNBREAKABLE

  if cur_token.node_split_penalty > 0:
    return cur_token.node_split_penalty

  if style.Get('SPLIT_BEFORE_LOGICAL_OPERATOR'):
    # Prefer to split before 'and' and 'or'.
    if pval in _LOGICAL_OPERATORS:
      return style.Get('SPLIT_PENALTY_LOGICAL_OPERATOR')
    if cval in _LOGICAL_OPERATORS:
      return 0
  else:
    # Prefer to split after 'and' and 'or'.
    if pval in _LOGICAL_OPERATORS:
      return 0
    if cval in _LOGICAL_OPERATORS:
      return style.Get('SPLIT_PENALTY_LOGICAL_OPERATOR')

  if style.Get('SPLIT_BEFORE_BITWISE_OPERATOR'):
    # Prefer to split before '&', '|', and '^'.
    if pval in _BITWISE_OPERATORS:
      return style.Get('SPLIT_PENALTY_BITWISE_OPERATOR')
    if cval in _BITWISE_OPERATORS:
      return 0
  else:
    # Prefer to split after '&', '|', and '^'.
    if pval in _BITWISE_OPERATORS:
      return 0
    if cval in _BITWISE_OPERATORS:
      return style.Get('SPLIT_PENALTY_BITWISE_OPERATOR')

  if (subtypes.COMP_FOR in cur_token.subtypes or
      subtypes.COMP_IF in cur_token.subtypes):
    # We don't mind breaking before the 'for' or 'if' of a list comprehension.
    return 0
  if subtypes.UNARY_OPERATOR in prev_token.subtypes:
    # Try not to break after a unary operator.
    return style.Get('SPLIT_PENALTY_AFTER_UNARY_OPERATOR')
  if pval == ',':
    # Breaking after a comma is fine, if need be.
    return 0
  if pval == '**' or cval == '**':
    return split_penalty.STRONGLY_CONNECTED
  if (subtypes.VARARGS_STAR in prev_token.subtypes or
      subtypes.KWARGS_STAR_STAR in prev_token.subtypes):
    # Don't split after a varargs * or kwargs **.
    return split_penalty.UNBREAKABLE
  if prev_token.OpensScope() and cval != '(':
    # Slightly prefer
    return style.Get('SPLIT_PENALTY_AFTER_OPENING_BRACKET')
  if cval == ':':
    # Don't split before a colon.
    return split_penalty.UNBREAKABLE
  if cval == '=':
    # Don't split before an assignment.
    return split_penalty.UNBREAKABLE
  if (subtypes.DEFAULT_OR_NAMED_ASSIGN in prev_token.subtypes or
      subtypes.DEFAULT_OR_NAMED_ASSIGN in cur_token.subtypes):
    # Don't break before or after an default or named assignment.
    return split_penalty.UNBREAKABLE
  if cval == '==':
    # We would rather not split before an equality operator.
    return split_penalty.STRONGLY_CONNECTED
  if cur_token.ClosesScope():
    # Give a slight penalty for splitting before the closing scope.
    return 100
  return 0
