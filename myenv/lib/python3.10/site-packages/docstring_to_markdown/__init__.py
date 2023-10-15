from .rst import looks_like_rst, rst_to_markdown

__version__ = "0.11"


class UnknownFormatError(Exception):
    pass


def convert(docstring: str) -> str:
    if looks_like_rst(docstring):
        return rst_to_markdown(docstring)
    raise UnknownFormatError()
