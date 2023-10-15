# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/astroid/blob/main/CONTRIBUTORS.txt

import textwrap

from astroid.brain.helpers import register_module_extender
from astroid.builder import parse
from astroid.const import PY39_PLUS, PY310_PLUS, PY311_PLUS
from astroid.manager import AstroidManager


def _subprocess_transform():
    communicate = (bytes("string", "ascii"), bytes("string", "ascii"))
    communicate_signature = "def communicate(self, input=None, timeout=None)"
    args = """\
        self, args, bufsize=-1, executable=None, stdin=None, stdout=None, stderr=None,
        preexec_fn=None, close_fds=True, shell=False, cwd=None, env=None,
        universal_newlines=None, startupinfo=None, creationflags=0, restore_signals=True,
        start_new_session=False, pass_fds=(), *, encoding=None, errors=None, text=None"""

    if PY39_PLUS:
        args += ", user=None, group=None, extra_groups=None, umask=-1"
    if PY310_PLUS:
        args += ", pipesize=-1"
    if PY311_PLUS:
        args += ", process_group=None"

    init = f"""
        def __init__({args}):
            pass"""
    wait_signature = "def wait(self, timeout=None)"
    ctx_manager = """
        def __enter__(self): return self
        def __exit__(self, *args): pass
    """
    py3_args = "args = []"

    check_output_signature = """
    check_output(
        args, *,
        stdin=None,
        stderr=None,
        shell=False,
        cwd=None,
        encoding=None,
        errors=None,
        universal_newlines=False,
        timeout=None,
        env=None,
        text=None,
        restore_signals=True,
        preexec_fn=None,
        pass_fds=(),
        input=None,
        bufsize=0,
        executable=None,
        close_fds=False,
        startupinfo=None,
        creationflags=0,
        start_new_session=False
    ):
    """.strip()

    code = textwrap.dedent(
        f"""
    def {check_output_signature}
        if universal_newlines:
            return ""
        return b""

    class Popen(object):
        returncode = pid = 0
        stdin = stdout = stderr = file()
        {py3_args}

        {communicate_signature}:
            return {communicate!r}
        {wait_signature}:
            return self.returncode
        def poll(self):
            return self.returncode
        def send_signal(self, signal):
            pass
        def terminate(self):
            pass
        def kill(self):
            pass
        {ctx_manager}
       """
    )
    if PY39_PLUS:
        code += """
    @classmethod
    def __class_getitem__(cls, item):
        pass
        """

    init_lines = textwrap.dedent(init).splitlines()
    indented_init = "\n".join(" " * 4 + line for line in init_lines)
    code += indented_init
    return parse(code)


register_module_extender(AstroidManager(), "subprocess", _subprocess_transform)
