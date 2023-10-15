"""Enhanced Pygame module for loading and rendering computer fonts"""

from pygame._freetype import (
    Font,
    STYLE_NORMAL,
    STYLE_OBLIQUE,
    STYLE_STRONG,
    STYLE_UNDERLINE,
    STYLE_WIDE,
    STYLE_DEFAULT,
    init,
    quit,
    get_init,
    was_init,
    get_cache_size,
    get_default_font,
    get_default_resolution,
    get_error,
    get_version,
    set_default_resolution,
)
from pygame.sysfont import match_font, get_fonts, SysFont as _SysFont

__all__ = [
    "Font",
    "STYLE_NORMAL",
    "STYLE_OBLIQUE",
    "STYLE_STRONG",
    "STYLE_UNDERLINE",
    "STYLE_WIDE",
    "STYLE_DEFAULT",
    "init",
    "quit",
    "get_init",
    "was_init",
    "get_cache_size",
    "get_default_font",
    "get_default_resolution",
    "get_error",
    "get_version",
    "set_default_resolution",
    "match_font",
    "get_fonts",
]


def SysFont(name, size, bold=False, italic=False, constructor=None):
    """pygame.ftfont.SysFont(name, size, bold=False, italic=False, constructor=None) -> Font
    Create a pygame Font from system font resources.

    This will search the system fonts for the given font
    name. You can also enable bold or italic styles, and
    the appropriate system font will be selected if available.

    This will always return a valid Font object, and will
    fallback on the builtin pygame font if the given font
    is not found.

    Name can also be an iterable of font names, a string of
    comma-separated font names, or a bytes of comma-separated
    font names, in which case the set of names will be searched
    in order. Pygame uses a small set of common font aliases. If the
    specific font you ask for is not available, a reasonable
    alternative may be used.

    If optional constructor is provided, it must be a function with
    signature constructor(fontpath, size, bold, italic) which returns
    a Font instance. If None, a pygame.freetype.Font object is created.
    """
    if constructor is None:

        def constructor(fontpath, size, bold, italic):
            font = Font(fontpath, size)
            font.strong = bold
            font.oblique = italic
            return font

    return _SysFont(name, size, bold, italic, constructor)
