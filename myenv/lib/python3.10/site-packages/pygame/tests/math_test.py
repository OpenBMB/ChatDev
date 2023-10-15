import math
import platform
import unittest
from collections.abc import Collection, Sequence

import pygame.math
from pygame.math import Vector2, Vector3

IS_PYPY = "PyPy" == platform.python_implementation()


class MathModuleTest(unittest.TestCase):
    """Math module tests."""

    def test_lerp(self):
        result = pygame.math.lerp(10, 100, 0.5)  # 55.0
        self.assertAlmostEqual(result, 55.0)

        result = pygame.math.lerp(10, 100, 0.0)  # 10
        self.assertAlmostEqual(result, 10.0)

        result = pygame.math.lerp(10, 100, 1.0)  # 100
        self.assertAlmostEqual(result, 100.0)

        # Not enough args
        self.assertRaises(TypeError, pygame.math.lerp, 1)

        # Wrong arg type
        self.assertRaises(TypeError, pygame.math.lerp, "str", "str", "str")

        # Percent outside range [0, 1]
        self.assertRaises(ValueError, pygame.math.lerp, 10, 100, 1.1)
        self.assertRaises(ValueError, pygame.math.lerp, 10, 100, -0.5)

    def test_clamp(self):
        """Test clamp function."""

        # Int tests
        # Test going above max
        result = pygame.math.clamp(10, 1, 5)
        self.assertEqual(result, 5)
        # Test going below min
        result = pygame.math.clamp(-10, 1, 5)
        self.assertEqual(result, 1)
        # Test equal to max
        result = pygame.math.clamp(5, 1, 5)
        self.assertEqual(result, 5)
        # Test equal to min
        result = pygame.math.clamp(1, 1, 5)
        self.assertEqual(result, 1)
        # Test between min and max
        result = pygame.math.clamp(3, 1, 5)
        self.assertEqual(result, 3)

        # Float tests
        # Test going above max
        result = pygame.math.clamp(10.0, 1.12, 5.0)
        self.assertAlmostEqual(result, 5.0)
        # Test going below min
        result = pygame.math.clamp(-10.0, 1.12, 5.0)
        self.assertAlmostEqual(result, 1.12)
        # Test equal to max
        result = pygame.math.clamp(5.0, 1.12, 5.0)
        self.assertAlmostEqual(result, 5.0)
        # Test equal to min
        result = pygame.math.clamp(1.12, 1.12, 5.0)
        self.assertAlmostEqual(result, 1.12)
        # Test between min and max
        result = pygame.math.clamp(2.5, 1.12, 5.0)
        self.assertAlmostEqual(result, 2.5)

        # Error tests
        # Not enough args
        self.assertRaises(TypeError, pygame.math.clamp, 10)
        # Non numeric args
        self.assertRaises(TypeError, pygame.math.clamp, "hello", "py", "thon")


class Vector2TypeTest(unittest.TestCase):
    def setUp(self):
        self.zeroVec = Vector2()
        self.e1 = Vector2(1, 0)
        self.e2 = Vector2(0, 1)
        self.t1 = (1.2, 3.4)
        self.l1 = list(self.t1)
        self.v1 = Vector2(self.t1)
        self.t2 = (5.6, 7.8)
        self.l2 = list(self.t2)
        self.v2 = Vector2(self.t2)
        self.s1 = 5.6
        self.s2 = 7.8

    def testConstructionDefault(self):
        v = Vector2()
        self.assertEqual(v.x, 0.0)
        self.assertEqual(v.y, 0.0)

    def testConstructionScalar(self):
        v = Vector2(1)
        self.assertEqual(v.x, 1.0)
        self.assertEqual(v.y, 1.0)

    def testConstructionScalarKeywords(self):
        v = Vector2(x=1)
        self.assertEqual(v.x, 1.0)
        self.assertEqual(v.y, 1.0)

    def testConstructionKeywords(self):
        v = Vector2(x=1, y=2)
        self.assertEqual(v.x, 1.0)
        self.assertEqual(v.y, 2.0)

    def testConstructionXY(self):
        v = Vector2(1.2, 3.4)
        self.assertEqual(v.x, 1.2)
        self.assertEqual(v.y, 3.4)

    def testConstructionTuple(self):
        v = Vector2((1.2, 3.4))
        self.assertEqual(v.x, 1.2)
        self.assertEqual(v.y, 3.4)

    def testConstructionList(self):
        v = Vector2([1.2, 3.4])
        self.assertEqual(v.x, 1.2)
        self.assertEqual(v.y, 3.4)

    def testConstructionVector2(self):
        v = Vector2(Vector2(1.2, 3.4))
        self.assertEqual(v.x, 1.2)
        self.assertEqual(v.y, 3.4)

    def testAttributeAccess(self):
        tmp = self.v1.x
        self.assertEqual(tmp, self.v1.x)
        self.assertEqual(tmp, self.v1[0])
        tmp = self.v1.y
        self.assertEqual(tmp, self.v1.y)
        self.assertEqual(tmp, self.v1[1])
        self.v1.x = 3.141
        self.assertEqual(self.v1.x, 3.141)
        self.v1.y = 3.141
        self.assertEqual(self.v1.y, 3.141)

        def assign_nonfloat():
            v = Vector2()
            v.x = "spam"

        self.assertRaises(TypeError, assign_nonfloat)

    def test___round___basic(self):
        self.assertEqual(round(pygame.Vector2(0.0, 0.0)), pygame.Vector2(0.0, 0.0))
        self.assertEqual(type(round(pygame.Vector2(0.0, 0.0))), pygame.Vector2)
        self.assertEqual(
            round(pygame.Vector2(1.0, 1.0)), round(pygame.Vector2(1.0, 1.0))
        )
        self.assertEqual(
            round(pygame.Vector2(10.0, 10.0)), round(pygame.Vector2(10.0, 10.0))
        )
        self.assertEqual(
            round(pygame.Vector2(1000000000.0, 1000000000.0)),
            pygame.Vector2(1000000000.0, 1000000000.0),
        )
        self.assertEqual(round(pygame.Vector2(1e20, 1e20)), pygame.Vector2(1e20, 1e20))

        self.assertEqual(round(pygame.Vector2(-1.0, -1.0)), pygame.Vector2(-1.0, -1.0))
        self.assertEqual(
            round(pygame.Vector2(-10.0, -10.0)), pygame.Vector2(-10.0, -10.0)
        )
        self.assertEqual(
            round(pygame.Vector2(-1000000000.0, -1000000000.0)),
            pygame.Vector2(-1000000000.0, -1000000000.0),
        )
        self.assertEqual(
            round(pygame.Vector2(-1e20, -1e20)), pygame.Vector2(-1e20, -1e20)
        )

        self.assertEqual(round(pygame.Vector2(0.1, 0.1)), pygame.Vector2(0.0, 0.0))
        self.assertEqual(round(pygame.Vector2(1.1, 1.1)), pygame.Vector2(1.0, 1.0))
        self.assertEqual(round(pygame.Vector2(10.1, 10.1)), pygame.Vector2(10.0, 10.0))
        self.assertEqual(
            round(pygame.Vector2(1000000000.1, 1000000000.1)),
            pygame.Vector2(1000000000.0, 1000000000.0),
        )

        self.assertEqual(round(pygame.Vector2(-1.1, -1.1)), pygame.Vector2(-1.0, -1.0))
        self.assertEqual(
            round(pygame.Vector2(-10.1, -10.1)), pygame.Vector2(-10.0, -10.0)
        )
        self.assertEqual(
            round(pygame.Vector2(-1000000000.1, -1000000000.1)),
            pygame.Vector2(-1000000000.0, -1000000000.0),
        )

        self.assertEqual(round(pygame.Vector2(0.9, 0.9)), pygame.Vector2(1.0, 1.0))
        self.assertEqual(round(pygame.Vector2(9.9, 9.9)), pygame.Vector2(10.0, 10.0))
        self.assertEqual(
            round(pygame.Vector2(999999999.9, 999999999.9)),
            pygame.Vector2(1000000000.0, 1000000000.0),
        )

        self.assertEqual(round(pygame.Vector2(-0.9, -0.9)), pygame.Vector2(-1.0, -1.0))
        self.assertEqual(
            round(pygame.Vector2(-9.9, -9.9)), pygame.Vector2(-10.0, -10.0)
        )
        self.assertEqual(
            round(pygame.Vector2(-999999999.9, -999999999.9)),
            pygame.Vector2(-1000000000.0, -1000000000.0),
        )

        self.assertEqual(
            round(pygame.Vector2(-8.0, -8.0), -1), pygame.Vector2(-10.0, -10.0)
        )
        self.assertEqual(type(round(pygame.Vector2(-8.0, -8.0), -1)), pygame.Vector2)

        self.assertEqual(type(round(pygame.Vector2(-8.0, -8.0), 0)), pygame.Vector2)
        self.assertEqual(type(round(pygame.Vector2(-8.0, -8.0), 1)), pygame.Vector2)

        # Check even / odd rounding behaviour
        self.assertEqual(round(pygame.Vector2(5.5, 5.5)), pygame.Vector2(6, 6))
        self.assertEqual(round(pygame.Vector2(5.4, 5.4)), pygame.Vector2(5.0, 5.0))
        self.assertEqual(round(pygame.Vector2(5.6, 5.6)), pygame.Vector2(6.0, 6.0))
        self.assertEqual(round(pygame.Vector2(-5.5, -5.5)), pygame.Vector2(-6, -6))
        self.assertEqual(round(pygame.Vector2(-5.4, -5.4)), pygame.Vector2(-5, -5))
        self.assertEqual(round(pygame.Vector2(-5.6, -5.6)), pygame.Vector2(-6, -6))

        self.assertRaises(TypeError, round, pygame.Vector2(1.0, 1.0), 1.5)
        self.assertRaises(TypeError, round, pygame.Vector2(1.0, 1.0), "a")

    def testCopy(self):
        v_copy0 = Vector2(2004.0, 2022.0)
        v_copy1 = v_copy0.copy()
        self.assertEqual(v_copy0.x, v_copy1.x)
        self.assertEqual(v_copy0.y, v_copy1.y)

    def test_move_towards_basic(self):
        expected = Vector2(8.08, 2006.87)
        origin = Vector2(7.22, 2004.0)
        target = Vector2(12.30, 2021.0)
        change_ip = Vector2(7.22, 2004.0)

        change = origin.move_towards(target, 3)
        change_ip.move_towards_ip(target, 3)

        self.assertEqual(round(change.x, 2), expected.x)
        self.assertEqual(round(change.y, 2), expected.y)
        self.assertEqual(round(change_ip.x, 2), expected.x)
        self.assertEqual(round(change_ip.y, 2), expected.y)

    def test_move_towards_max_distance(self):
        expected = Vector2(12.30, 2021)
        origin = Vector2(7.22, 2004.0)
        target = Vector2(12.30, 2021.0)
        change_ip = Vector2(7.22, 2004.0)

        change = origin.move_towards(target, 25)
        change_ip.move_towards_ip(target, 25)

        self.assertEqual(round(change.x, 2), expected.x)
        self.assertEqual(round(change.y, 2), expected.y)
        self.assertEqual(round(change_ip.x, 2), expected.x)
        self.assertEqual(round(change_ip.y, 2), expected.y)

    def test_move_nowhere(self):
        expected = Vector2(7.22, 2004.0)
        origin = Vector2(7.22, 2004.0)
        target = Vector2(12.30, 2021.0)
        change_ip = Vector2(7.22, 2004.0)

        change = origin.move_towards(target, 0)
        change_ip.move_towards_ip(target, 0)

        self.assertEqual(round(change.x, 2), expected.x)
        self.assertEqual(round(change.y, 2), expected.y)
        self.assertEqual(round(change_ip.x, 2), expected.x)
        self.assertEqual(round(change_ip.y, 2), expected.y)

    def test_move_away(self):
        expected = Vector2(6.36, 2001.13)
        origin = Vector2(7.22, 2004.0)
        target = Vector2(12.30, 2021.0)
        change_ip = Vector2(7.22, 2004.0)

        change = origin.move_towards(target, -3)
        change_ip.move_towards_ip(target, -3)

        self.assertEqual(round(change.x, 2), expected.x)
        self.assertEqual(round(change.y, 2), expected.y)
        self.assertEqual(round(change_ip.x, 2), expected.x)
        self.assertEqual(round(change_ip.y, 2), expected.y)

    def test_move_towards_self(self):
        vec = Vector2(6.36, 2001.13)
        vec2 = vec.copy()
        for dist in (-3.54, -1, 0, 0.234, 12):
            self.assertEqual(vec.move_towards(vec2, dist), vec)
            vec2.move_towards_ip(vec, dist)
            self.assertEqual(vec, vec2)

    def test_move_towards_errors(self):
        def overpopulate():
            origin = Vector2(7.22, 2004.0)
            target = Vector2(12.30, 2021.0)
            origin.move_towards(target, 3, 2)

        def overpopulate_ip():
            origin = Vector2(7.22, 2004.0)
            target = Vector2(12.30, 2021.0)
            origin.move_towards_ip(target, 3, 2)

        def invalid_types1():
            origin = Vector2(7.22, 2004.0)
            target = Vector2(12.30, 2021.0)
            origin.move_towards(target, "novial")

        def invalid_types_ip1():
            origin = Vector2(7.22, 2004.0)
            target = Vector2(12.30, 2021.0)
            origin.move_towards_ip(target, "is")

        def invalid_types2():
            origin = Vector2(7.22, 2004.0)
            target = Vector2(12.30, 2021.0)
            origin.move_towards("kinda", 3)

        def invalid_types_ip2():
            origin = Vector2(7.22, 2004.0)
            target = Vector2(12.30, 2021.0)
            origin.move_towards_ip("cool", 3)

        self.assertRaises(TypeError, overpopulate)
        self.assertRaises(TypeError, overpopulate_ip)
        self.assertRaises(TypeError, invalid_types1)
        self.assertRaises(TypeError, invalid_types_ip1)
        self.assertRaises(TypeError, invalid_types2)
        self.assertRaises(TypeError, invalid_types_ip2)

    def testSequence(self):
        v = Vector2(1.2, 3.4)
        Vector2()[:]
        self.assertEqual(len(v), 2)
        self.assertEqual(v[0], 1.2)
        self.assertEqual(v[1], 3.4)
        self.assertRaises(IndexError, lambda: v[2])
        self.assertEqual(v[-1], 3.4)
        self.assertEqual(v[-2], 1.2)
        self.assertRaises(IndexError, lambda: v[-3])
        self.assertEqual(v[:], [1.2, 3.4])
        self.assertEqual(v[1:], [3.4])
        self.assertEqual(v[:1], [1.2])
        self.assertEqual(list(v), [1.2, 3.4])
        self.assertEqual(tuple(v), (1.2, 3.4))
        v[0] = 5.6
        v[1] = 7.8
        self.assertEqual(v.x, 5.6)
        self.assertEqual(v.y, 7.8)
        v[:] = [9.1, 11.12]
        self.assertEqual(v.x, 9.1)
        self.assertEqual(v.y, 11.12)

        def overpopulate():
            v = Vector2()
            v[:] = [1, 2, 3]

        self.assertRaises(ValueError, overpopulate)

        def underpopulate():
            v = Vector2()
            v[:] = [1]

        self.assertRaises(ValueError, underpopulate)

        def assign_nonfloat():
            v = Vector2()
            v[0] = "spam"

        self.assertRaises(TypeError, assign_nonfloat)

    def testExtendedSlicing(self):
        #  deletion
        def delSlice(vec, start=None, stop=None, step=None):
            if start is not None and stop is not None and step is not None:
                del vec[start:stop:step]
            elif start is not None and stop is None and step is not None:
                del vec[start::step]
            elif start is None and stop is None and step is not None:
                del vec[::step]

        v = Vector2(self.v1)
        self.assertRaises(TypeError, delSlice, v, None, None, 2)
        self.assertRaises(TypeError, delSlice, v, 1, None, 2)
        self.assertRaises(TypeError, delSlice, v, 1, 2, 1)

        #  assignment
        v = Vector2(self.v1)
        v[::2] = [-1]
        self.assertEqual(v, [-1, self.v1.y])
        v = Vector2(self.v1)
        v[::-2] = [10]
        self.assertEqual(v, [self.v1.x, 10])
        v = Vector2(self.v1)
        v[::-1] = v
        self.assertEqual(v, [self.v1.y, self.v1.x])
        a = Vector2(self.v1)
        b = Vector2(self.v1)
        c = Vector2(self.v1)
        a[1:2] = [2.2]
        b[slice(1, 2)] = [2.2]
        c[1:2:] = (2.2,)
        self.assertEqual(a, b)
        self.assertEqual(a, c)
        self.assertEqual(type(a), type(self.v1))
        self.assertEqual(type(b), type(self.v1))
        self.assertEqual(type(c), type(self.v1))

    def test_contains(self):
        c = Vector2(0, 1)

        # call __contains__ explicitly to test that it is defined
        self.assertTrue(c.__contains__(0))
        self.assertTrue(0 in c)
        self.assertTrue(1 in c)
        self.assertTrue(2 not in c)
        self.assertFalse(c.__contains__(2))

        self.assertRaises(TypeError, lambda: "string" in c)
        self.assertRaises(TypeError, lambda: 3 + 4j in c)

    def testAdd(self):
        v3 = self.v1 + self.v2
        self.assertTrue(isinstance(v3, type(self.v1)))
        self.assertEqual(v3.x, self.v1.x + self.v2.x)
        self.assertEqual(v3.y, self.v1.y + self.v2.y)
        v3 = self.v1 + self.t2
        self.assertTrue(isinstance(v3, type(self.v1)))
        self.assertEqual(v3.x, self.v1.x + self.t2[0])
        self.assertEqual(v3.y, self.v1.y + self.t2[1])
        v3 = self.v1 + self.l2
        self.assertTrue(isinstance(v3, type(self.v1)))
        self.assertEqual(v3.x, self.v1.x + self.l2[0])
        self.assertEqual(v3.y, self.v1.y + self.l2[1])
        v3 = self.t1 + self.v2
        self.assertTrue(isinstance(v3, type(self.v1)))
        self.assertEqual(v3.x, self.t1[0] + self.v2.x)
        self.assertEqual(v3.y, self.t1[1] + self.v2.y)
        v3 = self.l1 + self.v2
        self.assertTrue(isinstance(v3, type(self.v1)))
        self.assertEqual(v3.x, self.l1[0] + self.v2.x)
        self.assertEqual(v3.y, self.l1[1] + self.v2.y)

    def testSub(self):
        v3 = self.v1 - self.v2
        self.assertTrue(isinstance(v3, type(self.v1)))
        self.assertEqual(v3.x, self.v1.x - self.v2.x)
        self.assertEqual(v3.y, self.v1.y - self.v2.y)
        v3 = self.v1 - self.t2
        self.assertTrue(isinstance(v3, type(self.v1)))
        self.assertEqual(v3.x, self.v1.x - self.t2[0])
        self.assertEqual(v3.y, self.v1.y - self.t2[1])
        v3 = self.v1 - self.l2
        self.assertTrue(isinstance(v3, type(self.v1)))
        self.assertEqual(v3.x, self.v1.x - self.l2[0])
        self.assertEqual(v3.y, self.v1.y - self.l2[1])
        v3 = self.t1 - self.v2
        self.assertTrue(isinstance(v3, type(self.v1)))
        self.assertEqual(v3.x, self.t1[0] - self.v2.x)
        self.assertEqual(v3.y, self.t1[1] - self.v2.y)
        v3 = self.l1 - self.v2
        self.assertTrue(isinstance(v3, type(self.v1)))
        self.assertEqual(v3.x, self.l1[0] - self.v2.x)
        self.assertEqual(v3.y, self.l1[1] - self.v2.y)

    def testScalarMultiplication(self):
        v = self.s1 * self.v1
        self.assertTrue(isinstance(v, type(self.v1)))
        self.assertEqual(v.x, self.s1 * self.v1.x)
        self.assertEqual(v.y, self.s1 * self.v1.y)
        v = self.v1 * self.s2
        self.assertEqual(v.x, self.v1.x * self.s2)
        self.assertEqual(v.y, self.v1.y * self.s2)

    def testScalarDivision(self):
        v = self.v1 / self.s1
        self.assertTrue(isinstance(v, type(self.v1)))
        self.assertAlmostEqual(v.x, self.v1.x / self.s1)
        self.assertAlmostEqual(v.y, self.v1.y / self.s1)
        v = self.v1 // self.s2
        self.assertTrue(isinstance(v, type(self.v1)))
        self.assertEqual(v.x, self.v1.x // self.s2)
        self.assertEqual(v.y, self.v1.y // self.s2)

    def testBool(self):
        self.assertEqual(bool(self.zeroVec), False)
        self.assertEqual(bool(self.v1), True)
        self.assertTrue(not self.zeroVec)
        self.assertTrue(self.v1)

    def testUnary(self):
        v = +self.v1
        self.assertTrue(isinstance(v, type(self.v1)))
        self.assertEqual(v.x, self.v1.x)
        self.assertEqual(v.y, self.v1.y)
        self.assertNotEqual(id(v), id(self.v1))
        v = -self.v1
        self.assertTrue(isinstance(v, type(self.v1)))
        self.assertEqual(v.x, -self.v1.x)
        self.assertEqual(v.y, -self.v1.y)
        self.assertNotEqual(id(v), id(self.v1))

    def testCompare(self):
        int_vec = Vector2(3, -2)
        flt_vec = Vector2(3.0, -2.0)
        zero_vec = Vector2(0, 0)
        self.assertEqual(int_vec == flt_vec, True)
        self.assertEqual(int_vec != flt_vec, False)
        self.assertEqual(int_vec != zero_vec, True)
        self.assertEqual(flt_vec == zero_vec, False)
        self.assertEqual(int_vec == (3, -2), True)
        self.assertEqual(int_vec != (3, -2), False)
        self.assertEqual(int_vec != [0, 0], True)
        self.assertEqual(int_vec == [0, 0], False)
        self.assertEqual(int_vec != 5, True)
        self.assertEqual(int_vec == 5, False)
        self.assertEqual(int_vec != [3, -2, 0], True)
        self.assertEqual(int_vec == [3, -2, 0], False)

    def testStr(self):
        v = Vector2(1.2, 3.4)
        self.assertEqual(str(v), "[1.2, 3.4]")

    def testRepr(self):
        v = Vector2(1.2, 3.4)
        self.assertEqual(v.__repr__(), "<Vector2(1.2, 3.4)>")
        self.assertEqual(v, Vector2(v.__repr__()))

    def testIter(self):
        it = self.v1.__iter__()
        next_ = it.__next__
        self.assertEqual(next_(), self.v1[0])
        self.assertEqual(next_(), self.v1[1])
        self.assertRaises(StopIteration, lambda: next_())
        it1 = self.v1.__iter__()
        it2 = self.v1.__iter__()
        self.assertNotEqual(id(it1), id(it2))
        self.assertEqual(id(it1), id(it1.__iter__()))
        self.assertEqual(list(it1), list(it2))
        self.assertEqual(list(self.v1.__iter__()), self.l1)
        idx = 0
        for val in self.v1:
            self.assertEqual(val, self.v1[idx])
            idx += 1

    def test_rotate(self):
        v1 = Vector2(1, 0)
        v2 = v1.rotate(90)
        v3 = v1.rotate(90 + 360)
        self.assertEqual(v1.x, 1)
        self.assertEqual(v1.y, 0)
        self.assertEqual(v2.x, 0)
        self.assertEqual(v2.y, 1)
        self.assertEqual(v3.x, v2.x)
        self.assertEqual(v3.y, v2.y)
        v1 = Vector2(-1, -1)
        v2 = v1.rotate(-90)
        self.assertEqual(v2.x, -1)
        self.assertEqual(v2.y, 1)
        v2 = v1.rotate(360)
        self.assertEqual(v1.x, v2.x)
        self.assertEqual(v1.y, v2.y)
        v2 = v1.rotate(0)
        self.assertEqual(v1.x, v2.x)
        self.assertEqual(v1.y, v2.y)
        # issue 214
        self.assertEqual(Vector2(0, 1).rotate(359.99999999), Vector2(0, 1))

    def test_rotate_rad(self):
        tests = (
            ((1, 0), math.pi),
            ((1, 0), math.pi / 2),
            ((1, 0), -math.pi / 2),
            ((1, 0), math.pi / 4),
        )
        for initialVec, radians in tests:
            self.assertEqual(
                Vector2(initialVec).rotate_rad(radians),
                (math.cos(radians), math.sin(radians)),
            )

    def test_rotate_ip(self):
        v = Vector2(1, 0)
        self.assertEqual(v.rotate_ip(90), None)
        self.assertEqual(v.x, 0)
        self.assertEqual(v.y, 1)
        v = Vector2(-1, -1)
        v.rotate_ip(-90)
        self.assertEqual(v.x, -1)
        self.assertEqual(v.y, 1)

    def test_rotate_rad_ip(self):
        tests = (
            ((1, 0), math.pi),
            ((1, 0), math.pi / 2),
            ((1, 0), -math.pi / 2),
            ((1, 0), math.pi / 4),
        )
        for initialVec, radians in tests:
            vec = Vector2(initialVec)
            vec.rotate_rad_ip(radians)
            self.assertEqual(vec, (math.cos(radians), math.sin(radians)))

    def test_normalize(self):
        v = self.v1.normalize()
        # length is 1
        self.assertAlmostEqual(v.x * v.x + v.y * v.y, 1.0)
        # v1 is unchanged
        self.assertEqual(self.v1.x, self.l1[0])
        self.assertEqual(self.v1.y, self.l1[1])
        # v2 is parallel to v1
        self.assertAlmostEqual(self.v1.x * v.y - self.v1.y * v.x, 0.0)
        self.assertRaises(ValueError, lambda: self.zeroVec.normalize())

    def test_normalize_ip(self):
        v = +self.v1
        # v has length != 1 before normalizing
        self.assertNotEqual(v.x * v.x + v.y * v.y, 1.0)
        # inplace operations should return None
        self.assertEqual(v.normalize_ip(), None)
        # length is 1
        self.assertAlmostEqual(v.x * v.x + v.y * v.y, 1.0)
        # v2 is parallel to v1
        self.assertAlmostEqual(self.v1.x * v.y - self.v1.y * v.x, 0.0)
        self.assertRaises(ValueError, lambda: self.zeroVec.normalize_ip())

    def test_is_normalized(self):
        self.assertEqual(self.v1.is_normalized(), False)
        v = self.v1.normalize()
        self.assertEqual(v.is_normalized(), True)
        self.assertEqual(self.e2.is_normalized(), True)
        self.assertEqual(self.zeroVec.is_normalized(), False)

    def test_cross(self):
        self.assertEqual(
            self.v1.cross(self.v2), self.v1.x * self.v2.y - self.v1.y * self.v2.x
        )
        self.assertEqual(
            self.v1.cross(self.l2), self.v1.x * self.l2[1] - self.v1.y * self.l2[0]
        )
        self.assertEqual(
            self.v1.cross(self.t2), self.v1.x * self.t2[1] - self.v1.y * self.t2[0]
        )
        self.assertEqual(self.v1.cross(self.v2), -self.v2.cross(self.v1))
        self.assertEqual(self.v1.cross(self.v1), 0)

    def test_dot(self):
        self.assertAlmostEqual(
            self.v1.dot(self.v2), self.v1.x * self.v2.x + self.v1.y * self.v2.y
        )
        self.assertAlmostEqual(
            self.v1.dot(self.l2), self.v1.x * self.l2[0] + self.v1.y * self.l2[1]
        )
        self.assertAlmostEqual(
            self.v1.dot(self.t2), self.v1.x * self.t2[0] + self.v1.y * self.t2[1]
        )
        self.assertEqual(self.v1.dot(self.v2), self.v2.dot(self.v1))
        self.assertEqual(self.v1.dot(self.v2), self.v1 * self.v2)

    def test_angle_to(self):
        self.assertEqual(
            self.v1.rotate(self.v1.angle_to(self.v2)).normalize(), self.v2.normalize()
        )
        self.assertEqual(Vector2(1, 1).angle_to((-1, 1)), 90)
        self.assertEqual(Vector2(1, 0).angle_to((0, -1)), -90)
        self.assertEqual(Vector2(1, 0).angle_to((-1, 1)), 135)
        self.assertEqual(abs(Vector2(1, 0).angle_to((-1, 0))), 180)

    def test_scale_to_length(self):
        v = Vector2(1, 1)
        v.scale_to_length(2.5)
        self.assertEqual(v, Vector2(2.5, 2.5) / math.sqrt(2))
        self.assertRaises(ValueError, lambda: self.zeroVec.scale_to_length(1))
        self.assertEqual(v.scale_to_length(0), None)
        self.assertEqual(v, self.zeroVec)

    def test_length(self):
        self.assertEqual(Vector2(3, 4).length(), 5)
        self.assertEqual(Vector2(-3, 4).length(), 5)
        self.assertEqual(self.zeroVec.length(), 0)

    def test_length_squared(self):
        self.assertEqual(Vector2(3, 4).length_squared(), 25)
        self.assertEqual(Vector2(-3, 4).length_squared(), 25)
        self.assertEqual(self.zeroVec.length_squared(), 0)

    def test_reflect(self):
        v = Vector2(1, -1)
        n = Vector2(0, 1)
        self.assertEqual(v.reflect(n), Vector2(1, 1))
        self.assertEqual(v.reflect(3 * n), v.reflect(n))
        self.assertEqual(v.reflect(-v), -v)
        self.assertRaises(ValueError, lambda: v.reflect(self.zeroVec))

    def test_reflect_ip(self):
        v1 = Vector2(1, -1)
        v2 = Vector2(v1)
        n = Vector2(0, 1)
        self.assertEqual(v2.reflect_ip(n), None)
        self.assertEqual(v2, Vector2(1, 1))
        v2 = Vector2(v1)
        v2.reflect_ip(3 * n)
        self.assertEqual(v2, v1.reflect(n))
        v2 = Vector2(v1)
        v2.reflect_ip(-v1)
        self.assertEqual(v2, -v1)
        self.assertRaises(ValueError, lambda: v2.reflect_ip(Vector2()))

    def test_distance_to(self):
        diff = self.v1 - self.v2
        self.assertEqual(self.e1.distance_to(self.e2), math.sqrt(2))
        self.assertEqual(self.e1.distance_to((0, 1)), math.sqrt(2))
        self.assertEqual(self.e1.distance_to([0, 1]), math.sqrt(2))
        self.assertAlmostEqual(
            self.v1.distance_to(self.v2), math.sqrt(diff.x * diff.x + diff.y * diff.y)
        )
        self.assertAlmostEqual(
            self.v1.distance_to(self.t2), math.sqrt(diff.x * diff.x + diff.y * diff.y)
        )
        self.assertAlmostEqual(
            self.v1.distance_to(self.l2), math.sqrt(diff.x * diff.x + diff.y * diff.y)
        )
        self.assertEqual(self.v1.distance_to(self.v1), 0)
        self.assertEqual(self.v1.distance_to(self.t1), 0)
        self.assertEqual(self.v1.distance_to(self.l1), 0)
        self.assertEqual(self.v1.distance_to(self.t2), self.v2.distance_to(self.t1))
        self.assertEqual(self.v1.distance_to(self.l2), self.v2.distance_to(self.l1))
        self.assertEqual(self.v1.distance_to(self.v2), self.v2.distance_to(self.v1))

    def test_distance_squared_to(self):
        diff = self.v1 - self.v2
        self.assertEqual(self.e1.distance_squared_to(self.e2), 2)
        self.assertEqual(self.e1.distance_squared_to((0, 1)), 2)
        self.assertEqual(self.e1.distance_squared_to([0, 1]), 2)
        self.assertAlmostEqual(
            self.v1.distance_squared_to(self.v2), diff.x * diff.x + diff.y * diff.y
        )
        self.assertAlmostEqual(
            self.v1.distance_squared_to(self.t2), diff.x * diff.x + diff.y * diff.y
        )
        self.assertAlmostEqual(
            self.v1.distance_squared_to(self.l2), diff.x * diff.x + diff.y * diff.y
        )
        self.assertEqual(self.v1.distance_squared_to(self.v1), 0)
        self.assertEqual(self.v1.distance_squared_to(self.t1), 0)
        self.assertEqual(self.v1.distance_squared_to(self.l1), 0)
        self.assertEqual(
            self.v1.distance_squared_to(self.v2), self.v2.distance_squared_to(self.v1)
        )
        self.assertEqual(
            self.v1.distance_squared_to(self.t2), self.v2.distance_squared_to(self.t1)
        )
        self.assertEqual(
            self.v1.distance_squared_to(self.l2), self.v2.distance_squared_to(self.l1)
        )

    def test_update(self):
        v = Vector2(3, 4)
        v.update(0)
        self.assertEqual(v, Vector2((0, 0)))
        v.update(5, 1)
        self.assertEqual(v, Vector2(5, 1))
        v.update((4, 1))
        self.assertNotEqual(v, Vector2((5, 1)))

    def test_swizzle(self):
        self.assertEqual(self.v1.yx, (self.v1.y, self.v1.x))
        self.assertEqual(
            self.v1.xxyyxy,
            (self.v1.x, self.v1.x, self.v1.y, self.v1.y, self.v1.x, self.v1.y),
        )
        self.v1.xy = self.t2
        self.assertEqual(self.v1, self.t2)
        self.v1.yx = self.t2
        self.assertEqual(self.v1, (self.t2[1], self.t2[0]))
        self.assertEqual(type(self.v1), Vector2)

        def invalidSwizzleX():
            Vector2().xx = (1, 2)

        def invalidSwizzleY():
            Vector2().yy = (1, 2)

        self.assertRaises(AttributeError, invalidSwizzleX)
        self.assertRaises(AttributeError, invalidSwizzleY)

        def invalidAssignment():
            Vector2().xy = 3

        self.assertRaises(TypeError, invalidAssignment)

        def unicodeAttribute():
            getattr(Vector2(), "ä")

        self.assertRaises(AttributeError, unicodeAttribute)

    def test_swizzle_return_types(self):
        self.assertEqual(type(self.v1.x), float)
        self.assertEqual(type(self.v1.xy), Vector2)
        self.assertEqual(type(self.v1.xyx), Vector3)
        # but we don't have vector4 or above... so tuple.
        self.assertEqual(type(self.v1.xyxy), tuple)
        self.assertEqual(type(self.v1.xyxyx), tuple)

    def test_elementwise(self):
        v1 = self.v1
        v2 = self.v2
        s1 = self.s1
        s2 = self.s2
        # behaviour for "elementwise op scalar"
        self.assertEqual(v1.elementwise() + s1, (v1.x + s1, v1.y + s1))
        self.assertEqual(v1.elementwise() - s1, (v1.x - s1, v1.y - s1))
        self.assertEqual(v1.elementwise() * s2, (v1.x * s2, v1.y * s2))
        self.assertEqual(v1.elementwise() / s2, (v1.x / s2, v1.y / s2))
        self.assertEqual(v1.elementwise() // s1, (v1.x // s1, v1.y // s1))
        self.assertEqual(v1.elementwise() ** s1, (v1.x**s1, v1.y**s1))
        self.assertEqual(v1.elementwise() % s1, (v1.x % s1, v1.y % s1))
        self.assertEqual(v1.elementwise() > s1, v1.x > s1 and v1.y > s1)
        self.assertEqual(v1.elementwise() < s1, v1.x < s1 and v1.y < s1)
        self.assertEqual(v1.elementwise() == s1, v1.x == s1 and v1.y == s1)
        self.assertEqual(v1.elementwise() != s1, s1 not in [v1.x, v1.y])
        self.assertEqual(v1.elementwise() >= s1, v1.x >= s1 and v1.y >= s1)
        self.assertEqual(v1.elementwise() <= s1, v1.x <= s1 and v1.y <= s1)
        self.assertEqual(v1.elementwise() != s1, s1 not in [v1.x, v1.y])
        # behaviour for "scalar op elementwise"
        self.assertEqual(s1 + v1.elementwise(), (s1 + v1.x, s1 + v1.y))
        self.assertEqual(s1 - v1.elementwise(), (s1 - v1.x, s1 - v1.y))
        self.assertEqual(s1 * v1.elementwise(), (s1 * v1.x, s1 * v1.y))
        self.assertEqual(s1 / v1.elementwise(), (s1 / v1.x, s1 / v1.y))
        self.assertEqual(s1 // v1.elementwise(), (s1 // v1.x, s1 // v1.y))
        self.assertEqual(s1 ** v1.elementwise(), (s1**v1.x, s1**v1.y))
        self.assertEqual(s1 % v1.elementwise(), (s1 % v1.x, s1 % v1.y))
        self.assertEqual(s1 < v1.elementwise(), s1 < v1.x and s1 < v1.y)
        self.assertEqual(s1 > v1.elementwise(), s1 > v1.x and s1 > v1.y)
        self.assertEqual(s1 == v1.elementwise(), s1 == v1.x and s1 == v1.y)
        self.assertEqual(s1 != v1.elementwise(), s1 not in [v1.x, v1.y])
        self.assertEqual(s1 <= v1.elementwise(), s1 <= v1.x and s1 <= v1.y)
        self.assertEqual(s1 >= v1.elementwise(), s1 >= v1.x and s1 >= v1.y)
        self.assertEqual(s1 != v1.elementwise(), s1 not in [v1.x, v1.y])

        # behaviour for "elementwise op vector"
        self.assertEqual(type(v1.elementwise() * v2), type(v1))
        self.assertEqual(v1.elementwise() + v2, v1 + v2)
        self.assertEqual(v1.elementwise() - v2, v1 - v2)
        self.assertEqual(v1.elementwise() * v2, (v1.x * v2.x, v1.y * v2.y))
        self.assertEqual(v1.elementwise() / v2, (v1.x / v2.x, v1.y / v2.y))
        self.assertEqual(v1.elementwise() // v2, (v1.x // v2.x, v1.y // v2.y))
        self.assertEqual(v1.elementwise() ** v2, (v1.x**v2.x, v1.y**v2.y))
        self.assertEqual(v1.elementwise() % v2, (v1.x % v2.x, v1.y % v2.y))
        self.assertEqual(v1.elementwise() > v2, v1.x > v2.x and v1.y > v2.y)
        self.assertEqual(v1.elementwise() < v2, v1.x < v2.x and v1.y < v2.y)
        self.assertEqual(v1.elementwise() >= v2, v1.x >= v2.x and v1.y >= v2.y)
        self.assertEqual(v1.elementwise() <= v2, v1.x <= v2.x and v1.y <= v2.y)
        self.assertEqual(v1.elementwise() == v2, v1.x == v2.x and v1.y == v2.y)
        self.assertEqual(v1.elementwise() != v2, v1.x != v2.x and v1.y != v2.y)
        # behaviour for "vector op elementwise"
        self.assertEqual(v2 + v1.elementwise(), v2 + v1)
        self.assertEqual(v2 - v1.elementwise(), v2 - v1)
        self.assertEqual(v2 * v1.elementwise(), (v2.x * v1.x, v2.y * v1.y))
        self.assertEqual(v2 / v1.elementwise(), (v2.x / v1.x, v2.y / v1.y))
        self.assertEqual(v2 // v1.elementwise(), (v2.x // v1.x, v2.y // v1.y))
        self.assertEqual(v2 ** v1.elementwise(), (v2.x**v1.x, v2.y**v1.y))
        self.assertEqual(v2 % v1.elementwise(), (v2.x % v1.x, v2.y % v1.y))
        self.assertEqual(v2 < v1.elementwise(), v2.x < v1.x and v2.y < v1.y)
        self.assertEqual(v2 > v1.elementwise(), v2.x > v1.x and v2.y > v1.y)
        self.assertEqual(v2 <= v1.elementwise(), v2.x <= v1.x and v2.y <= v1.y)
        self.assertEqual(v2 >= v1.elementwise(), v2.x >= v1.x and v2.y >= v1.y)
        self.assertEqual(v2 == v1.elementwise(), v2.x == v1.x and v2.y == v1.y)
        self.assertEqual(v2 != v1.elementwise(), v2.x != v1.x and v2.y != v1.y)

        # behaviour for "elementwise op elementwise"
        self.assertEqual(v2.elementwise() + v1.elementwise(), v2 + v1)
        self.assertEqual(v2.elementwise() - v1.elementwise(), v2 - v1)
        self.assertEqual(
            v2.elementwise() * v1.elementwise(), (v2.x * v1.x, v2.y * v1.y)
        )
        self.assertEqual(
            v2.elementwise() / v1.elementwise(), (v2.x / v1.x, v2.y / v1.y)
        )
        self.assertEqual(
            v2.elementwise() // v1.elementwise(), (v2.x // v1.x, v2.y // v1.y)
        )
        self.assertEqual(
            v2.elementwise() ** v1.elementwise(), (v2.x**v1.x, v2.y**v1.y)
        )
        self.assertEqual(
            v2.elementwise() % v1.elementwise(), (v2.x % v1.x, v2.y % v1.y)
        )
        self.assertEqual(
            v2.elementwise() < v1.elementwise(), v2.x < v1.x and v2.y < v1.y
        )
        self.assertEqual(
            v2.elementwise() > v1.elementwise(), v2.x > v1.x and v2.y > v1.y
        )
        self.assertEqual(
            v2.elementwise() <= v1.elementwise(), v2.x <= v1.x and v2.y <= v1.y
        )
        self.assertEqual(
            v2.elementwise() >= v1.elementwise(), v2.x >= v1.x and v2.y >= v1.y
        )
        self.assertEqual(
            v2.elementwise() == v1.elementwise(), v2.x == v1.x and v2.y == v1.y
        )
        self.assertEqual(
            v2.elementwise() != v1.elementwise(), v2.x != v1.x and v2.y != v1.y
        )

        # other behaviour
        self.assertEqual(abs(v1.elementwise()), (abs(v1.x), abs(v1.y)))
        self.assertEqual(-v1.elementwise(), -v1)
        self.assertEqual(+v1.elementwise(), +v1)
        self.assertEqual(bool(v1.elementwise()), bool(v1))
        self.assertEqual(bool(Vector2().elementwise()), bool(Vector2()))
        self.assertEqual(self.zeroVec.elementwise() ** 0, (1, 1))
        self.assertRaises(ValueError, lambda: pow(Vector2(-1, 0).elementwise(), 1.2))
        self.assertRaises(ZeroDivisionError, lambda: self.zeroVec.elementwise() ** -1)
        self.assertRaises(ZeroDivisionError, lambda: self.zeroVec.elementwise() ** -1)
        self.assertRaises(ZeroDivisionError, lambda: Vector2(1, 1).elementwise() / 0)
        self.assertRaises(ZeroDivisionError, lambda: Vector2(1, 1).elementwise() // 0)
        self.assertRaises(ZeroDivisionError, lambda: Vector2(1, 1).elementwise() % 0)
        self.assertRaises(
            ZeroDivisionError, lambda: Vector2(1, 1).elementwise() / self.zeroVec
        )
        self.assertRaises(
            ZeroDivisionError, lambda: Vector2(1, 1).elementwise() // self.zeroVec
        )
        self.assertRaises(
            ZeroDivisionError, lambda: Vector2(1, 1).elementwise() % self.zeroVec
        )
        self.assertRaises(ZeroDivisionError, lambda: 2 / self.zeroVec.elementwise())
        self.assertRaises(ZeroDivisionError, lambda: 2 // self.zeroVec.elementwise())
        self.assertRaises(ZeroDivisionError, lambda: 2 % self.zeroVec.elementwise())

    def test_slerp(self):
        self.assertRaises(ValueError, lambda: self.zeroVec.slerp(self.v1, 0.5))
        self.assertRaises(ValueError, lambda: self.v1.slerp(self.zeroVec, 0.5))
        self.assertRaises(ValueError, lambda: self.zeroVec.slerp(self.zeroVec, 0.5))
        v1 = Vector2(1, 0)
        v2 = Vector2(0, 1)
        steps = 10
        angle_step = v1.angle_to(v2) / steps
        for i, u in ((i, v1.slerp(v2, i / float(steps))) for i in range(steps + 1)):
            self.assertAlmostEqual(u.length(), 1)
            self.assertAlmostEqual(v1.angle_to(u), i * angle_step)
        self.assertEqual(u, v2)

        v1 = Vector2(100, 0)
        v2 = Vector2(0, 10)
        radial_factor = v2.length() / v1.length()
        for i, u in ((i, v1.slerp(v2, -i / float(steps))) for i in range(steps + 1)):
            self.assertAlmostEqual(
                u.length(),
                (v2.length() - v1.length()) * (float(i) / steps) + v1.length(),
            )
        self.assertEqual(u, v2)
        self.assertEqual(v1.slerp(v1, 0.5), v1)
        self.assertEqual(v2.slerp(v2, 0.5), v2)
        self.assertRaises(ValueError, lambda: v1.slerp(-v1, 0.5))

    def test_lerp(self):
        v1 = Vector2(0, 0)
        v2 = Vector2(10, 10)
        self.assertEqual(v1.lerp(v2, 0.5), (5, 5))
        self.assertRaises(ValueError, lambda: v1.lerp(v2, 2.5))

        v1 = Vector2(-10, -5)
        v2 = Vector2(10, 10)
        self.assertEqual(v1.lerp(v2, 0.5), (0, 2.5))

    def test_polar(self):
        v = Vector2()
        v.from_polar(self.v1.as_polar())
        self.assertEqual(self.v1, v)
        self.assertEqual(self.v1, Vector2.from_polar(self.v1.as_polar()))
        self.assertEqual(self.e1.as_polar(), (1, 0))
        self.assertEqual(self.e2.as_polar(), (1, 90))
        self.assertEqual((2 * self.e2).as_polar(), (2, 90))
        self.assertRaises(TypeError, lambda: v.from_polar((None, None)))
        self.assertRaises(TypeError, lambda: v.from_polar("ab"))
        self.assertRaises(TypeError, lambda: v.from_polar((None, 1)))
        self.assertRaises(TypeError, lambda: v.from_polar((1, 2, 3)))
        self.assertRaises(TypeError, lambda: v.from_polar((1,)))
        self.assertRaises(TypeError, lambda: v.from_polar(1, 2))
        self.assertRaises(TypeError, lambda: Vector2.from_polar((None, None)))
        self.assertRaises(TypeError, lambda: Vector2.from_polar("ab"))
        self.assertRaises(TypeError, lambda: Vector2.from_polar((None, 1)))
        self.assertRaises(TypeError, lambda: Vector2.from_polar((1, 2, 3)))
        self.assertRaises(TypeError, lambda: Vector2.from_polar((1,)))
        self.assertRaises(TypeError, lambda: Vector2.from_polar(1, 2))
        v.from_polar((0.5, 90))
        self.assertEqual(v, 0.5 * self.e2)
        self.assertEqual(Vector2.from_polar((0.5, 90)), 0.5 * self.e2)
        self.assertEqual(Vector2.from_polar((0.5, 90)), v)
        v.from_polar((1, 0))
        self.assertEqual(v, self.e1)
        self.assertEqual(Vector2.from_polar((1, 0)), self.e1)
        self.assertEqual(Vector2.from_polar((1, 0)), v)

    def test_subclass_operation(self):
        class Vector(pygame.math.Vector2):
            pass

        vec = Vector()

        vec_a = Vector(2, 0)
        vec_b = Vector(0, 1)

        vec_a + vec_b
        vec_a *= 2

    def test_project_v2_onto_x_axis(self):
        """Project onto x-axis, e.g. get the component pointing in the x-axis direction."""
        # arrange
        v = Vector2(2, 2)
        x_axis = Vector2(10, 0)

        # act
        actual = v.project(x_axis)

        # assert
        self.assertEqual(v.x, actual.x)
        self.assertEqual(0, actual.y)

    def test_project_v2_onto_y_axis(self):
        """Project onto y-axis, e.g. get the component pointing in the y-axis direction."""
        # arrange
        v = Vector2(2, 2)
        y_axis = Vector2(0, 100)

        # act
        actual = v.project(y_axis)

        # assert
        self.assertEqual(0, actual.x)
        self.assertEqual(v.y, actual.y)

    def test_project_v2_onto_other(self):
        """Project onto other vector."""
        # arrange
        v = Vector2(2, 3)
        other = Vector2(3, 5)

        # act
        actual = v.project(other)

        # assert
        expected = v.dot(other) / other.dot(other) * other
        self.assertEqual(expected.x, actual.x)
        self.assertEqual(expected.y, actual.y)

    def test_project_v2_onto_other_as_tuple(self):
        """Project onto other tuple as vector."""
        # arrange
        v = Vector2(2, 3)
        other = Vector2(3, 5)

        # act
        actual = v.project(tuple(other))

        # assert
        expected = v.dot(other) / other.dot(other) * other
        self.assertEqual(expected.x, actual.x)
        self.assertEqual(expected.y, actual.y)

    def test_project_v2_onto_other_as_list(self):
        """Project onto other list as vector."""
        # arrange
        v = Vector2(2, 3)
        other = Vector2(3, 5)

        # act
        actual = v.project(list(other))

        # assert
        expected = v.dot(other) / other.dot(other) * other
        self.assertEqual(expected.x, actual.x)
        self.assertEqual(expected.y, actual.y)

    def test_project_v2_raises_if_other_has_zero_length(self):
        """Check if exception is raise when projected on vector has zero length."""
        # arrange
        v = Vector2(2, 3)
        other = Vector2(0, 0)

        # act / assert
        self.assertRaises(ValueError, v.project, other)

    def test_project_v2_raises_if_other_is_not_iterable(self):
        """Check if exception is raise when projected on vector is not iterable."""
        # arrange
        v = Vector2(2, 3)
        other = 10

        # act / assert
        self.assertRaises(TypeError, v.project, other)

    def test_collection_abc(self):
        v = Vector2(3, 4)
        self.assertTrue(isinstance(v, Collection))
        self.assertFalse(isinstance(v, Sequence))

    def test_clamp_mag_v2_max(self):
        v1 = Vector2(7, 2)
        v2 = v1.clamp_magnitude(5)
        v3 = v1.clamp_magnitude(0, 5)
        self.assertEqual(v2, v3)

        v1.clamp_magnitude_ip(5)
        self.assertEqual(v1, v2)

        v1.clamp_magnitude_ip(0, 5)
        self.assertEqual(v1, v2)

        expected_v2 = Vector2(4.807619738204116, 1.3736056394868903)
        self.assertEqual(expected_v2, v2)

    def test_clamp_mag_v2_min(self):
        v1 = Vector2(1, 2)
        v2 = v1.clamp_magnitude(3, 5)
        v1.clamp_magnitude_ip(3, 5)
        expected_v2 = Vector2(1.3416407864998738, 2.6832815729997477)
        self.assertEqual(expected_v2, v2)
        self.assertEqual(expected_v2, v1)

    def test_clamp_mag_v2_no_change(self):
        v1 = Vector2(1, 2)
        for args in (
            (1, 6),
            (1.12, 3.55),
            (0.93, 2.83),
            (7.6,),
        ):
            with self.subTest(args=args):
                v2 = v1.clamp_magnitude(*args)
                v1.clamp_magnitude_ip(*args)
                self.assertEqual(v1, v2)
                self.assertEqual(v1, Vector2(1, 2))

    def test_clamp_mag_v2_edge_cases(self):
        v1 = Vector2(1, 2)
        v2 = v1.clamp_magnitude(6, 6)
        v1.clamp_magnitude_ip(6, 6)
        self.assertEqual(v1, v2)
        self.assertAlmostEqual(v1.length(), 6)

        v2 = v1.clamp_magnitude(0)
        v1.clamp_magnitude_ip(0, 0)
        self.assertEqual(v1, v2)
        self.assertEqual(v1, Vector2())

    def test_clamp_mag_v2_errors(self):
        v1 = Vector2(1, 2)
        for invalid_args in (
            ("foo", "bar"),
            (1, 2, 3),
            (342.234, "test"),
        ):
            with self.subTest(invalid_args=invalid_args):
                self.assertRaises(TypeError, v1.clamp_magnitude, *invalid_args)
                self.assertRaises(TypeError, v1.clamp_magnitude_ip, *invalid_args)

        for invalid_args in (
            (-1,),
            (4, 3),  # min > max
            (-4, 10),
            (-4, -2),
        ):
            with self.subTest(invalid_args=invalid_args):
                self.assertRaises(ValueError, v1.clamp_magnitude, *invalid_args)
                self.assertRaises(ValueError, v1.clamp_magnitude_ip, *invalid_args)

        # 0 vector
        v2 = Vector2()
        self.assertRaises(ValueError, v2.clamp_magnitude, 3)
        self.assertRaises(ValueError, v2.clamp_magnitude_ip, 4)

    def test_subclassing_v2(self):
        """Check if Vector2 is subclassable"""
        v = Vector2(4, 2)

        class TestVector(Vector2):
            def supermariobrosiscool(self):
                return 722

        other = TestVector(4, 1)

        self.assertEqual(other.supermariobrosiscool(), 722)
        self.assertNotEqual(type(v), TestVector)
        self.assertNotEqual(type(v), type(other.copy()))
        self.assertEqual(TestVector, type(other.reflect(v)))
        self.assertEqual(TestVector, type(other.lerp(v, 1)))
        self.assertEqual(TestVector, type(other.slerp(v, 1)))
        self.assertEqual(TestVector, type(other.rotate(5)))
        self.assertEqual(TestVector, type(other.rotate_rad(5)))
        self.assertEqual(TestVector, type(other.project(v)))
        self.assertEqual(TestVector, type(other.move_towards(v, 5)))
        self.assertEqual(TestVector, type(other.clamp_magnitude(5)))
        self.assertEqual(TestVector, type(other.clamp_magnitude(1, 5)))
        self.assertEqual(TestVector, type(other.elementwise() + other))

        other1 = TestVector(4, 2)

        self.assertEqual(type(other + other1), TestVector)
        self.assertEqual(type(other - other1), TestVector)
        self.assertEqual(type(other * 3), TestVector)
        self.assertEqual(type(other / 3), TestVector)
        self.assertEqual(type(other.elementwise() ** 3), TestVector)


class Vector3TypeTest(unittest.TestCase):
    def setUp(self):
        self.zeroVec = Vector3()
        self.e1 = Vector3(1, 0, 0)
        self.e2 = Vector3(0, 1, 0)
        self.e3 = Vector3(0, 0, 1)
        self.t1 = (1.2, 3.4, 9.6)
        self.l1 = list(self.t1)
        self.v1 = Vector3(self.t1)
        self.t2 = (5.6, 7.8, 2.1)
        self.l2 = list(self.t2)
        self.v2 = Vector3(self.t2)
        self.s1 = 5.6
        self.s2 = 7.8

    def testConstructionDefault(self):
        v = Vector3()
        self.assertEqual(v.x, 0.0)
        self.assertEqual(v.y, 0.0)
        self.assertEqual(v.z, 0.0)

    def testConstructionXYZ(self):
        v = Vector3(1.2, 3.4, 9.6)
        self.assertEqual(v.x, 1.2)
        self.assertEqual(v.y, 3.4)
        self.assertEqual(v.z, 9.6)

    def testConstructionTuple(self):
        v = Vector3((1.2, 3.4, 9.6))
        self.assertEqual(v.x, 1.2)
        self.assertEqual(v.y, 3.4)
        self.assertEqual(v.z, 9.6)

    def testConstructionList(self):
        v = Vector3([1.2, 3.4, -9.6])
        self.assertEqual(v.x, 1.2)
        self.assertEqual(v.y, 3.4)
        self.assertEqual(v.z, -9.6)

    def testConstructionVector3(self):
        v = Vector3(Vector3(1.2, 3.4, -9.6))
        self.assertEqual(v.x, 1.2)
        self.assertEqual(v.y, 3.4)
        self.assertEqual(v.z, -9.6)

    def testConstructionScalar(self):
        v = Vector3(1)
        self.assertEqual(v.x, 1.0)
        self.assertEqual(v.y, 1.0)
        self.assertEqual(v.z, 1.0)

    def testConstructionScalarKeywords(self):
        v = Vector3(x=1)
        self.assertEqual(v.x, 1.0)
        self.assertEqual(v.y, 1.0)
        self.assertEqual(v.z, 1.0)

    def testConstructionKeywords(self):
        v = Vector3(x=1, y=2, z=3)
        self.assertEqual(v.x, 1.0)
        self.assertEqual(v.y, 2.0)
        self.assertEqual(v.z, 3.0)

    def testConstructionMissing(self):
        self.assertRaises(ValueError, Vector3, 1, 2)
        self.assertRaises(ValueError, Vector3, x=1, y=2)

    def testAttributeAccess(self):
        tmp = self.v1.x
        self.assertEqual(tmp, self.v1.x)
        self.assertEqual(tmp, self.v1[0])
        tmp = self.v1.y
        self.assertEqual(tmp, self.v1.y)
        self.assertEqual(tmp, self.v1[1])
        tmp = self.v1.z
        self.assertEqual(tmp, self.v1.z)
        self.assertEqual(tmp, self.v1[2])
        self.v1.x = 3.141
        self.assertEqual(self.v1.x, 3.141)
        self.v1.y = 3.141
        self.assertEqual(self.v1.y, 3.141)
        self.v1.z = 3.141
        self.assertEqual(self.v1.z, 3.141)

        def assign_nonfloat():
            v = Vector2()
            v.x = "spam"

        self.assertRaises(TypeError, assign_nonfloat)

    def testCopy(self):
        v_copy0 = Vector3(2014.0, 2032.0, 2076.0)
        v_copy1 = v_copy0.copy()
        self.assertEqual(v_copy0.x, v_copy1.x)
        self.assertEqual(v_copy0.y, v_copy1.y)
        self.assertEqual(v_copy0.z, v_copy1.z)

    def testSequence(self):
        v = Vector3(1.2, 3.4, -9.6)
        self.assertEqual(len(v), 3)
        self.assertEqual(v[0], 1.2)
        self.assertEqual(v[1], 3.4)
        self.assertEqual(v[2], -9.6)
        self.assertRaises(IndexError, lambda: v[3])
        self.assertEqual(v[-1], -9.6)
        self.assertEqual(v[-2], 3.4)
        self.assertEqual(v[-3], 1.2)
        self.assertRaises(IndexError, lambda: v[-4])
        self.assertEqual(v[:], [1.2, 3.4, -9.6])
        self.assertEqual(v[1:], [3.4, -9.6])
        self.assertEqual(v[:1], [1.2])
        self.assertEqual(v[:-1], [1.2, 3.4])
        self.assertEqual(v[1:2], [3.4])
        self.assertEqual(list(v), [1.2, 3.4, -9.6])
        self.assertEqual(tuple(v), (1.2, 3.4, -9.6))
        v[0] = 5.6
        v[1] = 7.8
        v[2] = -2.1
        self.assertEqual(v.x, 5.6)
        self.assertEqual(v.y, 7.8)
        self.assertEqual(v.z, -2.1)
        v[:] = [9.1, 11.12, -13.41]
        self.assertEqual(v.x, 9.1)
        self.assertEqual(v.y, 11.12)
        self.assertEqual(v.z, -13.41)

        def overpopulate():
            v = Vector3()
            v[:] = [1, 2, 3, 4]

        self.assertRaises(ValueError, overpopulate)

        def underpopulate():
            v = Vector3()
            v[:] = [1]

        self.assertRaises(ValueError, underpopulate)

        def assign_nonfloat():
            v = Vector2()
            v[0] = "spam"

        self.assertRaises(TypeError, assign_nonfloat)

    def testExtendedSlicing(self):
        #  deletion
        def delSlice(vec, start=None, stop=None, step=None):
            if start is not None and stop is not None and step is not None:
                del vec[start:stop:step]
            elif start is not None and stop is None and step is not None:
                del vec[start::step]
            elif start is None and stop is None and step is not None:
                del vec[::step]

        v = Vector3(self.v1)
        self.assertRaises(TypeError, delSlice, v, None, None, 2)
        self.assertRaises(TypeError, delSlice, v, 1, None, 2)
        self.assertRaises(TypeError, delSlice, v, 1, 2, 1)

        #  assignment
        v = Vector3(self.v1)
        v[::2] = [-1.1, -2.2]
        self.assertEqual(v, [-1.1, self.v1.y, -2.2])
        v = Vector3(self.v1)
        v[::-2] = [10, 20]
        self.assertEqual(v, [20, self.v1.y, 10])
        v = Vector3(self.v1)
        v[::-1] = v
        self.assertEqual(v, [self.v1.z, self.v1.y, self.v1.x])
        a = Vector3(self.v1)
        b = Vector3(self.v1)
        c = Vector3(self.v1)
        a[1:2] = [2.2]
        b[slice(1, 2)] = [2.2]
        c[1:2:] = (2.2,)
        self.assertEqual(a, b)
        self.assertEqual(a, c)
        self.assertEqual(type(a), type(self.v1))
        self.assertEqual(type(b), type(self.v1))
        self.assertEqual(type(c), type(self.v1))

    def test_contains(self):
        c = Vector3(0, 1, 2)

        # call __contains__ explicitly to test that it is defined
        self.assertTrue(c.__contains__(0))
        self.assertTrue(0 in c)
        self.assertTrue(1 in c)
        self.assertTrue(2 in c)
        self.assertTrue(3 not in c)
        self.assertFalse(c.__contains__(10))

        self.assertRaises(TypeError, lambda: "string" in c)
        self.assertRaises(TypeError, lambda: 3 + 4j in c)

    def testAdd(self):
        v3 = self.v1 + self.v2
        self.assertTrue(isinstance(v3, type(self.v1)))
        self.assertEqual(v3.x, self.v1.x + self.v2.x)
        self.assertEqual(v3.y, self.v1.y + self.v2.y)
        self.assertEqual(v3.z, self.v1.z + self.v2.z)
        v3 = self.v1 + self.t2
        self.assertTrue(isinstance(v3, type(self.v1)))
        self.assertEqual(v3.x, self.v1.x + self.t2[0])
        self.assertEqual(v3.y, self.v1.y + self.t2[1])
        self.assertEqual(v3.z, self.v1.z + self.t2[2])
        v3 = self.v1 + self.l2
        self.assertTrue(isinstance(v3, type(self.v1)))
        self.assertEqual(v3.x, self.v1.x + self.l2[0])
        self.assertEqual(v3.y, self.v1.y + self.l2[1])
        self.assertEqual(v3.z, self.v1.z + self.l2[2])
        v3 = self.t1 + self.v2
        self.assertTrue(isinstance(v3, type(self.v1)))
        self.assertEqual(v3.x, self.t1[0] + self.v2.x)
        self.assertEqual(v3.y, self.t1[1] + self.v2.y)
        self.assertEqual(v3.z, self.t1[2] + self.v2.z)
        v3 = self.l1 + self.v2
        self.assertTrue(isinstance(v3, type(self.v1)))
        self.assertEqual(v3.x, self.l1[0] + self.v2.x)
        self.assertEqual(v3.y, self.l1[1] + self.v2.y)
        self.assertEqual(v3.z, self.l1[2] + self.v2.z)

    def testSub(self):
        v3 = self.v1 - self.v2
        self.assertTrue(isinstance(v3, type(self.v1)))
        self.assertEqual(v3.x, self.v1.x - self.v2.x)
        self.assertEqual(v3.y, self.v1.y - self.v2.y)
        self.assertEqual(v3.z, self.v1.z - self.v2.z)
        v3 = self.v1 - self.t2
        self.assertTrue(isinstance(v3, type(self.v1)))
        self.assertEqual(v3.x, self.v1.x - self.t2[0])
        self.assertEqual(v3.y, self.v1.y - self.t2[1])
        self.assertEqual(v3.z, self.v1.z - self.t2[2])
        v3 = self.v1 - self.l2
        self.assertTrue(isinstance(v3, type(self.v1)))
        self.assertEqual(v3.x, self.v1.x - self.l2[0])
        self.assertEqual(v3.y, self.v1.y - self.l2[1])
        self.assertEqual(v3.z, self.v1.z - self.l2[2])
        v3 = self.t1 - self.v2
        self.assertTrue(isinstance(v3, type(self.v1)))
        self.assertEqual(v3.x, self.t1[0] - self.v2.x)
        self.assertEqual(v3.y, self.t1[1] - self.v2.y)
        self.assertEqual(v3.z, self.t1[2] - self.v2.z)
        v3 = self.l1 - self.v2
        self.assertTrue(isinstance(v3, type(self.v1)))
        self.assertEqual(v3.x, self.l1[0] - self.v2.x)
        self.assertEqual(v3.y, self.l1[1] - self.v2.y)
        self.assertEqual(v3.z, self.l1[2] - self.v2.z)

    def testScalarMultiplication(self):
        v = self.s1 * self.v1
        self.assertTrue(isinstance(v, type(self.v1)))
        self.assertEqual(v.x, self.s1 * self.v1.x)
        self.assertEqual(v.y, self.s1 * self.v1.y)
        self.assertEqual(v.z, self.s1 * self.v1.z)
        v = self.v1 * self.s2
        self.assertEqual(v.x, self.v1.x * self.s2)
        self.assertEqual(v.y, self.v1.y * self.s2)
        self.assertEqual(v.z, self.v1.z * self.s2)

    def testScalarDivision(self):
        v = self.v1 / self.s1
        self.assertTrue(isinstance(v, type(self.v1)))
        self.assertAlmostEqual(v.x, self.v1.x / self.s1)
        self.assertAlmostEqual(v.y, self.v1.y / self.s1)
        self.assertAlmostEqual(v.z, self.v1.z / self.s1)
        v = self.v1 // self.s2
        self.assertTrue(isinstance(v, type(self.v1)))
        self.assertEqual(v.x, self.v1.x // self.s2)
        self.assertEqual(v.y, self.v1.y // self.s2)
        self.assertEqual(v.z, self.v1.z // self.s2)

    def testBool(self):
        self.assertEqual(bool(self.zeroVec), False)
        self.assertEqual(bool(self.v1), True)
        self.assertTrue(not self.zeroVec)
        self.assertTrue(self.v1)

    def testUnary(self):
        v = +self.v1
        self.assertTrue(isinstance(v, type(self.v1)))
        self.assertEqual(v.x, self.v1.x)
        self.assertEqual(v.y, self.v1.y)
        self.assertEqual(v.z, self.v1.z)
        self.assertNotEqual(id(v), id(self.v1))
        v = -self.v1
        self.assertTrue(isinstance(v, type(self.v1)))
        self.assertEqual(v.x, -self.v1.x)
        self.assertEqual(v.y, -self.v1.y)
        self.assertEqual(v.z, -self.v1.z)
        self.assertNotEqual(id(v), id(self.v1))

    def testCompare(self):
        int_vec = Vector3(3, -2, 13)
        flt_vec = Vector3(3.0, -2.0, 13.0)
        zero_vec = Vector3(0, 0, 0)
        self.assertEqual(int_vec == flt_vec, True)
        self.assertEqual(int_vec != flt_vec, False)
        self.assertEqual(int_vec != zero_vec, True)
        self.assertEqual(flt_vec == zero_vec, False)
        self.assertEqual(int_vec == (3, -2, 13), True)
        self.assertEqual(int_vec != (3, -2, 13), False)
        self.assertEqual(int_vec != [0, 0], True)
        self.assertEqual(int_vec == [0, 0], False)
        self.assertEqual(int_vec != 5, True)
        self.assertEqual(int_vec == 5, False)
        self.assertEqual(int_vec != [3, -2, 0, 1], True)
        self.assertEqual(int_vec == [3, -2, 0, 1], False)

    def testStr(self):
        v = Vector3(1.2, 3.4, 5.6)
        self.assertEqual(str(v), "[1.2, 3.4, 5.6]")

    def testRepr(self):
        v = Vector3(1.2, 3.4, -9.6)
        self.assertEqual(v.__repr__(), "<Vector3(1.2, 3.4, -9.6)>")
        self.assertEqual(v, Vector3(v.__repr__()))

    def testIter(self):
        it = self.v1.__iter__()
        next_ = it.__next__
        self.assertEqual(next_(), self.v1[0])
        self.assertEqual(next_(), self.v1[1])
        self.assertEqual(next_(), self.v1[2])
        self.assertRaises(StopIteration, lambda: next_())
        it1 = self.v1.__iter__()
        it2 = self.v1.__iter__()
        self.assertNotEqual(id(it1), id(it2))
        self.assertEqual(id(it1), id(it1.__iter__()))
        self.assertEqual(list(it1), list(it2))
        self.assertEqual(list(self.v1.__iter__()), self.l1)
        idx = 0
        for val in self.v1:
            self.assertEqual(val, self.v1[idx])
            idx += 1

    def test___round___basic(self):
        self.assertEqual(
            round(pygame.Vector3(0.0, 0.0, 0.0)), pygame.Vector3(0.0, 0.0, 0.0)
        )
        self.assertEqual(type(round(pygame.Vector3(0.0, 0.0, 0.0))), pygame.Vector3)
        self.assertEqual(
            round(pygame.Vector3(1.0, 1.0, 1.0)), round(pygame.Vector3(1.0, 1.0, 1.0))
        )
        self.assertEqual(
            round(pygame.Vector3(10.0, 10.0, 10.0)),
            round(pygame.Vector3(10.0, 10.0, 10.0)),
        )
        self.assertEqual(
            round(pygame.Vector3(1000000000.0, 1000000000.0, 1000000000.0)),
            pygame.Vector3(1000000000.0, 1000000000.0, 1000000000.0),
        )
        self.assertEqual(
            round(pygame.Vector3(1e20, 1e20, 1e20)), pygame.Vector3(1e20, 1e20, 1e20)
        )

        self.assertEqual(
            round(pygame.Vector3(-1.0, -1.0, -1.0)), pygame.Vector3(-1.0, -1.0, -1.0)
        )
        self.assertEqual(
            round(pygame.Vector3(-10.0, -10.0, -10.0)),
            pygame.Vector3(-10.0, -10.0, -10.0),
        )
        self.assertEqual(
            round(pygame.Vector3(-1000000000.0, -1000000000.0, -1000000000.0)),
            pygame.Vector3(-1000000000.0, -1000000000.0, -1000000000.0),
        )
        self.assertEqual(
            round(pygame.Vector3(-1e20, -1e20, -1e20)),
            pygame.Vector3(-1e20, -1e20, -1e20),
        )

        self.assertEqual(
            round(pygame.Vector3(0.1, 0.1, 0.1)), pygame.Vector3(0.0, 0.0, 0.0)
        )
        self.assertEqual(
            round(pygame.Vector3(1.1, 1.1, 1.1)), pygame.Vector3(1.0, 1.0, 1.0)
        )
        self.assertEqual(
            round(pygame.Vector3(10.1, 10.1, 10.1)), pygame.Vector3(10.0, 10.0, 10.0)
        )
        self.assertEqual(
            round(pygame.Vector3(1000000000.1, 1000000000.1, 1000000000.1)),
            pygame.Vector3(1000000000.0, 1000000000.0, 1000000000.0),
        )

        self.assertEqual(
            round(pygame.Vector3(-1.1, -1.1, -1.1)), pygame.Vector3(-1.0, -1.0, -1.0)
        )
        self.assertEqual(
            round(pygame.Vector3(-10.1, -10.1, -10.1)),
            pygame.Vector3(-10.0, -10.0, -10.0),
        )
        self.assertEqual(
            round(pygame.Vector3(-1000000000.1, -1000000000.1, -1000000000.1)),
            pygame.Vector3(-1000000000.0, -1000000000.0, -1000000000.0),
        )

        self.assertEqual(
            round(pygame.Vector3(0.9, 0.9, 0.9)), pygame.Vector3(1.0, 1.0, 1.0)
        )
        self.assertEqual(
            round(pygame.Vector3(9.9, 9.9, 9.9)), pygame.Vector3(10.0, 10.0, 10.0)
        )
        self.assertEqual(
            round(pygame.Vector3(999999999.9, 999999999.9, 999999999.9)),
            pygame.Vector3(1000000000.0, 1000000000.0, 1000000000.0),
        )

        self.assertEqual(
            round(pygame.Vector3(-0.9, -0.9, -0.9)), pygame.Vector3(-1.0, -1.0, -1.0)
        )
        self.assertEqual(
            round(pygame.Vector3(-9.9, -9.9, -9.9)), pygame.Vector3(-10.0, -10.0, -10.0)
        )
        self.assertEqual(
            round(pygame.Vector3(-999999999.9, -999999999.9, -999999999.9)),
            pygame.Vector3(-1000000000.0, -1000000000.0, -1000000000.0),
        )

        self.assertEqual(
            round(pygame.Vector3(-8.0, -8.0, -8.0), -1),
            pygame.Vector3(-10.0, -10.0, -10.0),
        )
        self.assertEqual(
            type(round(pygame.Vector3(-8.0, -8.0, -8.0), -1)), pygame.Vector3
        )

        self.assertEqual(
            type(round(pygame.Vector3(-8.0, -8.0, -8.0), 0)), pygame.Vector3
        )
        self.assertEqual(
            type(round(pygame.Vector3(-8.0, -8.0, -8.0), 1)), pygame.Vector3
        )

        # Check even / odd rounding behaviour
        self.assertEqual(round(pygame.Vector3(5.5, 5.5, 5.5)), pygame.Vector3(6, 6, 6))
        self.assertEqual(
            round(pygame.Vector3(5.4, 5.4, 5.4)), pygame.Vector3(5.0, 5.0, 5.0)
        )
        self.assertEqual(
            round(pygame.Vector3(5.6, 5.6, 5.6)), pygame.Vector3(6.0, 6.0, 6.0)
        )
        self.assertEqual(
            round(pygame.Vector3(-5.5, -5.5, -5.5)), pygame.Vector3(-6, -6, -6)
        )
        self.assertEqual(
            round(pygame.Vector3(-5.4, -5.4, -5.4)), pygame.Vector3(-5, -5, -5)
        )
        self.assertEqual(
            round(pygame.Vector3(-5.6, -5.6, -5.6)), pygame.Vector3(-6, -6, -6)
        )

        self.assertRaises(TypeError, round, pygame.Vector3(1.0, 1.0, 1.0), 1.5)
        self.assertRaises(TypeError, round, pygame.Vector3(1.0, 1.0, 1.0), "a")

    def test_rotate(self):
        v1 = Vector3(1, 0, 0)
        axis = Vector3(0, 1, 0)
        v2 = v1.rotate(90, axis)
        v3 = v1.rotate(90 + 360, axis)
        self.assertEqual(v1.x, 1)
        self.assertEqual(v1.y, 0)
        self.assertEqual(v1.z, 0)
        self.assertEqual(v2.x, 0)
        self.assertEqual(v2.y, 0)
        self.assertEqual(v2.z, -1)
        self.assertEqual(v3.x, v2.x)
        self.assertEqual(v3.y, v2.y)
        self.assertEqual(v3.z, v2.z)
        v1 = Vector3(-1, -1, -1)
        v2 = v1.rotate(-90, axis)
        self.assertEqual(v2.x, 1)
        self.assertEqual(v2.y, -1)
        self.assertEqual(v2.z, -1)
        v2 = v1.rotate(360, axis)
        self.assertEqual(v1.x, v2.x)
        self.assertEqual(v1.y, v2.y)
        self.assertEqual(v1.z, v2.z)
        v2 = v1.rotate(0, axis)
        self.assertEqual(v1.x, v2.x)
        self.assertEqual(v1.y, v2.y)
        self.assertEqual(v1.z, v2.z)
        # issue 214
        self.assertEqual(
            Vector3(0, 1, 0).rotate(359.9999999, Vector3(0, 0, 1)), Vector3(0, 1, 0)
        )

    def test_rotate_rad(self):
        axis = Vector3(0, 0, 1)
        tests = (
            ((1, 0, 0), math.pi),
            ((1, 0, 0), math.pi / 2),
            ((1, 0, 0), -math.pi / 2),
            ((1, 0, 0), math.pi / 4),
        )
        for initialVec, radians in tests:
            vec = Vector3(initialVec).rotate_rad(radians, axis)
            self.assertEqual(vec, (math.cos(radians), math.sin(radians), 0))

    def test_rotate_ip(self):
        v = Vector3(1, 0, 0)
        axis = Vector3(0, 1, 0)
        self.assertEqual(v.rotate_ip(90, axis), None)
        self.assertEqual(v.x, 0)
        self.assertEqual(v.y, 0)
        self.assertEqual(v.z, -1)
        v = Vector3(-1, -1, 1)
        v.rotate_ip(-90, axis)
        self.assertEqual(v.x, -1)
        self.assertEqual(v.y, -1)
        self.assertEqual(v.z, -1)

    def test_rotate_rad_ip(self):
        axis = Vector3(0, 0, 1)
        tests = (
            ((1, 0, 0), math.pi),
            ((1, 0, 0), math.pi / 2),
            ((1, 0, 0), -math.pi / 2),
            ((1, 0, 0), math.pi / 4),
        )
        for initialVec, radians in tests:
            vec = Vector3(initialVec)
            vec.rotate_rad_ip(radians, axis)
            self.assertEqual(vec, (math.cos(radians), math.sin(radians), 0))

    def test_rotate_x(self):
        v1 = Vector3(1, 0, 0)
        v2 = v1.rotate_x(90)
        v3 = v1.rotate_x(90 + 360)
        self.assertEqual(v1.x, 1)
        self.assertEqual(v1.y, 0)
        self.assertEqual(v1.z, 0)
        self.assertEqual(v2.x, 1)
        self.assertEqual(v2.y, 0)
        self.assertEqual(v2.z, 0)
        self.assertEqual(v3.x, v2.x)
        self.assertEqual(v3.y, v2.y)
        self.assertEqual(v3.z, v2.z)
        v1 = Vector3(-1, -1, -1)
        v2 = v1.rotate_x(-90)
        self.assertEqual(v2.x, -1)
        self.assertAlmostEqual(v2.y, -1)
        self.assertAlmostEqual(v2.z, 1)
        v2 = v1.rotate_x(360)
        self.assertAlmostEqual(v1.x, v2.x)
        self.assertAlmostEqual(v1.y, v2.y)
        self.assertAlmostEqual(v1.z, v2.z)
        v2 = v1.rotate_x(0)
        self.assertEqual(v1.x, v2.x)
        self.assertAlmostEqual(v1.y, v2.y)
        self.assertAlmostEqual(v1.z, v2.z)

    def test_rotate_x_rad(self):
        vec = Vector3(0, 1, 0)
        result = vec.rotate_x_rad(math.pi / 2)
        self.assertEqual(result, (0, 0, 1))

    def test_rotate_x_ip(self):
        v = Vector3(1, 0, 0)
        self.assertEqual(v.rotate_x_ip(90), None)
        self.assertEqual(v.x, 1)
        self.assertEqual(v.y, 0)
        self.assertEqual(v.z, 0)
        v = Vector3(-1, -1, 1)
        v.rotate_x_ip(-90)
        self.assertEqual(v.x, -1)
        self.assertAlmostEqual(v.y, 1)
        self.assertAlmostEqual(v.z, 1)

    def test_rotate_x_rad_ip(self):
        vec = Vector3(0, 1, 0)
        vec.rotate_x_rad_ip(math.pi / 2)
        self.assertEqual(vec, (0, 0, 1))

    def test_rotate_y(self):
        v1 = Vector3(1, 0, 0)
        v2 = v1.rotate_y(90)
        v3 = v1.rotate_y(90 + 360)
        self.assertEqual(v1.x, 1)
        self.assertEqual(v1.y, 0)
        self.assertEqual(v1.z, 0)
        self.assertAlmostEqual(v2.x, 0)
        self.assertEqual(v2.y, 0)
        self.assertAlmostEqual(v2.z, -1)
        self.assertAlmostEqual(v3.x, v2.x)
        self.assertEqual(v3.y, v2.y)
        self.assertAlmostEqual(v3.z, v2.z)
        v1 = Vector3(-1, -1, -1)
        v2 = v1.rotate_y(-90)
        self.assertAlmostEqual(v2.x, 1)
        self.assertEqual(v2.y, -1)
        self.assertAlmostEqual(v2.z, -1)
        v2 = v1.rotate_y(360)
        self.assertAlmostEqual(v1.x, v2.x)
        self.assertEqual(v1.y, v2.y)
        self.assertAlmostEqual(v1.z, v2.z)
        v2 = v1.rotate_y(0)
        self.assertEqual(v1.x, v2.x)
        self.assertEqual(v1.y, v2.y)
        self.assertEqual(v1.z, v2.z)

    def test_rotate_y_rad(self):
        vec = Vector3(1, 0, 0)
        result = vec.rotate_y_rad(math.pi / 2)
        self.assertEqual(result, (0, 0, -1))

    def test_rotate_y_ip(self):
        v = Vector3(1, 0, 0)
        self.assertEqual(v.rotate_y_ip(90), None)
        self.assertAlmostEqual(v.x, 0)
        self.assertEqual(v.y, 0)
        self.assertAlmostEqual(v.z, -1)
        v = Vector3(-1, -1, 1)
        v.rotate_y_ip(-90)
        self.assertAlmostEqual(v.x, -1)
        self.assertEqual(v.y, -1)
        self.assertAlmostEqual(v.z, -1)

    def test_rotate_y_rad_ip(self):
        vec = Vector3(1, 0, 0)
        vec.rotate_y_rad_ip(math.pi / 2)
        self.assertEqual(vec, (0, 0, -1))

    def test_rotate_z(self):
        v1 = Vector3(1, 0, 0)
        v2 = v1.rotate_z(90)
        v3 = v1.rotate_z(90 + 360)
        self.assertEqual(v1.x, 1)
        self.assertEqual(v1.y, 0)
        self.assertEqual(v1.z, 0)
        self.assertAlmostEqual(v2.x, 0)
        self.assertAlmostEqual(v2.y, 1)
        self.assertEqual(v2.z, 0)
        self.assertAlmostEqual(v3.x, v2.x)
        self.assertAlmostEqual(v3.y, v2.y)
        self.assertEqual(v3.z, v2.z)
        v1 = Vector3(-1, -1, -1)
        v2 = v1.rotate_z(-90)
        self.assertAlmostEqual(v2.x, -1)
        self.assertAlmostEqual(v2.y, 1)
        self.assertEqual(v2.z, -1)
        v2 = v1.rotate_z(360)
        self.assertAlmostEqual(v1.x, v2.x)
        self.assertAlmostEqual(v1.y, v2.y)
        self.assertEqual(v1.z, v2.z)
        v2 = v1.rotate_z(0)
        self.assertAlmostEqual(v1.x, v2.x)
        self.assertAlmostEqual(v1.y, v2.y)
        self.assertEqual(v1.z, v2.z)

    def test_rotate_z_rad(self):
        vec = Vector3(1, 0, 0)
        result = vec.rotate_z_rad(math.pi / 2)
        self.assertEqual(result, (0, 1, 0))

    def test_rotate_z_ip(self):
        v = Vector3(1, 0, 0)
        self.assertEqual(v.rotate_z_ip(90), None)
        self.assertAlmostEqual(v.x, 0)
        self.assertAlmostEqual(v.y, 1)
        self.assertEqual(v.z, 0)
        v = Vector3(-1, -1, 1)
        v.rotate_z_ip(-90)
        self.assertAlmostEqual(v.x, -1)
        self.assertAlmostEqual(v.y, 1)
        self.assertEqual(v.z, 1)

    def test_rotate_z_rad_ip(self):
        vec = Vector3(1, 0, 0)
        vec.rotate_z_rad_ip(math.pi / 2)
        self.assertEqual(vec, (0, 1, 0))

    def test_normalize(self):
        v = self.v1.normalize()
        # length is 1
        self.assertAlmostEqual(v.x * v.x + v.y * v.y + v.z * v.z, 1.0)
        # v1 is unchanged
        self.assertEqual(self.v1.x, self.l1[0])
        self.assertEqual(self.v1.y, self.l1[1])
        self.assertEqual(self.v1.z, self.l1[2])
        # v2 is parallel to v1 (tested via cross product)
        cross = (
            (self.v1.y * v.z - self.v1.z * v.y) ** 2
            + (self.v1.z * v.x - self.v1.x * v.z) ** 2
            + (self.v1.x * v.y - self.v1.y * v.x) ** 2
        )
        self.assertAlmostEqual(cross, 0.0)
        self.assertRaises(ValueError, lambda: self.zeroVec.normalize())

    def test_normalize_ip(self):
        v = +self.v1
        # v has length != 1 before normalizing
        self.assertNotEqual(v.x * v.x + v.y * v.y + v.z * v.z, 1.0)
        # inplace operations should return None
        self.assertEqual(v.normalize_ip(), None)
        # length is 1
        self.assertAlmostEqual(v.x * v.x + v.y * v.y + v.z * v.z, 1.0)
        # v2 is parallel to v1 (tested via cross product)
        cross = (
            (self.v1.y * v.z - self.v1.z * v.y) ** 2
            + (self.v1.z * v.x - self.v1.x * v.z) ** 2
            + (self.v1.x * v.y - self.v1.y * v.x) ** 2
        )
        self.assertAlmostEqual(cross, 0.0)
        self.assertRaises(ValueError, lambda: self.zeroVec.normalize_ip())

    def test_is_normalized(self):
        self.assertEqual(self.v1.is_normalized(), False)
        v = self.v1.normalize()
        self.assertEqual(v.is_normalized(), True)
        self.assertEqual(self.e2.is_normalized(), True)
        self.assertEqual(self.zeroVec.is_normalized(), False)

    def test_cross(self):
        def cross(a, b):
            return Vector3(
                a[1] * b[2] - a[2] * b[1],
                a[2] * b[0] - a[0] * b[2],
                a[0] * b[1] - a[1] * b[0],
            )

        self.assertEqual(self.v1.cross(self.v2), cross(self.v1, self.v2))
        self.assertEqual(self.v1.cross(self.l2), cross(self.v1, self.l2))
        self.assertEqual(self.v1.cross(self.t2), cross(self.v1, self.t2))
        self.assertEqual(self.v1.cross(self.v2), -self.v2.cross(self.v1))
        self.assertEqual(self.v1.cross(self.v1), self.zeroVec)

    def test_dot(self):
        self.assertAlmostEqual(
            self.v1.dot(self.v2),
            self.v1.x * self.v2.x + self.v1.y * self.v2.y + self.v1.z * self.v2.z,
        )
        self.assertAlmostEqual(
            self.v1.dot(self.l2),
            self.v1.x * self.l2[0] + self.v1.y * self.l2[1] + self.v1.z * self.l2[2],
        )
        self.assertAlmostEqual(
            self.v1.dot(self.t2),
            self.v1.x * self.t2[0] + self.v1.y * self.t2[1] + self.v1.z * self.t2[2],
        )
        self.assertAlmostEqual(self.v1.dot(self.v2), self.v2.dot(self.v1))
        self.assertAlmostEqual(self.v1.dot(self.v2), self.v1 * self.v2)

    def test_angle_to(self):
        self.assertEqual(Vector3(1, 1, 0).angle_to((-1, 1, 0)), 90)
        self.assertEqual(Vector3(1, 0, 0).angle_to((0, 0, -1)), 90)
        self.assertEqual(Vector3(1, 0, 0).angle_to((-1, 0, 1)), 135)
        self.assertEqual(abs(Vector3(1, 0, 1).angle_to((-1, 0, -1))), 180)
        # if we rotate v1 by the angle_to v2 around their cross product
        # we should look in the same direction
        self.assertEqual(
            self.v1.rotate(
                self.v1.angle_to(self.v2), self.v1.cross(self.v2)
            ).normalize(),
            self.v2.normalize(),
        )

    def test_scale_to_length(self):
        v = Vector3(1, 1, 1)
        v.scale_to_length(2.5)
        self.assertEqual(v, Vector3(2.5, 2.5, 2.5) / math.sqrt(3))
        self.assertRaises(ValueError, lambda: self.zeroVec.scale_to_length(1))
        self.assertEqual(v.scale_to_length(0), None)
        self.assertEqual(v, self.zeroVec)

    def test_length(self):
        self.assertEqual(Vector3(3, 4, 5).length(), math.sqrt(3 * 3 + 4 * 4 + 5 * 5))
        self.assertEqual(Vector3(-3, 4, 5).length(), math.sqrt(-3 * -3 + 4 * 4 + 5 * 5))
        self.assertEqual(self.zeroVec.length(), 0)

    def test_length_squared(self):
        self.assertEqual(Vector3(3, 4, 5).length_squared(), 3 * 3 + 4 * 4 + 5 * 5)
        self.assertEqual(Vector3(-3, 4, 5).length_squared(), -3 * -3 + 4 * 4 + 5 * 5)
        self.assertEqual(self.zeroVec.length_squared(), 0)

    def test_reflect(self):
        v = Vector3(1, -1, 1)
        n = Vector3(0, 1, 0)
        self.assertEqual(v.reflect(n), Vector3(1, 1, 1))
        self.assertEqual(v.reflect(3 * n), v.reflect(n))
        self.assertEqual(v.reflect(-v), -v)
        self.assertRaises(ValueError, lambda: v.reflect(self.zeroVec))

    def test_reflect_ip(self):
        v1 = Vector3(1, -1, 1)
        v2 = Vector3(v1)
        n = Vector3(0, 1, 0)
        self.assertEqual(v2.reflect_ip(n), None)
        self.assertEqual(v2, Vector3(1, 1, 1))
        v2 = Vector3(v1)
        v2.reflect_ip(3 * n)
        self.assertEqual(v2, v1.reflect(n))
        v2 = Vector3(v1)
        v2.reflect_ip(-v1)
        self.assertEqual(v2, -v1)
        self.assertRaises(ValueError, lambda: v2.reflect_ip(self.zeroVec))

    def test_distance_to(self):
        diff = self.v1 - self.v2
        self.assertEqual(self.e1.distance_to(self.e2), math.sqrt(2))
        self.assertEqual(self.e1.distance_to((0, 1, 0)), math.sqrt(2))
        self.assertEqual(self.e1.distance_to([0, 1, 0]), math.sqrt(2))
        self.assertEqual(
            self.v1.distance_to(self.v2),
            math.sqrt(diff.x * diff.x + diff.y * diff.y + diff.z * diff.z),
        )
        self.assertEqual(
            self.v1.distance_to(self.t2),
            math.sqrt(diff.x * diff.x + diff.y * diff.y + diff.z * diff.z),
        )
        self.assertEqual(
            self.v1.distance_to(self.l2),
            math.sqrt(diff.x * diff.x + diff.y * diff.y + diff.z * diff.z),
        )
        self.assertEqual(self.v1.distance_to(self.v1), 0)
        self.assertEqual(self.v1.distance_to(self.t1), 0)
        self.assertEqual(self.v1.distance_to(self.l1), 0)
        self.assertEqual(self.v1.distance_to(self.v2), self.v2.distance_to(self.v1))
        self.assertEqual(self.v1.distance_to(self.t2), self.v2.distance_to(self.t1))
        self.assertEqual(self.v1.distance_to(self.l2), self.v2.distance_to(self.l1))

    def test_distance_to_exceptions(self):
        v2 = Vector2(10, 10)
        v3 = Vector3(1, 1, 1)

        # illegal distance Vector3-Vector2 / Vector2-Vector3
        self.assertRaises(ValueError, v2.distance_to, v3)
        self.assertRaises(ValueError, v3.distance_to, v2)

        # distance to illegal tuple/list positions
        self.assertRaises(ValueError, v2.distance_to, (1, 1, 1))
        self.assertRaises(ValueError, v2.distance_to, (1, 1, 0))
        self.assertRaises(ValueError, v2.distance_to, (1,))
        self.assertRaises(ValueError, v2.distance_to, [1, 1, 1])
        self.assertRaises(ValueError, v2.distance_to, [1, 1, 0])
        self.assertRaises(
            ValueError,
            v2.distance_to,
            [
                1,
            ],
        )
        self.assertRaises(ValueError, v2.distance_to, (1, 1, 1))
        # vec3
        self.assertRaises(ValueError, v3.distance_to, (1, 1))
        self.assertRaises(ValueError, v3.distance_to, (1,))
        self.assertRaises(ValueError, v3.distance_to, [1, 1])
        self.assertRaises(
            ValueError,
            v3.distance_to,
            [
                1,
            ],
        )

        # illegal types as positions
        self.assertRaises(TypeError, v2.distance_to, (1, "hello"))
        self.assertRaises(TypeError, v2.distance_to, ([], []))
        self.assertRaises(TypeError, v2.distance_to, (1, ("hello",)))

        # illegal args number
        self.assertRaises(TypeError, v2.distance_to)
        self.assertRaises(TypeError, v2.distance_to, (1, 1), (1, 2))
        self.assertRaises(TypeError, v2.distance_to, (1, 1), (1, 2), 1)

    def test_distance_squared_to_exceptions(self):
        v2 = Vector2(10, 10)
        v3 = Vector3(1, 1, 1)
        dist_t = v2.distance_squared_to
        dist_t3 = v3.distance_squared_to
        # illegal distance Vector3-Vector2 / Vector2-Vector3
        self.assertRaises(ValueError, dist_t, v3)
        self.assertRaises(ValueError, dist_t3, v2)

        # distance to illegal tuple/list positions
        self.assertRaises(ValueError, dist_t, (1, 1, 1))
        self.assertRaises(ValueError, dist_t, (1, 1, 0))
        self.assertRaises(ValueError, dist_t, (1,))
        self.assertRaises(ValueError, dist_t, [1, 1, 1])
        self.assertRaises(ValueError, dist_t, [1, 1, 0])
        self.assertRaises(
            ValueError,
            dist_t,
            [
                1,
            ],
        )
        self.assertRaises(ValueError, dist_t, (1, 1, 1))
        # vec3
        self.assertRaises(ValueError, dist_t3, (1, 1))
        self.assertRaises(ValueError, dist_t3, (1,))
        self.assertRaises(ValueError, dist_t3, [1, 1])
        self.assertRaises(
            ValueError,
            dist_t3,
            [
                1,
            ],
        )

        # illegal types as positions
        self.assertRaises(TypeError, dist_t, (1, "hello"))
        self.assertRaises(TypeError, dist_t, ([], []))
        self.assertRaises(TypeError, dist_t, (1, ("hello",)))

        # illegal args number
        self.assertRaises(TypeError, dist_t)
        self.assertRaises(TypeError, dist_t, (1, 1), (1, 2))
        self.assertRaises(TypeError, dist_t, (1, 1), (1, 2), 1)

    def test_distance_squared_to(self):
        diff = self.v1 - self.v2
        self.assertEqual(self.e1.distance_squared_to(self.e2), 2)
        self.assertEqual(self.e1.distance_squared_to((0, 1, 0)), 2)
        self.assertEqual(self.e1.distance_squared_to([0, 1, 0]), 2)
        self.assertAlmostEqual(
            self.v1.distance_squared_to(self.v2),
            diff.x * diff.x + diff.y * diff.y + diff.z * diff.z,
        )
        self.assertAlmostEqual(
            self.v1.distance_squared_to(self.t2),
            diff.x * diff.x + diff.y * diff.y + diff.z * diff.z,
        )
        self.assertAlmostEqual(
            self.v1.distance_squared_to(self.l2),
            diff.x * diff.x + diff.y * diff.y + diff.z * diff.z,
        )
        self.assertEqual(self.v1.distance_squared_to(self.v1), 0)
        self.assertEqual(self.v1.distance_squared_to(self.t1), 0)
        self.assertEqual(self.v1.distance_squared_to(self.l1), 0)
        self.assertEqual(
            self.v1.distance_squared_to(self.v2), self.v2.distance_squared_to(self.v1)
        )
        self.assertEqual(
            self.v1.distance_squared_to(self.t2), self.v2.distance_squared_to(self.t1)
        )
        self.assertEqual(
            self.v1.distance_squared_to(self.l2), self.v2.distance_squared_to(self.l1)
        )

    def test_swizzle(self):
        self.assertEqual(self.v1.yxz, (self.v1.y, self.v1.x, self.v1.z))
        self.assertEqual(
            self.v1.xxyyzzxyz,
            (
                self.v1.x,
                self.v1.x,
                self.v1.y,
                self.v1.y,
                self.v1.z,
                self.v1.z,
                self.v1.x,
                self.v1.y,
                self.v1.z,
            ),
        )
        self.v1.xyz = self.t2
        self.assertEqual(self.v1, self.t2)
        self.v1.zxy = self.t2
        self.assertEqual(self.v1, (self.t2[1], self.t2[2], self.t2[0]))
        self.v1.yz = self.t2[:2]
        self.assertEqual(self.v1, (self.t2[1], self.t2[0], self.t2[1]))
        self.assertEqual(type(self.v1), Vector3)

    @unittest.skipIf(IS_PYPY, "known pypy failure")
    def test_invalid_swizzle(self):
        def invalidSwizzleX():
            Vector3().xx = (1, 2)

        def invalidSwizzleY():
            Vector3().yy = (1, 2)

        def invalidSwizzleZ():
            Vector3().zz = (1, 2)

        def invalidSwizzleW():
            Vector3().ww = (1, 2)

        self.assertRaises(AttributeError, invalidSwizzleX)
        self.assertRaises(AttributeError, invalidSwizzleY)
        self.assertRaises(AttributeError, invalidSwizzleZ)
        self.assertRaises(AttributeError, invalidSwizzleW)

        def invalidAssignment():
            Vector3().xy = 3

        self.assertRaises(TypeError, invalidAssignment)

    def test_swizzle_return_types(self):
        self.assertEqual(type(self.v1.x), float)
        self.assertEqual(type(self.v1.xy), Vector2)
        self.assertEqual(type(self.v1.xyz), Vector3)
        # but we don't have vector4 or above... so tuple.
        self.assertEqual(type(self.v1.xyxy), tuple)
        self.assertEqual(type(self.v1.xyxyx), tuple)

    def test_dir_works(self):
        # not every single one of the attributes...
        attributes = {"lerp", "normalize", "normalize_ip", "reflect", "slerp", "x", "y"}
        # check if this selection of attributes are all there.
        self.assertTrue(attributes.issubset(set(dir(self.v1))))

    def test_elementwise(self):
        # behaviour for "elementwise op scalar"
        self.assertEqual(
            self.v1.elementwise() + self.s1,
            (self.v1.x + self.s1, self.v1.y + self.s1, self.v1.z + self.s1),
        )
        self.assertEqual(
            self.v1.elementwise() - self.s1,
            (self.v1.x - self.s1, self.v1.y - self.s1, self.v1.z - self.s1),
        )
        self.assertEqual(
            self.v1.elementwise() * self.s2,
            (self.v1.x * self.s2, self.v1.y * self.s2, self.v1.z * self.s2),
        )
        self.assertEqual(
            self.v1.elementwise() / self.s2,
            (self.v1.x / self.s2, self.v1.y / self.s2, self.v1.z / self.s2),
        )
        self.assertEqual(
            self.v1.elementwise() // self.s1,
            (self.v1.x // self.s1, self.v1.y // self.s1, self.v1.z // self.s1),
        )
        self.assertEqual(
            self.v1.elementwise() ** self.s1,
            (self.v1.x**self.s1, self.v1.y**self.s1, self.v1.z**self.s1),
        )
        self.assertEqual(
            self.v1.elementwise() % self.s1,
            (self.v1.x % self.s1, self.v1.y % self.s1, self.v1.z % self.s1),
        )
        self.assertEqual(
            self.v1.elementwise() > self.s1,
            self.v1.x > self.s1 and self.v1.y > self.s1 and self.v1.z > self.s1,
        )
        self.assertEqual(
            self.v1.elementwise() < self.s1,
            self.v1.x < self.s1 and self.v1.y < self.s1 and self.v1.z < self.s1,
        )
        self.assertEqual(
            self.v1.elementwise() == self.s1,
            self.v1.x == self.s1 and self.v1.y == self.s1 and self.v1.z == self.s1,
        )
        self.assertEqual(
            self.v1.elementwise() != self.s1,
            self.v1.x != self.s1 and self.v1.y != self.s1 and self.v1.z != self.s1,
        )
        self.assertEqual(
            self.v1.elementwise() >= self.s1,
            self.v1.x >= self.s1 and self.v1.y >= self.s1 and self.v1.z >= self.s1,
        )
        self.assertEqual(
            self.v1.elementwise() <= self.s1,
            self.v1.x <= self.s1 and self.v1.y <= self.s1 and self.v1.z <= self.s1,
        )
        # behaviour for "scalar op elementwise"
        self.assertEqual(5 + self.v1.elementwise(), Vector3(5, 5, 5) + self.v1)
        self.assertEqual(3.5 - self.v1.elementwise(), Vector3(3.5, 3.5, 3.5) - self.v1)
        self.assertEqual(7.5 * self.v1.elementwise(), 7.5 * self.v1)
        self.assertEqual(
            -3.5 / self.v1.elementwise(),
            (-3.5 / self.v1.x, -3.5 / self.v1.y, -3.5 / self.v1.z),
        )
        self.assertEqual(
            -3.5 // self.v1.elementwise(),
            (-3.5 // self.v1.x, -3.5 // self.v1.y, -3.5 // self.v1.z),
        )
        self.assertEqual(
            -(3.5 ** self.v1.elementwise()),
            (-(3.5**self.v1.x), -(3.5**self.v1.y), -(3.5**self.v1.z)),
        )
        self.assertEqual(
            3 % self.v1.elementwise(), (3 % self.v1.x, 3 % self.v1.y, 3 % self.v1.z)
        )
        self.assertEqual(
            2 < self.v1.elementwise(), 2 < self.v1.x and 2 < self.v1.y and 2 < self.v1.z
        )
        self.assertEqual(
            2 > self.v1.elementwise(), 2 > self.v1.x and 2 > self.v1.y and 2 > self.v1.z
        )
        self.assertEqual(
            1 == self.v1.elementwise(),
            1 == self.v1.x and 1 == self.v1.y and 1 == self.v1.z,
        )
        self.assertEqual(
            1 != self.v1.elementwise(),
            1 != self.v1.x and 1 != self.v1.y and 1 != self.v1.z,
        )
        self.assertEqual(
            2 <= self.v1.elementwise(),
            2 <= self.v1.x and 2 <= self.v1.y and 2 <= self.v1.z,
        )
        self.assertEqual(
            -7 >= self.v1.elementwise(),
            -7 >= self.v1.x and -7 >= self.v1.y and -7 >= self.v1.z,
        )
        self.assertEqual(
            -7 != self.v1.elementwise(),
            -7 != self.v1.x and -7 != self.v1.y and -7 != self.v1.z,
        )

        # behaviour for "elementwise op vector"
        self.assertEqual(type(self.v1.elementwise() * self.v2), type(self.v1))
        self.assertEqual(self.v1.elementwise() + self.v2, self.v1 + self.v2)
        self.assertEqual(self.v1.elementwise() + self.v2, self.v1 + self.v2)
        self.assertEqual(self.v1.elementwise() - self.v2, self.v1 - self.v2)
        self.assertEqual(
            self.v1.elementwise() * self.v2,
            (self.v1.x * self.v2.x, self.v1.y * self.v2.y, self.v1.z * self.v2.z),
        )
        self.assertEqual(
            self.v1.elementwise() / self.v2,
            (self.v1.x / self.v2.x, self.v1.y / self.v2.y, self.v1.z / self.v2.z),
        )
        self.assertEqual(
            self.v1.elementwise() // self.v2,
            (self.v1.x // self.v2.x, self.v1.y // self.v2.y, self.v1.z // self.v2.z),
        )
        self.assertEqual(
            self.v1.elementwise() ** self.v2,
            (self.v1.x**self.v2.x, self.v1.y**self.v2.y, self.v1.z**self.v2.z),
        )
        self.assertEqual(
            self.v1.elementwise() % self.v2,
            (self.v1.x % self.v2.x, self.v1.y % self.v2.y, self.v1.z % self.v2.z),
        )
        self.assertEqual(
            self.v1.elementwise() > self.v2,
            self.v1.x > self.v2.x and self.v1.y > self.v2.y and self.v1.z > self.v2.z,
        )
        self.assertEqual(
            self.v1.elementwise() < self.v2,
            self.v1.x < self.v2.x and self.v1.y < self.v2.y and self.v1.z < self.v2.z,
        )
        self.assertEqual(
            self.v1.elementwise() >= self.v2,
            self.v1.x >= self.v2.x
            and self.v1.y >= self.v2.y
            and self.v1.z >= self.v2.z,
        )
        self.assertEqual(
            self.v1.elementwise() <= self.v2,
            self.v1.x <= self.v2.x
            and self.v1.y <= self.v2.y
            and self.v1.z <= self.v2.z,
        )
        self.assertEqual(
            self.v1.elementwise() == self.v2,
            self.v1.x == self.v2.x
            and self.v1.y == self.v2.y
            and self.v1.z == self.v2.z,
        )
        self.assertEqual(
            self.v1.elementwise() != self.v2,
            self.v1.x != self.v2.x
            and self.v1.y != self.v2.y
            and self.v1.z != self.v2.z,
        )
        # behaviour for "vector op elementwise"
        self.assertEqual(self.v2 + self.v1.elementwise(), self.v2 + self.v1)
        self.assertEqual(self.v2 - self.v1.elementwise(), self.v2 - self.v1)
        self.assertEqual(
            self.v2 * self.v1.elementwise(),
            (self.v2.x * self.v1.x, self.v2.y * self.v1.y, self.v2.z * self.v1.z),
        )
        self.assertEqual(
            self.v2 / self.v1.elementwise(),
            (self.v2.x / self.v1.x, self.v2.y / self.v1.y, self.v2.z / self.v1.z),
        )
        self.assertEqual(
            self.v2 // self.v1.elementwise(),
            (self.v2.x // self.v1.x, self.v2.y // self.v1.y, self.v2.z // self.v1.z),
        )
        self.assertEqual(
            self.v2 ** self.v1.elementwise(),
            (self.v2.x**self.v1.x, self.v2.y**self.v1.y, self.v2.z**self.v1.z),
        )
        self.assertEqual(
            self.v2 % self.v1.elementwise(),
            (self.v2.x % self.v1.x, self.v2.y % self.v1.y, self.v2.z % self.v1.z),
        )
        self.assertEqual(
            self.v2 < self.v1.elementwise(),
            self.v2.x < self.v1.x and self.v2.y < self.v1.y and self.v2.z < self.v1.z,
        )
        self.assertEqual(
            self.v2 > self.v1.elementwise(),
            self.v2.x > self.v1.x and self.v2.y > self.v1.y and self.v2.z > self.v1.z,
        )
        self.assertEqual(
            self.v2 <= self.v1.elementwise(),
            self.v2.x <= self.v1.x
            and self.v2.y <= self.v1.y
            and self.v2.z <= self.v1.z,
        )
        self.assertEqual(
            self.v2 >= self.v1.elementwise(),
            self.v2.x >= self.v1.x
            and self.v2.y >= self.v1.y
            and self.v2.z >= self.v1.z,
        )
        self.assertEqual(
            self.v2 == self.v1.elementwise(),
            self.v2.x == self.v1.x
            and self.v2.y == self.v1.y
            and self.v2.z == self.v1.z,
        )
        self.assertEqual(
            self.v2 != self.v1.elementwise(),
            self.v2.x != self.v1.x
            and self.v2.y != self.v1.y
            and self.v2.z != self.v1.z,
        )

        # behaviour for "elementwise op elementwise"
        self.assertEqual(
            self.v2.elementwise() + self.v1.elementwise(), self.v2 + self.v1
        )
        self.assertEqual(
            self.v2.elementwise() - self.v1.elementwise(), self.v2 - self.v1
        )
        self.assertEqual(
            self.v2.elementwise() * self.v1.elementwise(),
            (self.v2.x * self.v1.x, self.v2.y * self.v1.y, self.v2.z * self.v1.z),
        )
        self.assertEqual(
            self.v2.elementwise() / self.v1.elementwise(),
            (self.v2.x / self.v1.x, self.v2.y / self.v1.y, self.v2.z / self.v1.z),
        )
        self.assertEqual(
            self.v2.elementwise() // self.v1.elementwise(),
            (self.v2.x // self.v1.x, self.v2.y // self.v1.y, self.v2.z // self.v1.z),
        )
        self.assertEqual(
            self.v2.elementwise() ** self.v1.elementwise(),
            (self.v2.x**self.v1.x, self.v2.y**self.v1.y, self.v2.z**self.v1.z),
        )
        self.assertEqual(
            self.v2.elementwise() % self.v1.elementwise(),
            (self.v2.x % self.v1.x, self.v2.y % self.v1.y, self.v2.z % self.v1.z),
        )
        self.assertEqual(
            self.v2.elementwise() < self.v1.elementwise(),
            self.v2.x < self.v1.x and self.v2.y < self.v1.y and self.v2.z < self.v1.z,
        )
        self.assertEqual(
            self.v2.elementwise() > self.v1.elementwise(),
            self.v2.x > self.v1.x and self.v2.y > self.v1.y and self.v2.z > self.v1.z,
        )
        self.assertEqual(
            self.v2.elementwise() <= self.v1.elementwise(),
            self.v2.x <= self.v1.x
            and self.v2.y <= self.v1.y
            and self.v2.z <= self.v1.z,
        )
        self.assertEqual(
            self.v2.elementwise() >= self.v1.elementwise(),
            self.v2.x >= self.v1.x
            and self.v2.y >= self.v1.y
            and self.v2.z >= self.v1.z,
        )
        self.assertEqual(
            self.v2.elementwise() == self.v1.elementwise(),
            self.v2.x == self.v1.x
            and self.v2.y == self.v1.y
            and self.v2.z == self.v1.z,
        )
        self.assertEqual(
            self.v2.elementwise() != self.v1.elementwise(),
            self.v2.x != self.v1.x
            and self.v2.y != self.v1.y
            and self.v2.z != self.v1.z,
        )

        # other behaviour
        self.assertEqual(
            abs(self.v1.elementwise()), (abs(self.v1.x), abs(self.v1.y), abs(self.v1.z))
        )
        self.assertEqual(-self.v1.elementwise(), -self.v1)
        self.assertEqual(+self.v1.elementwise(), +self.v1)
        self.assertEqual(bool(self.v1.elementwise()), bool(self.v1))
        self.assertEqual(bool(Vector3().elementwise()), bool(Vector3()))
        self.assertEqual(self.zeroVec.elementwise() ** 0, (1, 1, 1))
        self.assertRaises(ValueError, lambda: pow(Vector3(-1, 0, 0).elementwise(), 1.2))
        self.assertRaises(ZeroDivisionError, lambda: self.zeroVec.elementwise() ** -1)
        self.assertRaises(ZeroDivisionError, lambda: Vector3(1, 1, 1).elementwise() / 0)
        self.assertRaises(
            ZeroDivisionError, lambda: Vector3(1, 1, 1).elementwise() // 0
        )
        self.assertRaises(ZeroDivisionError, lambda: Vector3(1, 1, 1).elementwise() % 0)
        self.assertRaises(
            ZeroDivisionError, lambda: Vector3(1, 1, 1).elementwise() / self.zeroVec
        )
        self.assertRaises(
            ZeroDivisionError, lambda: Vector3(1, 1, 1).elementwise() // self.zeroVec
        )
        self.assertRaises(
            ZeroDivisionError, lambda: Vector3(1, 1, 1).elementwise() % self.zeroVec
        )
        self.assertRaises(ZeroDivisionError, lambda: 2 / self.zeroVec.elementwise())
        self.assertRaises(ZeroDivisionError, lambda: 2 // self.zeroVec.elementwise())
        self.assertRaises(ZeroDivisionError, lambda: 2 % self.zeroVec.elementwise())

    def test_slerp(self):
        self.assertRaises(ValueError, lambda: self.zeroVec.slerp(self.v1, 0.5))
        self.assertRaises(ValueError, lambda: self.v1.slerp(self.zeroVec, 0.5))
        self.assertRaises(ValueError, lambda: self.zeroVec.slerp(self.zeroVec, 0.5))
        steps = 10
        angle_step = self.e1.angle_to(self.e2) / steps
        for i, u in (
            (i, self.e1.slerp(self.e2, i / float(steps))) for i in range(steps + 1)
        ):
            self.assertAlmostEqual(u.length(), 1)
            self.assertAlmostEqual(self.e1.angle_to(u), i * angle_step)
        self.assertEqual(u, self.e2)

        v1 = Vector3(100, 0, 0)
        v2 = Vector3(0, 10, 7)
        radial_factor = v2.length() / v1.length()
        for i, u in ((i, v1.slerp(v2, -i / float(steps))) for i in range(steps + 1)):
            self.assertAlmostEqual(
                u.length(),
                (v2.length() - v1.length()) * (float(i) / steps) + v1.length(),
            )
        self.assertEqual(u, v2)
        self.assertEqual(v1.slerp(v1, 0.5), v1)
        self.assertEqual(v2.slerp(v2, 0.5), v2)
        self.assertRaises(ValueError, lambda: v1.slerp(-v1, 0.5))

    def test_lerp(self):
        v1 = Vector3(0, 0, 0)
        v2 = Vector3(10, 10, 10)
        self.assertEqual(v1.lerp(v2, 0.5), (5, 5, 5))
        self.assertRaises(ValueError, lambda: v1.lerp(v2, 2.5))

        v1 = Vector3(-10, -5, -20)
        v2 = Vector3(10, 10, -20)
        self.assertEqual(v1.lerp(v2, 0.5), (0, 2.5, -20))

    def test_spherical(self):
        v = Vector3()
        v.from_spherical(self.v1.as_spherical())
        self.assertEqual(self.v1, v)
        self.assertEqual(self.v1, Vector3.from_spherical(self.v1.as_spherical()))
        self.assertEqual(self.e1.as_spherical(), (1, 90, 0))
        self.assertEqual(self.e2.as_spherical(), (1, 90, 90))
        self.assertEqual(self.e3.as_spherical(), (1, 0, 0))
        self.assertEqual((2 * self.e2).as_spherical(), (2, 90, 90))
        self.assertRaises(TypeError, lambda: v.from_spherical((None, None, None)))
        self.assertRaises(TypeError, lambda: v.from_spherical("abc"))
        self.assertRaises(TypeError, lambda: v.from_spherical((None, 1, 2)))
        self.assertRaises(TypeError, lambda: v.from_spherical((1, 2, 3, 4)))
        self.assertRaises(TypeError, lambda: v.from_spherical((1, 2)))
        self.assertRaises(TypeError, lambda: v.from_spherical(1, 2, 3))
        self.assertRaises(TypeError, lambda: Vector3.from_spherical((None, None, None)))
        self.assertRaises(TypeError, lambda: Vector3.from_spherical("abc"))
        self.assertRaises(TypeError, lambda: Vector3.from_spherical((None, 1, 2)))
        self.assertRaises(TypeError, lambda: Vector3.from_spherical((1, 2, 3, 4)))
        self.assertRaises(TypeError, lambda: Vector3.from_spherical((1, 2)))
        self.assertRaises(TypeError, lambda: Vector3.from_spherical(1, 2, 3))
        v.from_spherical((0.5, 90, 90))
        self.assertEqual(v, 0.5 * self.e2)
        self.assertEqual(Vector3.from_spherical((0.5, 90, 90)), 0.5 * self.e2)
        self.assertEqual(Vector3.from_spherical((0.5, 90, 90)), v)

    def test_inplace_operators(self):
        v = Vector3(1, 1, 1)
        v *= 2
        self.assertEqual(v, (2.0, 2.0, 2.0))

        v = Vector3(4, 4, 4)
        v /= 2
        self.assertEqual(v, (2.0, 2.0, 2.0))

        v = Vector3(3.0, 3.0, 3.0)
        v -= (1, 1, 1)
        self.assertEqual(v, (2.0, 2.0, 2.0))

        v = Vector3(3.0, 3.0, 3.0)
        v += (1, 1, 1)
        self.assertEqual(v, (4.0, 4.0, 4.0))

    def test_pickle(self):
        import pickle

        v2 = Vector2(1, 2)
        v3 = Vector3(1, 2, 3)
        self.assertEqual(pickle.loads(pickle.dumps(v2)), v2)
        self.assertEqual(pickle.loads(pickle.dumps(v3)), v3)

    def test_subclass_operation(self):
        class Vector(pygame.math.Vector3):
            pass

        v = Vector(2.0, 2.0, 2.0)
        v *= 2
        self.assertEqual(v, (4.0, 4.0, 4.0))

    def test_swizzle_constants(self):
        """We can get constant values from a swizzle."""
        v = Vector2(7, 6)
        self.assertEqual(
            v.xy1,
            (7.0, 6.0, 1.0),
        )

    def test_swizzle_four_constants(self):
        """We can get 4 constant values from a swizzle."""
        v = Vector2(7, 6)
        self.assertEqual(
            v.xy01,
            (7.0, 6.0, 0.0, 1.0),
        )

    def test_swizzle_oob(self):
        """An out-of-bounds swizzle raises an AttributeError."""
        v = Vector2(7, 6)
        with self.assertRaises(AttributeError):
            v.xyz

    @unittest.skipIf(IS_PYPY, "known pypy failure")
    def test_swizzle_set_oob(self):
        """An out-of-bounds swizzle set raises an AttributeError."""
        v = Vector2(7, 6)
        with self.assertRaises(AttributeError):
            v.xz = (1, 1)

    def test_project_v3_onto_x_axis(self):
        """Project onto x-axis, e.g. get the component pointing in the x-axis direction."""
        # arrange
        v = Vector3(2, 3, 4)
        x_axis = Vector3(10, 0, 0)

        # act
        actual = v.project(x_axis)

        # assert
        self.assertEqual(v.x, actual.x)
        self.assertEqual(0, actual.y)
        self.assertEqual(0, actual.z)

    def test_project_v3_onto_y_axis(self):
        """Project onto y-axis, e.g. get the component pointing in the y-axis direction."""
        # arrange
        v = Vector3(2, 3, 4)
        y_axis = Vector3(0, 100, 0)

        # act
        actual = v.project(y_axis)

        # assert
        self.assertEqual(0, actual.x)
        self.assertEqual(v.y, actual.y)
        self.assertEqual(0, actual.z)

    def test_project_v3_onto_z_axis(self):
        """Project onto z-axis, e.g. get the component pointing in the z-axis direction."""
        # arrange
        v = Vector3(2, 3, 4)
        y_axis = Vector3(0, 0, 77)

        # act
        actual = v.project(y_axis)

        # assert
        self.assertEqual(0, actual.x)
        self.assertEqual(0, actual.y)
        self.assertEqual(v.z, actual.z)

    def test_project_v3_onto_other(self):
        """Project onto other vector."""
        # arrange
        v = Vector3(2, 3, 4)
        other = Vector3(3, 5, 7)

        # act
        actual = v.project(other)

        # assert
        expected = v.dot(other) / other.dot(other) * other
        self.assertAlmostEqual(expected.x, actual.x)
        self.assertAlmostEqual(expected.y, actual.y)
        self.assertAlmostEqual(expected.z, actual.z)

    def test_project_v3_onto_other_as_tuple(self):
        """Project onto other tuple as vector."""
        # arrange
        v = Vector3(2, 3, 4)
        other = Vector3(3, 5, 7)

        # act
        actual = v.project(tuple(other))

        # assert
        expected = v.dot(other) / other.dot(other) * other
        self.assertAlmostEqual(expected.x, actual.x)
        self.assertAlmostEqual(expected.y, actual.y)
        self.assertAlmostEqual(expected.z, actual.z)

    def test_project_v3_onto_other_as_list(self):
        """Project onto other list as vector."""
        # arrange
        v = Vector3(2, 3, 4)
        other = Vector3(3, 5, 7)

        # act
        actual = v.project(list(other))

        # assert
        expected = v.dot(other) / other.dot(other) * other
        self.assertAlmostEqual(expected.x, actual.x)
        self.assertAlmostEqual(expected.y, actual.y)
        self.assertAlmostEqual(expected.z, actual.z)

    def test_project_v3_raises_if_other_has_zero_length(self):
        """Check if exception is raise when projected on vector has zero length."""
        # arrange
        v = Vector3(2, 3, 4)
        other = Vector3(0, 0, 0)

        # act / assert
        self.assertRaises(ValueError, v.project, other)

    def test_project_v3_raises_if_other_is_not_iterable(self):
        """Check if exception is raise when projected on vector is not iterable."""
        # arrange
        v = Vector3(2, 3, 4)
        other = 10

        # act / assert
        self.assertRaises(TypeError, v.project, other)

    def test_collection_abc(self):
        v = Vector3(3, 4, 5)
        self.assertTrue(isinstance(v, Collection))
        self.assertFalse(isinstance(v, Sequence))

    def test_clamp_mag_v3_max(self):
        v1 = Vector3(7, 2, 2)
        v2 = v1.clamp_magnitude(5)
        v3 = v1.clamp_magnitude(0, 5)
        self.assertEqual(v2, v3)

        v1.clamp_magnitude_ip(5)
        self.assertEqual(v1, v2)

        v1.clamp_magnitude_ip(0, 5)
        self.assertEqual(v1, v2)

        expected_v2 = Vector3(4.635863249727653, 1.3245323570650438, 1.3245323570650438)
        self.assertEqual(expected_v2, v2)

    def test_clamp_mag_v3_min(self):
        v1 = Vector3(3, 1, 2)
        v2 = v1.clamp_magnitude(5, 10)
        v1.clamp_magnitude_ip(5, 10)
        expected_v2 = Vector3(4.008918628686366, 1.3363062095621219, 2.6726124191242437)
        self.assertEqual(expected_v2, v1)
        self.assertEqual(expected_v2, v2)

    def test_clamp_mag_v3_no_change(self):
        v1 = Vector3(1, 2, 3)
        for args in (
            (1, 6),
            (1.12, 5.55),
            (0.93, 6.83),
            (7.6,),
        ):
            with self.subTest(args=args):
                v2 = v1.clamp_magnitude(*args)
                v1.clamp_magnitude_ip(*args)
                self.assertEqual(v1, v2)
                self.assertEqual(v1, Vector3(1, 2, 3))

    def test_clamp_mag_v3_edge_cases(self):
        v1 = Vector3(1, 2, 1)
        v2 = v1.clamp_magnitude(6, 6)
        v1.clamp_magnitude_ip(6, 6)
        self.assertEqual(v1, v2)
        self.assertAlmostEqual(v1.length(), 6)

        v2 = v1.clamp_magnitude(0)
        v1.clamp_magnitude_ip(0, 0)
        self.assertEqual(v1, v2)
        self.assertEqual(v1, Vector3())

    def test_clamp_mag_v3_errors(self):
        v1 = Vector3(1, 2, 2)
        for invalid_args in (
            ("foo", "bar"),
            (1, 2, 3),
            (342.234, "test"),
        ):
            with self.subTest(invalid_args=invalid_args):
                self.assertRaises(TypeError, v1.clamp_magnitude, *invalid_args)
                self.assertRaises(TypeError, v1.clamp_magnitude_ip, *invalid_args)

        for invalid_args in (
            (-1,),
            (4, 3),  # min > max
            (-4, 10),
            (-4, -2),
        ):
            with self.subTest(invalid_args=invalid_args):
                self.assertRaises(ValueError, v1.clamp_magnitude, *invalid_args)
                self.assertRaises(ValueError, v1.clamp_magnitude_ip, *invalid_args)

        # 0 vector
        v2 = Vector3()
        self.assertRaises(ValueError, v2.clamp_magnitude, 3)
        self.assertRaises(ValueError, v2.clamp_magnitude_ip, 4)

    def test_subclassing_v3(self):
        """Check if Vector3 is subclassable"""
        v = Vector3(4, 2, 0)

        class TestVector(Vector3):
            def supermariobrosiscool(self):
                return 722

        other = TestVector(4, 1, 0)

        self.assertEqual(other.supermariobrosiscool(), 722)
        self.assertNotEqual(type(v), TestVector)
        self.assertNotEqual(type(v), type(other.copy()))
        self.assertEqual(TestVector, type(other.reflect(v)))
        self.assertEqual(TestVector, type(other.lerp(v, 1)))
        self.assertEqual(TestVector, type(other.slerp(v, 1)))
        self.assertEqual(TestVector, type(other.rotate(5, v)))
        self.assertEqual(TestVector, type(other.rotate_rad(5, v)))
        self.assertEqual(TestVector, type(other.project(v)))
        self.assertEqual(TestVector, type(other.move_towards(v, 5)))
        self.assertEqual(TestVector, type(other.clamp_magnitude(5)))
        self.assertEqual(TestVector, type(other.clamp_magnitude(1, 5)))
        self.assertEqual(TestVector, type(other.elementwise() + other))

        other1 = TestVector(4, 2, 0)

        self.assertEqual(type(other + other1), TestVector)
        self.assertEqual(type(other - other1), TestVector)
        self.assertEqual(type(other * 3), TestVector)
        self.assertEqual(type(other / 3), TestVector)
        self.assertEqual(type(other.elementwise() ** 3), TestVector)

    def test_move_towards_basic(self):
        expected = Vector3(7.93205057, 2006.38284641, 43.80780420)
        origin = Vector3(7.22, 2004.0, 42.13)
        target = Vector3(12.30, 2021.0, 54.1)
        change_ip = origin.copy()

        change = origin.move_towards(target, 3)
        change_ip.move_towards_ip(target, 3)

        self.assertEqual(change, expected)
        self.assertEqual(change_ip, expected)

    def test_move_towards_max_distance(self):
        expected = Vector3(12.30, 2021, 42.5)
        origin = Vector3(7.22, 2004.0, 17.5)
        change_ip = origin.copy()

        change = origin.move_towards(expected, 100)
        change_ip.move_towards_ip(expected, 100)

        self.assertEqual(change, expected)
        self.assertEqual(change_ip, expected)

    def test_move_nowhere(self):
        origin = Vector3(7.22, 2004.0, 24.5)
        target = Vector3(12.30, 2021.0, 3.2)
        change_ip = origin.copy()

        change = origin.move_towards(target, 0)
        change_ip.move_towards_ip(target, 0)

        self.assertEqual(change, origin)
        self.assertEqual(change_ip, origin)

    def test_move_away(self):
        expected = Vector3(6.74137906, 2002.39831577, 49.70890994)
        origin = Vector3(7.22, 2004.0, 52.2)
        target = Vector3(12.30, 2021.0, 78.64)
        change_ip = origin.copy()

        change = origin.move_towards(target, -3)
        change_ip.move_towards_ip(target, -3)

        self.assertEqual(change, expected)
        self.assertEqual(change_ip, expected)

    def test_move_towards_self(self):
        vec = Vector3(6.36, 2001.13, -123.14)
        vec2 = vec.copy()
        for dist in (-3.54, -1, 0, 0.234, 12):
            self.assertEqual(vec.move_towards(vec2, dist), vec)
            vec2.move_towards_ip(vec, dist)
            self.assertEqual(vec, vec2)

    def test_move_towards_errors(self):
        origin = Vector3(7.22, 2004.0, 4.1)
        target = Vector3(12.30, 2021.0, -421.5)

        self.assertRaises(TypeError, origin.move_towards, target, 3, 2)
        self.assertRaises(TypeError, origin.move_towards_ip, target, 3, 2)
        self.assertRaises(TypeError, origin.move_towards, target, "a")
        self.assertRaises(TypeError, origin.move_towards_ip, target, "b")
        self.assertRaises(TypeError, origin.move_towards, "c", 3)
        self.assertRaises(TypeError, origin.move_towards_ip, "d", 3)


if __name__ == "__main__":
    unittest.main()
