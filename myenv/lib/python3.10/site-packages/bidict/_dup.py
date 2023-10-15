# Copyright 2009-2022 Joshua Bronson. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


"""Provide :class:`OnDup` and related functionality."""


from __future__ import annotations
from enum import Enum
import typing as t


class OD(Enum):
    """An action to take to prevent duplication from occurring."""

    #: Raise a :class:`~bidict.DuplicationError`.
    RAISE = 'RAISE'
    #: Overwrite existing items with new items.
    DROP_OLD = 'DROP_OLD'
    #: Keep existing items and drop new items.
    DROP_NEW = 'DROP_NEW'

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}.{self.name}'


RAISE: t.Final[OD] = OD.RAISE
DROP_OLD: t.Final[OD] = OD.DROP_OLD
DROP_NEW: t.Final[OD] = OD.DROP_NEW


class OnDup(t.NamedTuple('_OnDup', [('key', OD), ('val', OD), ('kv', OD)])):
    r"""A 3-tuple of :class:`OD`\s specifying how to handle the 3 kinds of duplication.

    *See also* :ref:`basic-usage:Values Must Be Unique`
    (https://bidict.rtfd.io/basic-usage.html#values-must-be-unique)

    If *kv* is not specified, *val* will be used for *kv*.
    """

    __slots__ = ()

    def __new__(cls, key: OD = DROP_OLD, val: OD = RAISE, kv: OD | None = None) -> OnDup:
        """Override to provide user-friendly default values."""
        return super().__new__(cls, key, val, kv or val)


#: Default :class:`OnDup` used for the
#: :meth:`~bidict.bidict.__init__`,
#: :meth:`~bidict.bidict.__setitem__`, and
#: :meth:`~bidict.bidict.update` methods.
ON_DUP_DEFAULT: t.Final[OnDup] = OnDup(key=DROP_OLD, val=RAISE, kv=RAISE)
#: An :class:`OnDup` whose members are all :obj:`RAISE`.
ON_DUP_RAISE: t.Final[OnDup] = OnDup(key=RAISE, val=RAISE, kv=RAISE)
#: An :class:`OnDup` whose members are all :obj:`DROP_OLD`.
ON_DUP_DROP_OLD: t.Final[OnDup] = OnDup(key=DROP_OLD, val=DROP_OLD, kv=DROP_OLD)
