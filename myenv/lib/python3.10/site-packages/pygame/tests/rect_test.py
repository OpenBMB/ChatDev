import math
import unittest
from collections.abc import Collection, Sequence
import platform
import random
import unittest

from pygame import Rect, Vector2
from pygame.tests import test_utils

IS_PYPY = "PyPy" == platform.python_implementation()

# todo can they be different on different platforms?
_int_min = -2147483647 - 1  # min value of int in C
_int_max = 2147483647  # max value of int in C


def _random_int():
    return random.randint(_int_min, _int_max)


class RectTypeTest(unittest.TestCase):
    def _assertCountEqual(self, *args, **kwargs):
        self.assertCountEqual(*args, **kwargs)

    def testConstructionXYWidthHeight(self):
        r = Rect(1, 2, 3, 4)
        self.assertEqual(1, r.left)
        self.assertEqual(2, r.top)
        self.assertEqual(3, r.width)
        self.assertEqual(4, r.height)

    def testConstructionTopLeftSize(self):
        r = Rect((1, 2), (3, 4))
        self.assertEqual(1, r.left)
        self.assertEqual(2, r.top)
        self.assertEqual(3, r.width)
        self.assertEqual(4, r.height)

    def testCalculatedAttributes(self):
        r = Rect(1, 2, 3, 4)

        self.assertEqual(r.left + r.width, r.right)
        self.assertEqual(r.top + r.height, r.bottom)
        self.assertEqual((r.width, r.height), r.size)
        self.assertEqual((r.left, r.top), r.topleft)
        self.assertEqual((r.right, r.top), r.topright)
        self.assertEqual((r.left, r.bottom), r.bottomleft)
        self.assertEqual((r.right, r.bottom), r.bottomright)

        midx = r.left + r.width // 2
        midy = r.top + r.height // 2

        self.assertEqual(midx, r.centerx)
        self.assertEqual(midy, r.centery)
        self.assertEqual((r.centerx, r.centery), r.center)
        self.assertEqual((r.centerx, r.top), r.midtop)
        self.assertEqual((r.centerx, r.bottom), r.midbottom)
        self.assertEqual((r.left, r.centery), r.midleft)
        self.assertEqual((r.right, r.centery), r.midright)

    def test_rect_iter(self):
        rect = Rect(50, 100, 150, 200)

        # call __iter__ explicitly to test that it is defined
        rect_iterator = rect.__iter__()
        for i, val in enumerate(rect_iterator):
            self.assertEqual(rect[i], val)

    def test_normalize(self):
        """Ensures normalize works when width and height are both negative."""
        test_rect = Rect((1, 2), (-3, -6))
        expected_normalized_rect = (
            (test_rect.x + test_rect.w, test_rect.y + test_rect.h),
            (-test_rect.w, -test_rect.h),
        )

        test_rect.normalize()

        self.assertEqual(test_rect, expected_normalized_rect)

    def test_normalize__positive_height(self):
        """Ensures normalize works with a negative width and a positive height."""
        test_rect = Rect((1, 2), (-3, 6))
        expected_normalized_rect = (
            (test_rect.x + test_rect.w, test_rect.y),
            (-test_rect.w, test_rect.h),
        )

        test_rect.normalize()

        self.assertEqual(test_rect, expected_normalized_rect)

    def test_normalize__positive_width(self):
        """Ensures normalize works with a positive width and a negative height."""
        test_rect = Rect((1, 2), (3, -6))
        expected_normalized_rect = (
            (test_rect.x, test_rect.y + test_rect.h),
            (test_rect.w, -test_rect.h),
        )

        test_rect.normalize()

        self.assertEqual(test_rect, expected_normalized_rect)

    def test_normalize__zero_height(self):
        """Ensures normalize works with a negative width and a zero height."""
        test_rect = Rect((1, 2), (-3, 0))
        expected_normalized_rect = (
            (test_rect.x + test_rect.w, test_rect.y),
            (-test_rect.w, test_rect.h),
        )

        test_rect.normalize()

        self.assertEqual(test_rect, expected_normalized_rect)

    def test_normalize__zero_width(self):
        """Ensures normalize works with a zero width and a negative height."""
        test_rect = Rect((1, 2), (0, -6))
        expected_normalized_rect = (
            (test_rect.x, test_rect.y + test_rect.h),
            (test_rect.w, -test_rect.h),
        )

        test_rect.normalize()

        self.assertEqual(test_rect, expected_normalized_rect)

    def test_normalize__non_negative(self):
        """Ensures normalize works when width and height are both non-negative.

        Tests combinations of positive and zero values for width and height.
        The normalize method has no impact when both width and height are
        non-negative.
        """
        for size in ((3, 6), (3, 0), (0, 6), (0, 0)):
            test_rect = Rect((1, 2), size)
            expected_normalized_rect = Rect(test_rect)

            test_rect.normalize()

            self.assertEqual(test_rect, expected_normalized_rect)

    def test_x(self):
        """Ensures changing the x attribute moves the rect and does not change
        the rect's size.
        """
        expected_x = 10
        expected_y = 2
        expected_size = (3, 4)
        r = Rect((1, expected_y), expected_size)

        r.x = expected_x

        self.assertEqual(r.x, expected_x)
        self.assertEqual(r.x, r.left)
        self.assertEqual(r.y, expected_y)
        self.assertEqual(r.size, expected_size)

    def test_x__invalid_value(self):
        """Ensures the x attribute handles invalid values correctly."""
        r = Rect(0, 0, 1, 1)

        for value in (None, [], "1", (1,), [1, 2, 3]):
            with self.assertRaises(TypeError):
                r.x = value

    def test_x__del(self):
        """Ensures the x attribute can't be deleted."""
        r = Rect(0, 0, 1, 1)

        with self.assertRaises(AttributeError):
            del r.x

    def test_y(self):
        """Ensures changing the y attribute moves the rect and does not change
        the rect's size.
        """
        expected_x = 1
        expected_y = 20
        expected_size = (3, 4)
        r = Rect((expected_x, 2), expected_size)

        r.y = expected_y

        self.assertEqual(r.y, expected_y)
        self.assertEqual(r.y, r.top)
        self.assertEqual(r.x, expected_x)
        self.assertEqual(r.size, expected_size)

    def test_y__invalid_value(self):
        """Ensures the y attribute handles invalid values correctly."""
        r = Rect(0, 0, 1, 1)

        for value in (None, [], "1", (1,), [1, 2, 3]):
            with self.assertRaises(TypeError):
                r.y = value

    def test_y__del(self):
        """Ensures the y attribute can't be deleted."""
        r = Rect(0, 0, 1, 1)

        with self.assertRaises(AttributeError):
            del r.y

    def test_left(self):
        """Changing the left attribute moves the rect and does not change
        the rect's width
        """
        r = Rect(1, 2, 3, 4)
        new_left = 10

        r.left = new_left
        self.assertEqual(new_left, r.left)
        self.assertEqual(Rect(new_left, 2, 3, 4), r)

    def test_left__invalid_value(self):
        """Ensures the left attribute handles invalid values correctly."""
        r = Rect(0, 0, 1, 1)

        for value in (None, [], "1", (1,), [1, 2, 3]):
            with self.assertRaises(TypeError):
                r.left = value

    def test_left__del(self):
        """Ensures the left attribute can't be deleted."""
        r = Rect(0, 0, 1, 1)

        with self.assertRaises(AttributeError):
            del r.left

    def test_right(self):
        """Changing the right attribute moves the rect and does not change
        the rect's width
        """
        r = Rect(1, 2, 3, 4)
        new_right = r.right + 20
        expected_left = r.left + 20
        old_width = r.width

        r.right = new_right
        self.assertEqual(new_right, r.right)
        self.assertEqual(expected_left, r.left)
        self.assertEqual(old_width, r.width)

    def test_right__invalid_value(self):
        """Ensures the right attribute handles invalid values correctly."""
        r = Rect(0, 0, 1, 1)

        for value in (None, [], "1", (1,), [1, 2, 3]):
            with self.assertRaises(TypeError):
                r.right = value

    def test_right__del(self):
        """Ensures the right attribute can't be deleted."""
        r = Rect(0, 0, 1, 1)

        with self.assertRaises(AttributeError):
            del r.right

    def test_top(self):
        """Changing the top attribute moves the rect and does not change
        the rect's width
        """
        r = Rect(1, 2, 3, 4)
        new_top = 10

        r.top = new_top
        self.assertEqual(Rect(1, new_top, 3, 4), r)
        self.assertEqual(new_top, r.top)

    def test_top__invalid_value(self):
        """Ensures the top attribute handles invalid values correctly."""
        r = Rect(0, 0, 1, 1)

        for value in (None, [], "1", (1,), [1, 2, 3]):
            with self.assertRaises(TypeError):
                r.top = value

    def test_top__del(self):
        """Ensures the top attribute can't be deleted."""
        r = Rect(0, 0, 1, 1)

        with self.assertRaises(AttributeError):
            del r.top

    def test_bottom(self):
        """Changing the bottom attribute moves the rect and does not change
        the rect's height
        """
        r = Rect(1, 2, 3, 4)
        new_bottom = r.bottom + 20
        expected_top = r.top + 20
        old_height = r.height

        r.bottom = new_bottom
        self.assertEqual(new_bottom, r.bottom)
        self.assertEqual(expected_top, r.top)
        self.assertEqual(old_height, r.height)

    def test_bottom__invalid_value(self):
        """Ensures the bottom attribute handles invalid values correctly."""
        r = Rect(0, 0, 1, 1)

        for value in (None, [], "1", (1,), [1, 2, 3]):
            with self.assertRaises(TypeError):
                r.bottom = value

    def test_bottom__del(self):
        """Ensures the bottom attribute can't be deleted."""
        r = Rect(0, 0, 1, 1)

        with self.assertRaises(AttributeError):
            del r.bottom

    def test_centerx(self):
        """Changing the centerx attribute moves the rect and does not change
        the rect's width
        """
        r = Rect(1, 2, 3, 4)
        new_centerx = r.centerx + 20
        expected_left = r.left + 20
        old_width = r.width

        r.centerx = new_centerx
        self.assertEqual(new_centerx, r.centerx)
        self.assertEqual(expected_left, r.left)
        self.assertEqual(old_width, r.width)

    def test_centerx__invalid_value(self):
        """Ensures the centerx attribute handles invalid values correctly."""
        r = Rect(0, 0, 1, 1)

        for value in (None, [], "1", (1,), [1, 2, 3]):
            with self.assertRaises(TypeError):
                r.centerx = value

    def test_centerx__del(self):
        """Ensures the centerx attribute can't be deleted."""
        r = Rect(0, 0, 1, 1)

        with self.assertRaises(AttributeError):
            del r.centerx

    def test_centery(self):
        """Changing the centery attribute moves the rect and does not change
        the rect's width
        """
        r = Rect(1, 2, 3, 4)
        new_centery = r.centery + 20
        expected_top = r.top + 20
        old_height = r.height

        r.centery = new_centery
        self.assertEqual(new_centery, r.centery)
        self.assertEqual(expected_top, r.top)
        self.assertEqual(old_height, r.height)

    def test_centery__invalid_value(self):
        """Ensures the centery attribute handles invalid values correctly."""
        r = Rect(0, 0, 1, 1)

        for value in (None, [], "1", (1,), [1, 2, 3]):
            with self.assertRaises(TypeError):
                r.centery = value

    def test_centery__del(self):
        """Ensures the centery attribute can't be deleted."""
        r = Rect(0, 0, 1, 1)

        with self.assertRaises(AttributeError):
            del r.centery

    def test_topleft(self):
        """Changing the topleft attribute moves the rect and does not change
        the rect's size
        """
        r = Rect(1, 2, 3, 4)
        new_topleft = (r.left + 20, r.top + 30)
        old_size = r.size

        r.topleft = new_topleft
        self.assertEqual(new_topleft, r.topleft)
        self.assertEqual(old_size, r.size)

    def test_topleft__invalid_value(self):
        """Ensures the topleft attribute handles invalid values correctly."""
        r = Rect(0, 0, 1, 1)

        for value in (None, [], "1", 1, (1,), [1, 2, 3]):
            with self.assertRaises(TypeError):
                r.topleft = value

    def test_topleft__del(self):
        """Ensures the topleft attribute can't be deleted."""
        r = Rect(0, 0, 1, 1)

        with self.assertRaises(AttributeError):
            del r.topleft

    def test_bottomleft(self):
        """Changing the bottomleft attribute moves the rect and does not change
        the rect's size
        """
        r = Rect(1, 2, 3, 4)
        new_bottomleft = (r.left + 20, r.bottom + 30)
        expected_topleft = (r.left + 20, r.top + 30)
        old_size = r.size

        r.bottomleft = new_bottomleft
        self.assertEqual(new_bottomleft, r.bottomleft)
        self.assertEqual(expected_topleft, r.topleft)
        self.assertEqual(old_size, r.size)

    def test_bottomleft__invalid_value(self):
        """Ensures the bottomleft attribute handles invalid values correctly."""
        r = Rect(0, 0, 1, 1)

        for value in (None, [], "1", 1, (1,), [1, 2, 3]):
            with self.assertRaises(TypeError):
                r.bottomleft = value

    def test_bottomleft__del(self):
        """Ensures the bottomleft attribute can't be deleted."""
        r = Rect(0, 0, 1, 1)

        with self.assertRaises(AttributeError):
            del r.bottomleft

    def test_topright(self):
        """Changing the topright attribute moves the rect and does not change
        the rect's size
        """
        r = Rect(1, 2, 3, 4)
        new_topright = (r.right + 20, r.top + 30)
        expected_topleft = (r.left + 20, r.top + 30)
        old_size = r.size

        r.topright = new_topright
        self.assertEqual(new_topright, r.topright)
        self.assertEqual(expected_topleft, r.topleft)
        self.assertEqual(old_size, r.size)

    def test_topright__invalid_value(self):
        """Ensures the topright attribute handles invalid values correctly."""
        r = Rect(0, 0, 1, 1)

        for value in (None, [], "1", 1, (1,), [1, 2, 3]):
            with self.assertRaises(TypeError):
                r.topright = value

    def test_topright__del(self):
        """Ensures the topright attribute can't be deleted."""
        r = Rect(0, 0, 1, 1)

        with self.assertRaises(AttributeError):
            del r.topright

    def test_bottomright(self):
        """Changing the bottomright attribute moves the rect and does not change
        the rect's size
        """
        r = Rect(1, 2, 3, 4)
        new_bottomright = (r.right + 20, r.bottom + 30)
        expected_topleft = (r.left + 20, r.top + 30)
        old_size = r.size

        r.bottomright = new_bottomright
        self.assertEqual(new_bottomright, r.bottomright)
        self.assertEqual(expected_topleft, r.topleft)
        self.assertEqual(old_size, r.size)

    def test_bottomright__invalid_value(self):
        """Ensures the bottomright attribute handles invalid values correctly."""
        r = Rect(0, 0, 1, 1)

        for value in (None, [], "1", 1, (1,), [1, 2, 3]):
            with self.assertRaises(TypeError):
                r.bottomright = value

    def test_bottomright__del(self):
        """Ensures the bottomright attribute can't be deleted."""
        r = Rect(0, 0, 1, 1)

        with self.assertRaises(AttributeError):
            del r.bottomright

    def test_center(self):
        """Changing the center attribute moves the rect and does not change
        the rect's size
        """
        r = Rect(1, 2, 3, 4)
        new_center = (r.centerx + 20, r.centery + 30)
        expected_topleft = (r.left + 20, r.top + 30)
        old_size = r.size

        r.center = new_center
        self.assertEqual(new_center, r.center)
        self.assertEqual(expected_topleft, r.topleft)
        self.assertEqual(old_size, r.size)

    def test_center__invalid_value(self):
        """Ensures the center attribute handles invalid values correctly."""
        r = Rect(0, 0, 1, 1)

        for value in (None, [], "1", 1, (1,), [1, 2, 3]):
            with self.assertRaises(TypeError):
                r.center = value

    def test_center__del(self):
        """Ensures the center attribute can't be deleted."""
        r = Rect(0, 0, 1, 1)

        with self.assertRaises(AttributeError):
            del r.center

    def test_midleft(self):
        """Changing the midleft attribute moves the rect and does not change
        the rect's size
        """
        r = Rect(1, 2, 3, 4)
        new_midleft = (r.left + 20, r.centery + 30)
        expected_topleft = (r.left + 20, r.top + 30)
        old_size = r.size

        r.midleft = new_midleft
        self.assertEqual(new_midleft, r.midleft)
        self.assertEqual(expected_topleft, r.topleft)
        self.assertEqual(old_size, r.size)

    def test_midleft__invalid_value(self):
        """Ensures the midleft attribute handles invalid values correctly."""
        r = Rect(0, 0, 1, 1)

        for value in (None, [], "1", 1, (1,), [1, 2, 3]):
            with self.assertRaises(TypeError):
                r.midleft = value

    def test_midleft__del(self):
        """Ensures the midleft attribute can't be deleted."""
        r = Rect(0, 0, 1, 1)

        with self.assertRaises(AttributeError):
            del r.midleft

    def test_midright(self):
        """Changing the midright attribute moves the rect and does not change
        the rect's size
        """
        r = Rect(1, 2, 3, 4)
        new_midright = (r.right + 20, r.centery + 30)
        expected_topleft = (r.left + 20, r.top + 30)
        old_size = r.size

        r.midright = new_midright
        self.assertEqual(new_midright, r.midright)
        self.assertEqual(expected_topleft, r.topleft)
        self.assertEqual(old_size, r.size)

    def test_midright__invalid_value(self):
        """Ensures the midright attribute handles invalid values correctly."""
        r = Rect(0, 0, 1, 1)

        for value in (None, [], "1", 1, (1,), [1, 2, 3]):
            with self.assertRaises(TypeError):
                r.midright = value

    def test_midright__del(self):
        """Ensures the midright attribute can't be deleted."""
        r = Rect(0, 0, 1, 1)

        with self.assertRaises(AttributeError):
            del r.midright

    def test_midtop(self):
        """Changing the midtop attribute moves the rect and does not change
        the rect's size
        """
        r = Rect(1, 2, 3, 4)
        new_midtop = (r.centerx + 20, r.top + 30)
        expected_topleft = (r.left + 20, r.top + 30)
        old_size = r.size

        r.midtop = new_midtop
        self.assertEqual(new_midtop, r.midtop)
        self.assertEqual(expected_topleft, r.topleft)
        self.assertEqual(old_size, r.size)

    def test_midtop__invalid_value(self):
        """Ensures the midtop attribute handles invalid values correctly."""
        r = Rect(0, 0, 1, 1)

        for value in (None, [], "1", 1, (1,), [1, 2, 3]):
            with self.assertRaises(TypeError):
                r.midtop = value

    def test_midtop__del(self):
        """Ensures the midtop attribute can't be deleted."""
        r = Rect(0, 0, 1, 1)

        with self.assertRaises(AttributeError):
            del r.midtop

    def test_midbottom(self):
        """Changing the midbottom attribute moves the rect and does not change
        the rect's size
        """
        r = Rect(1, 2, 3, 4)
        new_midbottom = (r.centerx + 20, r.bottom + 30)
        expected_topleft = (r.left + 20, r.top + 30)
        old_size = r.size

        r.midbottom = new_midbottom
        self.assertEqual(new_midbottom, r.midbottom)
        self.assertEqual(expected_topleft, r.topleft)
        self.assertEqual(old_size, r.size)

    def test_midbottom__invalid_value(self):
        """Ensures the midbottom attribute handles invalid values correctly."""
        r = Rect(0, 0, 1, 1)

        for value in (None, [], "1", 1, (1,), [1, 2, 3]):
            with self.assertRaises(TypeError):
                r.midbottom = value

    def test_midbottom__del(self):
        """Ensures the midbottom attribute can't be deleted."""
        r = Rect(0, 0, 1, 1)

        with self.assertRaises(AttributeError):
            del r.midbottom

    def test_width(self):
        """Changing the width resizes the rect from the top-left corner"""
        r = Rect(1, 2, 3, 4)
        new_width = 10
        old_topleft = r.topleft
        old_height = r.height

        r.width = new_width
        self.assertEqual(new_width, r.width)
        self.assertEqual(old_height, r.height)
        self.assertEqual(old_topleft, r.topleft)

    def test_width__invalid_value(self):
        """Ensures the width attribute handles invalid values correctly."""
        r = Rect(0, 0, 1, 1)

        for value in (None, [], "1", (1,), [1, 2, 3]):
            with self.assertRaises(TypeError):
                r.width = value

    def test_width__del(self):
        """Ensures the width attribute can't be deleted."""
        r = Rect(0, 0, 1, 1)

        with self.assertRaises(AttributeError):
            del r.width

    def test_height(self):
        """Changing the height resizes the rect from the top-left corner"""
        r = Rect(1, 2, 3, 4)
        new_height = 10
        old_topleft = r.topleft
        old_width = r.width

        r.height = new_height
        self.assertEqual(new_height, r.height)
        self.assertEqual(old_width, r.width)
        self.assertEqual(old_topleft, r.topleft)

    def test_height__invalid_value(self):
        """Ensures the height attribute handles invalid values correctly."""
        r = Rect(0, 0, 1, 1)

        for value in (None, [], "1", (1,), [1, 2, 3]):
            with self.assertRaises(TypeError):
                r.height = value

    def test_height__del(self):
        """Ensures the height attribute can't be deleted."""
        r = Rect(0, 0, 1, 1)

        with self.assertRaises(AttributeError):
            del r.height

    def test_size(self):
        """Changing the size resizes the rect from the top-left corner"""
        r = Rect(1, 2, 3, 4)
        new_size = (10, 20)
        old_topleft = r.topleft

        r.size = new_size
        self.assertEqual(new_size, r.size)
        self.assertEqual(old_topleft, r.topleft)

    def test_size__invalid_value(self):
        """Ensures the size attribute handles invalid values correctly."""
        r = Rect(0, 0, 1, 1)

        for value in (None, [], "1", 1, (1,), [1, 2, 3]):
            with self.assertRaises(TypeError):
                r.size = value

    def test_size__del(self):
        """Ensures the size attribute can't be deleted."""
        r = Rect(0, 0, 1, 1)

        with self.assertRaises(AttributeError):
            del r.size

    def test_contains(self):
        r = Rect(1, 2, 3, 4)

        self.assertTrue(
            r.contains(Rect(2, 3, 1, 1)), "r does not contain Rect(2, 3, 1, 1)"
        )
        self.assertTrue(Rect(2, 3, 1, 1) in r, "r does not contain Rect(2, 3, 1, 1) 2")
        self.assertTrue(
            r.contains(Rect(r)), "r does not contain the same rect as itself"
        )
        self.assertTrue(r in Rect(r), "r does not contain the same rect as itself")
        self.assertTrue(
            r.contains(Rect(2, 3, 0, 0)),
            "r does not contain an empty rect within its bounds",
        )
        self.assertTrue(
            Rect(2, 3, 0, 0) in r,
            "r does not contain an empty rect within its bounds",
        )
        self.assertFalse(r.contains(Rect(0, 0, 1, 2)), "r contains Rect(0, 0, 1, 2)")
        self.assertFalse(r.contains(Rect(4, 6, 1, 1)), "r contains Rect(4, 6, 1, 1)")
        self.assertFalse(r.contains(Rect(4, 6, 0, 0)), "r contains Rect(4, 6, 0, 0)")
        self.assertFalse(Rect(0, 0, 1, 2) in r, "r contains Rect(0, 0, 1, 2)")
        self.assertFalse(Rect(4, 6, 1, 1) in r, "r contains Rect(4, 6, 1, 1)")
        self.assertFalse(Rect(4, 6, 0, 0) in r, "r contains Rect(4, 6, 0, 0)")
        self.assertTrue(2 in Rect(0, 0, 1, 2), "r does not contain 2")
        self.assertFalse(3 in Rect(0, 0, 1, 2), "r contains 3")

        self.assertRaises(TypeError, lambda: "string" in Rect(0, 0, 1, 2))
        self.assertRaises(TypeError, lambda: 4 + 3j in Rect(0, 0, 1, 2))

    def test_collidepoint(self):
        r = Rect(1, 2, 3, 4)

        self.assertTrue(
            r.collidepoint(r.left, r.top), "r does not collide with point (left, top)"
        )
        self.assertFalse(
            r.collidepoint(r.left - 1, r.top), "r collides with point (left - 1, top)"
        )
        self.assertFalse(
            r.collidepoint(r.left, r.top - 1), "r collides with point (left, top - 1)"
        )
        self.assertFalse(
            r.collidepoint(r.left - 1, r.top - 1),
            "r collides with point (left - 1, top - 1)",
        )

        self.assertTrue(
            r.collidepoint(r.right - 1, r.bottom - 1),
            "r does not collide with point (right - 1, bottom - 1)",
        )
        self.assertFalse(
            r.collidepoint(r.right, r.bottom), "r collides with point (right, bottom)"
        )
        self.assertFalse(
            r.collidepoint(r.right - 1, r.bottom),
            "r collides with point (right - 1, bottom)",
        )
        self.assertFalse(
            r.collidepoint(r.right, r.bottom - 1),
            "r collides with point (right, bottom - 1)",
        )

    def test_inflate__larger(self):
        """The inflate method inflates around the center of the rectangle"""
        r = Rect(2, 4, 6, 8)
        r2 = r.inflate(4, 6)

        self.assertEqual(r.center, r2.center)
        self.assertEqual(r.left - 2, r2.left)
        self.assertEqual(r.top - 3, r2.top)
        self.assertEqual(r.right + 2, r2.right)
        self.assertEqual(r.bottom + 3, r2.bottom)
        self.assertEqual(r.width + 4, r2.width)
        self.assertEqual(r.height + 6, r2.height)

    def test_inflate__smaller(self):
        """The inflate method inflates around the center of the rectangle"""
        r = Rect(2, 4, 6, 8)
        r2 = r.inflate(-4, -6)

        self.assertEqual(r.center, r2.center)
        self.assertEqual(r.left + 2, r2.left)
        self.assertEqual(r.top + 3, r2.top)
        self.assertEqual(r.right - 2, r2.right)
        self.assertEqual(r.bottom - 3, r2.bottom)
        self.assertEqual(r.width - 4, r2.width)
        self.assertEqual(r.height - 6, r2.height)

    def test_inflate_ip__larger(self):
        """The inflate_ip method inflates around the center of the rectangle"""
        r = Rect(2, 4, 6, 8)
        r2 = Rect(r)
        r2.inflate_ip(-4, -6)

        self.assertEqual(r.center, r2.center)
        self.assertEqual(r.left + 2, r2.left)
        self.assertEqual(r.top + 3, r2.top)
        self.assertEqual(r.right - 2, r2.right)
        self.assertEqual(r.bottom - 3, r2.bottom)
        self.assertEqual(r.width - 4, r2.width)
        self.assertEqual(r.height - 6, r2.height)

    def test_inflate_ip__smaller(self):
        """The inflate method inflates around the center of the rectangle"""
        r = Rect(2, 4, 6, 8)
        r2 = Rect(r)
        r2.inflate_ip(-4, -6)

        self.assertEqual(r.center, r2.center)
        self.assertEqual(r.left + 2, r2.left)
        self.assertEqual(r.top + 3, r2.top)
        self.assertEqual(r.right - 2, r2.right)
        self.assertEqual(r.bottom - 3, r2.bottom)
        self.assertEqual(r.width - 4, r2.width)
        self.assertEqual(r.height - 6, r2.height)

    def test_scale_by__larger_single_argument(self):
        """The scale method scales around the center of the rectangle"""
        r = Rect(2, 4, 6, 8)
        r2 = r.scale_by(2)

        self.assertEqual(r.center, r2.center)
        self.assertEqual(r.left - 3, r2.left)
        self.assertEqual(r.top - 4, r2.top)
        self.assertEqual(r.right + 3, r2.right)
        self.assertEqual(r.bottom + 4, r2.bottom)
        self.assertEqual(r.width * 2, r2.width)
        self.assertEqual(r.height * 2, r2.height)

    def test_scale_by__larger_single_argument_kwarg(self):
        """The scale method scales around the center of the rectangle using
        keyword arguments 'x' and 'y'"""
        r = Rect(2, 4, 6, 8)
        r2 = r.scale_by(x=2)

        self.assertEqual(r.center, r2.center)
        self.assertEqual(r.left - 3, r2.left)
        self.assertEqual(r.top - 4, r2.top)
        self.assertEqual(r.right + 3, r2.right)
        self.assertEqual(r.bottom + 4, r2.bottom)
        self.assertEqual(r.width * 2, r2.width)
        self.assertEqual(r.height * 2, r2.height)

    def test_scale_by__smaller_single_argument(self):
        """The scale method scales around the center of the rectangle"""
        r = Rect(2, 4, 8, 8)
        r2 = r.scale_by(0.5)

        self.assertEqual(r.center, r2.center)
        self.assertEqual(r.left + 2, r2.left)
        self.assertEqual(r.top + 2, r2.top)
        self.assertEqual(r.right - 2, r2.right)
        self.assertEqual(r.bottom - 2, r2.bottom)
        self.assertEqual(r.width - 4, r2.width)
        self.assertEqual(r.height - 4, r2.height)

    def test_scale_by__larger(self):
        """The scale method scales around the center of the rectangle"""
        # arrange
        r = Rect(2, 4, 6, 8)
        # act
        r2 = r.scale_by(2, 4)
        # assert
        self.assertEqual(r.center, r2.center)
        self.assertEqual(r.left - 3, r2.left)
        self.assertEqual(r.centery - r.h * 4 / 2, r2.top)
        self.assertEqual(r.right + 3, r2.right)
        self.assertEqual(r.centery + r.h * 4 / 2, r2.bottom)
        self.assertEqual(r.width * 2, r2.width)
        self.assertEqual(r.height * 4, r2.height)

    def test_scale_by__larger_kwargs_scale_by(self):
        """
        The scale method scales around the center of the rectangle
        Uses 'scale_by' kwarg.
        """
        # arrange
        r = Rect(2, 4, 6, 8)
        # act
        r2 = r.scale_by(scale_by=(2, 4))
        # assert
        self.assertEqual(r.center, r2.center)
        self.assertEqual(r.left - 3, r2.left)
        self.assertEqual(r.centery - r.h * 4 / 2, r2.top)
        self.assertEqual(r.right + 3, r2.right)
        self.assertEqual(r.centery + r.h * 4 / 2, r2.bottom)
        self.assertEqual(r.width * 2, r2.width)
        self.assertEqual(r.height * 4, r2.height)

    def test_scale_by__larger_kwargs(self):
        """
        The scale method scales around the center of the rectangle
        Uses 'x' and 'y' kwargs.
        """
        # arrange
        r = Rect(2, 4, 6, 8)
        # act
        r2 = r.scale_by(x=2, y=4)
        # assert
        self.assertEqual(r.center, r2.center)
        self.assertEqual(r.left - 3, r2.left)
        self.assertEqual(r.centery - r.h * 4 / 2, r2.top)
        self.assertEqual(r.right + 3, r2.right)
        self.assertEqual(r.centery + r.h * 4 / 2, r2.bottom)
        self.assertEqual(r.width * 2, r2.width)
        self.assertEqual(r.height * 4, r2.height)

    def test_scale_by__smaller(self):
        """The scale method scales around the center of the rectangle"""
        # arrange
        r = Rect(2, 4, 8, 8)
        # act
        r2 = r.scale_by(0.5, 0.25)
        # assert
        self.assertEqual(r.center, r2.center)
        self.assertEqual(r.left + 2, r2.left)
        self.assertEqual(r.centery - r.h / 4 / 2, r2.top)
        self.assertEqual(r.right - 2, r2.right)
        self.assertEqual(r.centery + r.h / 4 / 2, r2.bottom)
        self.assertEqual(r.width - 4, r2.width)
        self.assertEqual(r.height // 4, r2.height)

    def test_scale_by__subzero(self):
        """The scale method scales around the center of the rectangle"""
        r = Rect(2, 4, 6, 8)
        r.scale_by(0)
        r.scale_by(-1)
        r.scale_by(-0.000001)
        r.scale_by(0.00001)

        rx1 = r.scale_by(10, 1)
        self.assertEqual(r.centerx - r.w * 10 / 2, rx1.x)
        self.assertEqual(r.y, rx1.y)
        self.assertEqual(r.w * 10, rx1.w)
        self.assertEqual(r.h, rx1.h)
        rx2 = r.scale_by(-10, 1)
        self.assertEqual(rx1.x, rx2.x)
        self.assertEqual(rx1.y, rx2.y)
        self.assertEqual(rx1.w, rx2.w)
        self.assertEqual(rx1.h, rx2.h)

        ry1 = r.scale_by(1, 10)
        self.assertEqual(r.x, ry1.x)
        self.assertEqual(r.centery - r.h * 10 / 2, ry1.y)
        self.assertEqual(r.w, ry1.w)
        self.assertEqual(r.h * 10, ry1.h)
        ry2 = r.scale_by(1, -10)
        self.assertEqual(ry1.x, ry2.x)
        self.assertEqual(ry1.y, ry2.y)
        self.assertEqual(ry1.w, ry2.w)
        self.assertEqual(ry1.h, ry2.h)

        r1 = r.scale_by(10)
        self.assertEqual(r.centerx - r.w * 10 / 2, r1.x)
        self.assertEqual(r.centery - r.h * 10 / 2, r1.y)
        self.assertEqual(r.w * 10, r1.w)
        self.assertEqual(r.h * 10, r1.h)

    def test_scale_by_identity(self):
        """The scale method scales around the center of the rectangle"""
        # arrange
        r = Rect(2, 4, 6, 8)
        # act
        actual = r.scale_by(1, 1)
        # assert
        self.assertEqual(r.x, actual.x)
        self.assertEqual(r.y, actual.y)
        self.assertEqual(r.w, actual.w)
        self.assertEqual(r.h, actual.h)

    def test_scale_by_negative_identity(self):
        """The scale method scales around the center of the rectangle"""
        # arrange
        r = Rect(2, 4, 6, 8)
        # act
        actual = r.scale_by(-1, -1)
        # assert
        self.assertEqual(r.x, actual.x)
        self.assertEqual(r.y, actual.y)
        self.assertEqual(r.w, actual.w)
        self.assertEqual(r.h, actual.h)

    def test_scale_by_identity_single_argument(self):
        """The scale method scales around the center of the rectangle"""
        # arrange
        r = Rect(2, 4, 6, 8)
        # act
        actual = r.scale_by(1)
        # assert
        self.assertEqual(r.x, actual.x)
        self.assertEqual(r.y, actual.y)
        self.assertEqual(r.w, actual.w)
        self.assertEqual(r.h, actual.h)

    def test_scale_by_negative_identity_single_argment(self):
        """The scale method scales around the center of the rectangle"""
        # arrange
        r = Rect(2, 4, 6, 8)
        # act
        actual = r.scale_by(-1)
        # assert
        self.assertEqual(r.x, actual.x)
        self.assertEqual(r.y, actual.y)
        self.assertEqual(r.w, actual.w)
        self.assertEqual(r.h, actual.h)

    def test_scale_by_ip__larger(self):
        """The scale method scales around the center of the rectangle"""
        r = Rect(2, 4, 6, 8)
        r2 = Rect(r)
        r2.scale_by_ip(2)

        self.assertEqual(r.center, r2.center)
        self.assertEqual(r.left - 3, r2.left)
        self.assertEqual(r.top - 4, r2.top)
        self.assertEqual(r.right + 3, r2.right)
        self.assertEqual(r.bottom + 4, r2.bottom)
        self.assertEqual(r.width * 2, r2.width)
        self.assertEqual(r.height * 2, r2.height)

    def test_scale_by_ip__smaller(self):
        """The scale method scales around the center of the rectangle"""
        r = Rect(2, 4, 8, 8)
        r2 = Rect(r)
        r2.scale_by_ip(0.5)

        self.assertEqual(r.center, r2.center)
        self.assertEqual(r.left + 2, r2.left)
        self.assertEqual(r.top + 2, r2.top)
        self.assertEqual(r.right - 2, r2.right)
        self.assertEqual(r.bottom - 2, r2.bottom)
        self.assertEqual(r.width / 2, r2.width)
        self.assertEqual(r.height / 2, r2.height)

    def test_scale_by_ip__subzero(self):
        """The scale method scales around the center of the rectangle"""
        r = Rect(2, 4, 6, 8)
        r.scale_by_ip(0)
        r.scale_by_ip(-1)
        r.scale_by_ip(-0.000001)
        r.scale_by_ip(0.00001)

    def test_scale_by_ip__kwargs(self):
        """The scale method scales around the center of the rectangle"""
        r = Rect(2, 4, 6, 8)
        r2 = Rect(r)
        r2.scale_by_ip(x=2, y=4)

        # assert
        self.assertEqual(r.center, r2.center)
        self.assertEqual(r.left - 3, r2.left)
        self.assertEqual(r.centery - r.h * 4 / 2, r2.top)
        self.assertEqual(r.right + 3, r2.right)
        self.assertEqual(r.centery + r.h * 4 / 2, r2.bottom)
        self.assertEqual(r.width * 2, r2.width)
        self.assertEqual(r.height * 4, r2.height)

    def test_scale_by_ip__kwarg_exceptions(self):
        """The scale method scales around the center of the rectangle using
        keyword argument 'scale_by'. Tests for incorrect keyword args"""
        r = Rect(2, 4, 6, 8)

        with self.assertRaises(TypeError):
            r.scale_by_ip(scale_by=2)

        with self.assertRaises(TypeError):
            r.scale_by_ip(scale_by=(1, 2), y=1)

    def test_clamp(self):
        r = Rect(10, 10, 10, 10)
        c = Rect(19, 12, 5, 5).clamp(r)
        self.assertEqual(c.right, r.right)
        self.assertEqual(c.top, 12)
        c = Rect(1, 2, 3, 4).clamp(r)
        self.assertEqual(c.topleft, r.topleft)
        c = Rect(5, 500, 22, 33).clamp(r)
        self.assertEqual(c.center, r.center)

    def test_clamp_ip(self):
        r = Rect(10, 10, 10, 10)
        c = Rect(19, 12, 5, 5)
        c.clamp_ip(r)
        self.assertEqual(c.right, r.right)
        self.assertEqual(c.top, 12)
        c = Rect(1, 2, 3, 4)
        c.clamp_ip(r)
        self.assertEqual(c.topleft, r.topleft)
        c = Rect(5, 500, 22, 33)
        c.clamp_ip(r)
        self.assertEqual(c.center, r.center)

    def test_clip(self):
        r1 = Rect(1, 2, 3, 4)
        self.assertEqual(Rect(1, 2, 2, 2), r1.clip(Rect(0, 0, 3, 4)))
        self.assertEqual(Rect(2, 2, 2, 4), r1.clip(Rect(2, 2, 10, 20)))
        self.assertEqual(Rect(2, 3, 1, 2), r1.clip(Rect(2, 3, 1, 2)))
        self.assertEqual((0, 0), r1.clip(20, 30, 5, 6).size)
        self.assertEqual(
            r1, r1.clip(Rect(r1)), "r1 does not clip an identical rect to itself"
        )

    def test_clipline(self):
        """Ensures clipline handles four int parameters.

        Tests the clipline(x1, y1, x2, y2) format.
        """
        rect = Rect((1, 2), (35, 40))
        x1 = 5
        y1 = 6
        x2 = 11
        y2 = 19
        expected_line = ((x1, y1), (x2, y2))

        clipped_line = rect.clipline(x1, y1, x2, y2)

        self.assertIsInstance(clipped_line, tuple)
        self.assertTupleEqual(clipped_line, expected_line)

    def test_clipline__two_sequences(self):
        """Ensures clipline handles a sequence of two sequences.

        Tests the clipline((x1, y1), (x2, y2)) format.
        Tests the sequences as different types.
        """
        rect = Rect((1, 2), (35, 40))
        pt1 = (5, 6)
        pt2 = (11, 19)

        INNER_SEQUENCES = (list, tuple, Vector2)
        expected_line = (pt1, pt2)

        for inner_seq1 in INNER_SEQUENCES:
            endpt1 = inner_seq1(pt1)

            for inner_seq2 in INNER_SEQUENCES:
                clipped_line = rect.clipline((endpt1, inner_seq2(pt2)))

                self.assertIsInstance(clipped_line, tuple)
                self.assertTupleEqual(clipped_line, expected_line)

    def test_clipline__two_sequences_kwarg(self):
        """Ensures clipline handles a sequence of two sequences using kwargs.

        Tests the clipline((x1, y1), (x2, y2)) format.
        Tests the sequences as different types.
        """
        rect = Rect((1, 2), (35, 40))
        pt1 = (5, 6)
        pt2 = (11, 19)

        INNER_SEQUENCES = (list, tuple, Vector2)
        expected_line = (pt1, pt2)

        for inner_seq1 in INNER_SEQUENCES:
            endpt1 = inner_seq1(pt1)

            for inner_seq2 in INNER_SEQUENCES:
                clipped_line = rect.clipline(
                    first_coordinate=endpt1, second_coordinate=inner_seq2(pt2)
                )

                self.assertIsInstance(clipped_line, tuple)
                self.assertTupleEqual(clipped_line, expected_line)

    def test_clipline__sequence_of_four_ints(self):
        """Ensures clipline handles a sequence of four ints.

        Tests the clipline((x1, y1, x2, y2)) format.
        Tests the sequence as different types.
        """
        rect = Rect((1, 2), (35, 40))
        line = (5, 6, 11, 19)
        expected_line = ((line[0], line[1]), (line[2], line[3]))

        for outer_seq in (list, tuple):
            clipped_line = rect.clipline(outer_seq(line))

            self.assertIsInstance(clipped_line, tuple)
            self.assertTupleEqual(clipped_line, expected_line)

    def test_clipline__sequence_of_four_ints_kwargs(self):
        """Ensures clipline handles a sequence of four ints using kwargs.

        Tests the clipline((x1, y1, x2, y2)) format.
        Tests the sequence as different types.
        """
        rect = Rect((1, 2), (35, 40))
        line = (5, 6, 11, 19)
        expected_line = ((line[0], line[1]), (line[2], line[3]))

        for outer_seq in (list, tuple):
            clipped_line = rect.clipline(rect_arg=outer_seq(line))

            self.assertIsInstance(clipped_line, tuple)
            self.assertTupleEqual(clipped_line, expected_line)

    def test_clipline__sequence_of_two_sequences(self):
        """Ensures clipline handles a sequence of two sequences.

        Tests the clipline(((x1, y1), (x2, y2))) format.
        Tests the sequences as different types.
        """
        rect = Rect((1, 2), (35, 40))
        pt1 = (5, 6)
        pt2 = (11, 19)

        INNER_SEQUENCES = (list, tuple, Vector2)
        expected_line = (pt1, pt2)

        for inner_seq1 in INNER_SEQUENCES:
            endpt1 = inner_seq1(pt1)

            for inner_seq2 in INNER_SEQUENCES:
                endpt2 = inner_seq2(pt2)

                for outer_seq in (list, tuple):
                    clipped_line = rect.clipline(outer_seq((endpt1, endpt2)))

                    self.assertIsInstance(clipped_line, tuple)
                    self.assertTupleEqual(clipped_line, expected_line)

    def test_clipline__sequence_of_two_sequences_kwargs(self):
        """Ensures clipline handles a sequence of two sequences using kwargs.

        Tests the clipline(((x1, y1), (x2, y2))) format.
        Tests the sequences as different types.
        """
        rect = Rect((1, 2), (35, 40))
        pt1 = (5, 6)
        pt2 = (11, 19)

        INNER_SEQUENCES = (list, tuple, Vector2)
        expected_line = (pt1, pt2)

        for inner_seq1 in INNER_SEQUENCES:
            endpt1 = inner_seq1(pt1)

            for inner_seq2 in INNER_SEQUENCES:
                endpt2 = inner_seq2(pt2)

                for outer_seq in (list, tuple):
                    clipped_line = rect.clipline(x1=outer_seq((endpt1, endpt2)))

                    self.assertIsInstance(clipped_line, tuple)
                    self.assertTupleEqual(clipped_line, expected_line)

    def test_clipline__floats(self):
        """Ensures clipline handles float parameters."""
        rect = Rect((1, 2), (35, 40))
        x1 = 5.9
        y1 = 6.9
        x2 = 11.9
        y2 = 19.9

        # Floats are truncated.
        expected_line = (
            (math.floor(x1), math.floor(y1)),
            (math.floor(x2), math.floor(y2)),
        )

        clipped_line = rect.clipline(x1, y1, x2, y2)

        self.assertIsInstance(clipped_line, tuple)
        self.assertTupleEqual(clipped_line, expected_line)

    def test_clipline__floats_kwargs(self):
        """Ensures clipline handles four float parameters.

        Tests the clipline(x1, y1, x2, y2) format.
        """
        rect = Rect((1, 2), (35, 40))
        x1 = 5.9
        y1 = 6.9
        x2 = 11.9
        y2 = 19.9

        # Floats are truncated.
        expected_line = (
            (math.floor(x1), math.floor(y1)),
            (math.floor(x2), math.floor(y2)),
        )

        clipped_line = rect.clipline(x1=x1, x2=y1, x3=x2, x4=y2)

        self.assertIsInstance(clipped_line, tuple)
        self.assertTupleEqual(clipped_line, expected_line)

    def test_clipline__kwarg_exceptions(self):
        """Ensure clipline handles incorrect keyword arguments"""
        r = Rect(2, 4, 6, 8)

        with self.assertRaises(TypeError):
            r.clipline(x1=0)

        with self.assertRaises(TypeError):
            r.clipline(first_coordinate=(1, 3, 5, 4), second_coordinate=(1, 2))

        with self.assertRaises(TypeError):
            r.clipline(first_coordinate=(1, 3), second_coordinate=(2, 2), x1=1)

        with self.assertRaises(TypeError):
            r.clipline(rect_arg=(1, 3, 5))

        with self.assertRaises(TypeError):
            r.clipline(rect_arg=(1, 3, 5, 4), second_coordinate=(2, 2))

    def test_clipline__no_overlap(self):
        """Ensures lines that do not overlap the rect are not clipped."""
        rect = Rect((10, 25), (15, 20))
        # Use a bigger rect to help create test lines.
        big_rect = rect.inflate(2, 2)
        lines = (
            (big_rect.bottomleft, big_rect.topleft),  # Left edge.
            (big_rect.topleft, big_rect.topright),  # Top edge.
            (big_rect.topright, big_rect.bottomright),  # Right edge.
            (big_rect.bottomright, big_rect.bottomleft),
        )  # Bottom edge.
        expected_line = ()

        # Test lines outside rect.
        for line in lines:
            clipped_line = rect.clipline(line)

            self.assertTupleEqual(clipped_line, expected_line)

    def test_clipline__both_endpoints_outside(self):
        """Ensures lines that overlap the rect are clipped.

        Testing lines with both endpoints outside the rect.
        """
        rect = Rect((0, 0), (20, 20))
        # Use a bigger rect to help create test lines.
        big_rect = rect.inflate(2, 2)

        # Create a dict of lines and expected results.
        line_dict = {
            (big_rect.midleft, big_rect.midright): (
                rect.midleft,
                (rect.midright[0] - 1, rect.midright[1]),
            ),
            (big_rect.midtop, big_rect.midbottom): (
                rect.midtop,
                (rect.midbottom[0], rect.midbottom[1] - 1),
            ),
            # Diagonals.
            (big_rect.topleft, big_rect.bottomright): (
                rect.topleft,
                (rect.bottomright[0] - 1, rect.bottomright[1] - 1),
            ),
            # This line needs a small adjustment to make sure it intersects
            # the rect correctly.
            (
                (big_rect.topright[0] - 1, big_rect.topright[1]),
                (big_rect.bottomleft[0], big_rect.bottomleft[1] - 1),
            ): (
                (rect.topright[0] - 1, rect.topright[1]),
                (rect.bottomleft[0], rect.bottomleft[1] - 1),
            ),
        }

        for line, expected_line in line_dict.items():
            clipped_line = rect.clipline(line)

            self.assertTupleEqual(clipped_line, expected_line)

            # Swap endpoints to test for symmetry.
            expected_line = (expected_line[1], expected_line[0])

            clipped_line = rect.clipline((line[1], line[0]))

            self.assertTupleEqual(clipped_line, expected_line)

    def test_clipline__both_endpoints_inside(self):
        """Ensures lines that overlap the rect are clipped.

        Testing lines with both endpoints inside the rect.
        """
        rect = Rect((-10, -5), (20, 20))
        # Use a smaller rect to help create test lines.
        small_rect = rect.inflate(-2, -2)

        lines = (
            (small_rect.midleft, small_rect.midright),
            (small_rect.midtop, small_rect.midbottom),
            # Diagonals.
            (small_rect.topleft, small_rect.bottomright),
            (small_rect.topright, small_rect.bottomleft),
        )

        for line in lines:
            expected_line = line

            clipped_line = rect.clipline(line)

            self.assertTupleEqual(clipped_line, expected_line)

            # Swap endpoints to test for symmetry.
            expected_line = (expected_line[1], expected_line[0])

            clipped_line = rect.clipline((line[1], line[0]))

            self.assertTupleEqual(clipped_line, expected_line)

    def test_clipline__endpoints_inside_and_outside(self):
        """Ensures lines that overlap the rect are clipped.

        Testing lines with one endpoint outside the rect and the other is
        inside the rect.
        """
        rect = Rect((0, 0), (21, 21))
        # Use a bigger rect to help create test lines.
        big_rect = rect.inflate(2, 2)

        # Create a dict of lines and expected results.
        line_dict = {
            (big_rect.midleft, rect.center): (rect.midleft, rect.center),
            (big_rect.midtop, rect.center): (rect.midtop, rect.center),
            (big_rect.midright, rect.center): (
                (rect.midright[0] - 1, rect.midright[1]),
                rect.center,
            ),
            (big_rect.midbottom, rect.center): (
                (rect.midbottom[0], rect.midbottom[1] - 1),
                rect.center,
            ),
            # Diagonals.
            (big_rect.topleft, rect.center): (rect.topleft, rect.center),
            (big_rect.topright, rect.center): (
                (rect.topright[0] - 1, rect.topright[1]),
                rect.center,
            ),
            (big_rect.bottomright, rect.center): (
                (rect.bottomright[0] - 1, rect.bottomright[1] - 1),
                rect.center,
            ),
            # This line needs a small adjustment to make sure it intersects
            # the rect correctly.
            ((big_rect.bottomleft[0], big_rect.bottomleft[1] - 1), rect.center): (
                (rect.bottomleft[0], rect.bottomleft[1] - 1),
                rect.center,
            ),
        }

        for line, expected_line in line_dict.items():
            clipped_line = rect.clipline(line)

            self.assertTupleEqual(clipped_line, expected_line)

            # Swap endpoints to test for symmetry.
            expected_line = (expected_line[1], expected_line[0])

            clipped_line = rect.clipline((line[1], line[0]))

            self.assertTupleEqual(clipped_line, expected_line)

    def test_clipline__edges(self):
        """Ensures clipline properly clips line that are along the rect edges."""
        rect = Rect((10, 25), (15, 20))

        # Create a dict of edges and expected results.
        edge_dict = {
            # Left edge.
            (rect.bottomleft, rect.topleft): (
                (rect.bottomleft[0], rect.bottomleft[1] - 1),
                rect.topleft,
            ),
            # Top edge.
            (rect.topleft, rect.topright): (
                rect.topleft,
                (rect.topright[0] - 1, rect.topright[1]),
            ),
            # Right edge.
            (rect.topright, rect.bottomright): (),
            # Bottom edge.
            (rect.bottomright, rect.bottomleft): (),
        }

        for edge, expected_line in edge_dict.items():
            clipped_line = rect.clipline(edge)

            self.assertTupleEqual(clipped_line, expected_line)

            # Swap endpoints to test for symmetry.
            if expected_line:
                expected_line = (expected_line[1], expected_line[0])

            clipped_line = rect.clipline((edge[1], edge[0]))

            self.assertTupleEqual(clipped_line, expected_line)

    def test_clipline__equal_endpoints_with_overlap(self):
        """Ensures clipline handles lines with both endpoints the same.

        Testing lines that overlap the rect.
        """
        rect = Rect((10, 25), (15, 20))

        # Test all the points in and on a rect.
        pts = (
            (x, y)
            for x in range(rect.left, rect.right)
            for y in range(rect.top, rect.bottom)
        )

        for pt in pts:
            expected_line = (pt, pt)

            clipped_line = rect.clipline((pt, pt))

            self.assertTupleEqual(clipped_line, expected_line)

    def test_clipline__equal_endpoints_no_overlap(self):
        """Ensures clipline handles lines with both endpoints the same.

        Testing lines that do not overlap the rect.
        """
        expected_line = ()
        rect = Rect((10, 25), (15, 20))

        # Test points outside rect.
        for pt in test_utils.rect_perimeter_pts(rect.inflate(2, 2)):
            clipped_line = rect.clipline((pt, pt))

            self.assertTupleEqual(clipped_line, expected_line)

    def test_clipline__zero_size_rect(self):
        """Ensures clipline handles zero sized rects correctly."""
        expected_line = ()

        for size in ((0, 15), (15, 0), (0, 0)):
            rect = Rect((10, 25), size)

            clipped_line = rect.clipline(rect.topleft, rect.topleft)

            self.assertTupleEqual(clipped_line, expected_line)

    def test_clipline__negative_size_rect(self):
        """Ensures clipline handles negative sized rects correctly."""
        expected_line = ()

        for size in ((-15, 20), (15, -20), (-15, -20)):
            rect = Rect((10, 25), size)
            norm_rect = rect.copy()
            norm_rect.normalize()
            # Use a bigger rect to help create test lines.
            big_rect = norm_rect.inflate(2, 2)

            # Create a dict of lines and expected results. Some line have both
            # endpoints outside the rect and some have one inside and one
            # outside.
            line_dict = {
                (big_rect.midleft, big_rect.midright): (
                    norm_rect.midleft,
                    (norm_rect.midright[0] - 1, norm_rect.midright[1]),
                ),
                (big_rect.midtop, big_rect.midbottom): (
                    norm_rect.midtop,
                    (norm_rect.midbottom[0], norm_rect.midbottom[1] - 1),
                ),
                (big_rect.midleft, norm_rect.center): (
                    norm_rect.midleft,
                    norm_rect.center,
                ),
                (big_rect.midtop, norm_rect.center): (
                    norm_rect.midtop,
                    norm_rect.center,
                ),
                (big_rect.midright, norm_rect.center): (
                    (norm_rect.midright[0] - 1, norm_rect.midright[1]),
                    norm_rect.center,
                ),
                (big_rect.midbottom, norm_rect.center): (
                    (norm_rect.midbottom[0], norm_rect.midbottom[1] - 1),
                    norm_rect.center,
                ),
            }

            for line, expected_line in line_dict.items():
                clipped_line = rect.clipline(line)

                # Make sure rect wasn't normalized.
                self.assertNotEqual(rect, norm_rect)
                self.assertTupleEqual(clipped_line, expected_line)

                # Swap endpoints to test for symmetry.
                expected_line = (expected_line[1], expected_line[0])

                clipped_line = rect.clipline((line[1], line[0]))

                self.assertTupleEqual(clipped_line, expected_line)

    def test_clipline__invalid_line(self):
        """Ensures clipline handles invalid lines correctly."""
        rect = Rect((0, 0), (10, 20))
        invalid_lines = (
            (),
            (1,),
            (1, 2),
            (1, 2, 3),
            (1, 2, 3, 4, 5),
            ((1, 2),),
            ((1, 2), (3,)),
            ((1, 2), 3),
            ((1, 2, 5), (3, 4)),
            ((1, 2), (3, 4, 5)),
            ((1, 2), (3, 4), (5, 6)),
        )

        for line in invalid_lines:
            with self.assertRaises(TypeError):
                clipped_line = rect.clipline(line)

            with self.assertRaises(TypeError):
                clipped_line = rect.clipline(*line)

    def test_move(self):
        r = Rect(1, 2, 3, 4)
        move_x = 10
        move_y = 20
        r2 = r.move(move_x, move_y)
        expected_r2 = Rect(r.left + move_x, r.top + move_y, r.width, r.height)
        self.assertEqual(expected_r2, r2)

    def test_move_ip(self):
        r = Rect(1, 2, 3, 4)
        r2 = Rect(r)
        move_x = 10
        move_y = 20
        r2.move_ip(move_x, move_y)
        expected_r2 = Rect(r.left + move_x, r.top + move_y, r.width, r.height)
        self.assertEqual(expected_r2, r2)

    @unittest.skipIf(
        IS_PYPY, "fails on pypy (but only for: bottom, right, centerx, centery)"
    )
    def test_set_float_values(self):
        zero = 0
        pos = 124
        neg = -432
        # (initial, increment, expected, other)
        data_rows = [
            (zero, 0.1, zero, _random_int()),
            (zero, 0.4, zero, _random_int()),
            (zero, 0.5, zero + 1, _random_int()),
            (zero, 1.1, zero + 1, _random_int()),
            (zero, 1.5, zero + 2, _random_int()),  # >0f
            (zero, -0.1, zero, _random_int()),
            (zero, -0.4, zero, _random_int()),
            (zero, -0.5, zero - 1, _random_int()),
            (zero, -0.6, zero - 1, _random_int()),
            (zero, -1.6, zero - 2, _random_int()),  # <0f
            (zero, 1, zero + 1, _random_int()),
            (zero, 4, zero + 4, _random_int()),  # >0i
            (zero, -1, zero - 1, _random_int()),
            (zero, -4, zero - 4, _random_int()),  # <0i
            (pos, 0.1, pos, _random_int()),
            (pos, 0.4, pos, _random_int()),
            (pos, 0.5, pos + 1, _random_int()),
            (pos, 1.1, pos + 1, _random_int()),
            (pos, 1.5, pos + 2, _random_int()),  # >0f
            (pos, -0.1, pos, _random_int()),
            (pos, -0.4, pos, _random_int()),
            (pos, -0.5, pos, _random_int()),
            (pos, -0.6, pos - 1, _random_int()),
            (pos, -1.6, pos - 2, _random_int()),  # <0f
            (pos, 1, pos + 1, _random_int()),
            (pos, 4, pos + 4, _random_int()),  # >0i
            (pos, -1, pos - 1, _random_int()),
            (pos, -4, pos - 4, _random_int()),  # <0i
            (neg, 0.1, neg, _random_int()),
            (neg, 0.4, neg, _random_int()),
            (neg, 0.5, neg, _random_int()),
            (neg, 1.1, neg + 1, _random_int()),
            (neg, 1.5, neg + 1, _random_int()),  # >0f
            (neg, -0.1, neg, _random_int()),
            (neg, -0.4, neg, _random_int()),
            (neg, -0.5, neg - 1, _random_int()),
            (neg, -0.6, neg - 1, _random_int()),
            (neg, -1.6, neg - 2, _random_int()),  # <0f
            (neg, 1, neg + 1, _random_int()),
            (neg, 4, neg + 4, _random_int()),  # >0i
            (neg, -1, neg - 1, _random_int()),
            (neg, -4, neg - 4, _random_int()),  # <0i
        ]

        single_value_attribute_names = [
            "x",
            "y",
            "w",
            "h",
            "width",
            "height",
            "top",
            "left",
            "bottom",
            "right",
            "centerx",
            "centery",
        ]

        tuple_value_attribute_names = [
            "topleft",
            "topright",
            "bottomleft",
            "bottomright",
            "midtop",
            "midleft",
            "midbottom",
            "midright",
            "size",
            "center",
        ]

        for row in data_rows:
            initial, inc, expected, other = row
            new_value = initial + inc
            for attribute_name in single_value_attribute_names:
                with self.subTest(row=row, name=f"r.{attribute_name}"):
                    actual = Rect(
                        _random_int(), _random_int(), _random_int(), _random_int()
                    )
                    # act
                    setattr(actual, attribute_name, new_value)
                    # assert
                    self.assertEqual(expected, getattr(actual, attribute_name))

            for attribute_name in tuple_value_attribute_names:
                with self.subTest(row=row, name=f"r.{attribute_name}[0]"):
                    actual = Rect(
                        _random_int(), _random_int(), _random_int(), _random_int()
                    )
                    # act
                    setattr(actual, attribute_name, (new_value, other))
                    # assert
                    self.assertEqual((expected, other), getattr(actual, attribute_name))

                with self.subTest(row=row, name=f"r.{attribute_name}[1]"):
                    actual = Rect(
                        _random_int(), _random_int(), _random_int(), _random_int()
                    )
                    # act
                    setattr(actual, attribute_name, (other, new_value))
                    # assert
                    self.assertEqual((other, expected), getattr(actual, attribute_name))

    def test_set_out_of_range_number_raises_exception(self):
        i = 0
        # (initial, expected)
        data_rows = [
            (_int_max + 1, TypeError),
            (_int_max + 0.00001, TypeError),
            (_int_max, None),
            (_int_max - 1, None),
            (_int_max - 2, None),
            (_int_max - 10, None),
            (_int_max - 63, None),
            (_int_max - 64, None),
            (_int_max - 65, None),
            (_int_min - 1, TypeError),
            (_int_min - 0.00001, TypeError),
            (_int_min, None),
            (_int_min + 1, None),
            (_int_min + 2, None),
            (_int_min + 10, None),
            (_int_min + 62, None),
            (_int_min + 63, None),
            (_int_min + 64, None),
            (0, None),
            (100000, None),
            (-100000, None),
        ]

        single_attribute_names = [
            "x",
            "y",
            "w",
            "h",
            "width",
            "height",
            "top",
            "left",
            "bottom",
            "right",
            "centerx",
            "centery",
        ]

        tuple_value_attribute_names = [
            "topleft",
            "topright",
            "bottomleft",
            "bottomright",
            "midtop",
            "midleft",
            "midbottom",
            "midright",
            "size",
            "center",
        ]

        for row in data_rows:
            for attribute_name in single_attribute_names:
                value, expected = row
                with self.subTest(row=row, name=f"r.{attribute_name}"):
                    actual = Rect(0, 0, 0, 0)
                    if expected:
                        # act/ assert
                        self.assertRaises(
                            TypeError, setattr, actual, attribute_name, value
                        )
                    else:
                        # act
                        setattr(actual, attribute_name, value)
                        # assert
                        self.assertEqual(value, getattr(actual, attribute_name))
            other = _random_int()

            for attribute_name in tuple_value_attribute_names:
                value, expected = row
                with self.subTest(row=row, name=f"r.{attribute_name}[0]"):
                    actual = Rect(0, 0, 0, 0)
                    # act/ assert
                    if expected:
                        # act/ assert
                        self.assertRaises(
                            TypeError, setattr, actual, attribute_name, (value, other)
                        )
                    else:
                        # act
                        setattr(actual, attribute_name, (value, other))
                        # assert
                        self.assertEqual(
                            (value, other), getattr(actual, attribute_name)
                        )
                with self.subTest(row=row, name=f"r.{attribute_name}[1]"):
                    actual = Rect(0, 0, 0, 0)
                    # act/ assert
                    if expected:
                        # act/ assert
                        self.assertRaises(
                            TypeError, setattr, actual, attribute_name, (other, value)
                        )
                    else:
                        # act
                        setattr(actual, attribute_name, (other, value))
                        # assert
                        self.assertEqual(
                            (other, value), getattr(actual, attribute_name)
                        )

    def test_update_XYWidthHeight(self):
        """Test update with 4 int values(x, y, w, h)"""
        rect = Rect(0, 0, 1, 1)
        rect.update(1, 2, 3, 4)

        self.assertEqual(1, rect.left)
        self.assertEqual(2, rect.top)
        self.assertEqual(3, rect.width)
        self.assertEqual(4, rect.height)

    def test_update__TopLeftSize(self):
        """Test update with 2 tuples((x, y), (w, h))"""
        rect = Rect(0, 0, 1, 1)
        rect.update((1, 2), (3, 4))

        self.assertEqual(1, rect.left)
        self.assertEqual(2, rect.top)
        self.assertEqual(3, rect.width)
        self.assertEqual(4, rect.height)

    def test_update__List(self):
        """Test update with list"""
        rect = Rect(0, 0, 1, 1)
        rect2 = [1, 2, 3, 4]
        rect.update(rect2)

        self.assertEqual(1, rect.left)
        self.assertEqual(2, rect.top)
        self.assertEqual(3, rect.width)
        self.assertEqual(4, rect.height)

    def test_update__RectObject(self):
        """Test update with other rect object"""
        rect = Rect(0, 0, 1, 1)
        rect2 = Rect(1, 2, 3, 4)
        rect.update(rect2)

        self.assertEqual(1, rect.left)
        self.assertEqual(2, rect.top)
        self.assertEqual(3, rect.width)
        self.assertEqual(4, rect.height)

    def test_union(self):
        r1 = Rect(1, 1, 1, 2)
        r2 = Rect(-2, -2, 1, 2)
        self.assertEqual(Rect(-2, -2, 4, 5), r1.union(r2))

    def test_union__with_identical_Rect(self):
        r1 = Rect(1, 2, 3, 4)
        self.assertEqual(r1, r1.union(Rect(r1)))

    def test_union_ip(self):
        r1 = Rect(1, 1, 1, 2)
        r2 = Rect(-2, -2, 1, 2)
        r1.union_ip(r2)
        self.assertEqual(Rect(-2, -2, 4, 5), r1)

    def test_unionall(self):
        r1 = Rect(0, 0, 1, 1)
        r2 = Rect(-2, -2, 1, 1)
        r3 = Rect(2, 2, 1, 1)

        r4 = r1.unionall([r2, r3])
        self.assertEqual(Rect(-2, -2, 5, 5), r4)

    def test_unionall__invalid_rect_format(self):
        """Ensures unionall correctly handles invalid rect parameters."""
        numbers = [0, 1.2, 2, 3.3]
        strs = ["a", "b", "c"]
        nones = [None, None]

        for invalid_rects in (numbers, strs, nones):
            with self.assertRaises(TypeError):
                Rect(0, 0, 1, 1).unionall(invalid_rects)

    def test_unionall__kwargs(self):
        r1 = Rect(0, 0, 1, 1)
        r2 = Rect(-2, -2, 1, 1)
        r3 = Rect(2, 2, 1, 1)

        r4 = r1.unionall(rect=[r2, r3])
        self.assertEqual(Rect(-2, -2, 5, 5), r4)

    def test_unionall_ip(self):
        r1 = Rect(0, 0, 1, 1)
        r2 = Rect(-2, -2, 1, 1)
        r3 = Rect(2, 2, 1, 1)

        r1.unionall_ip([r2, r3])
        self.assertEqual(Rect(-2, -2, 5, 5), r1)

        # Bug for an empty list. Would return a Rect instead of None.
        self.assertTrue(r1.unionall_ip([]) is None)

    def test_unionall_ip__kwargs(self):
        r1 = Rect(0, 0, 1, 1)
        r2 = Rect(-2, -2, 1, 1)
        r3 = Rect(2, 2, 1, 1)

        r1.unionall_ip(rects=[r2, r3])
        self.assertEqual(Rect(-2, -2, 5, 5), r1)

        # Bug for an empty list. Would return a Rect instead of None.
        self.assertTrue(r1.unionall_ip([]) is None)

    def test_colliderect(self):
        r1 = Rect(1, 2, 3, 4)
        self.assertTrue(
            r1.colliderect(Rect(0, 0, 2, 3)),
            "r1 does not collide with Rect(0, 0, 2, 3)",
        )
        self.assertFalse(
            r1.colliderect(Rect(0, 0, 1, 2)), "r1 collides with Rect(0, 0, 1, 2)"
        )
        self.assertFalse(
            r1.colliderect(Rect(r1.right, r1.bottom, 2, 2)),
            "r1 collides with Rect(r1.right, r1.bottom, 2, 2)",
        )
        self.assertTrue(
            r1.colliderect(Rect(r1.left + 1, r1.top + 1, r1.width - 2, r1.height - 2)),
            "r1 does not collide with Rect(r1.left + 1, r1.top + 1, "
            + "r1.width - 2, r1.height - 2)",
        )
        self.assertTrue(
            r1.colliderect(Rect(r1.left - 1, r1.top - 1, r1.width + 2, r1.height + 2)),
            "r1 does not collide with Rect(r1.left - 1, r1.top - 1, "
            + "r1.width + 2, r1.height + 2)",
        )
        self.assertTrue(
            r1.colliderect(Rect(r1)), "r1 does not collide with an identical rect"
        )
        self.assertFalse(
            r1.colliderect(Rect(r1.right, r1.bottom, 0, 0)),
            "r1 collides with Rect(r1.right, r1.bottom, 0, 0)",
        )
        self.assertFalse(
            r1.colliderect(Rect(r1.right, r1.bottom, 1, 1)),
            "r1 collides with Rect(r1.right, r1.bottom, 1, 1)",
        )

    def testEquals(self):
        """check to see how the rect uses __eq__"""
        r1 = Rect(1, 2, 3, 4)
        r2 = Rect(10, 20, 30, 40)
        r3 = (10, 20, 30, 40)
        r4 = Rect(10, 20, 30, 40)

        class foo(Rect):
            def __eq__(self, other):
                return id(self) == id(other)

            def __ne__(self, other):
                return id(self) != id(other)

        class foo2(Rect):
            pass

        r5 = foo(10, 20, 30, 40)
        r6 = foo2(10, 20, 30, 40)

        self.assertNotEqual(r5, r2)

        # because we define equality differently for this subclass.
        self.assertEqual(r6, r2)

        rect_list = [r1, r2, r3, r4, r6]

        # see if we can remove 4 of these.
        rect_list.remove(r2)
        rect_list.remove(r2)
        rect_list.remove(r2)
        rect_list.remove(r2)
        self.assertRaises(ValueError, rect_list.remove, r2)

    def test_collidedict(self):
        """Ensures collidedict detects collisions."""
        rect = Rect(1, 1, 10, 10)

        collide_item1 = ("collide 1", rect.copy())
        collide_item2 = ("collide 2", Rect(5, 5, 10, 10))
        no_collide_item1 = ("no collide 1", Rect(60, 60, 10, 10))
        no_collide_item2 = ("no collide 2", Rect(70, 70, 10, 10))

        # Dict to check collisions with values.
        rect_values = dict(
            (collide_item1, collide_item2, no_collide_item1, no_collide_item2)
        )
        value_collide_items = (collide_item1, collide_item2)

        # Dict to check collisions with keys.
        rect_keys = {tuple(v): k for k, v in rect_values.items()}
        key_collide_items = tuple((tuple(v), k) for k, v in value_collide_items)

        for use_values in (True, False):
            if use_values:
                expected_items = value_collide_items
                d = rect_values
            else:
                expected_items = key_collide_items
                d = rect_keys

            collide_item = rect.collidedict(d, use_values)

            # The detected collision could be any of the possible items.
            self.assertIn(collide_item, expected_items)

    def test_collidedict__no_collision(self):
        """Ensures collidedict returns None when no collisions."""
        rect = Rect(1, 1, 10, 10)

        no_collide_item1 = ("no collide 1", Rect(50, 50, 10, 10))
        no_collide_item2 = ("no collide 2", Rect(60, 60, 10, 10))
        no_collide_item3 = ("no collide 3", Rect(70, 70, 10, 10))

        # Dict to check collisions with values.
        rect_values = dict((no_collide_item1, no_collide_item2, no_collide_item3))

        # Dict to check collisions with keys.
        rect_keys = {tuple(v): k for k, v in rect_values.items()}

        for use_values in (True, False):
            d = rect_values if use_values else rect_keys

            collide_item = rect.collidedict(d, use_values)

            self.assertIsNone(collide_item)

    def test_collidedict__barely_touching(self):
        """Ensures collidedict works correctly for rects that barely touch."""
        rect = Rect(1, 1, 10, 10)
        # Small rect to test barely touching collisions.
        collide_rect = Rect(0, 0, 1, 1)

        collide_item1 = ("collide 1", collide_rect)
        no_collide_item1 = ("no collide 1", Rect(50, 50, 10, 10))
        no_collide_item2 = ("no collide 2", Rect(60, 60, 10, 10))
        no_collide_item3 = ("no collide 3", Rect(70, 70, 10, 10))

        # Dict to check collisions with values.
        no_collide_rect_values = dict(
            (no_collide_item1, no_collide_item2, no_collide_item3)
        )

        # Dict to check collisions with keys.
        no_collide_rect_keys = {tuple(v): k for k, v in no_collide_rect_values.items()}

        # Tests the collide_rect on each of the rect's corners.
        for attr in ("topleft", "topright", "bottomright", "bottomleft"):
            setattr(collide_rect, attr, getattr(rect, attr))

            for use_values in (True, False):
                if use_values:
                    expected_item = collide_item1
                    d = dict(no_collide_rect_values)
                else:
                    expected_item = (tuple(collide_item1[1]), collide_item1[0])
                    d = dict(no_collide_rect_keys)

                d.update((expected_item,))  # Add in the expected item.

                collide_item = rect.collidedict(d, use_values)

                self.assertTupleEqual(collide_item, expected_item)

    def test_collidedict__zero_sized_rects(self):
        """Ensures collidedict works correctly with zero sized rects.

        There should be no collisions with zero sized rects.
        """
        zero_rect1 = Rect(1, 1, 0, 0)
        zero_rect2 = Rect(1, 1, 1, 0)
        zero_rect3 = Rect(1, 1, 0, 1)
        zero_rect4 = Rect(1, 1, -1, 0)
        zero_rect5 = Rect(1, 1, 0, -1)

        no_collide_item1 = ("no collide 1", zero_rect1.copy())
        no_collide_item2 = ("no collide 2", zero_rect2.copy())
        no_collide_item3 = ("no collide 3", zero_rect3.copy())
        no_collide_item4 = ("no collide 4", zero_rect4.copy())
        no_collide_item5 = ("no collide 5", zero_rect5.copy())
        no_collide_item6 = ("no collide 6", Rect(0, 0, 10, 10))
        no_collide_item7 = ("no collide 7", Rect(0, 0, 2, 2))

        # Dict to check collisions with values.
        rect_values = dict(
            (
                no_collide_item1,
                no_collide_item2,
                no_collide_item3,
                no_collide_item4,
                no_collide_item5,
                no_collide_item6,
                no_collide_item7,
            )
        )

        # Dict to check collisions with keys.
        rect_keys = {tuple(v): k for k, v in rect_values.items()}

        for use_values in (True, False):
            d = rect_values if use_values else rect_keys

            for zero_rect in (
                zero_rect1,
                zero_rect2,
                zero_rect3,
                zero_rect4,
                zero_rect5,
            ):
                collide_item = zero_rect.collidedict(d, use_values)

                self.assertIsNone(collide_item)

    def test_collidedict__zero_sized_rects_as_args(self):
        """Ensures collidedict works correctly with zero sized rects as args.

        There should be no collisions with zero sized rects.
        """
        rect = Rect(0, 0, 10, 10)

        no_collide_item1 = ("no collide 1", Rect(1, 1, 0, 0))
        no_collide_item2 = ("no collide 2", Rect(1, 1, 1, 0))
        no_collide_item3 = ("no collide 3", Rect(1, 1, 0, 1))

        # Dict to check collisions with values.
        rect_values = dict((no_collide_item1, no_collide_item2, no_collide_item3))

        # Dict to check collisions with keys.
        rect_keys = {tuple(v): k for k, v in rect_values.items()}

        for use_values in (True, False):
            d = rect_values if use_values else rect_keys

            collide_item = rect.collidedict(d, use_values)

            self.assertIsNone(collide_item)

    def test_collidedict__negative_sized_rects(self):
        """Ensures collidedict works correctly with negative sized rects."""
        neg_rect = Rect(1, 1, -1, -1)

        collide_item1 = ("collide 1", neg_rect.copy())
        collide_item2 = ("collide 2", Rect(0, 0, 10, 10))
        no_collide_item1 = ("no collide 1", Rect(1, 1, 10, 10))

        # Dict to check collisions with values.
        rect_values = dict((collide_item1, collide_item2, no_collide_item1))
        value_collide_items = (collide_item1, collide_item2)

        # Dict to check collisions with keys.
        rect_keys = {tuple(v): k for k, v in rect_values.items()}
        key_collide_items = tuple((tuple(v), k) for k, v in value_collide_items)

        for use_values in (True, False):
            if use_values:
                collide_items = value_collide_items
                d = rect_values
            else:
                collide_items = key_collide_items
                d = rect_keys

            collide_item = neg_rect.collidedict(d, use_values)

            # The detected collision could be any of the possible items.
            self.assertIn(collide_item, collide_items)

    def test_collidedict__negative_sized_rects_as_args(self):
        """Ensures collidedict works correctly with negative sized rect args."""
        rect = Rect(0, 0, 10, 10)

        collide_item1 = ("collide 1", Rect(1, 1, -1, -1))
        no_collide_item1 = ("no collide 1", Rect(1, 1, -1, 0))
        no_collide_item2 = ("no collide 2", Rect(1, 1, 0, -1))

        # Dict to check collisions with values.
        rect_values = dict((collide_item1, no_collide_item1, no_collide_item2))

        # Dict to check collisions with keys.
        rect_keys = {tuple(v): k for k, v in rect_values.items()}

        for use_values in (True, False):
            if use_values:
                expected_item = collide_item1
                d = rect_values
            else:
                expected_item = (tuple(collide_item1[1]), collide_item1[0])
                d = rect_keys

            collide_item = rect.collidedict(d, use_values)

            self.assertTupleEqual(collide_item, expected_item)

    def test_collidedict__invalid_dict_format(self):
        """Ensures collidedict correctly handles invalid dict parameters."""
        rect = Rect(0, 0, 10, 10)

        invalid_value_dict = ("collide", rect.copy())
        invalid_key_dict = tuple(invalid_value_dict[1]), invalid_value_dict[0]

        for use_values in (True, False):
            d = invalid_value_dict if use_values else invalid_key_dict

            with self.assertRaises(TypeError):
                collide_item = rect.collidedict(d, use_values)

    def test_collidedict__invalid_dict_value_format(self):
        """Ensures collidedict correctly handles dicts with invalid values."""
        rect = Rect(0, 0, 10, 10)
        rect_keys = {tuple(rect): "collide"}

        with self.assertRaises(TypeError):
            collide_item = rect.collidedict(rect_keys, 1)

    def test_collidedict__invalid_dict_key_format(self):
        """Ensures collidedict correctly handles dicts with invalid keys."""
        rect = Rect(0, 0, 10, 10)
        rect_values = {"collide": rect.copy()}

        with self.assertRaises(TypeError):
            collide_item = rect.collidedict(rect_values)

    def test_collidedict__invalid_use_values_format(self):
        """Ensures collidedict correctly handles invalid use_values parameters."""
        rect = Rect(0, 0, 1, 1)
        d = {}

        for invalid_param in (None, d, 1.1):
            with self.assertRaises(TypeError):
                collide_item = rect.collidedict(d, invalid_param)

    def test_collidedict__kwargs(self):
        """Ensures collidedict detects collisions via keyword arguments."""
        rect = Rect(1, 1, 10, 10)

        collide_item1 = ("collide 1", rect.copy())
        collide_item2 = ("collide 2", Rect(5, 5, 10, 10))
        no_collide_item1 = ("no collide 1", Rect(60, 60, 10, 10))
        no_collide_item2 = ("no collide 2", Rect(70, 70, 10, 10))

        # Dict to check collisions with values.
        rect_values = dict(
            (collide_item1, collide_item2, no_collide_item1, no_collide_item2)
        )
        value_collide_items = (collide_item1, collide_item2)

        # Dict to check collisions with keys.
        rect_keys = {tuple(v): k for k, v in rect_values.items()}
        key_collide_items = tuple((tuple(v), k) for k, v in value_collide_items)

        for use_values in (True, False):
            if use_values:
                expected_items = value_collide_items
                d = rect_values
            else:
                expected_items = key_collide_items
                d = rect_keys

            collide_item = rect.collidedict(rect_dict=d, values=use_values)

            # The detected collision could be any of the possible items.
            self.assertIn(collide_item, expected_items)

    def test_collidedictall(self):
        """Ensures collidedictall detects collisions."""
        rect = Rect(1, 1, 10, 10)

        collide_item1 = ("collide 1", rect.copy())
        collide_item2 = ("collide 2", Rect(5, 5, 10, 10))
        no_collide_item1 = ("no collide 1", Rect(60, 60, 20, 20))
        no_collide_item2 = ("no collide 2", Rect(70, 70, 20, 20))

        # Dict to check collisions with values.
        rect_values = dict(
            (collide_item1, collide_item2, no_collide_item1, no_collide_item2)
        )
        value_collide_items = [collide_item1, collide_item2]

        # Dict to check collisions with keys.
        rect_keys = {tuple(v): k for k, v in rect_values.items()}
        key_collide_items = [(tuple(v), k) for k, v in value_collide_items]

        for use_values in (True, False):
            if use_values:
                expected_items = value_collide_items
                d = rect_values
            else:
                expected_items = key_collide_items
                d = rect_keys

            collide_items = rect.collidedictall(d, use_values)

            self._assertCountEqual(collide_items, expected_items)

    def test_collidedictall__no_collision(self):
        """Ensures collidedictall returns an empty list when no collisions."""
        rect = Rect(1, 1, 10, 10)

        no_collide_item1 = ("no collide 1", Rect(50, 50, 20, 20))
        no_collide_item2 = ("no collide 2", Rect(60, 60, 20, 20))
        no_collide_item3 = ("no collide 3", Rect(70, 70, 20, 20))

        # Dict to check collisions with values.
        rect_values = dict((no_collide_item1, no_collide_item2, no_collide_item3))

        # Dict to check collisions with keys.
        rect_keys = {tuple(v): k for k, v in rect_values.items()}

        expected_items = []

        for use_values in (True, False):
            d = rect_values if use_values else rect_keys

            collide_items = rect.collidedictall(d, use_values)

            self._assertCountEqual(collide_items, expected_items)

    def test_collidedictall__barely_touching(self):
        """Ensures collidedictall works correctly for rects that barely touch."""
        rect = Rect(1, 1, 10, 10)
        # Small rect to test barely touching collisions.
        collide_rect = Rect(0, 0, 1, 1)

        collide_item1 = ("collide 1", collide_rect)
        no_collide_item1 = ("no collide 1", Rect(50, 50, 20, 20))
        no_collide_item2 = ("no collide 2", Rect(60, 60, 20, 20))
        no_collide_item3 = ("no collide 3", Rect(70, 70, 20, 20))

        # Dict to check collisions with values.
        no_collide_rect_values = dict(
            (no_collide_item1, no_collide_item2, no_collide_item3)
        )

        # Dict to check collisions with keys.
        no_collide_rect_keys = {tuple(v): k for k, v in no_collide_rect_values.items()}

        # Tests the collide_rect on each of the rect's corners.
        for attr in ("topleft", "topright", "bottomright", "bottomleft"):
            setattr(collide_rect, attr, getattr(rect, attr))

            for use_values in (True, False):
                if use_values:
                    expected_items = [collide_item1]
                    d = dict(no_collide_rect_values)
                else:
                    expected_items = [(tuple(collide_item1[1]), collide_item1[0])]
                    d = dict(no_collide_rect_keys)

                d.update(expected_items)  # Add in the expected items.

                collide_items = rect.collidedictall(d, use_values)

                self._assertCountEqual(collide_items, expected_items)

    def test_collidedictall__zero_sized_rects(self):
        """Ensures collidedictall works correctly with zero sized rects.

        There should be no collisions with zero sized rects.
        """
        zero_rect1 = Rect(2, 2, 0, 0)
        zero_rect2 = Rect(2, 2, 2, 0)
        zero_rect3 = Rect(2, 2, 0, 2)
        zero_rect4 = Rect(2, 2, -2, 0)
        zero_rect5 = Rect(2, 2, 0, -2)

        no_collide_item1 = ("no collide 1", zero_rect1.copy())
        no_collide_item2 = ("no collide 2", zero_rect2.copy())
        no_collide_item3 = ("no collide 3", zero_rect3.copy())
        no_collide_item4 = ("no collide 4", zero_rect4.copy())
        no_collide_item5 = ("no collide 5", zero_rect5.copy())
        no_collide_item6 = ("no collide 6", Rect(0, 0, 10, 10))
        no_collide_item7 = ("no collide 7", Rect(0, 0, 2, 2))

        # Dict to check collisions with values.
        rect_values = dict(
            (
                no_collide_item1,
                no_collide_item2,
                no_collide_item3,
                no_collide_item4,
                no_collide_item5,
                no_collide_item6,
                no_collide_item7,
            )
        )

        # Dict to check collisions with keys.
        rect_keys = {tuple(v): k for k, v in rect_values.items()}

        expected_items = []

        for use_values in (True, False):
            d = rect_values if use_values else rect_keys

            for zero_rect in (
                zero_rect1,
                zero_rect2,
                zero_rect3,
                zero_rect4,
                zero_rect5,
            ):
                collide_items = zero_rect.collidedictall(d, use_values)

                self._assertCountEqual(collide_items, expected_items)

    def test_collidedictall__zero_sized_rects_as_args(self):
        """Ensures collidedictall works correctly with zero sized rects
        as args.

        There should be no collisions with zero sized rects.
        """
        rect = Rect(0, 0, 20, 20)

        no_collide_item1 = ("no collide 1", Rect(2, 2, 0, 0))
        no_collide_item2 = ("no collide 2", Rect(2, 2, 2, 0))
        no_collide_item3 = ("no collide 3", Rect(2, 2, 0, 2))

        # Dict to check collisions with values.
        rect_values = dict((no_collide_item1, no_collide_item2, no_collide_item3))

        # Dict to check collisions with keys.
        rect_keys = {tuple(v): k for k, v in rect_values.items()}

        expected_items = []

        for use_values in (True, False):
            d = rect_values if use_values else rect_keys

            collide_items = rect.collidedictall(d, use_values)

            self._assertCountEqual(collide_items, expected_items)

    def test_collidedictall__negative_sized_rects(self):
        """Ensures collidedictall works correctly with negative sized rects."""
        neg_rect = Rect(2, 2, -2, -2)

        collide_item1 = ("collide 1", neg_rect.copy())
        collide_item2 = ("collide 2", Rect(0, 0, 20, 20))
        no_collide_item1 = ("no collide 1", Rect(2, 2, 20, 20))

        # Dict to check collisions with values.
        rect_values = dict((collide_item1, collide_item2, no_collide_item1))
        value_collide_items = [collide_item1, collide_item2]

        # Dict to check collisions with keys.
        rect_keys = {tuple(v): k for k, v in rect_values.items()}
        key_collide_items = [(tuple(v), k) for k, v in value_collide_items]

        for use_values in (True, False):
            if use_values:
                expected_items = value_collide_items
                d = rect_values
            else:
                expected_items = key_collide_items
                d = rect_keys

            collide_items = neg_rect.collidedictall(d, use_values)

            self._assertCountEqual(collide_items, expected_items)

    def test_collidedictall__negative_sized_rects_as_args(self):
        """Ensures collidedictall works correctly with negative sized rect
        args.
        """
        rect = Rect(0, 0, 10, 10)

        collide_item1 = ("collide 1", Rect(1, 1, -1, -1))
        no_collide_item1 = ("no collide 1", Rect(1, 1, -1, 0))
        no_collide_item2 = ("no collide 2", Rect(1, 1, 0, -1))

        # Dict to check collisions with values.
        rect_values = dict((collide_item1, no_collide_item1, no_collide_item2))
        value_collide_items = [collide_item1]

        # Dict to check collisions with keys.
        rect_keys = {tuple(v): k for k, v in rect_values.items()}
        key_collide_items = [(tuple(v), k) for k, v in value_collide_items]

        for use_values in (True, False):
            if use_values:
                expected_items = value_collide_items
                d = rect_values
            else:
                expected_items = key_collide_items
                d = rect_keys

            collide_items = rect.collidedictall(d, use_values)

            self._assertCountEqual(collide_items, expected_items)

    def test_collidedictall__invalid_dict_format(self):
        """Ensures collidedictall correctly handles invalid dict parameters."""
        rect = Rect(0, 0, 10, 10)

        invalid_value_dict = ("collide", rect.copy())
        invalid_key_dict = tuple(invalid_value_dict[1]), invalid_value_dict[0]

        for use_values in (True, False):
            d = invalid_value_dict if use_values else invalid_key_dict

            with self.assertRaises(TypeError):
                collide_item = rect.collidedictall(d, use_values)

    def test_collidedictall__invalid_dict_value_format(self):
        """Ensures collidedictall correctly handles dicts with invalid values."""
        rect = Rect(0, 0, 10, 10)
        rect_keys = {tuple(rect): "collide"}

        with self.assertRaises(TypeError):
            collide_items = rect.collidedictall(rect_keys, 1)

    def test_collidedictall__invalid_dict_key_format(self):
        """Ensures collidedictall correctly handles dicts with invalid keys."""
        rect = Rect(0, 0, 10, 10)
        rect_values = {"collide": rect.copy()}

        with self.assertRaises(TypeError):
            collide_items = rect.collidedictall(rect_values)

    def test_collidedictall__invalid_use_values_format(self):
        """Ensures collidedictall correctly handles invalid use_values
        parameters.
        """
        rect = Rect(0, 0, 1, 1)
        d = {}

        for invalid_param in (None, d, 1.1):
            with self.assertRaises(TypeError):
                collide_items = rect.collidedictall(d, invalid_param)

    def test_collidedictall__kwargs(self):
        """Ensures collidedictall detects collisions via keyword arguments."""
        rect = Rect(1, 1, 10, 10)

        collide_item1 = ("collide 1", rect.copy())
        collide_item2 = ("collide 2", Rect(5, 5, 10, 10))
        no_collide_item1 = ("no collide 1", Rect(60, 60, 20, 20))
        no_collide_item2 = ("no collide 2", Rect(70, 70, 20, 20))

        # Dict to check collisions with values.
        rect_values = dict(
            (collide_item1, collide_item2, no_collide_item1, no_collide_item2)
        )
        value_collide_items = [collide_item1, collide_item2]

        # Dict to check collisions with keys.
        rect_keys = {tuple(v): k for k, v in rect_values.items()}
        key_collide_items = [(tuple(v), k) for k, v in value_collide_items]

        for use_values in (True, False):
            if use_values:
                expected_items = value_collide_items
                d = rect_values
            else:
                expected_items = key_collide_items
                d = rect_keys

            collide_items = rect.collidedictall(rect_dict=d, values=use_values)

            self._assertCountEqual(collide_items, expected_items)

    def test_collidelist(self):
        # __doc__ (as of 2008-08-02) for pygame.rect.Rect.collidelist:

        # Rect.collidelist(list): return index
        # test if one rectangle in a list intersects
        #
        # Test whether the rectangle collides with any in a sequence of
        # rectangles. The index of the first collision found is returned. If
        # no collisions are found an index of -1 is returned.

        r = Rect(1, 1, 10, 10)
        l = [Rect(50, 50, 1, 1), Rect(5, 5, 10, 10), Rect(15, 15, 1, 1)]

        self.assertEqual(r.collidelist(l), 1)

        f = [Rect(50, 50, 1, 1), (100, 100, 4, 4)]
        self.assertEqual(r.collidelist(f), -1)

    def test_collidelist__kwargs(self):
        # Rect.collidelist(list): return index
        # test if one rectangle in a list intersects
        #
        # Test whether the rectangle collides with any in a sequence of
        # rectangles using keyword arguments. The index of the first collision
        # found is returned. If no collisions are found an index
        # of -1 is returned.

        r = Rect(1, 1, 10, 10)
        l = [Rect(50, 50, 1, 1), Rect(5, 5, 10, 10), Rect(15, 15, 1, 1)]

        self.assertEqual(r.collidelist(l), 1)

        f = [Rect(50, 50, 1, 1), (100, 100, 4, 4)]
        self.assertEqual(r.collidelist(rects=f), -1)

    def test_collidelistall(self):
        # __doc__ (as of 2008-08-02) for pygame.rect.Rect.collidelistall:

        # Rect.collidelistall(list): return indices
        # test if all rectangles in a list intersect
        #
        # Returns a list of all the indices that contain rectangles that
        # collide with the Rect. If no intersecting rectangles are found, an
        # empty list is returned.

        r = Rect(1, 1, 10, 10)

        l = [
            Rect(1, 1, 10, 10),
            Rect(5, 5, 10, 10),
            Rect(15, 15, 1, 1),
            Rect(2, 2, 1, 1),
        ]
        self.assertEqual(r.collidelistall(l), [0, 1, 3])

        f = [Rect(50, 50, 1, 1), Rect(20, 20, 5, 5)]
        self.assertFalse(r.collidelistall(f))

    def test_collidelistall_returns_empty_list(self):
        r = Rect(1, 1, 10, 10)

        l = [
            Rect(112, 1, 10, 10),
            Rect(50, 5, 10, 10),
            Rect(15, 15, 1, 1),
            Rect(-20, 2, 1, 1),
        ]
        self.assertEqual(r.collidelistall(l), [])

    def test_collidelistall_list_of_tuples(self):
        r = Rect(1, 1, 10, 10)

        l = [
            (1, 1, 10, 10),
            (5, 5, 10, 10),
            (15, 15, 1, 1),
            (2, 2, 1, 1),
        ]
        self.assertEqual(r.collidelistall(l), [0, 1, 3])

        f = [(50, 50, 1, 1), (20, 20, 5, 5)]
        self.assertFalse(r.collidelistall(f))

    def test_collidelistall_list_of_two_tuples(self):
        r = Rect(1, 1, 10, 10)

        l = [
            ((1, 1), (10, 10)),
            ((5, 5), (10, 10)),
            ((15, 15), (1, 1)),
            ((2, 2), (1, 1)),
        ]
        self.assertEqual(r.collidelistall(l), [0, 1, 3])

        f = [((50, 50), (1, 1)), ((20, 20), (5, 5))]
        self.assertFalse(r.collidelistall(f))

    def test_collidelistall_list_of_lists(self):
        r = Rect(1, 1, 10, 10)

        l = [
            [1, 1, 10, 10],
            [5, 5, 10, 10],
            [15, 15, 1, 1],
            [2, 2, 1, 1],
        ]
        self.assertEqual(r.collidelistall(l), [0, 1, 3])

        f = [[50, 50, 1, 1], [20, 20, 5, 5]]
        self.assertFalse(r.collidelistall(f))

    class _ObjectWithRectAttribute:
        def __init__(self, r):
            self.rect = r

    class _ObjectWithCallableRectAttribute:
        def __init__(self, r):
            self._rect = r

        def rect(self):
            return self._rect

    class _ObjectWithRectProperty:
        def __init__(self, r):
            self._rect = r

        @property
        def rect(self):
            return self._rect

    class _ObjectWithMultipleRectAttribute:
        def __init__(self, r1, r2, r3):
            self.rect1 = r1
            self.rect2 = r2
            self.rect3 = r3

    def test_collidelistall_list_of_object_with_rect_attribute(self):
        r = Rect(1, 1, 10, 10)

        l = [
            self._ObjectWithRectAttribute(Rect(1, 1, 10, 10)),
            self._ObjectWithRectAttribute(Rect(5, 5, 10, 10)),
            self._ObjectWithRectAttribute(Rect(15, 15, 1, 1)),
            self._ObjectWithRectAttribute(Rect(2, 2, 1, 1)),
        ]
        self.assertEqual(r.collidelistall(l), [0, 1, 3])

        f = [
            self._ObjectWithRectAttribute(Rect(50, 50, 1, 1)),
            self._ObjectWithRectAttribute(Rect(20, 20, 5, 5)),
        ]
        self.assertFalse(r.collidelistall(f))

    def test_collidelistall_list_of_object_with_callable_rect_attribute(self):
        r = Rect(1, 1, 10, 10)

        l = [
            self._ObjectWithCallableRectAttribute(Rect(1, 1, 10, 10)),
            self._ObjectWithCallableRectAttribute(Rect(5, 5, 10, 10)),
            self._ObjectWithCallableRectAttribute(Rect(15, 15, 1, 1)),
            self._ObjectWithCallableRectAttribute(Rect(2, 2, 1, 1)),
        ]
        self.assertEqual(r.collidelistall(l), [0, 1, 3])

        f = [
            self._ObjectWithCallableRectAttribute(Rect(50, 50, 1, 1)),
            self._ObjectWithCallableRectAttribute(Rect(20, 20, 5, 5)),
        ]
        self.assertFalse(r.collidelistall(f))

    def test_collidelistall_list_of_object_with_callable_rect_returning_object_with_rect_attribute(
        self,
    ):
        r = Rect(1, 1, 10, 10)

        l = [
            self._ObjectWithCallableRectAttribute(
                self._ObjectWithRectAttribute(Rect(1, 1, 10, 10))
            ),
            self._ObjectWithCallableRectAttribute(
                self._ObjectWithRectAttribute(Rect(5, 5, 10, 10))
            ),
            self._ObjectWithCallableRectAttribute(
                self._ObjectWithRectAttribute(Rect(15, 15, 1, 1))
            ),
            self._ObjectWithCallableRectAttribute(
                self._ObjectWithRectAttribute(Rect(2, 2, 1, 1))
            ),
        ]
        self.assertEqual(r.collidelistall(l), [0, 1, 3])

        f = [
            self._ObjectWithCallableRectAttribute(Rect(50, 50, 1, 1)),
            self._ObjectWithCallableRectAttribute(Rect(20, 20, 5, 5)),
        ]
        self.assertFalse(r.collidelistall(f))

    def test_collidelistall_list_of_object_with_rect_property(self):
        r = Rect(1, 1, 10, 10)

        l = [
            self._ObjectWithRectProperty(Rect(1, 1, 10, 10)),
            self._ObjectWithRectProperty(Rect(5, 5, 10, 10)),
            self._ObjectWithRectProperty(Rect(15, 15, 1, 1)),
            self._ObjectWithRectProperty(Rect(2, 2, 1, 1)),
        ]
        self.assertEqual(r.collidelistall(l), [0, 1, 3])

        f = [
            self._ObjectWithRectProperty(Rect(50, 50, 1, 1)),
            self._ObjectWithRectProperty(Rect(20, 20, 5, 5)),
        ]
        self.assertFalse(r.collidelistall(f))

    def test_collidelistall__kwargs(self):
        # Rect.collidelistall(list): return indices
        # test if all rectangles in a list intersect using keyword arguments.
        #
        # Returns a list of all the indices that contain rectangles that
        # collide with the Rect. If no intersecting rectangles are found, an
        # empty list is returned.

        r = Rect(1, 1, 10, 10)

        l = [
            Rect(1, 1, 10, 10),
            Rect(5, 5, 10, 10),
            Rect(15, 15, 1, 1),
            Rect(2, 2, 1, 1),
        ]
        self.assertEqual(r.collidelistall(l), [0, 1, 3])

        f = [Rect(50, 50, 1, 1), Rect(20, 20, 5, 5)]
        self.assertFalse(r.collidelistall(rects=f))

    def test_collideobjects_call_variants(self):
        # arrange
        r = Rect(1, 1, 10, 10)
        rects = [Rect(1, 2, 3, 4), Rect(10, 20, 30, 40)]
        objects = [
            self._ObjectWithMultipleRectAttribute(
                Rect(1, 2, 3, 4), Rect(10, 20, 30, 40), Rect(100, 200, 300, 400)
            ),
            self._ObjectWithMultipleRectAttribute(
                Rect(1, 2, 3, 4), Rect(10, 20, 30, 40), Rect(100, 200, 300, 400)
            ),
        ]

        # act / verify
        r.collideobjects(rects)
        r.collideobjects(rects, key=None)
        r.collideobjects(objects, key=lambda o: o.rect1)
        self.assertRaises(TypeError, r.collideobjects, objects)

    def test_collideobjects_without_key(self):
        r = Rect(1, 1, 10, 10)
        types_to_test = [
            [Rect(50, 50, 1, 1), Rect(5, 5, 10, 10), Rect(4, 4, 1, 1)],
            [
                self._ObjectWithRectAttribute(Rect(50, 50, 1, 1)),
                self._ObjectWithRectAttribute(Rect(5, 5, 10, 10)),
                self._ObjectWithRectAttribute(Rect(4, 4, 1, 1)),
            ],
            [
                self._ObjectWithRectProperty(Rect(50, 50, 1, 1)),
                self._ObjectWithRectProperty(Rect(5, 5, 10, 10)),
                self._ObjectWithRectProperty(Rect(4, 4, 1, 1)),
            ],
            [
                self._ObjectWithCallableRectAttribute(Rect(50, 50, 1, 1)),
                self._ObjectWithCallableRectAttribute(Rect(5, 5, 10, 10)),
                self._ObjectWithCallableRectAttribute(Rect(4, 4, 1, 1)),
            ],
            [
                self._ObjectWithCallableRectAttribute(
                    self._ObjectWithRectAttribute(Rect(50, 50, 1, 1))
                ),
                self._ObjectWithCallableRectAttribute(
                    self._ObjectWithRectAttribute(Rect(5, 5, 10, 10))
                ),
                self._ObjectWithCallableRectAttribute(
                    self._ObjectWithRectAttribute(Rect(4, 4, 1, 1))
                ),
            ],
            [(50, 50, 1, 1), (5, 5, 10, 10), (4, 4, 1, 1)],
            [((50, 50), (1, 1)), ((5, 5), (10, 10)), ((4, 4), (1, 1))],
            [[50, 50, 1, 1], [5, 5, 10, 10], [4, 4, 1, 1]],
            [
                Rect(50, 50, 1, 1),
                self._ObjectWithRectAttribute(Rect(5, 5, 10, 10)),
                (4, 4, 1, 1),
            ],  # mix
        ]

        for l in types_to_test:
            with self.subTest(type=l[0].__class__.__name__):
                # act
                actual = r.collideobjects(l)
                # assert
                self.assertEqual(actual, l[1])

        types_to_test = [
            [Rect(50, 50, 1, 1), Rect(100, 100, 4, 4)],
            [
                self._ObjectWithRectAttribute(Rect(50, 50, 1, 1)),
                self._ObjectWithRectAttribute(Rect(100, 100, 4, 4)),
            ],
            [
                self._ObjectWithRectProperty(Rect(50, 50, 1, 1)),
                self._ObjectWithRectProperty(Rect(100, 100, 4, 4)),
            ],
            [
                self._ObjectWithCallableRectAttribute(Rect(50, 50, 1, 1)),
                self._ObjectWithCallableRectAttribute(Rect(100, 100, 4, 4)),
            ],
            [
                self._ObjectWithCallableRectAttribute(
                    self._ObjectWithRectAttribute(Rect(50, 50, 1, 1))
                ),
                self._ObjectWithCallableRectAttribute(
                    self._ObjectWithRectAttribute(Rect(100, 100, 4, 4))
                ),
            ],
            [(50, 50, 1, 1), (100, 100, 4, 4)],
            [((50, 50), (1, 1)), ((100, 100), (4, 4))],
            [[50, 50, 1, 1], [100, 100, 4, 4]],
            [Rect(50, 50, 1, 1), [100, 100, 4, 4]],  # mix
        ]

        for f in types_to_test:
            with self.subTest(type=f[0].__class__.__name__, expected=None):
                # act
                actual = r.collideobjects(f)
                # assert
                self.assertEqual(actual, None)

    def test_collideobjects_list_of_object_with_multiple_rect_attribute(self):
        r = Rect(1, 1, 10, 10)

        things = [
            self._ObjectWithMultipleRectAttribute(
                Rect(1, 1, 10, 10), Rect(5, 5, 1, 1), Rect(-73, 3, 3, 3)
            ),
            self._ObjectWithMultipleRectAttribute(
                Rect(5, 5, 10, 10), Rect(-5, -5, 10, 10), Rect(3, 3, 3, 3)
            ),
            self._ObjectWithMultipleRectAttribute(
                Rect(15, 15, 1, 1), Rect(100, 1, 1, 1), Rect(3, 83, 3, 3)
            ),
            self._ObjectWithMultipleRectAttribute(
                Rect(2, 2, 1, 1), Rect(1, -81, 10, 10), Rect(3, 8, 3, 3)
            ),
        ]
        self.assertEqual(r.collideobjects(things, key=lambda o: o.rect1), things[0])
        self.assertEqual(r.collideobjects(things, key=lambda o: o.rect2), things[0])
        self.assertEqual(r.collideobjects(things, key=lambda o: o.rect3), things[1])

        f = [
            self._ObjectWithMultipleRectAttribute(
                Rect(50, 50, 1, 1), Rect(11, 1, 1, 1), Rect(2, -32, 2, 2)
            ),
            self._ObjectWithMultipleRectAttribute(
                Rect(20, 20, 5, 5), Rect(1, 11, 1, 1), Rect(-20, 2, 2, 2)
            ),
        ]
        self.assertFalse(r.collideobjectsall(f, key=lambda o: o.rect1))
        self.assertFalse(r.collideobjectsall(f, key=lambda o: o.rect2))
        self.assertFalse(r.collideobjectsall(f, key=lambda o: o.rect3))

    def test_collideobjectsall_call_variants(self):
        # arrange
        r = Rect(1, 1, 10, 10)
        rects = [Rect(1, 2, 3, 4), Rect(10, 20, 30, 40)]
        objects = [
            self._ObjectWithMultipleRectAttribute(
                Rect(1, 2, 3, 4), Rect(10, 20, 30, 40), Rect(100, 200, 300, 400)
            ),
            self._ObjectWithMultipleRectAttribute(
                Rect(1, 2, 3, 4), Rect(10, 20, 30, 40), Rect(100, 200, 300, 400)
            ),
        ]

        # act / verify
        r.collideobjectsall(rects)
        r.collideobjectsall(rects, key=None)
        r.collideobjectsall(objects, key=lambda o: o.rect1)
        self.assertRaises(TypeError, r.collideobjectsall, objects)

    def test_collideobjectsall(self):
        r = Rect(1, 1, 10, 10)

        types_to_test = [
            [
                Rect(1, 1, 10, 10),
                Rect(5, 5, 10, 10),
                Rect(15, 15, 1, 1),
                Rect(2, 2, 1, 1),
            ],
            [
                (1, 1, 10, 10),
                (5, 5, 10, 10),
                (15, 15, 1, 1),
                (2, 2, 1, 1),
            ],
            [
                ((1, 1), (10, 10)),
                ((5, 5), (10, 10)),
                ((15, 15), (1, 1)),
                ((2, 2), (1, 1)),
            ],
            [
                [1, 1, 10, 10],
                [5, 5, 10, 10],
                [15, 15, 1, 1],
                [2, 2, 1, 1],
            ],
            [
                self._ObjectWithRectAttribute(Rect(1, 1, 10, 10)),
                self._ObjectWithRectAttribute(Rect(5, 5, 10, 10)),
                self._ObjectWithRectAttribute(Rect(15, 15, 1, 1)),
                self._ObjectWithRectAttribute(Rect(2, 2, 1, 1)),
            ],
            [
                self._ObjectWithCallableRectAttribute(Rect(1, 1, 10, 10)),
                self._ObjectWithCallableRectAttribute(Rect(5, 5, 10, 10)),
                self._ObjectWithCallableRectAttribute(Rect(15, 15, 1, 1)),
                self._ObjectWithCallableRectAttribute(Rect(2, 2, 1, 1)),
            ],
            [
                self._ObjectWithCallableRectAttribute(
                    self._ObjectWithRectAttribute(Rect(1, 1, 10, 10))
                ),
                self._ObjectWithCallableRectAttribute(
                    self._ObjectWithRectAttribute(Rect(5, 5, 10, 10))
                ),
                self._ObjectWithCallableRectAttribute(
                    self._ObjectWithRectAttribute(Rect(15, 15, 1, 1))
                ),
                self._ObjectWithCallableRectAttribute(
                    self._ObjectWithRectAttribute(Rect(2, 2, 1, 1))
                ),
            ],
            [
                self._ObjectWithRectProperty(Rect(1, 1, 10, 10)),
                self._ObjectWithRectProperty(Rect(5, 5, 10, 10)),
                self._ObjectWithRectProperty(Rect(15, 15, 1, 1)),
                self._ObjectWithRectProperty(Rect(2, 2, 1, 1)),
            ],
        ]
        for things in types_to_test:
            with self.subTest(type=things[0].__class__.__name__):
                # act
                actual = r.collideobjectsall(things, key=None)
                # assert
                self.assertEqual(actual, [things[0], things[1], things[3]])

        types_to_test = [
            [Rect(50, 50, 1, 1), Rect(20, 20, 5, 5)],
            [(50, 50, 1, 1), (20, 20, 5, 5)],
            [((50, 50), (1, 1)), ((20, 20), (5, 5))],
            [[50, 50, 1, 1], [20, 20, 5, 5]],
            [
                self._ObjectWithRectAttribute(Rect(50, 50, 1, 1)),
                self._ObjectWithRectAttribute(Rect(20, 20, 5, 5)),
            ],
            [
                self._ObjectWithCallableRectAttribute(Rect(50, 50, 1, 1)),
                self._ObjectWithCallableRectAttribute(Rect(20, 20, 5, 5)),
            ],
            [
                self._ObjectWithCallableRectAttribute(Rect(50, 50, 1, 1)),
                self._ObjectWithCallableRectAttribute(Rect(20, 20, 5, 5)),
            ],
            [
                self._ObjectWithRectProperty(Rect(50, 50, 1, 1)),
                self._ObjectWithRectProperty(Rect(20, 20, 5, 5)),
            ],
        ]
        for f in types_to_test:
            with self.subTest(type=f[0].__class__.__name__, expected=None):
                # act
                actual = r.collideobjectsall(f)
                # assert
                self.assertFalse(actual)

    def test_collideobjectsall_list_of_object_with_multiple_rect_attribute(self):
        r = Rect(1, 1, 10, 10)

        things = [
            self._ObjectWithMultipleRectAttribute(
                Rect(1, 1, 10, 10), Rect(5, 5, 1, 1), Rect(-73, 3, 3, 3)
            ),
            self._ObjectWithMultipleRectAttribute(
                Rect(5, 5, 10, 10), Rect(-5, -5, 10, 10), Rect(3, 3, 3, 3)
            ),
            self._ObjectWithMultipleRectAttribute(
                Rect(15, 15, 1, 1), Rect(100, 1, 1, 1), Rect(3, 83, 3, 3)
            ),
            self._ObjectWithMultipleRectAttribute(
                Rect(2, 2, 1, 1), Rect(1, -81, 10, 10), Rect(3, 8, 3, 3)
            ),
        ]
        self.assertEqual(
            r.collideobjectsall(things, key=lambda o: o.rect1),
            [things[0], things[1], things[3]],
        )
        self.assertEqual(
            r.collideobjectsall(things, key=lambda o: o.rect2), [things[0], things[1]]
        )
        self.assertEqual(
            r.collideobjectsall(things, key=lambda o: o.rect3), [things[1], things[3]]
        )

        f = [
            self._ObjectWithMultipleRectAttribute(
                Rect(50, 50, 1, 1), Rect(11, 1, 1, 1), Rect(2, -32, 2, 2)
            ),
            self._ObjectWithMultipleRectAttribute(
                Rect(20, 20, 5, 5), Rect(1, 11, 1, 1), Rect(-20, 2, 2, 2)
            ),
        ]
        self.assertFalse(r.collideobjectsall(f, key=lambda o: o.rect1))
        self.assertFalse(r.collideobjectsall(f, key=lambda o: o.rect2))
        self.assertFalse(r.collideobjectsall(f, key=lambda o: o.rect3))

    def test_fit(self):
        # __doc__ (as of 2008-08-02) for pygame.rect.Rect.fit:

        # Rect.fit(Rect): return Rect
        # resize and move a rectangle with aspect ratio
        #
        # Returns a new rectangle that is moved and resized to fit another.
        # The aspect ratio of the original Rect is preserved, so the new
        # rectangle may be smaller than the target in either width or height.

        r = Rect(10, 10, 30, 30)

        r2 = Rect(30, 30, 15, 10)

        f = r.fit(r2)
        self.assertTrue(r2.contains(f))

        f2 = r2.fit(r)
        self.assertTrue(r.contains(f2))

    def test_copy(self):
        r = Rect(1, 2, 10, 20)
        c = r.copy()
        self.assertEqual(c, r)

    def test_subscript(self):
        r = Rect(1, 2, 3, 4)
        self.assertEqual(r[0], 1)
        self.assertEqual(r[1], 2)
        self.assertEqual(r[2], 3)
        self.assertEqual(r[3], 4)
        self.assertEqual(r[-1], 4)
        self.assertEqual(r[-2], 3)
        self.assertEqual(r[-4], 1)
        self.assertRaises(IndexError, r.__getitem__, 5)
        self.assertRaises(IndexError, r.__getitem__, -5)
        self.assertEqual(r[0:2], [1, 2])
        self.assertEqual(r[0:4], [1, 2, 3, 4])
        self.assertEqual(r[0:-1], [1, 2, 3])
        self.assertEqual(r[:], [1, 2, 3, 4])
        self.assertEqual(r[...], [1, 2, 3, 4])
        self.assertEqual(r[0:4:2], [1, 3])
        self.assertEqual(r[0:4:3], [1, 4])
        self.assertEqual(r[3::-1], [4, 3, 2, 1])
        self.assertRaises(TypeError, r.__getitem__, None)

    def test_ass_subscript(self):
        r = Rect(0, 0, 0, 0)
        r[...] = 1, 2, 3, 4
        self.assertEqual(r, [1, 2, 3, 4])
        self.assertRaises(TypeError, r.__setitem__, None, 0)
        self.assertEqual(r, [1, 2, 3, 4])
        self.assertRaises(TypeError, r.__setitem__, 0, "")
        self.assertEqual(r, [1, 2, 3, 4])
        self.assertRaises(IndexError, r.__setitem__, 4, 0)
        self.assertEqual(r, [1, 2, 3, 4])
        self.assertRaises(IndexError, r.__setitem__, -5, 0)
        self.assertEqual(r, [1, 2, 3, 4])
        r[0] = 10
        self.assertEqual(r, [10, 2, 3, 4])
        r[3] = 40
        self.assertEqual(r, [10, 2, 3, 40])
        r[-1] = 400
        self.assertEqual(r, [10, 2, 3, 400])
        r[-4] = 100
        self.assertEqual(r, [100, 2, 3, 400])
        r[1:3] = 0
        self.assertEqual(r, [100, 0, 0, 400])
        r[...] = 0
        self.assertEqual(r, [0, 0, 0, 0])
        r[:] = 9
        self.assertEqual(r, [9, 9, 9, 9])
        r[:] = 11, 12, 13, 14
        self.assertEqual(r, [11, 12, 13, 14])
        r[::-1] = r
        self.assertEqual(r, [14, 13, 12, 11])

    def test_ass_subscript_deletion(self):
        r = Rect(0, 0, 0, 0)
        with self.assertRaises(TypeError):
            del r[0]

        with self.assertRaises(TypeError):
            del r[0:2]

        with self.assertRaises(TypeError):
            del r[...]

    def test_collection_abc(self):
        r = Rect(64, 70, 75, 30)
        self.assertTrue(isinstance(r, Collection))
        self.assertFalse(isinstance(r, Sequence))


class SubclassTest(unittest.TestCase):
    class MyRect(Rect):
        def __init__(self, *args, **kwds):
            super(SubclassTest.MyRect, self).__init__(*args, **kwds)
            self.an_attribute = True

    def test_copy(self):
        mr1 = self.MyRect(1, 2, 10, 20)
        self.assertTrue(mr1.an_attribute)
        mr2 = mr1.copy()
        self.assertTrue(isinstance(mr2, self.MyRect))
        self.assertRaises(AttributeError, getattr, mr2, "an_attribute")

    def test_move(self):
        mr1 = self.MyRect(1, 2, 10, 20)
        self.assertTrue(mr1.an_attribute)
        mr2 = mr1.move(1, 2)
        self.assertTrue(isinstance(mr2, self.MyRect))
        self.assertRaises(AttributeError, getattr, mr2, "an_attribute")

    def test_inflate(self):
        mr1 = self.MyRect(1, 2, 10, 20)
        self.assertTrue(mr1.an_attribute)
        mr2 = mr1.inflate(2, 4)
        self.assertTrue(isinstance(mr2, self.MyRect))
        self.assertRaises(AttributeError, getattr, mr2, "an_attribute")

    def test_clamp(self):
        mr1 = self.MyRect(19, 12, 5, 5)
        self.assertTrue(mr1.an_attribute)
        mr2 = mr1.clamp(Rect(10, 10, 10, 10))
        self.assertTrue(isinstance(mr2, self.MyRect))
        self.assertRaises(AttributeError, getattr, mr2, "an_attribute")

    def test_clip(self):
        mr1 = self.MyRect(1, 2, 3, 4)
        self.assertTrue(mr1.an_attribute)
        mr2 = mr1.clip(Rect(0, 0, 3, 4))
        self.assertTrue(isinstance(mr2, self.MyRect))
        self.assertRaises(AttributeError, getattr, mr2, "an_attribute")

    def test_union(self):
        mr1 = self.MyRect(1, 1, 1, 2)
        self.assertTrue(mr1.an_attribute)
        mr2 = mr1.union(Rect(-2, -2, 1, 2))
        self.assertTrue(isinstance(mr2, self.MyRect))
        self.assertRaises(AttributeError, getattr, mr2, "an_attribute")

    def test_unionall(self):
        mr1 = self.MyRect(0, 0, 1, 1)
        self.assertTrue(mr1.an_attribute)
        mr2 = mr1.unionall([Rect(-2, -2, 1, 1), Rect(2, 2, 1, 1)])
        self.assertTrue(isinstance(mr2, self.MyRect))
        self.assertRaises(AttributeError, getattr, mr2, "an_attribute")

    def test_fit(self):
        mr1 = self.MyRect(10, 10, 30, 30)
        self.assertTrue(mr1.an_attribute)
        mr2 = mr1.fit(Rect(30, 30, 15, 10))
        self.assertTrue(isinstance(mr2, self.MyRect))
        self.assertRaises(AttributeError, getattr, mr2, "an_attribute")

    def test_collection_abc(self):
        mr1 = self.MyRect(64, 70, 75, 30)
        self.assertTrue(isinstance(mr1, Collection))
        self.assertFalse(isinstance(mr1, Sequence))


if __name__ == "__main__":
    unittest.main()
