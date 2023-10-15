"""Load and run the Pygame test suite

python -c "import pygame.tests.go" [<test options>]

or

python test/go.py [<test options>]

Command line option --help displays a command line usage message.

run_tests.py in the main distribution directory is an alternative to test.go

"""

import sys

if __name__ == "__main__":
    import os

    pkg_dir = os.path.split(os.path.abspath(__file__))[0]
    parent_dir, pkg_name = os.path.split(pkg_dir)
    is_pygame_pkg = pkg_name == "tests" and os.path.split(parent_dir)[1] == "pygame"
    if not is_pygame_pkg:
        sys.path.insert(0, parent_dir)
else:
    is_pygame_pkg = __name__.startswith("pygame.tests.")

if is_pygame_pkg:
    from pygame.tests.test_utils.run_tests import run_and_exit
    from pygame.tests.test_utils.test_runner import opt_parser
else:
    from test.test_utils.run_tests import run_and_exit
    from test.test_utils.test_runner import opt_parser

if is_pygame_pkg:
    test_pkg_name = "pygame.tests"
else:
    test_pkg_name = "test"
program_name = sys.argv[0]
if program_name == "-c":
    program_name = f'python -c "import {test_pkg_name}.go"'

###########################################################################
# Set additional command line options
#
# Defined in test_runner.py as it shares options, added to here

opt_parser.set_usage(
    f"""

Runs all or some of the {test_pkg_name}.xxxx_test tests.

$ {program_name} sprite threads -sd

Runs the sprite and threads module tests isolated in subprocesses, dumping
all failing tests info in the form of a dict.

"""
)

opt_parser.add_option(
    "-d", "--dump", action="store_true", help="dump results as dict ready to eval"
)

opt_parser.add_option("-F", "--file", help="dump results to a file")

opt_parser.add_option(
    "-m",
    "--multi_thread",
    metavar="THREADS",
    type="int",
    help="run subprocessed tests in x THREADS",
)

opt_parser.add_option(
    "-t",
    "--time_out",
    metavar="SECONDS",
    type="int",
    help="kill stalled subprocessed tests after SECONDS",
)

opt_parser.add_option(
    "-f", "--fake", metavar="DIR", help="run fake tests in run_tests__tests/$DIR"
)

opt_parser.add_option(
    "-p",
    "--python",
    metavar="PYTHON",
    help="path to python executable to run subproccesed tests\n"
    "default (sys.executable): %s" % sys.executable,
)

opt_parser.add_option(
    "-I",
    "--interactive",
    action="store_true",
    help="include tests requiring user input",
)

opt_parser.add_option("-S", "--seed", type="int", help="Randomisation seed")

###########################################################################
# Set run() keyword arguments according to command line arguments.
# args will be the test module list, passed as positional argumemts.

options, args = opt_parser.parse_args()
kwds = {}
if options.incomplete:
    kwds["incomplete"] = True
if options.usesubprocess:
    kwds["usesubprocess"] = True
else:
    kwds["usesubprocess"] = False
if options.dump:
    kwds["dump"] = True
if options.file:
    kwds["file"] = options.file
if options.exclude:
    kwds["exclude"] = options.exclude
if options.unbuffered:
    kwds["unbuffered"] = True
if options.randomize:
    kwds["randomize"] = True
if options.seed is not None:
    kwds["seed"] = options.seed
if options.multi_thread is not None:
    kwds["multi_thread"] = options.multi_thread
if options.time_out is not None:
    kwds["time_out"] = options.time_out
if options.fake:
    kwds["fake"] = options.fake
if options.python:
    kwds["python"] = options.python
if options.interactive:
    kwds["interactive"] = True
kwds["verbosity"] = options.verbosity if options.verbosity is not None else 1


###########################################################################
# Run the test suite.
run_and_exit(*args, **kwds)
