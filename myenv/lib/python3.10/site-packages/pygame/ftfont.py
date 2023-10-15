"""pygame module for loading and rendering fonts (freetype alternative)"""

__all__ = [
    "Font",
    "init",
    "quit",
    "get_default_font",
    "get_init",
    "SysFont",
    "match_font",
    "get_fonts",
]

from pygame._freetype import init, Font as _Font, get_default_resolution
from pygame._freetype import quit, get_default_font, get_init as _get_init
from pygame._freetype import _internal_mod_init
from pygame.sysfont import match_font, get_fonts, SysFont as _SysFont
from pygame import encode_file_path


class Font(_Font):
    """Font(filename, size) -> Font
    Font(object, size) -> Font
    create a new Font object from a file (freetype alternative)

    This Font type differs from font.Font in that it can render glyphs
    for Unicode code points in the supplementary planes (> 0xFFFF).
    """

    __encode_file_path = staticmethod(encode_file_path)
    __get_default_resolution = staticmethod(get_default_resolution)
    __default_font = encode_file_path(get_default_font())

    __unull = "\x00"
    __bnull = b"\x00"

    def __init__(self, file=None, size=-1):
        size = max(size, 1)
        if isinstance(file, str):
            try:
                bfile = self.__encode_file_path(file, ValueError)
            except ValueError:
                bfile = ""
        else:
            bfile = file
        if isinstance(bfile, bytes) and bfile == self.__default_font:
            file = None
        if file is None:
            resolution = int(self.__get_default_resolution() * 0.6875)
            if resolution == 0:
                resolution = 1
        else:
            resolution = 0
        super().__init__(file, size=size, resolution=resolution)
        self.strength = 1.0 / 12.0
        self.kerning = False
        self.origin = True
        self.pad = True
        self.ucs4 = True
        self.underline_adjustment = 1.0

    def render(self, text, antialias, color, background=None):
        """render(text, antialias, color, background=None) -> Surface
        draw text on a new Surface"""

        if text is None:
            text = ""
        if isinstance(text, str) and self.__unull in text:
            raise ValueError("A null character was found in the text")
        if isinstance(text, bytes) and self.__bnull in text:
            raise ValueError("A null character was found in the text")
        save_antialiased = (
            self.antialiased  # pylint: disable = access-member-before-definition
        )
        self.antialiased = bool(antialias)
        try:
            s, _ = super().render(text, color, background)
            return s
        finally:
            self.antialiased = save_antialiased

    def set_bold(self, value):
        """set_bold(bool) -> None
        enable fake rendering of bold text"""

        self.wide = bool(value)

    def get_bold(self):
        """get_bold() -> bool
        check if text will be rendered bold"""

        return self.wide

    bold = property(get_bold, set_bold)

    def set_italic(self, value):
        """set_italic(bool) -> None
        enable fake rendering of italic text"""

        self.oblique = bool(value)

    def get_italic(self):
        """get_italic() -> bool
        check if the text will be rendered italic"""

        return self.oblique

    italic = property(get_italic, set_italic)

    def set_underline(self, value):
        """set_underline(bool) -> None
        control if text is rendered with an underline"""

        self.underline = bool(value)

    def get_underline(self):
        """set_bold(bool) -> None
        enable fake rendering of bold text"""

        return self.underline

    def metrics(self, text):
        """metrics(text) -> list
        Gets the metrics for each character in the passed string."""

        return self.get_metrics(text)

    def get_ascent(self):
        """get_ascent() -> int
        get the ascent of the font"""

        return self.get_sized_ascender()

    def get_descent(self):
        """get_descent() -> int
        get the descent of the font"""

        return self.get_sized_descender()

    def get_height(self):
        """get_height() -> int
        get the height of the font"""

        return self.get_sized_ascender() - self.get_sized_descender() + 1

    def get_linesize(self):
        """get_linesize() -> int
        get the line space of the font text"""

        return self.get_sized_height()

    def size(self, text):
        """size(text) -> (width, height)
        determine the amount of space needed to render text"""

        return self.get_rect(text).size


FontType = Font


def get_init():
    """get_init() -> bool
    true if the font module is initialized"""

    return _get_init()


def SysFont(name, size, bold=0, italic=0, constructor=None):
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
    a Font instance. If None, a pygame.ftfont.Font object is created.
    """
    if constructor is None:

        def constructor(fontpath, size, bold, italic):
            font = Font(fontpath, size)
            font.set_bold(bold)
            font.set_italic(italic)
            return font

    return _SysFont(name, size, bold, italic, constructor)


del _Font, get_default_resolution, encode_file_path
