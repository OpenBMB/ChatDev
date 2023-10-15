from typing import Optional, Sequence, Tuple, Union

from pygame.bufferproxy import BufferProxy
from pygame.surface import Surface

from ._common import FileArg, Literal

_BufferStyle = Union[BufferProxy, bytes, bytearray, memoryview]
_to_string_format = Literal[
    "P", "RGB", "RGBX", "RGBA", "ARGB", "BGRA", "RGBA_PREMULT", "ARGB_PREMULT"
]
_from_buffer_format = Literal["P", "RGB", "BGR", "BGRA", "RGBX", "RGBA", "ARGB"]
_from_string_format = Literal["P", "RGB", "RGBX", "RGBA", "ARGB", "BGRA"]

def load(filename: FileArg, namehint: str = "") -> Surface: ...
def save(surface: Surface, filename: FileArg, namehint: str = "") -> None: ...
def get_sdl_image_version(linked: bool = True) -> Optional[Tuple[int, int, int]]: ...
def get_extended() -> bool: ...
def tostring(
    surface: Surface, format: _to_string_format, flipped: bool = False
) -> bytes: ...
def fromstring(
    bytes: bytes,
    size: Union[Sequence[int], Tuple[int, int]],
    format: _from_string_format,
    flipped: bool = False,
) -> Surface: ...
# the use of tobytes/frombytes is preferred over tostring/fromstring
def tobytes(
    surface: Surface, format: _to_string_format, flipped: bool = False
) -> bytes: ...
def frombytes(
    bytes: bytes,
    size: Union[Sequence[int], Tuple[int, int]],
    format: _from_string_format,
    flipped: bool = False,
) -> Surface: ...
def frombuffer(
    bytes: _BufferStyle,
    size: Union[Sequence[int], Tuple[int, int]],
    format: _from_buffer_format,
) -> Surface: ...
def load_basic(filename: FileArg) -> Surface: ...
def load_extended(filename: FileArg, namehint: str = "") -> Surface: ...
def save_extended(surface: Surface, filename: FileArg, namehint: str = "") -> None: ...
