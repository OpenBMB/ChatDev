# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/astroid/blob/main/CONTRIBUTORS.txt

from astroid.brain.helpers import register_module_extender
from astroid.builder import AstroidBuilder
from astroid.manager import AstroidManager


def mechanize_transform():
    return AstroidBuilder(AstroidManager()).string_build(
        """class Browser(object):
    def __getattr__(self, name):
        return None

    def __getitem__(self, name):
        return None

    def __setitem__(self, name, val):
        return None

    def back(self, n=1):
        return None

    def clear_history(self):
        return None

    def click(self, *args, **kwds):
        return None

    def click_link(self, link=None, **kwds):
        return None

    def close(self):
        return None

    def encoding(self):
        return None

    def find_link(
        self,
        text=None,
        text_regex=None,
        name=None,
        name_regex=None,
        url=None,
        url_regex=None,
        tag=None,
        predicate=None,
        nr=0,
    ):
        return None

    def follow_link(self, link=None, **kwds):
        return None

    def forms(self):
        return None

    def geturl(self):
        return None

    def global_form(self):
        return None

    def links(self, **kwds):
        return None

    def open_local_file(self, filename):
        return None

    def open(self, url, data=None, timeout=None):
        return None

    def open_novisit(self, url, data=None, timeout=None):
        return None

    def open_local_file(self, filename):
        return None

    def reload(self):
        return None

    def response(self):
        return None

    def select_form(self, name=None, predicate=None, nr=None, **attrs):
        return None

    def set_cookie(self, cookie_string):
        return None

    def set_handle_referer(self, handle):
        return None

    def set_header(self, header, value=None):
        return None

    def set_html(self, html, url="http://example.com/"):
        return None

    def set_response(self, response):
        return None

    def set_simple_cookie(self, name, value, domain, path="/"):
        return None

    def submit(self, *args, **kwds):
        return None

    def title(self):
        return None

    def viewing_html(self):
        return None

    def visit_response(self, response, request=None):
        return None
"""
    )


register_module_extender(AstroidManager(), "mechanize", mechanize_transform)
