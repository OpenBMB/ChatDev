################################################################################
"""

Modification of http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/440554

"""

#################################### IMPORTS ###################################

import os
import platform
import subprocess
import errno
import time
import sys
import unittest
import tempfile


def geterror():
    return sys.exc_info()[1]


null_byte = "\x00".encode("ascii")

if platform.system() == "Windows":

    def encode(s):
        return s.encode("ascii")

    def decode(b):
        return b.decode("ascii")

    try:
        import ctypes
        from ctypes.wintypes import DWORD

        kernel32 = ctypes.windll.kernel32
        TerminateProcess = ctypes.windll.kernel32.TerminateProcess

        def WriteFile(handle, data, ol=None):
            c_written = DWORD()
            success = ctypes.windll.kernel32.WriteFile(
                handle,
                ctypes.create_string_buffer(encode(data)),
                len(data),
                ctypes.byref(c_written),
                ol,
            )
            return ctypes.windll.kernel32.GetLastError(), c_written.value

        def ReadFile(handle, desired_bytes, ol=None):
            c_read = DWORD()
            buffer = ctypes.create_string_buffer(desired_bytes + 1)
            success = ctypes.windll.kernel32.ReadFile(
                handle, buffer, desired_bytes, ctypes.byref(c_read), ol
            )
            buffer[c_read.value] = null_byte
            return ctypes.windll.kernel32.GetLastError(), decode(buffer.value)

        def PeekNamedPipe(handle, desired_bytes):
            c_avail = DWORD()
            c_message = DWORD()
            if desired_bytes > 0:
                c_read = DWORD()
                buffer = ctypes.create_string_buffer(desired_bytes + 1)
                success = ctypes.windll.kernel32.PeekNamedPipe(
                    handle,
                    buffer,
                    desired_bytes,
                    ctypes.byref(c_read),
                    ctypes.byref(c_avail),
                    ctypes.byref(c_message),
                )
                buffer[c_read.value] = null_byte
                return decode(buffer.value), c_avail.value, c_message.value
            else:
                success = ctypes.windll.kernel32.PeekNamedPipe(
                    handle,
                    None,
                    desired_bytes,
                    None,
                    ctypes.byref(c_avail),
                    ctypes.byref(c_message),
                )
                return "", c_avail.value, c_message.value

    except ImportError:
        from win32file import ReadFile, WriteFile
        from win32pipe import PeekNamedPipe
        from win32api import TerminateProcess
    import msvcrt

else:
    from signal import SIGINT, SIGTERM, SIGKILL
    import select
    import fcntl

################################### CONSTANTS ##################################

PIPE = subprocess.PIPE

################################################################################


class Popen(subprocess.Popen):
    def recv(self, maxsize=None):
        return self._recv("stdout", maxsize)

    def recv_err(self, maxsize=None):
        return self._recv("stderr", maxsize)

    def send_recv(self, input="", maxsize=None):
        return self.send(input), self.recv(maxsize), self.recv_err(maxsize)

    def read_async(self, wait=0.1, e=1, tr=5, stderr=0):
        if tr < 1:
            tr = 1
        x = time.time() + wait
        y = []
        r = ""
        pr = self.recv
        if stderr:
            pr = self.recv_err
        while time.time() < x or r:
            r = pr()
            if r is None:
                if e:
                    raise Exception("Other end disconnected!")
                else:
                    break
            elif r:
                y.append(r)
            else:
                time.sleep(max((x - time.time()) / tr, 0))
        return "".join(y)

    def send_all(self, data):
        while len(data):
            sent = self.send(data)
            if sent is None:
                raise Exception("Other end disconnected!")
            data = memoryview(data, sent)

    def get_conn_maxsize(self, which, maxsize):
        if maxsize is None:
            maxsize = 1024
        elif maxsize < 1:
            maxsize = 1
        return getattr(self, which), maxsize

    def _close(self, which):
        getattr(self, which).close()
        setattr(self, which, None)

    if platform.system() == "Windows":

        def kill(self):
            # Recipes
            # http://me.in-berlin.de/doc/python/faq/windows.html#how-do-i-emulate-os-kill-in-windows
            # http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/347462

            """kill function for Win32"""
            TerminateProcess(int(self._handle), 0)  # returns None

        def send(self, input):
            if not self.stdin:
                return None

            try:
                x = msvcrt.get_osfhandle(self.stdin.fileno())
                (errCode, written) = WriteFile(x, input)
            except ValueError:
                return self._close("stdin")
            except (subprocess.pywintypes.error, Exception):
                if geterror()[0] in (109, errno.ESHUTDOWN):
                    return self._close("stdin")
                raise

            return written

        def _recv(self, which, maxsize):
            conn, maxsize = self.get_conn_maxsize(which, maxsize)
            if conn is None:
                return None

            try:
                x = msvcrt.get_osfhandle(conn.fileno())
                (read, nAvail, nMessage) = PeekNamedPipe(x, 0)
                if maxsize < nAvail:
                    nAvail = maxsize
                if nAvail > 0:
                    (errCode, read) = ReadFile(x, nAvail, None)
            except ValueError:
                return self._close(which)
            except (subprocess.pywintypes.error, Exception):
                if geterror()[0] in (109, errno.ESHUTDOWN):
                    return self._close(which)
                raise

            if self.universal_newlines:
                # Translate newlines. For Python 3.x assume read is text.
                # If bytes then another solution is needed.
                read = read.replace("\r\n", "\n").replace("\r", "\n")
            return read

    else:

        def kill(self):
            for i, sig in enumerate([SIGTERM, SIGKILL] * 2):
                if i % 2 == 0:
                    os.kill(self.pid, sig)
                time.sleep((i * (i % 2) / 5.0) + 0.01)

                killed_pid, stat = os.waitpid(self.pid, os.WNOHANG)
                if killed_pid != 0:
                    return

        def send(self, input):
            if not self.stdin:
                return None

            if not select.select([], [self.stdin], [], 0)[1]:
                return 0

            try:
                written = os.write(self.stdin.fileno(), input)
            except OSError:
                if geterror()[0] == errno.EPIPE:  # broken pipe
                    return self._close("stdin")
                raise

            return written

        def _recv(self, which, maxsize):
            conn, maxsize = self.get_conn_maxsize(which, maxsize)
            if conn is None:
                return None

            if not select.select([conn], [], [], 0)[0]:
                return ""

            r = conn.read(maxsize)
            if not r:
                return self._close(which)

            if self.universal_newlines:
                r = r.replace("\r\n", "\n").replace("\r", "\n")
            return r


################################################################################


def proc_in_time_or_kill(cmd, time_out, wd=None, env=None):
    proc = Popen(
        cmd,
        cwd=wd,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=1,
    )

    ret_code = None
    response = []

    t = time.time()
    while ret_code is None and ((time.time() - t) < time_out):
        ret_code = proc.poll()
        response += [proc.read_async(wait=0.1, e=0)]

    if ret_code is None:
        ret_code = f'"Process timed out (time_out = {time_out} secs) '
        try:
            proc.kill()
            ret_code += 'and was successfully terminated"'
        except Exception:
            ret_code += f'and termination failed (exception: {geterror()})"'

    return ret_code, "".join(response)


################################################################################


class AsyncTest(unittest.TestCase):
    def test_proc_in_time_or_kill(self):
        ret_code, response = proc_in_time_or_kill(
            [sys.executable, "-c", "while True: pass"], time_out=1
        )

        self.assertIn("rocess timed out", ret_code)
        self.assertIn("successfully terminated", ret_code)


################################################################################

if __name__ == "__main__":
    unittest.main()
