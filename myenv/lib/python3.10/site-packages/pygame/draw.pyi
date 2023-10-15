from typing import Optional, Sequence

from pygame.rect import Rect
from pygame.surface import Surface

from ._common import ColorValue, Coordinate, RectValue

def rect(
    surface: Surface,
    color: ColorValue,
    rect: RectValue,
    width: int = 0,
    border_radius: int = -1,
    border_top_left_radius: int = -1,
    border_top_right_radius: int = -1,
    border_bottom_left_radius: int = -1,
    border_bottom_right_radius: int = -1,
) -> Rect: ...
def polygon(
    surface: Surface,
    color: ColorValue,
    points: Sequence[Coordinate],
    width: int = 0,
) -> Rect: ...
def circle(
    surface: Surface,
    color: ColorValue,
    center: Coordinate,
    radius: float,
    width: int = 0,
    draw_top_right: bool = False,
    draw_top_left: bool = False,
    draw_bottom_left: bool = False,
    draw_bottom_right: bool = False,
) -> Rect: ...
def ellipse(
    surface: Surface, color: ColorValue, rect: RectValue, width: int = 0
) -> Rect: ...
def arc(
    surface: Surface,
    color: ColorValue,
    rect: RectValue,
    start_angle: float,
    stop_angle: float,
    width: int = 1,
) -> Rect: ...
def line(
    surface: Surface,
    color: ColorValue,
    start_pos: Coordinate,
    end_pos: Coordinate,
    width: int = 1,
) -> Rect: ...
def lines(
    surface: Surface,
    color: ColorValue,
    closed: bool,
    points: Sequence[Coordinate],
    width: int = 1,
) -> Rect: ...
def aaline(
    surface: Surface,
    color: ColorValue,
    start_pos: Coordinate,
    end_pos: Coordinate,
    blend: int = 1,
) -> Rect: ...
def aalines(
    surface: Surface,
    color: ColorValue,
    closed: bool,
    points: Sequence[Coordinate],
    blend: int = 1,
) -> Rect: ...
