import sys
import ctypes
from ctypes import *
import unittest

__all__ = [
    "PAI_CONTIGUOUS",
    "PAI_FORTRAN",
    "PAI_ALIGNED",
    "PAI_NOTSWAPPED",
    "PAI_WRITEABLE",
    "PAI_ARR_HAS_DESCR",
    "ArrayInterface",
]

if sizeof(c_uint) == sizeof(c_void_p):
    c_size_t = c_uint
    c_ssize_t = c_int
elif sizeof(c_ulong) == sizeof(c_void_p):
    c_size_t = c_ulong
    c_ssize_t = c_long
elif sizeof(c_ulonglong) == sizeof(c_void_p):
    c_size_t = c_ulonglong
    c_ssize_t = c_longlong


SIZEOF_VOID_P = sizeof(c_void_p)
if SIZEOF_VOID_P <= sizeof(c_int):
    Py_intptr_t = c_int
elif SIZEOF_VOID_P <= sizeof(c_long):
    Py_intptr_t = c_long
elif "c_longlong" in globals() and SIZEOF_VOID_P <= sizeof(c_longlong):
    Py_intptr_t = c_longlong
else:
    raise RuntimeError("Unrecognized pointer size %i" % (SIZEOF_VOID_P,))


class PyArrayInterface(Structure):
    _fields_ = [
        ("two", c_int),
        ("nd", c_int),
        ("typekind", c_char),
        ("itemsize", c_int),
        ("flags", c_int),
        ("shape", POINTER(Py_intptr_t)),
        ("strides", POINTER(Py_intptr_t)),
        ("data", c_void_p),
        ("descr", py_object),
    ]


PAI_Ptr = POINTER(PyArrayInterface)

try:
    PyCObject_AsVoidPtr = pythonapi.PyCObject_AsVoidPtr
except AttributeError:

    def PyCObject_AsVoidPtr(o):
        raise TypeError("Not available")

else:
    PyCObject_AsVoidPtr.restype = c_void_p
    PyCObject_AsVoidPtr.argtypes = [py_object]
    PyCObject_GetDesc = pythonapi.PyCObject_GetDesc
    PyCObject_GetDesc.restype = c_void_p
    PyCObject_GetDesc.argtypes = [py_object]

try:
    PyCapsule_IsValid = pythonapi.PyCapsule_IsValid
except AttributeError:

    def PyCapsule_IsValid(capsule, name):
        return 0

else:
    PyCapsule_IsValid.restype = c_int
    PyCapsule_IsValid.argtypes = [py_object, c_char_p]
    PyCapsule_GetPointer = pythonapi.PyCapsule_GetPointer
    PyCapsule_GetPointer.restype = c_void_p
    PyCapsule_GetPointer.argtypes = [py_object, c_char_p]
    PyCapsule_GetContext = pythonapi.PyCapsule_GetContext
    PyCapsule_GetContext.restype = c_void_p
    PyCapsule_GetContext.argtypes = [py_object]

PyCapsule_Destructor = CFUNCTYPE(None, py_object)
PyCapsule_New = pythonapi.PyCapsule_New
PyCapsule_New.restype = py_object
PyCapsule_New.argtypes = [c_void_p, c_char_p, POINTER(PyCapsule_Destructor)]


def capsule_new(p):
    return PyCapsule_New(addressof(p), None, None)


PAI_CONTIGUOUS = 0x01
PAI_FORTRAN = 0x02
PAI_ALIGNED = 0x100
PAI_NOTSWAPPED = 0x200
PAI_WRITEABLE = 0x400
PAI_ARR_HAS_DESCR = 0x800


class ArrayInterface:
    def __init__(self, arr):
        try:
            self._cobj = arr.__array_struct__
        except AttributeError:
            raise TypeError("The array object lacks an array structure")
        if not self._cobj:
            raise TypeError("The array object has a NULL array structure value")
        try:
            vp = PyCObject_AsVoidPtr(self._cobj)
        except TypeError:
            if PyCapsule_IsValid(self._cobj, None):
                vp = PyCapsule_GetPointer(self._cobj, None)
            else:
                raise TypeError("The array object has an invalid array structure")
            self.desc = PyCapsule_GetContext(self._cobj)
        else:
            self.desc = PyCObject_GetDesc(self._cobj)
        self._inter = cast(vp, PAI_Ptr)[0]

    def __getattr__(self, name):
        if name == "typekind":
            return self._inter.typekind.decode("latin-1")
        return getattr(self._inter, name)

    def __str__(self):
        if isinstance(self.desc, tuple):
            ver = self.desc[0]
        else:
            ver = "N/A"
        return (
            "nd: %i\n"
            "typekind: %s\n"
            "itemsize: %i\n"
            "flags: %s\n"
            "shape: %s\n"
            "strides: %s\n"
            "ver: %s\n"
            % (
                self.nd,
                self.typekind,
                self.itemsize,
                format_flags(self.flags),
                format_shape(self.nd, self.shape),
                format_strides(self.nd, self.strides),
                ver,
            )
        )


def format_flags(flags):
    names = []
    for flag, name in [
        (PAI_CONTIGUOUS, "CONTIGUOUS"),
        (PAI_FORTRAN, "FORTRAN"),
        (PAI_ALIGNED, "ALIGNED"),
        (PAI_NOTSWAPPED, "NOTSWAPPED"),
        (PAI_WRITEABLE, "WRITEABLE"),
        (PAI_ARR_HAS_DESCR, "ARR_HAS_DESCR"),
    ]:
        if flag & flags:
            names.append(name)
    return ", ".join(names)


def format_shape(nd, shape):
    return ", ".join([str(shape[i]) for i in range(nd)])


def format_strides(nd, strides):
    return ", ".join([str(strides[i]) for i in range(nd)])


class Exporter:
    def __init__(
        self, shape, typekind=None, itemsize=None, strides=None, descr=None, flags=None
    ):
        if typekind is None:
            typekind = "u"
        if itemsize is None:
            itemsize = 1
        if flags is None:
            flags = PAI_WRITEABLE | PAI_ALIGNED | PAI_NOTSWAPPED
        if descr is not None:
            flags |= PAI_ARR_HAS_DESCR
        if len(typekind) != 1:
            raise ValueError("Argument 'typekind' must be length 1 string")
        nd = len(shape)
        self.typekind = typekind
        self.itemsize = itemsize
        self.nd = nd
        self.shape = tuple(shape)
        self._shape = (c_ssize_t * self.nd)(*self.shape)
        if strides is None:
            self._strides = (c_ssize_t * self.nd)()
            self._strides[self.nd - 1] = self.itemsize
            for i in range(self.nd - 1, 0, -1):
                self._strides[i - 1] = self.shape[i] * self._strides[i]
            strides = tuple(self._strides)
            self.strides = strides
        elif len(strides) == nd:
            self.strides = tuple(strides)
            self._strides = (c_ssize_t * self.nd)(*self.strides)
        else:
            raise ValueError("Mismatch in length of strides and shape")
        self.descr = descr
        if self.is_contiguous("C"):
            flags |= PAI_CONTIGUOUS
        if self.is_contiguous("F"):
            flags |= PAI_FORTRAN
        self.flags = flags
        sz = max(shape[i] * strides[i] for i in range(nd))
        self._data = (c_ubyte * sz)()
        self.data = addressof(self._data)
        self._inter = PyArrayInterface(
            2,
            nd,
            typekind.encode("latin_1"),
            itemsize,
            flags,
            self._shape,
            self._strides,
            self.data,
            descr,
        )
        self.len = itemsize
        for i in range(nd):
            self.len *= self.shape[i]

    __array_struct__ = property(lambda self: capsule_new(self._inter))

    def is_contiguous(self, fortran):
        if fortran in "CA":
            if self.strides[-1] == self.itemsize:
                for i in range(self.nd - 1, 0, -1):
                    if self.strides[i - 1] != self.shape[i] * self.strides[i]:
                        break
                else:
                    return True
        if fortran in "FA":
            if self.strides[0] == self.itemsize:
                for i in range(0, self.nd - 1):
                    if self.strides[i + 1] != self.shape[i] * self.strides[i]:
                        break
                else:
                    return True
        return False


class Array(Exporter):
    _ctypes = {
        ("u", 1): c_uint8,
        ("u", 2): c_uint16,
        ("u", 4): c_uint32,
        ("u", 8): c_uint64,
        ("i", 1): c_int8,
        ("i", 2): c_int16,
        ("i", 4): c_int32,
        ("i", 8): c_int64,
    }

    def __init__(self, *args, **kwds):
        super().__init__(*args, **kwds)
        try:
            if self.flags & PAI_NOTSWAPPED:
                ct = self._ctypes[self.typekind, self.itemsize]
            elif c_int.__ctype_le__ is c_int:
                ct = self._ctypes[self.typekind, self.itemsize].__ctype_be__
            else:
                ct = self._ctypes[self.typekind, self.itemsize].__ctype_le__
        except KeyError:
            ct = c_uint8 * self.itemsize
        self._ctype = ct
        self._ctype_p = POINTER(ct)

    def __getitem__(self, key):
        return cast(self._addr_at(key), self._ctype_p)[0]

    def __setitem__(self, key, value):
        cast(self._addr_at(key), self._ctype_p)[0] = value

    def _addr_at(self, key):
        if not isinstance(key, tuple):
            key = (key,)
        if len(key) != self.nd:
            raise ValueError("wrong number of indexes")
        for i in range(self.nd):
            if not (0 <= key[i] < self.shape[i]):
                raise IndexError(f"index {i} out of range")
        return self.data + sum(i * s for i, s in zip(key, self.strides))


class ExporterTest(unittest.TestCase):
    def test_strides(self):
        self.check_args(0, (10,), "u", (2,), 20, 20, 2)
        self.check_args(0, (5, 3), "u", (6, 2), 30, 30, 2)
        self.check_args(0, (7, 3, 5), "u", (30, 10, 2), 210, 210, 2)
        self.check_args(0, (13, 5, 11, 3), "u", (330, 66, 6, 2), 4290, 4290, 2)
        self.check_args(3, (7, 3, 5), "i", (2, 14, 42), 210, 210, 2)
        self.check_args(3, (7, 3, 5), "x", (2, 16, 48), 210, 240, 2)
        self.check_args(3, (13, 5, 11, 3), "%", (440, 88, 8, 2), 4290, 5720, 2)
        self.check_args(3, (7, 5), "-", (15, 3), 105, 105, 3)
        self.check_args(3, (7, 5), "*", (3, 21), 105, 105, 3)
        self.check_args(3, (7, 5), " ", (3, 24), 105, 120, 3)

    def test_is_contiguous(self):
        a = Exporter((10,), itemsize=2)
        self.assertTrue(a.is_contiguous("C"))
        self.assertTrue(a.is_contiguous("F"))
        self.assertTrue(a.is_contiguous("A"))
        a = Exporter((10, 4), itemsize=2)
        self.assertTrue(a.is_contiguous("C"))
        self.assertTrue(a.is_contiguous("A"))
        self.assertFalse(a.is_contiguous("F"))
        a = Exporter((13, 5, 11, 3), itemsize=2, strides=(330, 66, 6, 2))
        self.assertTrue(a.is_contiguous("C"))
        self.assertTrue(a.is_contiguous("A"))
        self.assertFalse(a.is_contiguous("F"))
        a = Exporter((10, 4), itemsize=2, strides=(2, 20))
        self.assertTrue(a.is_contiguous("F"))
        self.assertTrue(a.is_contiguous("A"))
        self.assertFalse(a.is_contiguous("C"))
        a = Exporter((13, 5, 11, 3), itemsize=2, strides=(2, 26, 130, 1430))
        self.assertTrue(a.is_contiguous("F"))
        self.assertTrue(a.is_contiguous("A"))
        self.assertFalse(a.is_contiguous("C"))
        a = Exporter((2, 11, 6, 4), itemsize=2, strides=(576, 48, 8, 2))
        self.assertFalse(a.is_contiguous("A"))
        a = Exporter((2, 11, 6, 4), itemsize=2, strides=(2, 4, 48, 288))
        self.assertFalse(a.is_contiguous("A"))
        a = Exporter((3, 2, 2), itemsize=2, strides=(16, 8, 4))
        self.assertFalse(a.is_contiguous("A"))
        a = Exporter((3, 2, 2), itemsize=2, strides=(4, 12, 24))
        self.assertFalse(a.is_contiguous("A"))

    def check_args(
        self, call_flags, shape, typekind, strides, length, bufsize, itemsize, offset=0
    ):
        if call_flags & 1:
            typekind_arg = typekind
        else:
            typekind_arg = None
        if call_flags & 2:
            strides_arg = strides
        else:
            strides_arg = None
        a = Exporter(shape, itemsize=itemsize, strides=strides_arg)
        self.assertEqual(sizeof(a._data), bufsize)
        self.assertEqual(a.data, ctypes.addressof(a._data) + offset)
        m = ArrayInterface(a)
        self.assertEqual(m.data, a.data)
        self.assertEqual(m.itemsize, itemsize)
        self.assertEqual(tuple(m.shape[0 : m.nd]), shape)
        self.assertEqual(tuple(m.strides[0 : m.nd]), strides)


class ArrayTest(unittest.TestCase):
    def __init__(self, *args, **kwds):
        unittest.TestCase.__init__(self, *args, **kwds)
        self.a = Array((20, 15), "i", 4)

    def setUp(self):
        # Every test starts with a zeroed array.
        memset(self.a.data, 0, sizeof(self.a._data))

    def test__addr_at(self):
        a = self.a
        self.assertEqual(a._addr_at((0, 0)), a.data)
        self.assertEqual(a._addr_at((0, 1)), a.data + 4)
        self.assertEqual(a._addr_at((1, 0)), a.data + 60)
        self.assertEqual(a._addr_at((1, 1)), a.data + 64)

    def test_indices(self):
        a = self.a
        self.assertEqual(a[0, 0], 0)
        self.assertEqual(a[19, 0], 0)
        self.assertEqual(a[0, 14], 0)
        self.assertEqual(a[19, 14], 0)
        self.assertEqual(a[5, 8], 0)
        a[0, 0] = 12
        a[5, 8] = 99
        self.assertEqual(a[0, 0], 12)
        self.assertEqual(a[5, 8], 99)
        self.assertRaises(IndexError, a.__getitem__, (-1, 0))
        self.assertRaises(IndexError, a.__getitem__, (0, -1))
        self.assertRaises(IndexError, a.__getitem__, (20, 0))
        self.assertRaises(IndexError, a.__getitem__, (0, 15))
        self.assertRaises(ValueError, a.__getitem__, 0)
        self.assertRaises(ValueError, a.__getitem__, (0, 0, 0))
        a = Array((3,), "i", 4)
        a[1] = 333
        self.assertEqual(a[1], 333)

    def test_typekind(self):
        a = Array((1,), "i", 4)
        self.assertTrue(a._ctype is c_int32)
        self.assertTrue(a._ctype_p is POINTER(c_int32))
        a = Array((1,), "u", 4)
        self.assertTrue(a._ctype is c_uint32)
        self.assertTrue(a._ctype_p is POINTER(c_uint32))
        a = Array((1,), "f", 4)  # float types unsupported: size system dependent
        ct = a._ctype
        self.assertTrue(issubclass(ct, ctypes.Array))
        self.assertEqual(sizeof(ct), 4)

    def test_itemsize(self):
        for size in [1, 2, 4, 8]:
            a = Array((1,), "i", size)
            ct = a._ctype
            self.assertTrue(issubclass(ct, ctypes._SimpleCData))
            self.assertEqual(sizeof(ct), size)

    def test_oddball_itemsize(self):
        for size in [3, 5, 6, 7, 9]:
            a = Array((1,), "i", size)
            ct = a._ctype
            self.assertTrue(issubclass(ct, ctypes.Array))
            self.assertEqual(sizeof(ct), size)

    def test_byteswapped(self):
        a = Array((1,), "u", 4, flags=(PAI_ALIGNED | PAI_WRITEABLE))
        ct = a._ctype
        self.assertTrue(ct is not c_uint32)
        if sys.byteorder == "little":
            self.assertTrue(ct is c_uint32.__ctype_be__)
        else:
            self.assertTrue(ct is c_uint32.__ctype_le__)
        i = 0xA0B0C0D
        n = c_uint32(i)
        a[0] = i
        self.assertEqual(a[0], i)
        self.assertEqual(a._data[0:4], cast(addressof(n), POINTER(c_uint8))[3:-1:-1])


if __name__ == "__main__":
    unittest.main()
