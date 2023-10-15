# Copyright 2021 Google Inc. All Rights Reserved.
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
"""Token subtypes used to improve formatting."""

NONE = 0
UNARY_OPERATOR = 1
BINARY_OPERATOR = 2
SUBSCRIPT_COLON = 3
SUBSCRIPT_BRACKET = 4
DEFAULT_OR_NAMED_ASSIGN = 5
DEFAULT_OR_NAMED_ASSIGN_ARG_LIST = 6
VARARGS_LIST = 7
VARARGS_STAR = 8
KWARGS_STAR_STAR = 9
ASSIGN_OPERATOR = 10
DICTIONARY_KEY = 11
DICTIONARY_KEY_PART = 12
DICTIONARY_VALUE = 13
DICT_SET_GENERATOR = 14
COMP_EXPR = 15
COMP_FOR = 16
COMP_IF = 17
FUNC_DEF = 18
DECORATOR = 19
TYPED_NAME = 20
TYPED_NAME_ARG_LIST = 21
SIMPLE_EXPRESSION = 22
PARAMETER_START = 23
PARAMETER_STOP = 24
