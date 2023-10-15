"""A module to ease code analysis

This module is here to help source code analysis.
"""
import re

from rope.base import codeanalyze, utils


@utils.cached(7)
def real_code(source):
    """Simplify `source` for analysis

    It replaces:

    * comments with spaces
    * strs with a new str filled with spaces
    * implicit and explicit continuations with spaces
    * tabs and semicolons with spaces

    The resulting code is a lot easier to analyze if we are interested
    only in offsets.
    """
    collector = codeanalyze.ChangeCollector(source)
    for start, end, matchgroups in ignored_regions(source):
        if source[start] == "#":
            replacement = " " * (end - start)
        elif "f" in matchgroups.get("prefix", "").lower():
            replacement = None
        else:
            replacement = '"%s"' % (" " * (end - start - 2))
        if replacement is not None:
            collector.add_change(start, end, replacement)
    source = collector.get_changed() or source
    collector = codeanalyze.ChangeCollector(source)
    parens = 0
    for match in _parens.finditer(source):
        i = match.start()
        c = match.group()
        if c in "({[":
            parens += 1
        if c in ")}]":
            parens -= 1
        if c == "\n" and parens > 0:
            collector.add_change(i, i + 1, " ")
    source = collector.get_changed() or source
    return source.replace("\\\n", "  ").replace("\t", " ").replace(";", "\n")


@utils.cached(7)
def ignored_regions(source):
    """Return ignored regions like strings and comments in `source`"""
    return [
        (match.start(), match.end(), match.groupdict())
        for match in _str.finditer(source)
    ]


_str = re.compile(
    "|".join(
        [
            codeanalyze.get_comment_pattern(),
            codeanalyze.get_any_string_pattern(),
        ]
    )
)
_parens = re.compile(r"[\({\[\]}\)\n]")
