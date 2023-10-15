# Copyright 2009-2022 Joshua Bronson. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


#                             * Code review nav *
#                        (see comments in __init__.py)
#==============================================================================
# ← Prev: _abc.py              Current: _base.py      Next: _frozenbidict.py →
#==============================================================================


"""Provide :class:`BidictBase`."""

from __future__ import annotations
from functools import partial
from itertools import starmap
from operator import eq
from types import MappingProxyType
import typing as t
import weakref

from ._abc import BidirectionalMapping
from ._dup import ON_DUP_DEFAULT, RAISE, DROP_OLD, DROP_NEW, OnDup
from ._exc import DuplicationError, KeyDuplicationError, ValueDuplicationError, KeyAndValueDuplicationError
from ._iter import iteritems, inverted
from ._typing import KT, VT, MISSING, OKT, OVT, Items, MapOrItems, TypeAlias


OldKV: TypeAlias = 'tuple[OKT[KT], OVT[VT]]'
DedupResult: TypeAlias = 'OldKV[KT, VT] | None'
Write: TypeAlias = 'list[t.Callable[[], None]]'
Unwrite: TypeAlias = Write
PreparedWrite: TypeAlias = 'tuple[Write, Unwrite]'
BT = t.TypeVar('BT', bound='BidictBase[t.Any, t.Any]')


class BidictKeysView(t.KeysView[KT], t.ValuesView[KT]):
    """Since the keys of a bidict are the values of its inverse (and vice versa),
    the :class:`~collections.abc.ValuesView` result of calling *bi.values()*
    is also a :class:`~collections.abc.KeysView` of *bi.inverse*.
    """


def get_arg(*args: MapOrItems[KT, VT]) -> MapOrItems[KT, VT]:
    """Ensure there's only a single arg in *args*, then return it."""
    if len(args) > 1:
        raise TypeError(f'Expected at most 1 positional argument, got {len(args)}')
    return args[0] if args else ()


class BidictBase(BidirectionalMapping[KT, VT]):
    """Base class implementing :class:`BidirectionalMapping`."""

    #: The default :class:`~bidict.OnDup`
    #: that governs behavior when a provided item
    #: duplicates the key or value of other item(s).
    #:
    #: *See also*
    #: :ref:`basic-usage:Values Must Be Unique` (https://bidict.rtfd.io/basic-usage.html#values-must-be-unique),
    #: :doc:`extending` (https://bidict.rtfd.io/extending.html)
    on_dup = ON_DUP_DEFAULT

    _fwdm: t.MutableMapping[KT, VT]  #: the backing forward mapping (*key* → *val*)
    _invm: t.MutableMapping[VT, KT]  #: the backing inverse mapping (*val* → *key*)

    # Use Any rather than KT/VT in the following to avoid "ClassVar cannot contain type variables" errors:
    _fwdm_cls: t.ClassVar[t.Type[t.MutableMapping[t.Any, t.Any]]] = dict  #: class of the backing forward mapping
    _invm_cls: t.ClassVar[t.Type[t.MutableMapping[t.Any, t.Any]]] = dict  #: class of the backing inverse mapping

    #: The class of the inverse bidict instance.
    _inv_cls: t.ClassVar[t.Type[BidictBase[t.Any, t.Any]]]

    #: Used by :meth:`__repr__` for the contained items.
    _repr_delegate: t.ClassVar[t.Any] = dict

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        cls._init_class()

    @classmethod
    def _init_class(cls) -> None:
        cls._ensure_inv_cls()
        cls._set_reversed()

    __reversed__: t.Any

    @classmethod
    def _set_reversed(cls) -> None:
        """Set __reversed__ for subclasses that do not set it explicitly
        according to whether backing mappings are reversible.
        """
        if cls is not BidictBase:
            resolved = cls.__reversed__
            overridden = resolved is not BidictBase.__reversed__
            if overridden:  # E.g. OrderedBidictBase, OrderedBidict, FrozenOrderedBidict
                return
        # The following will be False for MutableBidict, bidict, and frozenbidict on Python < 3.8,
        # and True for them on 3.8+ (where dicts are reversible). Will also be True for custom
        # subclasses like SortedBidict (see https://bidict.rtfd.io/extending.html#sortedbidict-recipes).
        backing_reversible = all(issubclass(i, t.Reversible) for i in (cls._fwdm_cls, cls._invm_cls))
        cls.__reversed__ = _fwdm_reversed if backing_reversible else None

    @classmethod
    def _ensure_inv_cls(cls) -> None:
        """Ensure :attr:`_inv_cls` is set, computing it dynamically if necessary.

        See: :ref:`extending:Dynamic Inverse Class Generation`
        (https://bidict.rtfd.io/extending.html#dynamic-inverse-class-generation)

        Most subclasses will be their own inverse classes, but some
        (e.g. those created via namedbidict) will have distinct inverse classes.
        """
        if cls.__dict__.get('_inv_cls'):
            return  # Already set, nothing to do.
        cls._inv_cls = cls._make_inv_cls()

    @classmethod
    def _make_inv_cls(cls: t.Type[BT], _miss: t.Any = object()) -> t.Type[BT]:
        diff = cls._inv_cls_dict_diff()
        cls_is_own_inv = all(getattr(cls, k, _miss) == v for (k, v) in diff.items())
        if cls_is_own_inv:
            return cls
        # Suppress auto-calculation of _inv_cls's _inv_cls since we know it already.
        # Works with the guard in BidictBase._ensure_inv_cls() to prevent infinite recursion.
        diff['_inv_cls'] = cls
        inv_cls = type(f'{cls.__name__}Inv', (cls, GeneratedBidictInverse), diff)
        inv_cls.__module__ = cls.__module__
        return t.cast(t.Type[BT], inv_cls)

    @classmethod
    def _inv_cls_dict_diff(cls) -> dict[str, t.Any]:
        return {
            '_fwdm_cls': cls._invm_cls,
            '_invm_cls': cls._fwdm_cls,
        }

    @t.overload
    def __init__(self, **kw: VT) -> None: ...
    @t.overload
    def __init__(self, __m: t.Mapping[KT, VT], **kw: VT) -> None: ...
    @t.overload
    def __init__(self, __i: Items[KT, VT], **kw: VT) -> None: ...

    def __init__(self, *args: MapOrItems[KT, VT], **kw: VT) -> None:
        """Make a new bidirectional mapping.
        The signature behaves like that of :class:`dict`.
        Items passed in are added in the order they are passed,
        respecting the :attr:`on_dup` class attribute in the process.
        """
        self._fwdm = self._fwdm_cls()
        self._invm = self._invm_cls()
        if args or kw:
            self._update(get_arg(*args), kw, rbof=False)

    # If Python ever adds support for higher-kinded types, `inverse` could use them, e.g.
    #     def inverse(self: BT[KT, VT]) -> BT[VT, KT]:
    # Ref: https://github.com/python/typing/issues/548#issuecomment-621571821
    @property
    def inverse(self) -> BidictBase[VT, KT]:
        """The inverse of this bidirectional mapping instance."""
        # When `bi.inverse` is called for the first time, this method
        # computes the inverse instance, stores it for subsequent use, and then
        # returns it. It also stores a reference on `bi.inverse` back to `bi`,
        # but uses a weakref to avoid creating a reference cycle. Strong references
        # to inverse instances are stored in ._inv, and weak references are stored
        # in ._invweak.

        # First check if a strong reference is already stored.
        inv: BidictBase[VT, KT] | None = getattr(self, '_inv', None)
        if inv is not None:
            return inv
        # Next check if a weak reference is already stored.
        invweak = getattr(self, '_invweak', None)
        if invweak is not None:
            inv = invweak()  # Try to resolve a strong reference and return it.
            if inv is not None:
                return inv
        # No luck. Compute the inverse reference and store it for subsequent use.
        inv = self._make_inverse()
        self._inv: BidictBase[VT, KT] | None = inv
        self._invweak: weakref.ReferenceType[BidictBase[VT, KT]] | None = None
        # Also store a weak reference back to `instance` on its inverse instance, so that
        # the second `.inverse` access in `bi.inverse.inverse` hits the cached weakref.
        inv._inv = None
        inv._invweak = weakref.ref(self)
        # In e.g. `bidict().inverse.inverse`, this design ensures that a strong reference
        # back to the original instance is retained before its refcount drops to zero,
        # avoiding an unintended potential deallocation.
        return inv

    def _make_inverse(self) -> BidictBase[VT, KT]:
        inv: BidictBase[VT, KT] = self._inv_cls()
        inv._fwdm = self._invm
        inv._invm = self._fwdm
        return inv

    @property
    def inv(self) -> BidictBase[VT, KT]:
        """Alias for :attr:`inverse`."""
        return self.inverse

    def __repr__(self) -> str:
        """See :func:`repr`."""
        clsname = self.__class__.__name__
        items = self._repr_delegate(self.items()) if self else ''
        return f'{clsname}({items})'

    def values(self) -> BidictKeysView[VT]:
        """A set-like object providing a view on the contained values.

        Since the values of a bidict are equivalent to the keys of its inverse,
        this method returns a set-like object for this bidict's values
        rather than just a collections.abc.ValuesView.
        This object supports set operations like union and difference,
        and constant- rather than linear-time containment checks,
        and is no more expensive to provide than the less capable
        collections.abc.ValuesView would be.

        See :meth:`keys` for more information.
        """
        return t.cast(BidictKeysView[VT], self.inverse.keys())

    def keys(self) -> t.KeysView[KT]:
        """A set-like object providing a view on the contained keys.

        When *b._fwdm* is a :class:`dict`, *b.keys()* returns a
        *dict_keys* object that behaves exactly the same as
        *collections.abc.KeysView(b)*, except for

          - offering better performance

          - being reversible on Python 3.8+

          - having a .mapping attribute in Python 3.10+
            that exposes a mappingproxy to *b._fwdm*.
        """
        fwdm = self._fwdm
        kv = fwdm.keys() if isinstance(fwdm, dict) else BidictKeysView(self)
        return kv

    def items(self) -> t.ItemsView[KT, VT]:
        """A set-like object providing a view on the contained items.

        When *b._fwdm* is a :class:`dict`, *b.items()* returns a
        *dict_items* object that behaves exactly the same as
        *collections.abc.ItemsView(b)*, except for:

          - offering better performance

          - being reversible on Python 3.8+

          - having a .mapping attribute in Python 3.10+
            that exposes a mappingproxy to *b._fwdm*.
        """
        return self._fwdm.items() if isinstance(self._fwdm, dict) else super().items()

    # The inherited collections.abc.Mapping.__contains__() method is implemented by doing a `try`
    # `except KeyError` around `self[key]`. The following implementation is much faster,
    # especially in the missing case.
    def __contains__(self, key: t.Any) -> bool:
        """True if the mapping contains the specified key, else False."""
        return key in self._fwdm

    # The inherited collections.abc.Mapping.__eq__() method is implemented in terms of an inefficient
    # `dict(self.items()) == dict(other.items())` comparison, so override it with a
    # more efficient implementation.
    def __eq__(self, other: object) -> bool:
        """*x.__eq__(other)　⟺　x == other*

        Equivalent to *dict(x.items()) == dict(other.items())*
        but more efficient.

        Note that :meth:`bidict's __eq__() <bidict.bidict.__eq__>` implementation
        is inherited by subclasses,
        in particular by the ordered bidict subclasses,
        so even with ordered bidicts,
        :ref:`== comparison is order-insensitive <eq-order-insensitive>`
        (https://bidict.rtfd.io/other-bidict-types.html#eq-is-order-insensitive).

        *See also* :meth:`equals_order_sensitive`
        """
        if isinstance(other, t.Mapping):
            return self._fwdm.items() == other.items()
        # Ref: https://docs.python.org/3/library/constants.html#NotImplemented
        return NotImplemented

    def equals_order_sensitive(self, other: object) -> bool:
        """Order-sensitive equality check.

        *See also* :ref:`eq-order-insensitive`
        (https://bidict.rtfd.io/other-bidict-types.html#eq-is-order-insensitive)
        """
        if not isinstance(other, t.Mapping) or len(self) != len(other):
            return False
        return all(starmap(eq, zip(self.items(), other.items())))

    def _dedup(self, key: KT, val: VT, on_dup: OnDup) -> DedupResult[KT, VT]:
        """Check *key* and *val* for any duplication in self.

        Handle any duplication as per the passed in *on_dup*.

        If (key, val) is already present, return None
        since writing (key, val) would be a no-op.

        If duplication is found and the corresponding :class:`~bidict.OnDupAction` is
        :attr:`~bidict.DROP_NEW`, return None.

        If duplication is found and the corresponding :class:`~bidict.OnDupAction` is
        :attr:`~bidict.RAISE`, raise the appropriate exception.

        If duplication is found and the corresponding :class:`~bidict.OnDupAction` is
        :attr:`~bidict.DROP_OLD`, or if no duplication is found,
        return *(oldkey, oldval)*.
        """
        fwdm, invm = self._fwdm, self._invm
        oldval: OVT[VT] = fwdm.get(key, MISSING)
        oldkey: OKT[KT] = invm.get(val, MISSING)
        isdupkey, isdupval = oldval is not MISSING, oldkey is not MISSING
        if isdupkey and isdupval:
            if key == oldkey:
                assert val == oldval
                # (key, val) duplicates an existing item -> no-op.
                return None
            # key and val each duplicate a different existing item.
            if on_dup.kv is RAISE:
                raise KeyAndValueDuplicationError(key, val)
            if on_dup.kv is DROP_NEW:
                return None
            assert on_dup.kv is DROP_OLD
            # Fall through to the return statement on the last line.
        elif isdupkey:
            if on_dup.key is RAISE:
                raise KeyDuplicationError(key)
            if on_dup.key is DROP_NEW:
                return None
            assert on_dup.key is DROP_OLD
            # Fall through to the return statement on the last line.
        elif isdupval:
            if on_dup.val is RAISE:
                raise ValueDuplicationError(val)
            if on_dup.val is DROP_NEW:
                return None
            assert on_dup.val is DROP_OLD
            # Fall through to the return statement on the last line.
        # else neither isdupkey nor isdupval.
        return oldkey, oldval

    def _prep_write(self, newkey: KT, newval: VT, oldkey: OKT[KT], oldval: OVT[VT], save_unwrite: bool) -> PreparedWrite:
        """Given (newkey, newval) to insert, return the list of operations necessary to perform the write.

        *oldkey* and *oldval* are as returned by :meth:`_dedup`.

        If *save_unwrite* is true, also return the list of inverse operations necessary to undo the write.
        This design allows :meth:`_update` to roll back a partially applied update that fails part-way through
        when necessary. This design also allows subclasses that require additional operations to complete
        a write to easily extend this implementation. For example, :class:`bidict.OrderedBidictBase` calls this
        inherited implementation, and then extends the list of ops returned with additional operations
        needed to keep its internal linked list nodes consistent with its items' order as changes are made.
        """
        fwdm, invm = self._fwdm, self._invm
        write: list[t.Callable[[], None]] = [
            partial(fwdm.__setitem__, newkey, newval),
            partial(invm.__setitem__, newval, newkey),
        ]
        unwrite: list[t.Callable[[], None]]
        if oldval is MISSING and oldkey is MISSING:  # no key or value duplication
            # {0: 1, 2: 3} + (4, 5) => {0: 1, 2: 3, 4: 5}
            unwrite = [
                partial(fwdm.__delitem__, newkey),
                partial(invm.__delitem__, newval),
            ] if save_unwrite else []
        elif oldval is not MISSING and oldkey is not MISSING:  # key and value duplication across two different items
            # {0: 1, 2: 3} + (0, 3) => {0: 3}
            write.extend((
                partial(fwdm.__delitem__, oldkey),
                partial(invm.__delitem__, oldval),
            ))
            unwrite = [
                partial(fwdm.__setitem__, newkey, oldval),
                partial(invm.__setitem__, oldval, newkey),
                partial(fwdm.__setitem__, oldkey, newval),
                partial(invm.__setitem__, newval, oldkey),
            ] if save_unwrite else []
        elif oldval is not MISSING:  # just key duplication
            # {0: 1, 2: 3} + (2, 4) => {0: 1, 2: 4}
            write.append(partial(invm.__delitem__, oldval))
            unwrite = [
                partial(fwdm.__setitem__, newkey, oldval),
                partial(invm.__setitem__, oldval, newkey),
                partial(invm.__delitem__, newval),
            ] if save_unwrite else []
        else:
            assert oldkey is not MISSING  # just value duplication
            # {0: 1, 2: 3} + (4, 3) => {0: 1, 4: 3}
            write.append(partial(fwdm.__delitem__, oldkey))
            unwrite = [
                partial(fwdm.__setitem__, oldkey, newval),
                partial(invm.__setitem__, newval, oldkey),
                partial(fwdm.__delitem__, newkey),
            ] if save_unwrite else []
        return write, unwrite

    def _update(
        self,
        arg: MapOrItems[KT, VT],
        kw: t.Mapping[str, VT] = MappingProxyType({}),
        *,
        rbof: bool | None = None,
        on_dup: OnDup | None = None,
    ) -> None:
        """Update, possibly rolling back on failure as per *rbof*."""
        # Must process input in a single pass, since arg may be a generator.
        if not arg and not kw:
            return
        if on_dup is None:
            on_dup = self.on_dup
        if rbof is None:
            rbof = RAISE in on_dup
        if not self and not kw:
            if isinstance(arg, BidictBase):  # can skip dup check
                self._init_from(arg)
                return
            # If arg is not a BidictBase, fall through to the general treatment below,
            # which includes duplication checking. (If arg is some BidirectionalMapping
            # that does not inherit from BidictBase, it's a foreign implementation, so we
            # perform duplication checking to err on the safe side.)

        # If we roll back on failure and we know that there are more updates to process than
        # already-contained items, our rollback strategy is to update a copy of self (without
        # rolling back on failure), and then to become the copy if all updates succeed.
        if rbof and isinstance(arg, t.Sized) and len(arg) + len(kw) > len(self):
            target = self.copy()
            target._update(arg, kw, rbof=False, on_dup=on_dup)
            self._init_from(target)
            return

        # There are more already-contained items than updates to process, or we don't know
        # how many updates there are to process. If we need to roll back on failure,
        # save a log of Unwrites as we update so we can undo changes if the update fails.
        unwrites: list[Unwrite] = []
        append_unwrite = unwrites.append
        prep_write = self._prep_write
        for (key, val) in iteritems(arg, **kw):
            try:
                dedup_result = self._dedup(key, val, on_dup)
            except DuplicationError:
                if rbof:
                    while unwrites:  # apply saved unwrites
                        unwrite = unwrites.pop()
                        for unwriteop in unwrite:
                            unwriteop()
                raise
            if dedup_result is None:  # no-op
                continue
            write, unwrite = prep_write(key, val, *dedup_result, save_unwrite=rbof)
            for writeop in write:  # apply the write
                writeop()
            if rbof and unwrite:  # save the unwrite for later application if needed
                append_unwrite(unwrite)

    def copy(self: BT) -> BT:
        """Make a (shallow) copy of this bidict."""
        # Could just `return self.__class__(self)` here, but the below is faster. The former
        # would copy this bidict's items into a new instance one at a time (checking for duplication
        # for each item), whereas the below copies from the backing mappings all at once, and foregoes
        # item-by-item duplication checking since the backing mappings have been checked already.
        return self._from_other(self.__class__, self)

    @staticmethod
    def _from_other(bt: t.Type[BT], other: MapOrItems[KT, VT], inv: bool = False) -> BT:
        """Fast, private constructor based on :meth:`_init_from`.

        If *inv* is true, return the inverse of the instance instead of the instance itself.
        (Useful for pickling with dynamically-generated inverse classes -- see :meth:`__reduce__`.)
        """
        inst = bt()
        inst._init_from(other)
        return t.cast(BT, inst.inverse) if inv else inst

    def _init_from(self, other: MapOrItems[KT, VT]) -> None:
        """Fast init from *other*, bypassing item-by-item duplication checking."""
        self._fwdm.clear()
        self._invm.clear()
        self._fwdm.update(other)
        # If other is a bidict, use its existing backing inverse mapping, otherwise
        # other could be a generator that's now exhausted, so invert self._fwdm on the fly.
        inv = other.inverse if isinstance(other, BidictBase) else inverted(self._fwdm)
        self._invm.update(inv)

    #: Used for the copy protocol.
    #: *See also* the :mod:`copy` module
    __copy__ = copy

    def __or__(self: BT, other: t.Mapping[KT, VT]) -> BT:
        """Return self|other."""
        if not isinstance(other, t.Mapping):
            return NotImplemented
        new = self.copy()
        new._update(other, rbof=False)
        return new

    def __ror__(self: BT, other: t.Mapping[KT, VT]) -> BT:
        """Return other|self."""
        if not isinstance(other, t.Mapping):
            return NotImplemented
        new = self.__class__(other)
        new._update(self, rbof=False)
        return new

    def __len__(self) -> int:
        """The number of contained items."""
        return len(self._fwdm)

    def __iter__(self) -> t.Iterator[KT]:
        """Iterator over the contained keys."""
        return iter(self._fwdm)

    def __getitem__(self, key: KT) -> VT:
        """*x.__getitem__(key) ⟺ x[key]*"""
        return self._fwdm[key]

    def __reduce__(self) -> tuple[t.Any, ...]:
        """Return state information for pickling."""
        # If this bidict's class is dynamically generated, pickle the inverse instead, whose
        # (presumably not dynamically generated) class the caller is more likely to have a reference to
        # somewhere in sys.modules that pickle can discover.
        should_invert = isinstance(self, GeneratedBidictInverse)
        cls, init_from = (self._inv_cls, self.inverse) if should_invert else (self.__class__, self)
        return self._from_other, (cls, dict(init_from), should_invert)  # type: ignore [call-overload]


# See BidictBase._set_reversed() above.
def _fwdm_reversed(self: BidictBase[KT, t.Any]) -> t.Iterator[KT]:
    """Iterator over the contained keys in reverse order."""
    assert isinstance(self._fwdm, t.Reversible)
    return reversed(self._fwdm)


BidictBase._init_class()


class GeneratedBidictInverse:
    """Base class for dynamically-generated inverse bidict classes."""


#                             * Code review nav *
#==============================================================================
# ← Prev: _abc.py              Current: _base.py      Next: _frozenbidict.py →
#==============================================================================
