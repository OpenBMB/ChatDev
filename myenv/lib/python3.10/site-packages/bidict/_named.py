# Copyright 2009-2022 Joshua Bronson. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Provide :func:`bidict.namedbidict`."""

from __future__ import annotations
from sys import _getframe
import typing as t

from ._base import BidictBase
from ._bidict import bidict
from ._typing import KT, VT


class NamedBidictBase:
    """Base class that namedbidicts derive from."""


def namedbidict(
    typename: str,
    keyname: str,
    valname: str,
    *,
    base_type: t.Type[BidictBase[KT, VT]] = bidict,
) -> t.Type[BidictBase[KT, VT]]:
    r"""Create a new subclass of *base_type* with custom accessors.

    Like :func:`collections.namedtuple` for bidicts.

    The new class's ``__name__`` and ``__qualname__`` will be set to *typename*,
    and its ``__module__`` will be set to the caller's module.

    Instances of the new class will provide access to their
    :attr:`inverse <BidirectionalMapping.inverse>` instances
    via the custom *keyname*\_for property,
    and access to themselves
    via the custom *valname*\_for property.

    *See also* the :ref:`namedbidict usage documentation
    <other-bidict-types:\:func\:\`~bidict.namedbidict\`>`
    (https://bidict.rtfd.io/other-bidict-types.html#namedbidict)

    :raises ValueError: if any of the *typename*, *keyname*, or *valname*
        strings is not a valid Python identifier, or if *keyname == valname*.

    :raises TypeError: if *base_type* is not a :class:`bidict.BidictBase` subclass.
        Any of the concrete bidict types pictured in the
        :ref:`other-bidict-types:Bidict Types Diagram` may be provided
        (https://bidict.rtfd.io/other-bidict-types.html#bidict-types-diagram).
    """
    if not issubclass(base_type, BidictBase):
        raise TypeError(f'{base_type} is not a BidictBase subclass')
    names = (typename, keyname, valname)
    if not all(map(str.isidentifier, names)) or keyname == valname:
        raise ValueError(names)

    basename = base_type.__name__
    get_keyname = property(lambda self: keyname, doc='The keyname of this namedbidict.')
    get_valname = property(lambda self: valname, doc='The valname of this namedbidict.')
    val_by_key_name = f'{valname}_for'
    key_by_val_name = f'{keyname}_for'
    val_by_key_doc = f'{typename} forward {basename}: {keyname} -> {valname}'
    key_by_val_doc = f'{typename} inverse {basename}: {valname} -> {keyname}'
    get_val_by_key = property(lambda self: self, doc=val_by_key_doc)
    get_key_by_val = property(lambda self: self.inverse, doc=key_by_val_doc)

    class NamedBidict(base_type, NamedBidictBase):  # type: ignore [valid-type,misc]  # https://github.com/python/mypy/issues/5865
        """NamedBidict."""

        keyname = get_keyname
        valname = get_valname

        @classmethod
        def _inv_cls_dict_diff(cls) -> dict[str, t.Any]:
            base_diff = super()._inv_cls_dict_diff()
            return {
                **base_diff,
                'keyname': get_valname,
                'valname': get_keyname,
                val_by_key_name: get_key_by_val,
                key_by_val_name: get_val_by_key,
            }

    NamedInv = NamedBidict._inv_cls
    assert NamedInv is not NamedBidict, 'namedbidict classes are not their own inverses'
    setattr(NamedBidict, val_by_key_name, get_val_by_key)
    setattr(NamedBidict, key_by_val_name, get_key_by_val)
    NamedBidict.__name__ = NamedBidict.__qualname__ = typename
    NamedInv.__name__ = NamedInv.__qualname__ = f'{typename}Inv'
    NamedBidict.__doc__ = f'NamedBidict({basename}) {typename!r}: {keyname} -> {valname}'
    NamedInv.__doc__ = f'NamedBidictInv({basename}) {typename!r}: {valname} -> {keyname}'
    caller_module = _getframe(1).f_globals.get('__name__', '__main__')
    NamedBidict.__module__ = NamedInv.__module__ = caller_module
    return NamedBidict
