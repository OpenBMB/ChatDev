# Copyright 2009-2022 Joshua Bronson. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


"""Provide typing-related objects."""

from __future__ import annotations
from enum import Enum
import typing as t

if t.TYPE_CHECKING:
    from typing_extensions import TypeAlias as TypeAlias
else:
    TypeAlias = 'TypeAlias'


KT = t.TypeVar('KT')
VT = t.TypeVar('VT')


Items: TypeAlias = 't.Iterable[tuple[KT, VT]]'
MapOrItems: TypeAlias = 't.Mapping[KT, VT] | Items[KT, VT]'
ItemsIter: TypeAlias = 't.Iterator[tuple[KT, VT]]'


class MissingT(Enum):
    """Sentinel used to represent none/missing when None itself can't be used."""

    MISSING = 'MISSING'

    def __repr__(self) -> str:
        return '<MISSING>'


MISSING: t.Final[MissingT] = MissingT.MISSING
OKT: TypeAlias = 'KT | MissingT'  #: optional key type
OVT: TypeAlias = 'VT | MissingT'  #: optional value type

DT = t.TypeVar('DT')              #: for default arguments
ODT: TypeAlias = 'DT | MissingT'  #: optional default arg type
