# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/astroid/blob/main/CONTRIBUTORS.txt

"""Astroid hooks for dateutil."""

import textwrap

from astroid.brain.helpers import register_module_extender
from astroid.builder import AstroidBuilder
from astroid.manager import AstroidManager


def dateutil_transform():
    return AstroidBuilder(AstroidManager()).string_build(
        textwrap.dedent(
            """
    import datetime
    def parse(timestr, parserinfo=None, **kwargs):
        return datetime.datetime()
    """
        )
    )


register_module_extender(AstroidManager(), "dateutil.parser", dateutil_transform)
