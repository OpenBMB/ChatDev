# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/astroid/blob/main/CONTRIBUTORS.txt

from astroid.brain.helpers import register_module_extender
from astroid.builder import parse
from astroid.manager import AstroidManager


def _session_transform():
    return parse(
        """
    from sqlalchemy.orm.session import Session

    class sessionmaker:
        def __init__(
            self,
            bind=None,
            class_=Session,
            autoflush=True,
            autocommit=False,
            expire_on_commit=True,
            info=None,
            **kw
        ):
            return

        def __call__(self, **local_kw):
            return Session()

        def configure(self, **new_kw):
            return

        return Session()
    """
    )


register_module_extender(AstroidManager(), "sqlalchemy.orm.session", _session_transform)
