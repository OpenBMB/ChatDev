#    pygame - Python Game Library
#    Copyright (C) 2000-2003, 2007  Pete Shinners
#              (C) 2004 Joe Wreschnig
#    This library is free software; you can redistribute it and/or
#    modify it under the terms of the GNU Library General Public
#    License as published by the Free Software Foundation; either
#    version 2 of the License, or (at your option) any later version.
#
#    This library is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#    Library General Public License for more details.
#
#    You should have received a copy of the GNU Library General Public
#    License along with this library; if not, write to the Free
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
#    Pete Shinners
#    pete@shinners.org

"""pygame module with basic game object classes

This module contains several simple classes to be used within games. There
are the main Sprite class and several Group classes that contain Sprites.
The use of these classes is entirely optional when using Pygame. The classes
are fairly lightweight and only provide a starting place for the code
that is common to most games.

The Sprite class is intended to be used as a base class for the different
types of objects in the game. There is also a base Group class that simply
stores sprites. A game could create new types of Group classes that operate
on specially customized Sprite instances they contain.

The basic Sprite class can draw the Sprites it contains to a Surface. The
Group.draw() method requires that each Sprite have a Surface.image attribute
and a Surface.rect. The Group.clear() method requires these same attributes
and can be used to erase all the Sprites with background. There are also
more advanced Groups: pygame.sprite.RenderUpdates() and
pygame.sprite.OrderedUpdates().

Lastly, this module contains several collision functions. These help find
sprites inside multiple groups that have intersecting bounding rectangles.
To find the collisions, the Sprites are required to have a Surface.rect
attribute assigned.

The groups are designed for high efficiency in removing and adding Sprites
to them. They also allow cheap testing to see if a Sprite already exists in
a Group. A given Sprite can exist in any number of groups. A game could use
some groups to control object rendering, and a completely separate set of
groups to control interaction or player movement. Instead of adding type
attributes or bools to a derived Sprite class, consider keeping the
Sprites inside organized Groups. This will allow for easier lookup later
in the game.

Sprites and Groups manage their relationships with the add() and remove()
methods. These methods can accept a single or multiple group arguments for
membership.  The default initializers for these classes also take a
single group or list of groups as arguments for initial membership. It is safe
to repeatedly add and remove the same Sprite from a Group.

While it is possible to design sprite and group classes that don't derive
from the Sprite and AbstractGroup classes below, it is strongly recommended
that you extend those when you create a new Sprite or Group class.

Sprites are not thread safe, so lock them yourself if using threads.

"""

# TODO:  a group that holds only the 'n' most recent elements.
#        sort of like the GroupSingle class, but holding more
#        than one sprite
#
# drawing groups that can 'automatically' store the area
# underneath so they can "clear" without needing a background
# function. obviously a little slower than normal, but nice
# to use in many situations. (also remember it must "clear"
# in the reverse order that it draws :])
#
# the drawing groups should also be able to take a background
# function, instead of just a background surface. the function
# would take a surface and a rectangle on that surface to erase.
#
# perhaps more types of collision functions? the current two
# should handle just about every need, but perhaps more optimized
# specific ones that aren't quite so general but fit into common
# specialized cases.

from weakref import WeakSet
from warnings import warn

import pygame

from pygame.rect import Rect
from pygame.time import get_ticks
from pygame.mask import from_surface


class Sprite:
    """simple base class for visible game objects

    pygame.sprite.Sprite(*groups): return Sprite

    The base class for visible game objects. Derived classes will want to
    override the Sprite.update() method and assign Sprite.image and Sprite.rect
    attributes.  The initializer can accept any number of Group instances that
    the Sprite will become a member of.

    When subclassing the Sprite class, be sure to call the base initializer
    before adding the Sprite to Groups.

    """

    def __init__(self, *groups):
        self.__g = set()  # The groups the sprite is in
        if groups:
            self.add(*groups)

    def add(self, *groups):
        """add the sprite to groups

        Sprite.add(*groups): return None

        Any number of Group instances can be passed as arguments. The
        Sprite will be added to the Groups it is not already a member of.

        """
        has = self.__g.__contains__
        for group in groups:
            if hasattr(group, "_spritegroup"):
                if not has(group):
                    group.add_internal(self)
                    self.add_internal(group)
            else:
                self.add(*group)

    def remove(self, *groups):
        """remove the sprite from groups

        Sprite.remove(*groups): return None

        Any number of Group instances can be passed as arguments. The Sprite
        will be removed from the Groups it is currently a member of.

        """
        has = self.__g.__contains__
        for group in groups:
            if hasattr(group, "_spritegroup"):
                if has(group):
                    group.remove_internal(self)
                    self.remove_internal(group)
            else:
                self.remove(*group)

    def add_internal(self, group):
        """
        For adding this sprite to a group internally.

        :param group: The group we are adding to.
        """
        self.__g.add(group)

    def remove_internal(self, group):
        """
        For removing this sprite from a group internally.

        :param group: The group we are removing from.
        """
        self.__g.remove(group)

    def update(self, *args, **kwargs):
        """method to control sprite behavior

        Sprite.update(*args, **kwargs):

        The default implementation of this method does nothing; it's just a
        convenient "hook" that you can override. This method is called by
        Group.update() with whatever arguments you give it.

        There is no need to use this method if not using the convenience
        method by the same name in the Group class.

        """

    def kill(self):
        """remove the Sprite from all Groups

        Sprite.kill(): return None

        The Sprite is removed from all the Groups that contain it. This won't
        change anything about the state of the Sprite. It is possible to
        continue to use the Sprite after this method has been called, including
        adding it to Groups.

        """
        for group in self.__g:
            group.remove_internal(self)
        self.__g.clear()

    def groups(self):
        """list of Groups that contain this Sprite

        Sprite.groups(): return group_list

        Returns a list of all the Groups that contain this Sprite.

        """
        return list(self.__g)

    def alive(self):
        """does the sprite belong to any groups

        Sprite.alive(): return bool

        Returns True when the Sprite belongs to one or more Groups.
        """
        return bool(self.__g)

    def __repr__(self):
        return f"<{self.__class__.__name__} Sprite(in {len(self.__g)} groups)>"

    @property
    def layer(self):
        """
        Dynamic, read only property for protected _layer attribute.
        This will get the _layer variable if it exists.

        If you try to get it before it is set it will raise an attribute error.

        Layer property can only be set before the sprite is added to a group,
        after that it is read only and a sprite's layer in a group should be
        set via the group's change_layer() method.

        :return: layer as an int, or raise AttributeError.
        """
        return self._layer

    @layer.setter
    def layer(self, value):
        if not self.alive():
            self._layer = value
        else:
            raise AttributeError(
                "Can't set layer directly after "
                "adding to group. Use "
                "group.change_layer(sprite, new_layer) "
                "instead."
            )


class WeakSprite(Sprite):
    """A subclass of Sprite that references its Groups weakly. This
    means that any group this belongs to that is not referenced anywhere
    else is garbage collected automatically.
    """

    def __init__(self, *groups):
        super().__init__(*groups)
        self.__dict__["_Sprite__g"] = WeakSet(self._Sprite__g)


class DirtySprite(Sprite):
    """a more featureful subclass of Sprite with more attributes

    pygame.sprite.DirtySprite(*groups): return DirtySprite

    Extra DirtySprite attributes with their default values:

    dirty = 1
        If set to 1, it is repainted and then set to 0 again.
        If set to 2, it is always dirty (repainted each frame;
        flag is not reset).
        If set to 0, it is not dirty and therefore not repainted again.

    blendmode = 0
        It's the special_flags argument of Surface.blit; see the blendmodes in
        the Surface.blit documentation

    source_rect = None
        This is the source rect to use. Remember that it is relative to the top
        left corner (0, 0) of self.image.

    visible = 1
        Normally this is 1. If set to 0, it will not be repainted. (If you
        change visible to 1, you must set dirty to 1 for it to be erased from
        the screen.)

    _layer = 0
        0 is the default value but this is able to be set differently
        when subclassing.

    """

    def __init__(self, *groups):
        self.dirty = 1

        # referred to as special_flags in the documentation of Surface.blit
        self.blendmode = 0
        self._visible = 1

        # Default 0 unless initialized differently.
        self._layer = getattr(self, "_layer", 0)
        self.source_rect = None
        Sprite.__init__(self, *groups)

    def _set_visible(self, val):
        """set the visible value (0 or 1) and makes the sprite dirty"""
        self._visible = val
        if self.dirty < 2:
            self.dirty = 1

    def _get_visible(self):
        """return the visible value of that sprite"""
        return self._visible

    @property
    def visible(self):
        """
        You can make this sprite disappear without removing it from the group
        assign 0 for invisible and 1 for visible
        """
        return self._get_visible()

    @visible.setter
    def visible(self, value):
        self._set_visible(value)

    @property
    def layer(self):
        """
        Layer property can only be set before the sprite is added to a group,
        after that it is read only and a sprite's layer in a group should be
        set via the group's change_layer() method.

        Overwrites dynamic property from sprite class for speed.
        """
        return self._layer

    @layer.setter
    def layer(self, value):
        if not self.alive():
            self._layer = value
        else:
            raise AttributeError(
                "Can't set layer directly after "
                "adding to group. Use "
                "group.change_layer(sprite, new_layer) "
                "instead."
            )

    def __repr__(self):
        return (
            f"<{self.__class__.__name__} DirtySprite(in {len(self.groups())} groups)>"
        )


class WeakDirtySprite(WeakSprite, DirtySprite):
    """A subclass of WeakSprite and DirtySprite that combines the benefits
    of both classes.
    """


class AbstractGroup:
    """base class for containers of sprites

    AbstractGroup does everything needed to behave as a normal group. You can
    easily subclass a new group class from this or the other groups below if
    you want to add more features.

    Any AbstractGroup-derived sprite groups act like sequences and support
    iteration, len, and so on.

    """

    # dummy val to identify sprite groups, and avoid infinite recursion
    _spritegroup = True

    def __init__(self):
        self.spritedict = {}
        self.lostsprites = []

    def sprites(self):
        """get a list of sprites in the group

        Group.sprites(): return list

        Returns an object that can be looped over with a 'for' loop. (For now,
        it is always a list, but this could change in a future version of
        pygame.) Alternatively, you can get the same information by iterating
        directly over the sprite group, e.g. 'for sprite in group'.

        """
        return list(self.spritedict)

    def add_internal(
        self,
        sprite,
        layer=None,  # noqa pylint: disable=unused-argument; supporting legacy derived classes that override in non-pythonic way
    ):
        """
        For adding a sprite to this group internally.

        :param sprite: The sprite we are adding.
        :param layer: the layer to add to, if the group type supports layers
        """
        self.spritedict[sprite] = None

    def remove_internal(self, sprite):
        """
        For removing a sprite from this group internally.

        :param sprite: The sprite we are removing.
        """
        lost_rect = self.spritedict[sprite]
        if lost_rect:
            self.lostsprites.append(lost_rect)
        del self.spritedict[sprite]

    def has_internal(self, sprite):
        """
        For checking if a sprite is in this group internally.

        :param sprite: The sprite we are checking.
        """
        return sprite in self.spritedict

    def copy(self):
        """copy a group with all the same sprites

        Group.copy(): return Group

        Returns a copy of the group that is an instance of the same class
        and has the same sprites in it.

        """
        return self.__class__(  # noqa pylint: disable=too-many-function-args
            self.sprites()  # Needed because copy() won't work on AbstractGroup
        )

    def __iter__(self):
        return iter(self.sprites())

    def __contains__(self, sprite):
        return self.has(sprite)

    def add(self, *sprites):
        """add sprite(s) to group

        Group.add(sprite, list, group, ...): return None

        Adds a sprite or sequence of sprites to a group.

        """
        for sprite in sprites:
            # It's possible that some sprite is also an iterator.
            # If this is the case, we should add the sprite itself,
            # and not the iterator object.
            if isinstance(sprite, Sprite):
                if not self.has_internal(sprite):
                    self.add_internal(sprite)
                    sprite.add_internal(self)
            else:
                try:
                    # See if sprite is an iterator, like a list or sprite
                    # group.
                    self.add(*sprite)
                except (TypeError, AttributeError):
                    # Not iterable. This is probably a sprite that is not an
                    # instance of the Sprite class or is not an instance of a
                    # subclass of the Sprite class. Alternately, it could be an
                    # old-style sprite group.
                    if hasattr(sprite, "_spritegroup"):
                        for spr in sprite.sprites():
                            if not self.has_internal(spr):
                                self.add_internal(spr)
                                spr.add_internal(self)
                    elif not self.has_internal(sprite):
                        self.add_internal(sprite)
                        sprite.add_internal(self)

    def remove(self, *sprites):
        """remove sprite(s) from group

        Group.remove(sprite, list, or group, ...): return None

        Removes a sprite or sequence of sprites from a group.

        """
        # This function behaves essentially the same as Group.add. It first
        # tries to handle each argument as an instance of the Sprite class. If
        # that fails, then it tries to handle the argument as an iterable
        # object. If that fails, then it tries to handle the argument as an
        # old-style sprite group. Lastly, if that fails, it assumes that the
        # normal Sprite methods should be used.
        for sprite in sprites:
            if isinstance(sprite, Sprite):
                if self.has_internal(sprite):
                    self.remove_internal(sprite)
                    sprite.remove_internal(self)
            else:
                try:
                    self.remove(*sprite)
                except (TypeError, AttributeError):
                    if hasattr(sprite, "_spritegroup"):
                        for spr in sprite.sprites():
                            if self.has_internal(spr):
                                self.remove_internal(spr)
                                spr.remove_internal(self)
                    elif self.has_internal(sprite):
                        self.remove_internal(sprite)
                        sprite.remove_internal(self)

    def has(self, *sprites):
        """ask if group has a sprite or sprites

        Group.has(sprite or group, ...): return bool

        Returns True if the given sprite or sprites are contained in the
        group. Alternatively, you can get the same information using the
        'in' operator, e.g. 'sprite in group', 'subgroup in group'.

        """
        if not sprites:
            return False  # return False if no sprites passed in

        for sprite in sprites:
            if isinstance(sprite, Sprite):
                # Check for Sprite instance's membership in this group
                if not self.has_internal(sprite):
                    return False
            else:
                try:
                    if not self.has(*sprite):
                        return False
                except (TypeError, AttributeError):
                    if hasattr(sprite, "_spritegroup"):
                        for spr in sprite.sprites():
                            if not self.has_internal(spr):
                                return False
                    else:
                        if not self.has_internal(sprite):
                            return False

        return True

    def update(self, *args, **kwargs):
        """call the update method of every member sprite

        Group.update(*args, **kwargs): return None

        Calls the update method of every member sprite. All arguments that
        were passed to this method are passed to the Sprite update function.

        """
        for sprite in self.sprites():
            sprite.update(*args, **kwargs)

    def draw(
        self, surface, bgsurf=None, special_flags=0
    ):  # noqa pylint: disable=unused-argument; bgsurf arg used in LayeredDirty
        """draw all sprites onto the surface

        Group.draw(surface, special_flags=0): return Rect_list

        Draws all of the member sprites onto the given surface.

        """
        sprites = self.sprites()
        if hasattr(surface, "blits"):
            self.spritedict.update(
                zip(
                    sprites,
                    surface.blits(
                        (spr.image, spr.rect, None, special_flags) for spr in sprites
                    ),
                )
            )
        else:
            for spr in sprites:
                self.spritedict[spr] = surface.blit(
                    spr.image, spr.rect, None, special_flags
                )
        self.lostsprites = []
        dirty = self.lostsprites

        return dirty

    def clear(self, surface, bgd):
        """erase the previous position of all sprites

        Group.clear(surface, bgd): return None

        Clears the area under every drawn sprite in the group. The bgd
        argument should be Surface which is the same dimensions as the
        screen surface. The bgd could also be a function which accepts
        the given surface and the area to be cleared as arguments.

        """
        if callable(bgd):
            for lost_clear_rect in self.lostsprites:
                bgd(surface, lost_clear_rect)
            for clear_rect in self.spritedict.values():
                if clear_rect:
                    bgd(surface, clear_rect)
        else:
            surface_blit = surface.blit
            for lost_clear_rect in self.lostsprites:
                surface_blit(bgd, lost_clear_rect, lost_clear_rect)
            for clear_rect in self.spritedict.values():
                if clear_rect:
                    surface_blit(bgd, clear_rect, clear_rect)

    def empty(self):
        """remove all sprites

        Group.empty(): return None

        Removes all the sprites from the group.

        """
        for sprite in self.sprites():
            self.remove_internal(sprite)
            sprite.remove_internal(self)

    def __bool__(self):
        return bool(self.sprites())

    def __len__(self):
        """return number of sprites in group

        Group.len(group): return int

        Returns the number of sprites contained in the group.

        """
        return len(self.sprites())

    def __repr__(self):
        return f"<{self.__class__.__name__}({len(self)} sprites)>"


class Group(AbstractGroup):
    """container class for many Sprites

    pygame.sprite.Group(*sprites): return Group

    A simple container for Sprite objects. This class can be subclassed to
    create containers with more specific behaviors. The constructor takes any
    number of Sprite arguments to add to the Group. The group supports the
    following standard Python operations:

        in      test if a Sprite is contained
        len     the number of Sprites contained
        bool    test if any Sprites are contained
        iter    iterate through all the Sprites

    The Sprites in the Group are not ordered, so the Sprites are drawn and
    iterated over in no particular order.

    """

    def __init__(self, *sprites):
        AbstractGroup.__init__(self)
        self.add(*sprites)


RenderPlain = Group
RenderClear = Group


class RenderUpdates(Group):
    """Group class that tracks dirty updates

    pygame.sprite.RenderUpdates(*sprites): return RenderUpdates

    This class is derived from pygame.sprite.Group(). It has an enhanced draw
    method that tracks the changed areas of the screen.

    """

    def draw(self, surface, bgsurf=None, special_flags=0):
        surface_blit = surface.blit
        dirty = self.lostsprites
        self.lostsprites = []
        dirty_append = dirty.append
        for sprite in self.sprites():
            old_rect = self.spritedict[sprite]
            new_rect = surface_blit(sprite.image, sprite.rect, None, special_flags)
            if old_rect:
                if new_rect.colliderect(old_rect):
                    dirty_append(new_rect.union(old_rect))
                else:
                    dirty_append(new_rect)
                    dirty_append(old_rect)
            else:
                dirty_append(new_rect)
            self.spritedict[sprite] = new_rect
        return dirty


class OrderedUpdates(RenderUpdates):
    """RenderUpdates class that draws Sprites in order of addition

    pygame.sprite.OrderedUpdates(*sprites): return OrderedUpdates

    This class derives from pygame.sprite.RenderUpdates().  It maintains
    the order in which the Sprites were added to the Group for rendering.
    This makes adding and removing Sprites from the Group a little
    slower than regular Groups.

    """

    def __init__(self, *sprites):
        self._spritelist = []
        RenderUpdates.__init__(self, *sprites)

    def sprites(self):
        return self._spritelist.copy()

    def add_internal(self, sprite, layer=None):
        RenderUpdates.add_internal(self, sprite)
        self._spritelist.append(sprite)

    def remove_internal(self, sprite):
        RenderUpdates.remove_internal(self, sprite)
        self._spritelist.remove(sprite)


class LayeredUpdates(AbstractGroup):
    """LayeredUpdates Group handles layers, which are drawn like OrderedUpdates

    pygame.sprite.LayeredUpdates(*sprites, **kwargs): return LayeredUpdates

    This group is fully compatible with pygame.sprite.Sprite.
    New in pygame 1.8.0

    """

    _init_rect = Rect(0, 0, 0, 0)

    def __init__(self, *sprites, **kwargs):
        """initialize an instance of LayeredUpdates with the given attributes

        You can set the default layer through kwargs using 'default_layer'
        and an integer for the layer. The default layer is 0.

        If the sprite you add has an attribute _layer, then that layer will be
        used. If **kwarg contains 'layer', then the passed sprites will be
        added to that layer (overriding the sprite._layer attribute). If
        neither the sprite nor **kwarg has a 'layer', then the default layer is
        used to add the sprites.

        """
        self._spritelayers = {}
        self._spritelist = []
        AbstractGroup.__init__(self)
        self._default_layer = kwargs.get("default_layer", 0)

        self.add(*sprites, **kwargs)

    def add_internal(self, sprite, layer=None):
        """Do not use this method directly.

        It is used by the group to add a sprite internally.

        """
        self.spritedict[sprite] = self._init_rect

        if layer is None:
            try:
                layer = sprite.layer
            except AttributeError:
                layer = self._default_layer
                setattr(sprite, "_layer", layer)
        elif hasattr(sprite, "_layer"):
            setattr(sprite, "_layer", layer)

        sprites = self._spritelist  # speedup
        sprites_layers = self._spritelayers
        sprites_layers[sprite] = layer

        # add the sprite at the right position
        # bisect algorithmus
        leng = len(sprites)
        low = mid = 0
        high = leng - 1
        while low <= high:
            mid = low + (high - low) // 2
            if sprites_layers[sprites[mid]] <= layer:
                low = mid + 1
            else:
                high = mid - 1
        # linear search to find final position
        while mid < leng and sprites_layers[sprites[mid]] <= layer:
            mid += 1
        sprites.insert(mid, sprite)

    def add(self, *sprites, **kwargs):
        """add a sprite or sequence of sprites to a group

        LayeredUpdates.add(*sprites, **kwargs): return None

        If the sprite you add has an attribute _layer, then that layer will be
        used. If **kwarg contains 'layer', then the passed sprites will be
        added to that layer (overriding the sprite._layer attribute). If
        neither the sprite nor **kwarg has a 'layer', then the default layer is
        used to add the sprites.

        """

        if not sprites:
            return
        layer = kwargs["layer"] if "layer" in kwargs else None
        for sprite in sprites:
            # It's possible that some sprite is also an iterator.
            # If this is the case, we should add the sprite itself,
            # and not the iterator object.
            if isinstance(sprite, Sprite):
                if not self.has_internal(sprite):
                    self.add_internal(sprite, layer)
                    sprite.add_internal(self)
            else:
                try:
                    # See if sprite is an iterator, like a list or sprite
                    # group.
                    self.add(*sprite, **kwargs)
                except (TypeError, AttributeError):
                    # Not iterable. This is probably a sprite that is not an
                    # instance of the Sprite class or is not an instance of a
                    # subclass of the Sprite class. Alternately, it could be an
                    # old-style sprite group.
                    if hasattr(sprite, "_spritegroup"):
                        for spr in sprite.sprites():
                            if not self.has_internal(spr):
                                self.add_internal(spr, layer)
                                spr.add_internal(self)
                    elif not self.has_internal(sprite):
                        self.add_internal(sprite, layer)
                        sprite.add_internal(self)

    def remove_internal(self, sprite):
        """Do not use this method directly.

        The group uses it to add a sprite.

        """
        self._spritelist.remove(sprite)
        # these dirty rects are suboptimal for one frame
        old_rect = self.spritedict[sprite]
        if old_rect is not self._init_rect:
            self.lostsprites.append(old_rect)  # dirty rect
        if hasattr(sprite, "rect"):
            self.lostsprites.append(sprite.rect)  # dirty rect

        del self.spritedict[sprite]
        del self._spritelayers[sprite]

    def sprites(self):
        """return a ordered list of sprites (first back, last top).

        LayeredUpdates.sprites(): return sprites

        """
        return self._spritelist.copy()

    def draw(self, surface, bgsurf=None, special_flags=0):
        """draw all sprites in the right order onto the passed surface

        LayeredUpdates.draw(surface, special_flags=0): return Rect_list

        """
        spritedict = self.spritedict
        surface_blit = surface.blit
        dirty = self.lostsprites
        self.lostsprites = []
        dirty_append = dirty.append
        init_rect = self._init_rect
        for spr in self.sprites():
            rec = spritedict[spr]
            newrect = surface_blit(spr.image, spr.rect, None, special_flags)
            if rec is init_rect:
                dirty_append(newrect)
            else:
                if newrect.colliderect(rec):
                    dirty_append(newrect.union(rec))
                else:
                    dirty_append(newrect)
                    dirty_append(rec)
            spritedict[spr] = newrect
        return dirty

    def get_sprites_at(self, pos):
        """return a list with all sprites at that position

        LayeredUpdates.get_sprites_at(pos): return colliding_sprites

        Bottom sprites are listed first; the top ones are listed last.

        """
        _sprites = self._spritelist
        rect = Rect(pos, (1, 1))
        colliding_idx = rect.collidelistall(_sprites)
        return [_sprites[i] for i in colliding_idx]

    def get_sprite(self, idx):
        """return the sprite at the index idx from the groups sprites

        LayeredUpdates.get_sprite(idx): return sprite

        Raises IndexOutOfBounds if the idx is not within range.

        """
        return self._spritelist[idx]

    def remove_sprites_of_layer(self, layer_nr):
        """remove all sprites from a layer and return them as a list

        LayeredUpdates.remove_sprites_of_layer(layer_nr): return sprites

        """
        sprites = self.get_sprites_from_layer(layer_nr)
        self.remove(*sprites)
        return sprites

    # layer methods
    def layers(self):
        """return a list of unique defined layers defined.

        LayeredUpdates.layers(): return layers

        """
        return sorted(set(self._spritelayers.values()))

    def change_layer(self, sprite, new_layer):
        """change the layer of the sprite

        LayeredUpdates.change_layer(sprite, new_layer): return None

        The sprite must have been added to the renderer already. This is not
        checked.

        """
        sprites = self._spritelist  # speedup
        sprites_layers = self._spritelayers  # speedup

        sprites.remove(sprite)
        sprites_layers.pop(sprite)

        # add the sprite at the right position
        # bisect algorithmus
        leng = len(sprites)
        low = mid = 0
        high = leng - 1
        while low <= high:
            mid = low + (high - low) // 2
            if sprites_layers[sprites[mid]] <= new_layer:
                low = mid + 1
            else:
                high = mid - 1
        # linear search to find final position
        while mid < leng and sprites_layers[sprites[mid]] <= new_layer:
            mid += 1
        sprites.insert(mid, sprite)
        if hasattr(sprite, "_layer"):
            setattr(sprite, "_layer", new_layer)

        # add layer info
        sprites_layers[sprite] = new_layer

    def get_layer_of_sprite(self, sprite):
        """return the layer that sprite is currently in

        If the sprite is not found, then it will return the default layer.

        """
        return self._spritelayers.get(sprite, self._default_layer)

    def get_top_layer(self):
        """return the top layer

        LayeredUpdates.get_top_layer(): return layer

        """
        return self._spritelayers[self._spritelist[-1]]

    def get_bottom_layer(self):
        """return the bottom layer

        LayeredUpdates.get_bottom_layer(): return layer

        """
        return self._spritelayers[self._spritelist[0]]

    def move_to_front(self, sprite):
        """bring the sprite to front layer

        LayeredUpdates.move_to_front(sprite): return None

        Brings the sprite to front by changing the sprite layer to the top-most
        layer. The sprite is added at the end of the list of sprites in that
        top-most layer.

        """
        self.change_layer(sprite, self.get_top_layer())

    def move_to_back(self, sprite):
        """move the sprite to the bottom layer

        LayeredUpdates.move_to_back(sprite): return None

        Moves the sprite to the bottom layer by moving it to a new layer below
        the current bottom layer.

        """
        self.change_layer(sprite, self.get_bottom_layer() - 1)

    def get_top_sprite(self):
        """return the topmost sprite

        LayeredUpdates.get_top_sprite(): return Sprite

        """
        return self._spritelist[-1]

    def get_sprites_from_layer(self, layer):
        """return all sprites from a layer ordered as they where added

        LayeredUpdates.get_sprites_from_layer(layer): return sprites

        Returns all sprites from a layer. The sprites are ordered in the
        sequence that they where added. (The sprites are not removed from the
        layer.

        """
        sprites = []
        sprites_append = sprites.append
        sprite_layers = self._spritelayers
        for spr in self._spritelist:
            if sprite_layers[spr] == layer:
                sprites_append(spr)
            elif sprite_layers[spr] > layer:
                # break after because no other will
                # follow with same layer
                break
        return sprites

    def switch_layer(self, layer1_nr, layer2_nr):
        """switch the sprites from layer1_nr to layer2_nr

        LayeredUpdates.switch_layer(layer1_nr, layer2_nr): return None

        The layers number must exist. This method does not check for the
        existence of the given layers.

        """
        sprites1 = self.remove_sprites_of_layer(layer1_nr)
        for spr in self.get_sprites_from_layer(layer2_nr):
            self.change_layer(spr, layer1_nr)
        self.add(layer=layer2_nr, *sprites1)


class LayeredDirty(LayeredUpdates):
    """LayeredDirty Group is for DirtySprites; subclasses LayeredUpdates

    pygame.sprite.LayeredDirty(*sprites, **kwargs): return LayeredDirty

    This group requires pygame.sprite.DirtySprite or any sprite that
    has the following attributes:
        image, rect, dirty, visible, blendmode (see doc of DirtySprite).

    It uses the dirty flag technique and is therefore faster than
    pygame.sprite.RenderUpdates if you have many static sprites.  It
    also switches automatically between dirty rect updating and full
    screen drawing, so you do no have to worry which would be faster.

    As with the pygame.sprite.Group, you can specify some additional attributes
    through kwargs:
        _use_update: True/False   (default is False)
        _default_layer: default layer where the sprites without a layer are
            added
        _time_threshold: threshold time for switching between dirty rect mode
            and fullscreen mode; defaults to updating at 80 frames per second,
            which is equal to 1000.0 / 80.0

    New in pygame 1.8.0

    """

    def __init__(self, *sprites, **kwargs):
        """initialize group.

        pygame.sprite.LayeredDirty(*sprites, **kwargs): return LayeredDirty

        You can specify some additional attributes through kwargs:
            _use_update: True/False   (default is False)
            _default_layer: default layer where the sprites without a layer are
                added
            _time_threshold: threshold time for switching between dirty rect
                mode and fullscreen mode; defaults to updating at 80 frames per
                second, which is equal to 1000.0 / 80.0

        """
        LayeredUpdates.__init__(self, *sprites, **kwargs)
        self._clip = None

        self._use_update = False

        self._time_threshold = 1000.0 / 80.0  # 1000.0 / fps

        self._bgd = None
        for key, val in kwargs.items():
            if key in ["_use_update", "_time_threshold", "_default_layer"] and hasattr(
                self, key
            ):
                setattr(self, key, val)

    def add_internal(self, sprite, layer=None):
        """Do not use this method directly.

        It is used by the group to add a sprite internally.

        """
        # check if all needed attributes are set
        if not hasattr(sprite, "dirty"):
            raise AttributeError()
        if not hasattr(sprite, "visible"):
            raise AttributeError()
        if not hasattr(sprite, "blendmode"):
            raise AttributeError()

        if not isinstance(sprite, DirtySprite):
            raise TypeError()

        if sprite.dirty == 0:  # set it dirty if it is not
            sprite.dirty = 1

        LayeredUpdates.add_internal(self, sprite, layer)

    def draw(self, surface, bgsurf=None, special_flags=None):
        """draw all sprites in the right order onto the given surface

        LayeredDirty.draw(surface, bgsurf=None, special_flags=None): return Rect_list

        You can pass the background too. If a self.bgd is already set to some
        value that is not None, then the bgsurf argument has no effect.
        Passing a value to special_flags will pass that value as the
        special_flags argument to pass to all Surface.blit calls, overriding
        the sprite.blendmode attribute

        """
        # functions and classes assigned locally to speed up loops
        orig_clip = surface.get_clip()
        latest_clip = self._clip
        if latest_clip is None:
            latest_clip = orig_clip

        local_sprites = self._spritelist
        local_old_rect = self.spritedict
        local_update = self.lostsprites
        rect_type = Rect

        surf_blit_func = surface.blit
        if bgsurf is not None:
            self._bgd = bgsurf
        local_bgd = self._bgd

        surface.set_clip(latest_clip)
        # -------
        # 0. decide whether to render with update or flip
        start_time = get_ticks()
        if self._use_update:  # dirty rects mode
            # 1. find dirty area on screen and put the rects into
            # self.lostsprites still not happy with that part
            self._find_dirty_area(
                latest_clip,
                local_old_rect,
                rect_type,
                local_sprites,
                local_update,
                local_update.append,
                self._init_rect,
            )
            # can it be done better? because that is an O(n**2) algorithm in
            # worst case

            # clear using background
            if local_bgd is not None:
                flags = 0 if special_flags is None else special_flags
                for rec in local_update:
                    surf_blit_func(local_bgd, rec, rec, flags)

            # 2. draw
            self._draw_dirty_internal(
                local_old_rect,
                rect_type,
                local_sprites,
                surf_blit_func,
                local_update,
                special_flags,
            )
            local_ret = list(local_update)
        else:  # flip, full screen mode
            if local_bgd is not None:
                flags = 0 if special_flags is None else special_flags
                surf_blit_func(local_bgd, (0, 0), None, flags)
            for spr in local_sprites:
                if spr.visible:
                    flags = spr.blendmode if special_flags is None else special_flags
                    local_old_rect[spr] = surf_blit_func(
                        spr.image, spr.rect, spr.source_rect, flags
                    )
            # return only the part of the screen changed
            local_ret = [rect_type(latest_clip)]

        # timing for switching modes
        # How may a good threshold be found? It depends on the hardware.
        end_time = get_ticks()
        if end_time - start_time > self._time_threshold:
            self._use_update = False
        else:
            self._use_update = True

        # empty dirty rects list
        local_update[:] = []

        # -------
        # restore original clip
        surface.set_clip(orig_clip)
        return local_ret

    @staticmethod
    def _draw_dirty_internal(
        _old_rect, _rect, _sprites, _surf_blit, _update, _special_flags
    ):
        for spr in _sprites:
            flags = spr.blendmode if _special_flags is None else _special_flags
            if spr.dirty < 1 and spr.visible:
                # sprite not dirty; blit only the intersecting part
                if spr.source_rect is not None:
                    # For possible future speed up, source_rect's data
                    # can be pre-fetched outside of this loop.
                    _spr_rect = _rect(spr.rect.topleft, spr.source_rect.size)
                    rect_offset_x = spr.source_rect[0] - _spr_rect[0]
                    rect_offset_y = spr.source_rect[1] - _spr_rect[1]
                else:
                    _spr_rect = spr.rect
                    rect_offset_x = -_spr_rect[0]
                    rect_offset_y = -_spr_rect[1]

                _spr_rect_clip = _spr_rect.clip

                for idx in _spr_rect.collidelistall(_update):
                    # clip
                    clip = _spr_rect_clip(_update[idx])
                    _surf_blit(
                        spr.image,
                        clip,
                        (
                            clip[0] + rect_offset_x,
                            clip[1] + rect_offset_y,
                            clip[2],
                            clip[3],
                        ),
                        flags,
                    )
            else:  # dirty sprite
                if spr.visible:
                    _old_rect[spr] = _surf_blit(
                        spr.image, spr.rect, spr.source_rect, flags
                    )
                if spr.dirty == 1:
                    spr.dirty = 0

    @staticmethod
    def _find_dirty_area(
        _clip, _old_rect, _rect, _sprites, _update, _update_append, init_rect
    ):
        for spr in _sprites:
            if spr.dirty > 0:
                # chose the right rect
                if spr.source_rect:
                    _union_rect = _rect(spr.rect.topleft, spr.source_rect.size)
                else:
                    _union_rect = _rect(spr.rect)

                _union_rect_collidelist = _union_rect.collidelist
                _union_rect_union_ip = _union_rect.union_ip
                i = _union_rect_collidelist(_update)
                while i > -1:
                    _union_rect_union_ip(_update[i])
                    del _update[i]
                    i = _union_rect_collidelist(_update)
                _update_append(_union_rect.clip(_clip))

                if _old_rect[spr] is not init_rect:
                    _union_rect = _rect(_old_rect[spr])
                    _union_rect_collidelist = _union_rect.collidelist
                    _union_rect_union_ip = _union_rect.union_ip
                    i = _union_rect_collidelist(_update)
                    while i > -1:
                        _union_rect_union_ip(_update[i])
                        del _update[i]
                        i = _union_rect_collidelist(_update)
                    _update_append(_union_rect.clip(_clip))

    def clear(self, surface, bgd):
        """use to set background

        Group.clear(surface, bgd): return None

        """
        self._bgd = bgd

    def repaint_rect(self, screen_rect):
        """repaint the given area

        LayeredDirty.repaint_rect(screen_rect): return None

        screen_rect is in screen coordinates.

        """
        if self._clip:
            self.lostsprites.append(screen_rect.clip(self._clip))
        else:
            self.lostsprites.append(Rect(screen_rect))

    def set_clip(self, screen_rect=None):
        """clip the area where to draw; pass None (default) to reset the clip

        LayeredDirty.set_clip(screen_rect=None): return None

        """
        if screen_rect is None:
            self._clip = pygame.display.get_surface().get_rect()
        else:
            self._clip = screen_rect
        self._use_update = False

    def get_clip(self):
        """get the area where drawing will occur

        LayeredDirty.get_clip(): return Rect

        """
        return self._clip

    def change_layer(self, sprite, new_layer):
        """change the layer of the sprite

        LayeredUpdates.change_layer(sprite, new_layer): return None

        The sprite must have been added to the renderer already. This is not
        checked.

        """
        LayeredUpdates.change_layer(self, sprite, new_layer)
        if sprite.dirty == 0:
            sprite.dirty = 1

    def set_timing_treshold(self, time_ms):
        """set the threshold in milliseconds

        set_timing_treshold(time_ms): return None

        Defaults to 1000.0 / 80.0. This means that the screen will be painted
        using the flip method rather than the update method if the update
        method is taking so long to update the screen that the frame rate falls
        below 80 frames per second.

        Raises TypeError if time_ms is not int or float.

        """
        warn(
            "This function will be removed, use set_timing_threshold function instead",
            DeprecationWarning,
        )
        self.set_timing_threshold(time_ms)

    def set_timing_threshold(self, time_ms):
        """set the threshold in milliseconds

        set_timing_threshold(time_ms): return None

        Defaults to 1000.0 / 80.0. This means that the screen will be painted
        using the flip method rather than the update method if the update
        method is taking so long to update the screen that the frame rate falls
        below 80 frames per second.

        Raises TypeError if time_ms is not int or float.

        """
        if isinstance(time_ms, (int, float)):
            self._time_threshold = time_ms
        else:
            raise TypeError(
                f"Expected numeric value, got {time_ms.__class__.__name__} instead"
            )


class GroupSingle(AbstractGroup):
    """A group container that holds a single most recent item.

    This class works just like a regular group, but it only keeps a single
    sprite in the group. Whatever sprite has been added to the group last will
    be the only sprite in the group.

    You can access its one sprite as the .sprite attribute.  Assigning to this
    attribute will properly remove the old sprite and then add the new one.

    """

    def __init__(self, sprite=None):
        AbstractGroup.__init__(self)
        self.__sprite = None
        if sprite is not None:
            self.add(sprite)

    def copy(self):
        return GroupSingle(self.__sprite)

    def sprites(self):
        if self.__sprite is not None:
            return [self.__sprite]
        return []

    def add_internal(self, sprite, layer=None):
        if self.__sprite is not None:
            self.__sprite.remove_internal(self)
            self.remove_internal(self.__sprite)
        self.__sprite = sprite

    def __bool__(self):
        return self.__sprite is not None

    def _get_sprite(self):
        return self.__sprite

    def _set_sprite(self, sprite):
        self.add_internal(sprite)
        sprite.add_internal(self)
        return sprite

    @property
    def sprite(self):
        """
        Property for the single sprite contained in this group

        :return: The sprite.
        """
        return self._get_sprite()

    @sprite.setter
    def sprite(self, sprite_to_set):
        self._set_sprite(sprite_to_set)

    def remove_internal(self, sprite):
        if sprite is self.__sprite:
            self.__sprite = None
        if sprite in self.spritedict:
            AbstractGroup.remove_internal(self, sprite)

    def has_internal(self, sprite):
        return self.__sprite is sprite

    # Optimizations...
    def __contains__(self, sprite):
        return self.__sprite is sprite


# Some different collision detection functions that could be used.
def collide_rect(left, right):
    """collision detection between two sprites, using rects.

    pygame.sprite.collide_rect(left, right): return bool

    Tests for collision between two sprites. Uses the pygame.Rect colliderect
    function to calculate the collision. It is intended to be passed as a
    collided callback function to the *collide functions. Sprites must have
    "rect" attributes.

    New in pygame 1.8.0

    """
    return left.rect.colliderect(right.rect)


class collide_rect_ratio:  # noqa pylint: disable=invalid-name; this is a function-like class
    """A callable class that checks for collisions using scaled rects

    The class checks for collisions between two sprites using a scaled version
    of the sprites' rects. Is created with a ratio; the instance is then
    intended to be passed as a collided callback function to the *collide
    functions.

    New in pygame 1.8.1

    """

    def __init__(self, ratio):
        """create a new collide_rect_ratio callable

        Ratio is expected to be a floating point value used to scale
        the underlying sprite rect before checking for collisions.

        """
        self.ratio = ratio

    def __repr__(self):
        """
        Turn the class into a string.
        """
        # pylint: disable=consider-using-f-string
        return "<{klass} @{id:x} {attrs}>".format(
            klass=self.__class__.__name__,
            id=id(self) & 0xFFFFFF,
            attrs=" ".join(f"{k}={v!r}" for k, v in self.__dict__.items()),
        )

    def __call__(self, left, right):
        """detect collision between two sprites using scaled rects

        pygame.sprite.collide_rect_ratio(ratio)(left, right): return bool

        Tests for collision between two sprites. Uses the pygame.Rect
        colliderect function to calculate the collision after scaling the rects
        by the stored ratio. Sprites must have "rect" attributes.

        """

        ratio = self.ratio

        leftrect = left.rect
        width = leftrect.width
        height = leftrect.height
        leftrect = leftrect.inflate(width * ratio - width, height * ratio - height)

        rightrect = right.rect
        width = rightrect.width
        height = rightrect.height
        rightrect = rightrect.inflate(width * ratio - width, height * ratio - height)

        return leftrect.colliderect(rightrect)


def collide_circle(left, right):
    """detect collision between two sprites using circles

    pygame.sprite.collide_circle(left, right): return bool

    Tests for collision between two sprites by testing whether two circles
    centered on the sprites overlap. If the sprites have a "radius" attribute,
    then that radius is used to create the circle; otherwise, a circle is
    created that is big enough to completely enclose the sprite's rect as
    given by the "rect" attribute. This function is intended to be passed as
    a collided callback function to the *collide functions. Sprites must have a
    "rect" and an optional "radius" attribute.

    New in pygame 1.8.0

    """

    xdistance = left.rect.centerx - right.rect.centerx
    ydistance = left.rect.centery - right.rect.centery
    distancesquared = xdistance**2 + ydistance**2

    try:
        leftradius = left.radius
    except AttributeError:
        leftrect = left.rect
        # approximating the radius of a square by using half of the diagonal,
        # might give false positives (especially if its a long small rect)
        leftradius = 0.5 * ((leftrect.width**2 + leftrect.height**2) ** 0.5)
        # store the radius on the sprite for next time
        left.radius = leftradius

    try:
        rightradius = right.radius
    except AttributeError:
        rightrect = right.rect
        # approximating the radius of a square by using half of the diagonal
        # might give false positives (especially if its a long small rect)
        rightradius = 0.5 * ((rightrect.width**2 + rightrect.height**2) ** 0.5)
        # store the radius on the sprite for next time
        right.radius = rightradius
    return distancesquared <= (leftradius + rightradius) ** 2


class collide_circle_ratio:  # noqa pylint: disable=invalid-name; this is a function-like class
    """detect collision between two sprites using scaled circles

    This callable class checks for collisions between two sprites using a
    scaled version of a sprite's radius. It is created with a ratio as the
    argument to the constructor. The instance is then intended to be passed as
    a collided callback function to the *collide functions.

    New in pygame 1.8.1

    """

    def __init__(self, ratio):
        """creates a new collide_circle_ratio callable instance

        The given ratio is expected to be a floating point value used to scale
        the underlying sprite radius before checking for collisions.

        When the ratio is ratio=1.0, then it behaves exactly like the
        collide_circle method.

        """
        self.ratio = ratio

    def __repr__(self):
        """
        Turn the class into a string.
        """
        # pylint: disable=consider-using-f-string
        return "<{klass} @{id:x} {attrs}>".format(
            klass=self.__class__.__name__,
            id=id(self) & 0xFFFFFF,
            attrs=" ".join(f"{k}={v!r}" for k, v in self.__dict__.items()),
        )

    def __call__(self, left, right):
        """detect collision between two sprites using scaled circles

        pygame.sprite.collide_circle_radio(ratio)(left, right): return bool

        Tests for collision between two sprites by testing whether two circles
        centered on the sprites overlap after scaling the circle's radius by
        the stored ratio. If the sprites have a "radius" attribute, that is
        used to create the circle; otherwise, a circle is created that is big
        enough to completely enclose the sprite's rect as given by the "rect"
        attribute. Intended to be passed as a collided callback function to the
        *collide functions. Sprites must have a "rect" and an optional "radius"
        attribute.

        """

        ratio = self.ratio
        xdistance = left.rect.centerx - right.rect.centerx
        ydistance = left.rect.centery - right.rect.centery
        distancesquared = xdistance**2 + ydistance**2

        try:
            leftradius = left.radius
        except AttributeError:
            leftrect = left.rect
            leftradius = 0.5 * ((leftrect.width**2 + leftrect.height**2) ** 0.5)
            # store the radius on the sprite for next time
            left.radius = leftradius
        leftradius *= ratio

        try:
            rightradius = right.radius
        except AttributeError:
            rightrect = right.rect
            rightradius = 0.5 * ((rightrect.width**2 + rightrect.height**2) ** 0.5)
            # store the radius on the sprite for next time
            right.radius = rightradius
        rightradius *= ratio

        return distancesquared <= (leftradius + rightradius) ** 2


def collide_mask(left, right):
    """collision detection between two sprites, using masks.

    pygame.sprite.collide_mask(SpriteLeft, SpriteRight): bool

    Tests for collision between two sprites by testing if their bitmasks
    overlap. If the sprites have a "mask" attribute, that is used as the mask;
    otherwise, a mask is created from the sprite image. Intended to be passed
    as a collided callback function to the *collide functions. Sprites must
    have a "rect" and an optional "mask" attribute.

    New in pygame 1.8.0

    """
    xoffset = right.rect[0] - left.rect[0]
    yoffset = right.rect[1] - left.rect[1]
    try:
        leftmask = left.mask
    except AttributeError:
        leftmask = from_surface(left.image)
    try:
        rightmask = right.mask
    except AttributeError:
        rightmask = from_surface(right.image)
    return leftmask.overlap(rightmask, (xoffset, yoffset))


def spritecollide(sprite, group, dokill, collided=None):
    """find Sprites in a Group that intersect another Sprite

    pygame.sprite.spritecollide(sprite, group, dokill, collided=None):
        return Sprite_list

    Return a list containing all Sprites in a Group that intersect with another
    Sprite. Intersection is determined by comparing the Sprite.rect attribute
    of each Sprite.

    The dokill argument is a bool. If set to True, all Sprites that collide
    will be removed from the Group.

    The collided argument is a callback function used to calculate if two
    sprites are colliding. it should take two sprites as values, and return a
    bool value indicating if they are colliding. If collided is not passed, all
    sprites must have a "rect" value, which is a rectangle of the sprite area,
    which will be used to calculate the collision.

    """
    # pull the default collision function in as a local variable outside
    # the loop as this makes the loop run faster
    default_sprite_collide_func = sprite.rect.colliderect

    if dokill:
        crashed = []
        append = crashed.append

        for group_sprite in group.sprites():
            if collided is not None:
                if collided(sprite, group_sprite):
                    group_sprite.kill()
                    append(group_sprite)
            else:
                if default_sprite_collide_func(group_sprite.rect):
                    group_sprite.kill()
                    append(group_sprite)

        return crashed

    if collided is not None:
        return [
            group_sprite for group_sprite in group if collided(sprite, group_sprite)
        ]

    return [
        group_sprite
        for group_sprite in group
        if default_sprite_collide_func(group_sprite.rect)
    ]


def groupcollide(groupa, groupb, dokilla, dokillb, collided=None):
    """detect collision between a group and another group

    pygame.sprite.groupcollide(groupa, groupb, dokilla, dokillb):
        return dict

    Given two groups, this will find the intersections between all sprites in
    each group. It returns a dictionary of all sprites in the first group that
    collide. The value for each item in the dictionary is a list of the sprites
    in the second group it collides with. The two dokill arguments control if
    the sprites from either group will be automatically removed from all
    groups. Collided is a callback function used to calculate if two sprites
    are colliding. it should take two sprites as values, and return a bool
    value indicating if they are colliding. If collided is not passed, all
    sprites must have a "rect" value, which is a rectangle of the sprite area
    that will be used to calculate the collision.

    """
    crashed = {}
    # pull the collision function in as a local variable outside
    # the loop as this makes the loop run faster
    sprite_collide_func = spritecollide
    if dokilla:
        for group_a_sprite in groupa.sprites():
            collision = sprite_collide_func(group_a_sprite, groupb, dokillb, collided)
            if collision:
                crashed[group_a_sprite] = collision
                group_a_sprite.kill()
    else:
        for group_a_sprite in groupa:
            collision = sprite_collide_func(group_a_sprite, groupb, dokillb, collided)
            if collision:
                crashed[group_a_sprite] = collision
    return crashed


def spritecollideany(sprite, group, collided=None):
    """finds any sprites in a group that collide with the given sprite

    pygame.sprite.spritecollideany(sprite, group): return sprite

    Given a sprite and a group of sprites, this will return return any single
    sprite that collides with with the given sprite. If there are no
    collisions, then this returns None.

    If you don't need all the features of the spritecollide function, this
    function will be a bit quicker.

    Collided is a callback function used to calculate if two sprites are
    colliding. It should take two sprites as values and return a bool value
    indicating if they are colliding. If collided is not passed, then all
    sprites must have a "rect" value, which is a rectangle of the sprite area,
    which will be used to calculate the collision.


    """
    # pull the default collision function in as a local variable outside
    # the loop as this makes the loop run faster
    default_sprite_collide_func = sprite.rect.colliderect

    if collided is not None:
        for group_sprite in group:
            if collided(sprite, group_sprite):
                return group_sprite
    else:
        # Special case old behaviour for speed.
        for group_sprite in group:
            if default_sprite_collide_func(group_sprite.rect):
                return group_sprite
    return None
