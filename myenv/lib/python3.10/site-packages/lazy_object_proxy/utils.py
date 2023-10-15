from collections.abc import Awaitable
from inspect import CO_ITERABLE_COROUTINE
from types import CoroutineType
from types import GeneratorType


async def do_await(obj):
    return await obj


def do_yield_from(gen):
    return (yield from gen)


def await_(obj):
    obj_type = type(obj)
    if (
        obj_type is CoroutineType
        or obj_type is GeneratorType
        and bool(obj.gi_code.co_flags & CO_ITERABLE_COROUTINE)
        or isinstance(obj, Awaitable)
    ):
        return do_await(obj).__await__()
    else:
        return do_yield_from(obj)


def __aiter__(self):
    return self.__wrapped__.__aiter__()


async def __anext__(self):
    return await self.__wrapped__.__anext__()


def __await__(self):
    return await_(self.__wrapped__)


def __aenter__(self):
    return self.__wrapped__.__aenter__()


def __aexit__(self, *args, **kwargs):
    return self.__wrapped__.__aexit__(*args, **kwargs)


def identity(obj):
    return obj


class cached_property(object):
    def __init__(self, func):
        self.func = func

    def __get__(self, obj, cls):
        if obj is None:
            return self
        value = obj.__dict__[self.func.__name__] = self.func(obj)
        return value
