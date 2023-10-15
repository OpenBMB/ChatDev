from typing import Sequence

from pygame.surface import Surface

from ._common import ColorValue, Coordinate, RectValue

def pixel(surface: Surface, x: int, y: int, color: ColorValue) -> None: ...
def hline(surface: Surface, x1: int, x2: int, y: int, color: ColorValue) -> None: ...
def vline(surface: Surface, x: int, y1: int, y2: int, color: ColorValue) -> None: ...
def line(
    surface: Surface, x1: int, y1: int, x2: int, y2: int, color: ColorValue
) -> None: ...
def rectangle(surface: Surface, rect: RectValue, color: ColorValue) -> None: ...
def box(surface: Surface, rect: RectValue, color: ColorValue) -> None: ...
def circle(surface: Surface, x: int, y: int, r: int, color: ColorValue) -> None: ...
def aacircle(surface: Surface, x: int, y: int, r: int, color: ColorValue) -> None: ...
def filled_circle(
    surface: Surface, x: int, y: int, r: int, color: ColorValue
) -> None: ...
def ellipse(
    surface: Surface, x: int, y: int, rx: int, ry: int, color: ColorValue
) -> None: ...
def aaellipse(
    surface: Surface, x: int, y: int, rx: int, ry: int, color: ColorValue
) -> None: ...
def filled_ellipse(
    surface: Surface, x: int, y: int, rx: int, ry: int, color: ColorValue
) -> None: ...
def arc(
    surface: Surface,
    x: int,
    y: int,
    r: int,
    start_angle: int,
    atp_angle: int,
    color: ColorValue,
) -> None: ...
def pie(
    surface: Surface,
    x: int,
    y: int,
    r: int,
    start_angle: int,
    atp_angle: int,
    color: ColorValue,
) -> None: ...
def trigon(
    surface: Surface,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    x3: int,
    y3: int,
    color: ColorValue,
) -> None: ...
def aatrigon(
    surface: Surface,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    x3: int,
    y3: int,
    color: ColorValue,
) -> None: ...
def filled_trigon(
    surface: Surface,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    x3: int,
    y3: int,
    color: ColorValue,
) -> None: ...
def polygon(
    surface: Surface, points: Sequence[Coordinate], color: ColorValue
) -> None: ...
def aapolygon(
    surface: Surface, points: Sequence[Coordinate], color: ColorValue
) -> None: ...
def filled_polygon(
    surface: Surface, points: Sequence[Coordinate], color: ColorValue
) -> None: ...
def textured_polygon(
    surface: Surface, points: Sequence[Coordinate], texture: Surface, tx: int, ty: int
) -> None: ...
def bezier(
    surface: Surface, points: Sequence[Coordinate], steps: int, color: ColorValue
) -> None: ...
