# Copyright 2009-2022 Joshua Bronson. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


"""Functions for iterating over items in a mapping."""

from __future__ import annotations
from operator import itemgetter
import typing as t

from ._typing import KT, VT, ItemsIter, MapOrItems


def iteritems_mapping_or_iterable(arg: MapOrItems[KT, VT]) -> ItemsIter[KT, VT]:
    """Yield the items in *arg* based on whether it's a mapping."""
    yield from arg.items() if isinstance(arg, t.Mapping) else arg


def iteritems(__arg: MapOrItems[KT, VT], **kw: VT) -> ItemsIter[KT, VT]:
    """Yield the items from *arg* and then any from *kw* in the order given."""
    yield from iteritems_mapping_or_iterable(__arg)
    yield from kw.items()  # type: ignore [misc]


swap = itemgetter(1, 0)


def inverted(arg: MapOrItems[KT, VT]) -> ItemsIter[VT, KT]:
    """Yield the inverse items of the provided object.

    If *arg* has a :func:`callable` ``__inverted__`` attribute,
    return the result of calling it.

    Otherwise, return an iterator over the items in `arg`,
    inverting each item on the fly.

    *See also* :attr:`bidict.BidirectionalMapping.__inverted__`
    """
    invattr = getattr(arg, '__inverted__', None)
    if callable(invattr):
        inv: ItemsIter[VT, KT] = invattr()
        return inv
    return map(swap, iteritems_mapping_or_iterable(arg))
