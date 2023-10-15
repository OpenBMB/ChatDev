# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/astroid/blob/main/CONTRIBUTORS.txt

"""Transform utilities (filters and decorator)."""

from __future__ import annotations

import typing
from collections.abc import Iterator

import wrapt

from astroid.exceptions import InferenceOverwriteError, UseInferenceDefault
from astroid.nodes import NodeNG
from astroid.typing import InferenceResult, InferFn

_cache: dict[tuple[InferFn, NodeNG], list[InferenceResult] | None] = {}


def clear_inference_tip_cache() -> None:
    """Clear the inference tips cache."""
    _cache.clear()


@wrapt.decorator
def _inference_tip_cached(
    func: InferFn, instance: None, args: typing.Any, kwargs: typing.Any
) -> Iterator[InferenceResult]:
    """Cache decorator used for inference tips."""
    node = args[0]
    try:
        result = _cache[func, node]
        # If through recursion we end up trying to infer the same
        # func + node we raise here.
        if result is None:
            raise UseInferenceDefault()
    except KeyError:
        _cache[func, node] = None
        result = _cache[func, node] = list(func(*args, **kwargs))
        assert result
    return iter(result)


def inference_tip(infer_function: InferFn, raise_on_overwrite: bool = False) -> InferFn:
    """Given an instance specific inference function, return a function to be
    given to AstroidManager().register_transform to set this inference function.

    :param bool raise_on_overwrite: Raise an `InferenceOverwriteError`
        if the inference tip will overwrite another. Used for debugging

    Typical usage

    .. sourcecode:: python

       AstroidManager().register_transform(Call, inference_tip(infer_named_tuple),
                                  predicate)

    .. Note::

        Using an inference tip will override
        any previously set inference tip for the given
        node. Use a predicate in the transform to prevent
        excess overwrites.
    """

    def transform(node: NodeNG, infer_function: InferFn = infer_function) -> NodeNG:
        if (
            raise_on_overwrite
            and node._explicit_inference is not None
            and node._explicit_inference is not infer_function
        ):
            raise InferenceOverwriteError(
                "Inference already set to {existing_inference}. "
                "Trying to overwrite with {new_inference} for {node}".format(
                    existing_inference=infer_function,
                    new_inference=node._explicit_inference,
                    node=node,
                )
            )
        # pylint: disable=no-value-for-parameter
        node._explicit_inference = _inference_tip_cached(infer_function)
        return node

    return transform
