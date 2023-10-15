"""Pygame unit test suite package

Exports function run()

A quick way to run the test suite package from the command line
is by importing the go submodule:

python -m "import pygame.tests" [<test options>]

Command line option --help displays a usage message. Available options
correspond to the pygame.tests.run arguments.

The xxxx_test submodules of the tests package are unit test suites for
individual parts of Pygame. Each can also be run as a main program. This is
useful if the test, such as cdrom_test, is interactive.

For Pygame development the test suite can be run from a Pygame distribution
root directory using run_tests.py. Alternately, test/__main__.py can be run
directly.

"""

if __name__ == "pygame.tests":
    from pygame.tests.test_utils.run_tests import run
elif __name__ == "__main__":
    import os
    import sys

    pkg_dir = os.path.split(os.path.abspath(__file__))[0]
    parent_dir, pkg_name = os.path.split(pkg_dir)
    is_pygame_pkg = pkg_name == "tests" and os.path.split(parent_dir)[1] == "pygame"
    if not is_pygame_pkg:
        sys.path.insert(0, parent_dir)

    if is_pygame_pkg:
        import pygame.tests.__main__
    else:
        import test.__main__
else:
    from test.test_utils.run_tests import run
