from typing import Any, Generator, Iterable, Optional, Tuple, Union

from pygame.rect import Rect
from pygame.surface import Surface

from .._common import RectValue, Literal, ColorValue

WINDOWPOS_UNDEFINED: int
WINDOWPOS_CENTERED: int

MESSAGEBOX_ERROR: int
MESSAGEBOX_WARNING: int
MESSAGEBOX_INFORMATION: int

class RendererDriverInfo:
    name: str
    flags: int
    num_texture_formats: int
    max_texture_width: int
    max_texture_height: int

def get_drivers() -> Generator[RendererDriverInfo, None, None]: ...
def get_grabbed_window() -> Optional[Window]: ...
def messagebox(
    title: str,
    message: str,
    window: Optional[Window] = None,
    info: bool = False,
    warn: bool = False,
    error: bool = False,
    buttons: Tuple[str, ...] = ("OK",),
    return_button: int = 0,
    escape_button: int = 0,
) -> int: ...

class Window:
    DEFAULT_SIZE: Tuple[Literal[640], Literal[480]]
    def __init__(
        self,
        title: str = "pygame",
        size: Iterable[int] = (640, 480),
        position: Optional[Iterable[int]] = None,
        fullscreen: bool = False,
        fullscreen_desktop: bool = False,
        **kwargs: bool
    ) -> None: ...
    @classmethod
    def from_display_module(cls) -> Window: ...
    @classmethod
    def from_window(cls, other: int) -> Window: ...
    grab: bool
    relative_mouse: bool
    def set_windowed(self) -> None: ...
    def set_fullscreen(self, desktop: bool = False) -> None: ...
    title: str
    def destroy(self) -> None: ...
    def hide(self) -> None: ...
    def show(self) -> None: ...
    def focus(self, input_only: bool = False) -> None: ...
    def restore(self) -> None: ...
    def maximize(self) -> None: ...
    def minimize(self) -> None: ...
    resizable: bool
    borderless: bool
    def set_icon(self, surface: Surface) -> None: ...
    id: int
    size: Iterable[int]
    position: Union[int, Iterable[int]]
    opacity: float
    display_index: int
    def set_modal_for(self, parent: Window) -> None: ...

class Texture:
    def __init__(
        self,
        renderer: Renderer,
        size: Iterable[int],
        static: bool = False,
        streaming: bool = False,
        target: bool = False,
    ) -> None: ...
    @staticmethod
    def from_surface(renderer: Renderer, surface: Surface) -> Texture: ...
    renderer: Renderer
    width: int
    height: int
    alpha: int
    blend_mode: int
    color: ColorValue
    def get_rect(self, **kwargs: Any) -> Rect: ...
    def draw(
        self,
        srcrect: Optional[RectValue] = None,
        dstrect: Optional[RectValue] = None,
        angle: float = 0.0,
        origin: Optional[Iterable[int]] = None,
        flip_x: bool = False,
        flip_y: bool = False,
    ) -> None: ...
    def update(self, surface: Surface, area: Optional[RectValue] = None) -> None: ...

class Image:
    def __init__(
        self,
        textureOrImage: Union[Texture, Image],
        srcrect: Optional[RectValue] = None,
    ) -> None: ...
    def get_rect(self, **kwargs: Any) -> Rect: ...
    def draw(
        self, srcrect: Optional[RectValue] = None, dstrect: Optional[RectValue] = None
    ) -> None: ...
    angle: float
    origin: Optional[Iterable[float]]
    flip_x: bool
    flip_y: bool
    color: ColorValue
    alpha: float
    blend_mode: int
    texture: Texture
    srcrect: Rect

class Renderer:
    def __init__(
        self,
        window: Window,
        index: int = -1,
        accelerated: int = -1,
        vsync: bool = False,
        target_texture: bool = False,
    ) -> None: ...
    @classmethod
    def from_window(cls, window: Window) -> Renderer: ...
    draw_blend_mode: int
    draw_color: ColorValue
    def clear(self) -> None: ...
    def present(self) -> None: ...
    def get_viewport(self) -> Rect: ...
    def set_viewport(self, area: Optional[RectValue]) -> None: ...
    logical_size: Iterable[int]
    scale: Iterable[float]
    target: Optional[Texture]
    def blit(
        self,
        source: Union[Texture, Image],
        dest: Optional[RectValue] = None,
        area: Optional[RectValue] = None,
        special_flags: int = 0,
    ) -> Rect: ...
    def draw_line(self, p1: Iterable[int], p2: Iterable[int]) -> None: ...
    def draw_point(self, point: Iterable[int]) -> None: ...
    def draw_rect(self, rect: RectValue) -> None: ...
    def fill_rect(self, rect: RectValue) -> None: ...
    def to_surface(
        self, surface: Optional[Surface] = None, area: Optional[RectValue] = None
    ) -> Surface: ...
    @staticmethod
    def compose_custom_blend_mode(
        color_mode: Tuple[int, int, int], alpha_mode: Tuple[int, int, int]
    ) -> int: ...
