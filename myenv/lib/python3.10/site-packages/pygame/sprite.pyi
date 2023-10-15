from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    Iterable,
    Iterator,
    List,
    Literal,
    Optional,
    SupportsFloat,
    Tuple,
    TypeVar,
    Union,
)

# Protocol added in python 3.8
from typing_extensions import Protocol

from pygame.rect import Rect
from pygame.surface import Surface
from pygame.mask import Mask

from ._common import RectValue, Coordinate

# non-generic Group, used in Sprite
_Group = AbstractGroup[_SpriteSupportsGroup]

# protocol helps with structural subtyping for typevars in sprite group generics
class _SupportsSprite(Protocol):
    @property
    def layer(self) -> int: ...
    @layer.setter
    def layer(self, value: int) -> None: ...
    def __init__(self, *groups: _Group) -> None: ...
    def add_internal(self, group: _Group) -> None: ...
    def remove_internal(self, group: _Group) -> None: ...
    def update(self, *args: Any, **kwargs: Any) -> None: ...
    def add(self, *groups: _Group) -> None: ...
    def remove(self, *groups: _Group) -> None: ...
    def kill(self) -> None: ...
    def alive(self) -> bool: ...
    def groups(self) -> List[_Group]: ...

# also a protocol
class _SupportsDirtySprite(_SupportsSprite, Protocol):
    dirty: int
    blendmode: int
    source_rect: Rect
    visible: int
    _layer: int
    def _set_visible(self, val: int) -> None: ...
    def _get_visible(self) -> int: ...

# concrete sprite implementation class
class Sprite(_SupportsSprite):
    @property
    def layer(self) -> int: ...
    @layer.setter
    def layer(self, value: int) -> None: ...
    def __init__(self, *groups: _Group) -> None: ...
    def add_internal(self, group: _Group) -> None: ...
    def remove_internal(self, group: _Group) -> None: ...
    def update(self, *args: Any, **kwargs: Any) -> None: ...
    def add(self, *groups: _Group) -> None: ...
    def remove(self, *groups: _Group) -> None: ...
    def kill(self) -> None: ...
    def alive(self) -> bool: ...
    def groups(self) -> List[_Group]: ...

class WeakSprite(Sprite):
    ...

# concrete dirty sprite implementation class
class DirtySprite(_SupportsDirtySprite):
    dirty: int
    blendmode: int
    source_rect: Rect
    visible: int
    _layer: int
    def _set_visible(self, val: int) -> None: ...
    def _get_visible(self) -> int: ...
    
class WeakDirtySprite(WeakSprite, DirtySprite):
    ...

# used as a workaround for typing.Self because it is added in python 3.11
_TGroup = TypeVar("_TGroup", bound=AbstractGroup)

# define some useful protocols first, which sprite functions accept
# sprite functions don't need all sprite attributes to be present in the
# arguments passed, they only use a few which are marked in the below protocols
class _HasRect(Protocol):
    rect: Rect

# image in addition to rect
class _HasImageAndRect(_HasRect, Protocol):
    image: Surface

# mask in addition to rect
class _HasMaskAndRect(_HasRect, Protocol):
    mask: Mask

# radius in addition to rect
class _HasRadiusAndRect(_HasRect, Protocol):
    radius: float

class _SpriteSupportsGroup(_SupportsSprite, _HasImageAndRect, Protocol): ...
class _DirtySpriteSupportsGroup(_SupportsDirtySprite, _HasImageAndRect, Protocol): ...

# typevar bound to Sprite, _SpriteSupportsGroup Protocol ensures sprite
# subclass passed to group has image and rect attributes
_TSprite = TypeVar("_TSprite", bound=_SpriteSupportsGroup)
_TSprite2 = TypeVar("_TSprite2", bound=_SpriteSupportsGroup)

# almost the same as _TSprite but bound to DirtySprite
_TDirtySprite = TypeVar("_TDirtySprite", bound=_DirtySpriteSupportsGroup)

# Below code demonstrates the advantages of the _SpriteSupportsGroup protocol

# typechecker should error, regular Sprite does not support Group.draw due to
# missing image and rect attributes
# a = Group(Sprite())

# typechecker should error, other Sprite attibutes are also needed for Group
# class MySprite:
#     image: Surface
#     rect: Rect
#
# b = Group(MySprite())

# typechecker should pass
# class MySprite(Sprite):
#     image: Surface
#     rect: Rect
#
# b = Group(MySprite())

class AbstractGroup(Generic[_TSprite]):
    spritedict: Dict[_TSprite, Optional[Rect]]
    lostsprites: List[Rect]
    def __init__(self) -> None: ...
    def __len__(self) -> int: ...
    def __iter__(self) -> Iterator[_TSprite]: ...
    def __bool__(self) -> bool: ...
    def __contains__(self, item: Any) -> bool: ...
    def add_internal(self, sprite: _TSprite, layer: None = None) -> None: ...
    def remove_internal(self, sprite: _TSprite) -> None: ...
    def has_internal(self, sprite: _TSprite) -> bool: ...
    def copy(self: _TGroup) -> _TGroup: ...  # typing.Self is py3.11+
    def sprites(self) -> List[_TSprite]: ...
    def add(
        self, *sprites: Union[_TSprite, AbstractGroup[_TSprite], Iterable[_TSprite]]
    ) -> None: ...
    def remove(
        self, *sprites: Union[_TSprite, AbstractGroup[_TSprite], Iterable[_TSprite]]
    ) -> None: ...
    def has(
        self, *sprites: Union[_TSprite, AbstractGroup[_TSprite], Iterable[_TSprite]]
    ) -> bool: ...
    def update(self, *args: Any, **kwargs: Any) -> None: ...
    def draw(
        self, surface: Surface, bgsurf: Optional[Surface] = None, special_flags: int = 0
    ) -> List[Rect]: ...
    def clear(
        self, surface: Surface, bgd: Union[Surface, Callable[[Surface, Rect], Any]]
    ) -> None: ...
    def empty(self) -> None: ...

class Group(AbstractGroup[_TSprite]):
    def __init__(
        self, *sprites: Union[_TSprite, AbstractGroup[_TSprite], Iterable[_TSprite]]
    ) -> None: ...

# these are aliased in the code too
RenderPlain = Group
RenderClear = Group

class RenderUpdates(Group[_TSprite]): ...
class OrderedUpdates(RenderUpdates[_TSprite]): ...

class LayeredUpdates(AbstractGroup[_TSprite]):
    def __init__(
        self,
        *sprites: Union[
            _TSprite,
            AbstractGroup[_TSprite],
            Iterable[Union[_TSprite, AbstractGroup[_TSprite]]],
        ],
        **kwargs: Any
    ) -> None: ...
    def add(
        self,
        *sprites: Union[
            _TSprite,
            AbstractGroup[_TSprite],
            Iterable[Union[_TSprite, AbstractGroup[_TSprite]]],
        ],
        **kwargs: Any
    ) -> None: ...
    def get_sprites_at(self, pos: Coordinate) -> List[_TSprite]: ...
    def get_sprite(self, idx: int) -> _TSprite: ...
    def remove_sprites_of_layer(self, layer_nr: int) -> List[_TSprite]: ...
    def layers(self) -> List[int]: ...
    def change_layer(self, sprite: _TSprite, new_layer: int) -> None: ...
    def get_layer_of_sprite(self, sprite: _TSprite) -> int: ...
    def get_top_layer(self) -> int: ...
    def get_bottom_layer(self) -> int: ...
    def move_to_front(self, sprite: _TSprite) -> None: ...
    def move_to_back(self, sprite: _TSprite) -> None: ...
    def get_top_sprite(self) -> _TSprite: ...
    def get_sprites_from_layer(self, layer: int) -> List[_TSprite]: ...
    def switch_layer(self, layer1_nr: int, layer2_nr: int) -> None: ...

class LayeredDirty(LayeredUpdates[_TDirtySprite]):
    def __init__(self, *sprites: _TDirtySprite, **kwargs: Any) -> None: ...
    def draw(
        self, surface: Surface, bgsurf: Optional[Surface] = None, special_flags: Optional[int] = None
    ) -> List[Rect]: ...
    # clear breaks Liskov substitution principle in code
    def clear(self, surface: Surface, bgd: Surface) -> None: ...  # type: ignore[override]
    def repaint_rect(self, screen_rect: RectValue) -> None: ...
    def set_clip(self, screen_rect: Optional[RectValue] = None) -> None: ...
    def get_clip(self) -> Rect: ...
    def set_timing_threshold(
        self, time_ms: SupportsFloat
    ) -> None: ...  # This actually accept any value
    # deprecated alias
    set_timing_treshold = set_timing_threshold

class GroupSingle(AbstractGroup[_TSprite]):
    sprite: _TSprite
    def __init__(self, sprite: Optional[_TSprite] = None) -> None: ...

# argument to collide_rect must have rect attribute
def collide_rect(left: _HasRect, right: _HasRect) -> bool: ...

class collide_rect_ratio:
    ratio: float
    def __init__(self, ratio: float) -> None: ...
    def __call__(self, left: _HasRect, right: _HasRect) -> bool: ...

# must have rect attribute, may optionally have radius attribute
_SupportsCollideCircle = Union[_HasRect, _HasRadiusAndRect]

def collide_circle(
    left: _SupportsCollideCircle, right: _SupportsCollideCircle
) -> bool: ...

class collide_circle_ratio:
    ratio: float
    def __init__(self, ratio: float) -> None: ...
    def __call__(
        self, left: _SupportsCollideCircle, right: _SupportsCollideCircle
    ) -> bool: ...

# argument to collide_mask must either have mask or have image attribute, in
# addtion to mandatorily having a rect attribute
_SupportsCollideMask = Union[_HasImageAndRect, _HasMaskAndRect]

def collide_mask(
    left: _SupportsCollideMask, right: _SupportsCollideMask
) -> Optional[Tuple[int, int]]: ...
def spritecollide(
    sprite: _HasRect,
    group: AbstractGroup[_TSprite],
    dokill: bool | Literal[1] | Literal[0],
    collided: Optional[Callable[[_HasRect, _TSprite], bool]] = None,
) -> List[_TSprite]: ...
def groupcollide(
    groupa: AbstractGroup[_TSprite],
    groupb: AbstractGroup[_TSprite2],
    dokilla: bool | Literal[1] | Literal[0],
    dokillb: bool | Literal[1] | Literal[0],
    collided: Optional[Callable[[_TSprite, _TSprite2], bool]] = None,
) -> Dict[_TSprite, List[_TSprite2]]: ...
def spritecollideany(
    sprite: _HasRect,
    group: AbstractGroup[_TSprite],
    collided: Optional[Callable[[_HasRect, _TSprite], bool]] = None,
) -> Optional[_TSprite]: ...
