# Copyright 2009-2022 Joshua Bronson. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


#                             * Code review nav *
#                        (see comments in __init__.py)
#==============================================================================
#← Prev: _orderedbase.py  Current: _frozenordered.py  Next: _orderedbidict.py →
#==============================================================================

"""Provide :class:`FrozenOrderedBidict`, an immutable, hashable, ordered bidict."""

from __future__ import annotations
import typing as t

from ._frozenbidict import frozenbidict
from ._orderedbase import OrderedBidictBase
from ._typing import KT, VT


class FrozenOrderedBidict(OrderedBidictBase[KT, VT]):
    """Hashable, immutable, ordered bidict type.

    Like a hashable :class:`bidict.OrderedBidict`
    without the mutating APIs, or like a
    reversible :class:`bidict.frozenbidict` even on Python < 3.8.
    (All bidicts are order-preserving when never mutated, so frozenbidict is
    already order-preserving, but only on Python 3.8+, where dicts are
    reversible, are all bidicts (including frozenbidict) also reversible.)

    If you are using Python 3.8+, frozenbidict gives you everything that
    FrozenOrderedBidict gives you, but with less space overhead.
    On the other hand, using FrozenOrderedBidict when you are depending on
    the ordering of the items can make the ordering dependence more explicit.
    """

    __hash__: t.Callable[[t.Any], int] = frozenbidict.__hash__

    if t.TYPE_CHECKING:
        @property
        def inverse(self) -> FrozenOrderedBidict[VT, KT]: ...


#                             * Code review nav *
#==============================================================================
#← Prev: _orderedbase.py  Current: _frozenordered.py  Next: _orderedbidict.py →
#==============================================================================
