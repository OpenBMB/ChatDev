"""Errors"""


from __future__ import annotations


class ProcessCallFailed(RuntimeError):
    """Failed a process call"""

    def __init__(self, code, out, err, cmd):
        super().__init__(code, out, err, cmd)
        self.code = code
        self.out = out
        self.err = err
        self.cmd = cmd
