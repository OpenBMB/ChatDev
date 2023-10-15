# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/astroid/blob/main/CONTRIBUTORS.txt

"""
Astroid hooks for responses.

It might need to be manually updated from the public methods of
:class:`responses.RequestsMock`.

See: https://github.com/getsentry/responses/blob/master/responses.py
"""
from astroid.brain.helpers import register_module_extender
from astroid.builder import parse
from astroid.manager import AstroidManager


def responses_funcs():
    return parse(
        """
        DELETE = "DELETE"
        GET = "GET"
        HEAD = "HEAD"
        OPTIONS = "OPTIONS"
        PATCH = "PATCH"
        POST = "POST"
        PUT = "PUT"
        response_callback = None

        def reset():
            return

        def add(
            method=None,  # method or ``Response``
            url=None,
            body="",
            adding_headers=None,
            *args,
            **kwargs
        ):
            return

        def add_passthru(prefix):
            return

        def remove(method_or_response=None, url=None):
            return

        def replace(method_or_response=None, url=None, body="", *args, **kwargs):
            return

        def add_callback(
            method, url, callback, match_querystring=False, content_type="text/plain"
        ):
            return

        calls = []

        def __enter__():
            return

        def __exit__(type, value, traceback):
            success = type is None
            return success

        def activate(func):
            return func

        def start():
            return

        def stop(allow_assert=True):
            return
        """
    )


register_module_extender(AstroidManager(), "responses", responses_funcs)
