from typing import Literal, Optional, Sequence, Union

from pygame.color import Color
from pygame.surface import Surface

from ._common import ColorValue, Coordinate, RectValue

def flip(
    surface: Surface,
    flip_x: bool | Literal[0] | Literal[1],
    flip_y: bool | Literal[0] | Literal[1],
) -> Surface: ...
def scale(
    surface: Surface,
    size: Coordinate,
    dest_surface: Optional[Surface] = None,
) -> Surface: ...
def scale_by(
    surface: Surface,
    factor: Union[float, Sequence[float]],
    dest_surface: Optional[Surface] = None,
) -> Surface: ...
def rotate(surface: Surface, angle: float) -> Surface: ...
def rotozoom(surface: Surface, angle: float, scale: float) -> Surface: ...
def scale2x(surface: Surface, dest_surface: Optional[Surface] = None) -> Surface: ...
def grayscale(surface: Surface, dest_surface: Optional[Surface] = None) -> Surface: ...
def smoothscale(
    surface: Surface,
    size: Coordinate,
    dest_surface: Optional[Surface] = None,
) -> Surface: ...
def smoothscale_by(
    surface: Surface,
    factor: Union[float, Sequence[float]],
    dest_surface: Optional[Surface] = None,
) -> Surface: ...
def get_smoothscale_backend() -> str: ...
def set_smoothscale_backend(backend: str) -> None: ...
def chop(surface: Surface, rect: RectValue) -> Surface: ...
def laplacian(surface: Surface, dest_surface: Optional[Surface] = None) -> Surface: ...
def average_surfaces(
    surfaces: Sequence[Surface],
    dest_surface: Optional[Surface] = None,
    palette_colors: Union[bool, int] = 1,
) -> Surface: ...
def average_color(
    surface: Surface, rect: Optional[RectValue] = None, consider_alpha: bool = False
) -> Color: ...
def threshold(
    dest_surface: Optional[Surface],
    surface: Surface,
    search_color: Optional[ColorValue],
    threshold: ColorValue = (0, 0, 0, 0),
    set_color: Optional[ColorValue] = (0, 0, 0, 0),
    set_behavior: int = 1,
    search_surf: Optional[Surface] = None,
    inverse_set: bool = False,
) -> int: ...
