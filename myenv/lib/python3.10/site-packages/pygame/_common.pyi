from os import PathLike
from typing import IO, Callable, Sequence, Tuple, Union

from typing_extensions import Literal as Literal
from typing_extensions import Protocol

from pygame.color import Color
from pygame.math import Vector2
from pygame.rect import Rect

# For functions that take a file name
AnyPath = Union[str, bytes, PathLike[str], PathLike[bytes]]

# Most pygame functions that take a file argument should be able to handle
# a FileArg type
FileArg = Union[AnyPath, IO[bytes], IO[str]]

Coordinate = Union[Tuple[float, float], Sequence[float], Vector2]

# This typehint is used when a function would return an RGBA tuble
RGBAOutput = Tuple[int, int, int, int]
ColorValue = Union[Color, int, str, Tuple[int, int, int], RGBAOutput, Sequence[int]]
from typing import Union

def my_function(my_var: Union[int, float, complex]) -> None:
    print(my_var)
_CanBeRect = Union[
    Rect,
    Tuple[Union[float, int], Union[float, int], Union[float, int], Union[float, int]],
    Tuple[Coordinate, Coordinate],
    Sequence[Union[float, int]],
    Sequence[Coordinate],
]

class _HasRectAttribute(Protocol):
    # An object that has a rect attribute that is either a rect, or a function
    # that returns a rect confirms to the rect protocol
    rect: Union[RectValue, Callable[[], RectValue]]

RectValue = Union[_CanBeRect, _HasRectAttribute]
