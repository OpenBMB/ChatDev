import os
import pygame
import sys
import tempfile
import time

is_pygame_pkg = __name__.startswith("pygame.tests.")

###############################################################################


def tostring(row):
    """Convert row of bytes to string.  Expects `row` to be an
    ``array``.
    """
    return row.tobytes()


def geterror():
    return sys.exc_info()[1]


###############################################################################

this_dir = os.path.dirname(os.path.abspath(__file__))
trunk_dir = os.path.split(os.path.split(this_dir)[0])[0]
if is_pygame_pkg:
    test_module = "tests"
else:
    test_module = "test"


def trunk_relative_path(relative):
    return os.path.normpath(os.path.join(trunk_dir, relative))


def fixture_path(path):
    return trunk_relative_path(os.path.join(test_module, "fixtures", path))


def example_path(path):
    return trunk_relative_path(os.path.join("examples", path))


sys.path.insert(0, trunk_relative_path("."))


################################## TEMP FILES #################################


def get_tmp_dir():
    return tempfile.mkdtemp()


###############################################################################


def question(q):
    return input(f"\n{q.rstrip(' ')} (y/n): ").lower().strip() == "y"


def prompt(p):
    return input(f"\n{p.rstrip(' ')} (press enter to continue): ")


#################################### HELPERS ##################################


def rgba_between(value, minimum=0, maximum=255):
    if value < minimum:
        return minimum
    elif value > maximum:
        return maximum
    else:
        return value


def combinations(seqs):
    """

    Recipe 496807 from ActiveState Python CookBook

    Non recursive technique for getting all possible combinations of a sequence
    of sequences.

    """

    r = [[]]
    for x in seqs:
        r = [i + [y] for y in x for i in r]
    return r


def gradient(width, height):
    """

    Yields a pt and corresponding RGBA tuple, for every (width, height) combo.
    Useful for generating gradients.

    Actual gradient may be changed, no tests rely on specific values.

    Used in transform.rotate lossless tests to generate a fixture.

    """

    for l in range(width):
        for t in range(height):
            yield (l, t), tuple(map(rgba_between, (l, t, l, l + t)))


def rect_area_pts(rect):
    for l in range(rect.left, rect.right):
        for t in range(rect.top, rect.bottom):
            yield l, t


def rect_perimeter_pts(rect):
    """

    Returns pts ((L, T) tuples) encompassing the perimeter of a rect.

    The order is clockwise:

          topleft to topright
         topright to bottomright
      bottomright to bottomleft
       bottomleft to topleft

    Duplicate pts are not returned

    """
    clock_wise_from_top_left = (
        [(l, rect.top) for l in range(rect.left, rect.right)],
        [(rect.right - 1, t) for t in range(rect.top + 1, rect.bottom)],
        [(l, rect.bottom - 1) for l in range(rect.right - 2, rect.left - 1, -1)],
        [(rect.left, t) for t in range(rect.bottom - 2, rect.top, -1)],
    )

    for line in clock_wise_from_top_left:
        yield from line


def rect_outer_bounds(rect):
    """

     Returns topleft outerbound if possible and then the other pts, that are
     "exclusive" bounds of the rect

    ?------O
     |RECT|      ?|0)uterbound
     |----|
    O      O

    """
    return ([(rect.left - 1, rect.top)] if rect.left else []) + [
        rect.topright,
        rect.bottomleft,
        rect.bottomright,
    ]


def import_submodule(module):
    m = __import__(module)
    for n in module.split(".")[1:]:
        m = getattr(m, n)
    return m


class SurfaceSubclass(pygame.Surface):
    """A subclassed Surface to test inheritance."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.test_attribute = True


def test():
    """

    Lightweight test for helpers

    """

    r = pygame.Rect(0, 0, 10, 10)
    assert rect_outer_bounds(r) == [(10, 0), (0, 10), (10, 10)]  # tr # bl # br

    assert len(list(rect_area_pts(r))) == 100

    r = pygame.Rect(0, 0, 3, 3)
    assert list(rect_perimeter_pts(r)) == [
        (0, 0),
        (1, 0),
        (2, 0),  # tl -> tr
        (2, 1),
        (2, 2),  # tr -> br
        (1, 2),
        (0, 2),  # br -> bl
        (0, 1),  # bl -> tl
    ]

    print("Tests: OK")
