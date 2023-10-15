import re
import weakref
import gc
import ctypes
import unittest

import pygame
from pygame.bufferproxy import BufferProxy


try:
    BufferError
except NameError:
    from pygame import BufferError


class BufferProxyTest(unittest.TestCase):
    view_keywords = {
        "shape": (5, 4, 3),
        "typestr": "|u1",
        "data": (0, True),
        "strides": (4, 20, 1),
    }

    def test_module_name(self):
        self.assertEqual(pygame.bufferproxy.__name__, "pygame.bufferproxy")

    def test_class_name(self):
        self.assertEqual(BufferProxy.__name__, "BufferProxy")

    def test___array_struct___property(self):
        kwds = self.view_keywords
        v = BufferProxy(kwds)
        d = pygame.get_array_interface(v)
        self.assertEqual(len(d), 5)
        self.assertEqual(d["version"], 3)
        self.assertEqual(d["shape"], kwds["shape"])
        self.assertEqual(d["typestr"], kwds["typestr"])
        self.assertEqual(d["data"], kwds["data"])
        self.assertEqual(d["strides"], kwds["strides"])

    def test___array_interface___property(self):
        kwds = self.view_keywords
        v = BufferProxy(kwds)
        d = v.__array_interface__
        self.assertEqual(len(d), 5)
        self.assertEqual(d["version"], 3)
        self.assertEqual(d["shape"], kwds["shape"])
        self.assertEqual(d["typestr"], kwds["typestr"])
        self.assertEqual(d["data"], kwds["data"])
        self.assertEqual(d["strides"], kwds["strides"])

    def test_parent_property(self):
        kwds = dict(self.view_keywords)
        p = []
        kwds["parent"] = p
        v = BufferProxy(kwds)

        self.assertIs(v.parent, p)

    def test_before(self):
        def callback(parent):
            success.append(parent is p)

        class MyException(Exception):
            pass

        def raise_exception(parent):
            raise MyException("Just a test.")

        kwds = dict(self.view_keywords)
        p = []
        kwds["parent"] = p

        # For array interface
        success = []
        kwds["before"] = callback
        v = BufferProxy(kwds)
        self.assertEqual(len(success), 0)
        d = v.__array_interface__
        self.assertEqual(len(success), 1)
        self.assertTrue(success[0])
        d = v.__array_interface__
        self.assertEqual(len(success), 1)
        d = v = None
        gc.collect()
        self.assertEqual(len(success), 1)

        # For array struct
        success = []
        kwds["before"] = callback
        v = BufferProxy(kwds)
        self.assertEqual(len(success), 0)
        c = v.__array_struct__
        self.assertEqual(len(success), 1)
        self.assertTrue(success[0])
        c = v.__array_struct__
        self.assertEqual(len(success), 1)
        c = v = None
        gc.collect()
        self.assertEqual(len(success), 1)

        # Callback raises an exception
        kwds["before"] = raise_exception
        v = BufferProxy(kwds)
        self.assertRaises(MyException, lambda: v.__array_struct__)

    def test_after(self):
        def callback(parent):
            success.append(parent is p)

        kwds = dict(self.view_keywords)
        p = []
        kwds["parent"] = p

        # For array interface
        success = []
        kwds["after"] = callback
        v = BufferProxy(kwds)
        self.assertEqual(len(success), 0)
        d = v.__array_interface__
        self.assertEqual(len(success), 0)
        d = v.__array_interface__
        self.assertEqual(len(success), 0)
        d = v = None
        gc.collect()
        self.assertEqual(len(success), 1)
        self.assertTrue(success[0])

        # For array struct
        success = []
        kwds["after"] = callback
        v = BufferProxy(kwds)
        self.assertEqual(len(success), 0)
        c = v.__array_struct__
        self.assertEqual(len(success), 0)
        c = v.__array_struct__
        self.assertEqual(len(success), 0)
        c = v = None
        gc.collect()
        self.assertEqual(len(success), 1)
        self.assertTrue(success[0])

    def test_attribute(self):
        v = BufferProxy(self.view_keywords)
        self.assertRaises(AttributeError, getattr, v, "undefined")
        v.undefined = 12
        self.assertEqual(v.undefined, 12)
        del v.undefined
        self.assertRaises(AttributeError, getattr, v, "undefined")

    def test_weakref(self):
        v = BufferProxy(self.view_keywords)
        weak_v = weakref.ref(v)

        self.assertIs(weak_v(), v)

        v = None
        gc.collect()

        self.assertIsNone(weak_v())

    def test_gc(self):
        """refcount agnostic check that contained objects are freed"""

        def before_callback(parent):
            return r[0]

        def after_callback(parent):
            return r[1]

        class Obj:
            pass

        p = Obj()
        a = Obj()
        r = [Obj(), Obj()]
        weak_p = weakref.ref(p)
        weak_a = weakref.ref(a)
        weak_r0 = weakref.ref(r[0])
        weak_r1 = weakref.ref(r[1])
        weak_before = weakref.ref(before_callback)
        weak_after = weakref.ref(after_callback)
        kwds = dict(self.view_keywords)
        kwds["parent"] = p
        kwds["before"] = before_callback
        kwds["after"] = after_callback
        v = BufferProxy(kwds)
        v.some_attribute = a
        weak_v = weakref.ref(v)
        kwds = p = a = before_callback = after_callback = None
        gc.collect()
        self.assertTrue(weak_p() is not None)
        self.assertTrue(weak_a() is not None)
        self.assertTrue(weak_before() is not None)
        self.assertTrue(weak_after() is not None)
        v = None
        [gc.collect() for x in range(4)]
        self.assertTrue(weak_v() is None)
        self.assertTrue(weak_p() is None)
        self.assertTrue(weak_a() is None)
        self.assertTrue(weak_before() is None)
        self.assertTrue(weak_after() is None)
        self.assertTrue(weak_r0() is not None)
        self.assertTrue(weak_r1() is not None)
        r = None
        gc.collect()
        self.assertTrue(weak_r0() is None)
        self.assertTrue(weak_r1() is None)

        # Cycle removal
        kwds = dict(self.view_keywords)
        kwds["parent"] = []
        v = BufferProxy(kwds)
        v.some_attribute = v
        tracked = True
        for o in gc.get_objects():
            if o is v:
                break
        else:
            tracked = False
        self.assertTrue(tracked)
        kwds["parent"].append(v)
        kwds = None
        gc.collect()
        n1 = len(gc.garbage)
        v = None
        gc.collect()
        n2 = len(gc.garbage)
        self.assertEqual(n2, n1)

    def test_c_api(self):
        api = pygame.bufferproxy._PYGAME_C_API
        api_type = type(pygame.base._PYGAME_C_API)

        self.assertIsInstance(api, api_type)

    def test_repr(self):
        v = BufferProxy(self.view_keywords)
        cname = BufferProxy.__name__
        oname, ovalue = re.findall(r"<([^)]+)\(([^)]+)\)>", repr(v))[0]
        self.assertEqual(oname, cname)
        self.assertEqual(v.length, int(ovalue))

    def test_subclassing(self):
        class MyBufferProxy(BufferProxy):
            def __repr__(self):
                return f"*{BufferProxy.__repr__(self)}*"

        kwds = dict(self.view_keywords)
        kwds["parent"] = 0
        v = MyBufferProxy(kwds)
        self.assertEqual(v.parent, 0)
        r = repr(v)
        self.assertEqual(r[:2], "*<")
        self.assertEqual(r[-2:], ">*")

    @unittest.skipIf(not pygame.HAVE_NEWBUF, "newbuf not implemented")
    def NEWBUF_test_newbuf(self):
        from ctypes import string_at

        from pygame.tests.test_utils import buftools

        Exporter = buftools.Exporter
        Importer = buftools.Importer
        exp = Exporter((10,), "B", readonly=True)
        b = BufferProxy(exp)
        self.assertEqual(b.length, exp.len)
        self.assertEqual(b.raw, string_at(exp.buf, exp.len))
        d = b.__array_interface__
        try:
            self.assertEqual(d["typestr"], "|u1")
            self.assertEqual(d["shape"], exp.shape)
            self.assertEqual(d["strides"], exp.strides)
            self.assertEqual(d["data"], (exp.buf, True))
        finally:
            d = None
        exp = Exporter((3,), "=h")
        b = BufferProxy(exp)
        self.assertEqual(b.length, exp.len)
        self.assertEqual(b.raw, string_at(exp.buf, exp.len))
        d = b.__array_interface__
        try:
            lil_endian = pygame.get_sdl_byteorder() == pygame.LIL_ENDIAN
            f = f"{'<' if lil_endian else '>'}i{exp.itemsize}"
            self.assertEqual(d["typestr"], f)
            self.assertEqual(d["shape"], exp.shape)
            self.assertEqual(d["strides"], exp.strides)
            self.assertEqual(d["data"], (exp.buf, False))
        finally:
            d = None

        exp = Exporter((10, 2), "=i")
        b = BufferProxy(exp)
        imp = Importer(b, buftools.PyBUF_RECORDS)
        self.assertTrue(imp.obj is b)
        self.assertEqual(imp.buf, exp.buf)
        self.assertEqual(imp.ndim, exp.ndim)
        self.assertEqual(imp.format, exp.format)
        self.assertEqual(imp.readonly, exp.readonly)
        self.assertEqual(imp.itemsize, exp.itemsize)
        self.assertEqual(imp.len, exp.len)
        self.assertEqual(imp.shape, exp.shape)
        self.assertEqual(imp.strides, exp.strides)
        self.assertTrue(imp.suboffsets is None)

        d = {
            "typestr": "|u1",
            "shape": (10,),
            "strides": (1,),
            "data": (9, True),
        }  # 9? Will not reading the data anyway.
        b = BufferProxy(d)
        imp = Importer(b, buftools.PyBUF_SIMPLE)
        self.assertTrue(imp.obj is b)
        self.assertEqual(imp.buf, 9)
        self.assertEqual(imp.len, 10)
        self.assertEqual(imp.format, None)
        self.assertEqual(imp.itemsize, 1)
        self.assertEqual(imp.ndim, 0)
        self.assertTrue(imp.readonly)
        self.assertTrue(imp.shape is None)
        self.assertTrue(imp.strides is None)
        self.assertTrue(imp.suboffsets is None)

    try:
        pygame.bufferproxy.get_segcount
    except AttributeError:
        pass
    else:

        def test_oldbuf_arg(self):
            self.OLDBUF_test_oldbuf_arg()

    def OLDBUF_test_oldbuf_arg(self):
        from pygame.bufferproxy import get_segcount, get_read_buffer, get_write_buffer

        content = b"\x01\x00\x00\x02" * 12
        memory = ctypes.create_string_buffer(content)
        memaddr = ctypes.addressof(memory)

        def raise_exception(o):
            raise ValueError("An exception")

        bf = BufferProxy(
            {
                "shape": (len(content),),
                "typestr": "|u1",
                "data": (memaddr, False),
                "strides": (1,),
            }
        )
        seglen, segaddr = get_read_buffer(bf, 0)
        self.assertEqual(segaddr, 0)
        self.assertEqual(seglen, 0)
        seglen, segaddr = get_write_buffer(bf, 0)
        self.assertEqual(segaddr, 0)
        self.assertEqual(seglen, 0)
        segcount, buflen = get_segcount(bf)
        self.assertEqual(segcount, 1)
        self.assertEqual(buflen, len(content))
        seglen, segaddr = get_read_buffer(bf, 0)
        self.assertEqual(segaddr, memaddr)
        self.assertEqual(seglen, len(content))
        seglen, segaddr = get_write_buffer(bf, 0)
        self.assertEqual(segaddr, memaddr)
        self.assertEqual(seglen, len(content))

        bf = BufferProxy(
            {
                "shape": (len(content),),
                "typestr": "|u1",
                "data": (memaddr, True),
                "strides": (1,),
            }
        )
        segcount, buflen = get_segcount(bf)
        self.assertEqual(segcount, 1)
        self.assertEqual(buflen, len(content))
        seglen, segaddr = get_read_buffer(bf, 0)
        self.assertEqual(segaddr, memaddr)
        self.assertEqual(seglen, len(content))
        self.assertRaises(ValueError, get_write_buffer, bf, 0)

        bf = BufferProxy(
            {
                "shape": (len(content),),
                "typestr": "|u1",
                "data": (memaddr, True),
                "strides": (1,),
                "before": raise_exception,
            }
        )
        segcount, buflen = get_segcount(bf)
        self.assertEqual(segcount, 0)
        self.assertEqual(buflen, 0)

        bf = BufferProxy(
            {
                "shape": (3, 4),
                "typestr": "|u4",
                "data": (memaddr, True),
                "strides": (12, 4),
            }
        )
        segcount, buflen = get_segcount(bf)
        self.assertEqual(segcount, 3 * 4)
        self.assertEqual(buflen, 3 * 4 * 4)
        for i in range(0, 4):
            seglen, segaddr = get_read_buffer(bf, i)
            self.assertEqual(segaddr, memaddr + i * 4)
            self.assertEqual(seglen, 4)


class BufferProxyLegacyTest(unittest.TestCase):
    content = b"\x01\x00\x00\x02" * 12
    buffer = ctypes.create_string_buffer(content)
    data = (ctypes.addressof(buffer), True)

    def test_length(self):
        # __doc__ (as of 2008-08-02) for pygame.bufferproxy.BufferProxy.length:

        # The size of the buffer data in bytes.
        bf = BufferProxy(
            {"shape": (3, 4), "typestr": "|u4", "data": self.data, "strides": (12, 4)}
        )
        self.assertEqual(bf.length, len(self.content))
        bf = BufferProxy(
            {"shape": (3, 3), "typestr": "|u4", "data": self.data, "strides": (12, 4)}
        )
        self.assertEqual(bf.length, 3 * 3 * 4)

    def test_raw(self):
        # __doc__ (as of 2008-08-02) for pygame.bufferproxy.BufferProxy.raw:

        # The raw buffer data as string. The string may contain NUL bytes.

        bf = BufferProxy(
            {"shape": (len(self.content),), "typestr": "|u1", "data": self.data}
        )
        self.assertEqual(bf.raw, self.content)
        bf = BufferProxy(
            {"shape": (3, 4), "typestr": "|u4", "data": self.data, "strides": (4, 12)}
        )
        self.assertEqual(bf.raw, self.content)
        bf = BufferProxy(
            {"shape": (3, 4), "typestr": "|u1", "data": self.data, "strides": (16, 4)}
        )
        self.assertRaises(ValueError, getattr, bf, "raw")

    def test_write(self):
        # __doc__ (as of 2008-08-02) for pygame.bufferproxy.BufferProxy.write:

        # B.write (bufferproxy, buffer, offset) -> None
        #
        # Writes raw data to the bufferproxy.
        #
        # Writes the raw data from buffer to the BufferProxy object, starting
        # at the specified offset within the BufferProxy.
        # If the length of the passed buffer exceeds the length of the
        # BufferProxy (reduced by the offset), an IndexError will be raised.
        from ctypes import c_byte, sizeof, addressof, string_at, memset

        nullbyte = b"\x00"
        Buf = c_byte * 10
        data_buf = Buf(*range(1, 3 * sizeof(Buf) + 1, 3))
        data = string_at(data_buf, sizeof(data_buf))
        buf = Buf()
        bp = BufferProxy(
            {"typestr": "|u1", "shape": (sizeof(buf),), "data": (addressof(buf), False)}
        )
        try:
            self.assertEqual(bp.raw, nullbyte * sizeof(Buf))
            bp.write(data)
            self.assertEqual(bp.raw, data)
            memset(buf, 0, sizeof(buf))
            bp.write(data[:3], 2)
            raw = bp.raw
            self.assertEqual(raw[:2], nullbyte * 2)
            self.assertEqual(raw[2:5], data[:3])
            self.assertEqual(raw[5:], nullbyte * (sizeof(Buf) - 5))
            bp.write(data[:3], bp.length - 3)
            raw = bp.raw
            self.assertEqual(raw[-3:], data[:3])
            self.assertRaises(IndexError, bp.write, data, 1)
            self.assertRaises(IndexError, bp.write, data[:5], -1)
            self.assertRaises(IndexError, bp.write, data[:5], bp.length)
            self.assertRaises(TypeError, bp.write, 12)
            bp = BufferProxy(
                {
                    "typestr": "|u1",
                    "shape": (sizeof(buf),),
                    "data": (addressof(buf), True),
                }
            )
            self.assertRaises(pygame.BufferError, bp.write, b"123")
        finally:
            # Make sure bp is garbage collected before buf
            bp = None
            gc.collect()


if __name__ == "__main__":
    unittest.main()
