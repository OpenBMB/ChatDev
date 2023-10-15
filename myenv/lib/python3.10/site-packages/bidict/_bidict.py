# Copyright 2009-2022 Joshua Bronson. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


#                             * Code review nav *
#                        (see comments in __init__.py)
#==============================================================================
# ← Prev: _frozenbidict.py     Current: _bidict.py     Next: _orderedbase.py →
#==============================================================================


"""Provide :class:`MutableBidict`."""

from __future__ import annotations
import typing as t

from ._abc import MutableBidirectionalMapping
from ._base import BidictBase, get_arg
from ._dup import OnDup, ON_DUP_RAISE, ON_DUP_DROP_OLD
from ._typing import KT, VT, DT, ODT, MISSING, Items, MapOrItems


class MutableBidict(BidictBase[KT, VT], MutableBidirectionalMapping[KT, VT]):
    """Base class for mutable bidirectional mappings."""

    if t.TYPE_CHECKING:
        @property
        def inverse(self) -> MutableBidict[VT, KT]: ...

    def _pop(self, key: KT) -> VT:
        val = self._fwdm.pop(key)
        del self._invm[val]
        return val

    def __delitem__(self, key: KT) -> None:
        """*x.__delitem__(y)　⟺　del x[y]*"""
        self._pop(key)

    def __setitem__(self, key: KT, val: VT) -> None:
        """Set the value for *key* to *val*.

        If *key* is already associated with *val*, this is a no-op.

        If *key* is already associated with a different value,
        the old value will be replaced with *val*,
        as with dict's :meth:`__setitem__`.

        If *val* is already associated with a different key,
        an exception is raised
        to protect against accidental removal of the key
        that's currently associated with *val*.

        Use :meth:`put` instead if you want to specify different behavior in
        the case that the provided key or value duplicates an existing one.
        Or use :meth:`forceput` to unconditionally associate *key* with *val*,
        replacing any existing items as necessary to preserve uniqueness.

        :raises bidict.ValueDuplicationError: if *val* duplicates that of an
            existing item.

        :raises bidict.KeyAndValueDuplicationError: if *key* duplicates the key of an
            existing item and *val* duplicates the value of a different
            existing item.
        """
        self.put(key, val, on_dup=self.on_dup)

    def put(self, key: KT, val: VT, on_dup: OnDup = ON_DUP_RAISE) -> None:
        """Associate *key* with *val*, honoring the :class:`OnDup` given in *on_dup*.

        For example, if *on_dup* is :attr:`~bidict.ON_DUP_RAISE`,
        then *key* will be associated with *val* if and only if
        *key* is not already associated with an existing value and
        *val* is not already associated with an existing key,
        otherwise an exception will be raised.

        If *key* is already associated with *val*, this is a no-op.

        :raises bidict.KeyDuplicationError: if attempting to insert an item
            whose key only duplicates an existing item's, and *on_dup.key* is
            :attr:`~bidict.RAISE`.

        :raises bidict.ValueDuplicationError: if attempting to insert an item
            whose value only duplicates an existing item's, and *on_dup.val* is
            :attr:`~bidict.RAISE`.

        :raises bidict.KeyAndValueDuplicationError: if attempting to insert an
            item whose key duplicates one existing item's, and whose value
            duplicates another existing item's, and *on_dup.kv* is
            :attr:`~bidict.RAISE`.
        """
        self._update([(key, val)], on_dup=on_dup)

    def forceput(self, key: KT, val: VT) -> None:
        """Associate *key* with *val* unconditionally.

        Replace any existing mappings containing key *key* or value *val*
        as necessary to preserve uniqueness.
        """
        self.put(key, val, on_dup=ON_DUP_DROP_OLD)

    def clear(self) -> None:
        """Remove all items."""
        self._fwdm.clear()
        self._invm.clear()

    @t.overload
    def pop(self, __key: KT) -> VT: ...
    @t.overload
    def pop(self, __key: KT, __default: DT = ...) -> VT | DT: ...

    def pop(self, key: KT, default: ODT[DT] = MISSING) -> VT | DT:
        """*x.pop(k[, d]) → v*

        Remove specified key and return the corresponding value.

        :raises KeyError: if *key* is not found and no *default* is provided.
        """
        try:
            return self._pop(key)
        except KeyError:
            if default is MISSING:
                raise
            return default

    def popitem(self) -> tuple[KT, VT]:
        """*x.popitem() → (k, v)*

        Remove and return some item as a (key, value) pair.

        :raises KeyError: if *x* is empty.
        """
        key, val = self._fwdm.popitem()
        del self._invm[val]
        return key, val

    @t.overload  # type: ignore [override]  # https://github.com/jab/bidict/pull/242#discussion_r825464731
    def update(self, __m: t.Mapping[KT, VT], **kw: VT) -> None: ...
    @t.overload
    def update(self, __i: Items[KT, VT], **kw: VT) -> None: ...
    @t.overload
    def update(self, **kw: VT) -> None: ...

    def update(self, *args: MapOrItems[KT, VT], **kw: VT) -> None:
        """Like calling :meth:`putall` with *self.on_dup* passed for *on_dup*."""
        if args or kw:
            self._update(get_arg(*args), kw)

    @t.overload
    def forceupdate(self, __m: t.Mapping[KT, VT], **kw: VT) -> None: ...
    @t.overload
    def forceupdate(self, __i: Items[KT, VT], **kw: VT) -> None: ...
    @t.overload
    def forceupdate(self, **kw: VT) -> None: ...

    def forceupdate(self, *args: MapOrItems[KT, VT], **kw: VT) -> None:
        """Like a bulk :meth:`forceput`."""
        if args or kw:
            self._update(get_arg(*args), kw, on_dup=ON_DUP_DROP_OLD)

    def __ior__(self, other: t.Mapping[KT, VT]) -> MutableBidict[KT, VT]:
        """Return self|=other."""
        self.update(other)
        return self

    @t.overload
    def putall(self, items: t.Mapping[KT, VT], on_dup: OnDup) -> None: ...
    @t.overload
    def putall(self, items: Items[KT, VT], on_dup: OnDup = ...) -> None: ...

    def putall(self, items: MapOrItems[KT, VT], on_dup: OnDup = ON_DUP_RAISE) -> None:
        """Like a bulk :meth:`put`.

        If one of the given items causes an exception to be raised,
        none of the items is inserted.
        """
        if items:
            self._update(items, on_dup=on_dup)


class bidict(MutableBidict[KT, VT]):
    """The main bidirectional mapping type.

    See :ref:`intro:Introduction` and :ref:`basic-usage:Basic Usage`
    to get started (also available at https://bidict.rtfd.io).
    """

    if t.TYPE_CHECKING:
        @property
        def inverse(self) -> bidict[VT, KT]: ...


#                             * Code review nav *
#==============================================================================
# ← Prev: _frozenbidict.py     Current: _bidict.py     Next: _orderedbase.py →
#==============================================================================
