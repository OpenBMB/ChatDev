# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/astroid/blob/main/CONTRIBUTORS.txt

from astroid.brain.helpers import register_module_extender
from astroid.builder import parse
from astroid.manager import AstroidManager


def _re_transform():
    return parse(
        """
    from collections import namedtuple
    _Method = namedtuple('_Method', 'name ident salt_chars total_size')

    METHOD_SHA512 = _Method('SHA512', '6', 16, 106)
    METHOD_SHA256 = _Method('SHA256', '5', 16, 63)
    METHOD_BLOWFISH = _Method('BLOWFISH', 2, 'b', 22)
    METHOD_MD5 = _Method('MD5', '1', 8, 34)
    METHOD_CRYPT = _Method('CRYPT', None, 2, 13)
    """
    )


register_module_extender(AstroidManager(), "crypt", _re_transform)
