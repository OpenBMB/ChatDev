from typing import Any, Callable, Iterable, List, Optional, Tuple, Union

from pygame.color import Color
from pygame.rect import Rect
from pygame.surface import Surface

from ._common import ColorValue, FileArg, RectValue

def get_error() -> str: ...
def get_version(linked: bool = True) -> Tuple[int, int, int]: ...
def init(cache_size: int = 64, resolution: int = 72) -> None: ...
def quit() -> None: ...
def get_init() -> bool: ...
def was_init() -> bool: ...
def get_cache_size() -> int: ...
def get_default_resolution() -> int: ...
def set_default_resolution(resolution: int) -> None: ...
def SysFont(
    name: Union[str, bytes, Iterable[Union[str, bytes]]],
    size: int,
    bold: int = False,
    italic: int = False,
    constructor: Optional[Callable[[Optional[str], int, bool, bool], Font]] = None,
) -> Font: ...
def get_default_font() -> str: ...
def get_fonts() -> List[str]: ...
def match_font(
    name: Union[str, bytes, Iterable[Union[str, bytes]]],
    bold: Any = False,
    italic: Any = False,
) -> str: ...

STYLE_NORMAL: int
STYLE_UNDERLINE: int
STYLE_OBLIQUE: int
STYLE_STRONG: int
STYLE_WIDE: int
STYLE_DEFAULT: int

class Font:
    name: str
    path: str
    size: Union[float, Tuple[float, float]]
    height: int
    ascender: int
    descender: int
    style: int
    underline: bool
    strong: bool
    oblique: bool
    wide: bool
    strength: float
    underline_adjustment: float
    fixed_width: bool
    fixed_sizes: int
    scalable: bool
    use_bitmap_strikes: bool
    antialiased: bool
    kerning: bool
    vertical: bool
    rotation: int
    fgcolor: Color
    bgcolor: Color
    origin: bool
    pad: bool
    ucs4: bool
    resolution: int
    def __init__(
        self,
        file: Optional[FileArg],
        size: float = 0,
        font_index: int = 0,
        resolution: int = 0,
        ucs4: int = False,
    ) -> None: ...
    def get_rect(
        self,
        text: str,
        style: int = STYLE_DEFAULT,
        rotation: int = 0,
        size: float = 0,
    ) -> Rect: ...
    def get_metrics(
        self, text: str, size: float = 0
    ) -> List[Tuple[int, int, int, int, float, float]]: ...
    def get_sized_ascender(self, size: float) -> int: ...
    def get_sized_descender(self, size: float) -> int: ...
    def get_sized_height(self, size: float) -> int: ...
    def get_sized_glyph_height(self, size: float) -> int: ...
    def get_sizes(self) -> List[Tuple[int, int, int, float, float]]: ...
    def render(
        self,
        text: str,
        fgcolor: Optional[ColorValue] = None,
        bgcolor: Optional[ColorValue] = None,
        style: int = STYLE_DEFAULT,
        rotation: int = 0,
        size: float = 0,
    ) -> Tuple[Surface, Rect]: ...
    def render_to(
        self,
        surf: Surface,
        dest: RectValue,
        text: str,
        fgcolor: Optional[ColorValue] = None,
        bgcolor: Optional[ColorValue] = None,
        style: int = STYLE_DEFAULT,
        rotation: int = 0,
        size: float = 0,
    ) -> Rect: ...
    def render_raw(
        self,
        text: str,
        style: int = STYLE_DEFAULT,
        rotation: int = 0,
        size: float = 0,
        invert: bool = False,
    ) -> Tuple[bytes, Tuple[int, int]]: ...
    def render_raw_to(
        self,
        array: Any,
        text: str,
        dest: Optional[RectValue] = None,
        style: int = STYLE_DEFAULT,
        rotation: int = 0,
        size: float = 0,
        invert: bool = False,
    ) -> Rect: ...
