from typing import Any, Dict, Sequence, Tuple

from pygame.surface import Surface

from ._common import ColorValue

class PixelArray:
    surface: Surface
    itemsize: int
    ndim: int
    shape: Tuple[int, ...]
    strides: Tuple[int, ...]
    # possibly going to be deprecated/removed soon, in which case these
    # typestubs must be removed too
    __array_interface__: Dict[str, Any]
    __array_struct__: Any
    def __init__(self, surface: Surface) -> None: ...
    def __enter__(self) -> PixelArray: ...
    def __exit__(self, *args, **kwargs) -> None: ...
    def make_surface(self) -> Surface: ...
    def replace(
        self,
        color: ColorValue,
        repcolor: ColorValue,
        distance: float = 0,
        weights: Sequence[float] = (0.299, 0.587, 0.114),
    ) -> None: ...
    def extract(
        self,
        color: ColorValue,
        distance: float = 0,
        weights: Sequence[float] = (0.299, 0.587, 0.114),
    ) -> PixelArray: ...
    def compare(
        self,
        array: PixelArray,
        distance: float = 0,
        weights: Sequence[float] = (0.299, 0.587, 0.114),
    ) -> PixelArray: ...
    def transpose(self) -> PixelArray: ...
    def close(self) -> PixelArray: ...
