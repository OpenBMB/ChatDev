import sys

if __name__ == "__main__":
    raise RuntimeError("This module is for import only")
test_pkg_name = ".".join(__name__.split(".")[0:-2])
is_pygame_pkg = test_pkg_name == "pygame.tests"
test_runner_mod = test_pkg_name + ".test_utils.test_runner"

if is_pygame_pkg:
    from pygame.tests.test_utils import import_submodule
    from pygame.tests.test_utils.test_runner import (
        prepare_test_env,
        run_test,
        combine_results,
        get_test_results,
        TEST_RESULTS_START,
    )
else:
    from test.test_utils import import_submodule
    from test.test_utils.test_runner import (
        prepare_test_env,
        run_test,
        combine_results,
        get_test_results,
        TEST_RESULTS_START,
    )
import pygame
import pygame.threads

import os
import re
import shutil
import tempfile
import time
import random
from pprint import pformat

was_run = False


def run(*args, **kwds):
    """Run the Pygame unit test suite and return (total tests run, fails dict)

    Positional arguments (optional):
    The names of tests to include. If omitted then all tests are run. Test
    names need not include the trailing '_test'.

    Keyword arguments:
    incomplete - fail incomplete tests (default False)
    usesubprocess - run all test suites in the current process
                   (default False, use separate subprocesses)
    dump - dump failures/errors as dict ready to eval (default False)
    file - if provided, the name of a file into which to dump failures/errors
    timings - if provided, the number of times to run each individual test to
              get an average run time (default is run each test once)
    exclude - A list of TAG names to exclude from the run. The items may be
              comma or space separated.
    show_output - show silenced stderr/stdout on errors (default False)
    all - dump all results, not just errors (default False)
    randomize - randomize order of tests (default False)
    seed - if provided, a seed randomizer integer
    multi_thread - if provided, the number of THREADS in which to run
                   subprocessed tests
    time_out - if subprocess is True then the time limit in seconds before
               killing a test (default 30)
    fake - if provided, the name of the fake tests package in the
           run_tests__tests subpackage to run instead of the normal
           Pygame tests
    python - the path to a python executable to run subprocessed tests
             (default sys.executable)
    interactive - allow tests tagged 'interactive'.

    Return value:
    A tuple of total number of tests run, dictionary of error information. The
    dictionary is empty if no errors were recorded.

    By default individual test modules are run in separate subprocesses. This
    recreates normal Pygame usage where pygame.init() and pygame.quit() are
    called only once per program execution, and avoids unfortunate
    interactions between test modules. Also, a time limit is placed on test
    execution, so frozen tests are killed when there time allotment expired.
    Use the single process option if threading is not working properly or if
    tests are taking too long. It is not guaranteed that all tests will pass
    in single process mode.

    Tests are run in a randomized order if the randomize argument is True or a
    seed argument is provided. If no seed integer is provided then the system
    time is used.

    Individual test modules may have a corresponding *_tags.py module,
    defining a __tags__ attribute, a list of tag strings used to selectively
    omit modules from a run. By default only the 'interactive', 'ignore', and
    'subprocess_ignore' tags are ignored. 'interactive' is for modules that
    take user input, like cdrom_test.py. 'ignore' and 'subprocess_ignore' for
    for disabling modules for foreground and subprocess modes respectively.
    These are for disabling tests on optional modules or for experimental
    modules with known problems. These modules can be run from the console as
    a Python program.

    This function can only be called once per Python session. It is not
    reentrant.

    """

    global was_run

    if was_run:
        raise RuntimeError("run() was already called this session")
    was_run = True

    options = kwds.copy()
    option_usesubprocess = options.get("usesubprocess", False)
    option_dump = options.pop("dump", False)
    option_file = options.pop("file", None)
    option_randomize = options.get("randomize", False)
    option_seed = options.get("seed", None)
    option_multi_thread = options.pop("multi_thread", 1)
    option_time_out = options.pop("time_out", 120)
    option_fake = options.pop("fake", None)
    option_python = options.pop("python", sys.executable)
    option_exclude = options.pop("exclude", ())
    option_interactive = options.pop("interactive", False)

    if not option_interactive and "interactive" not in option_exclude:
        option_exclude += ("interactive",)
    if option_usesubprocess and "subprocess_ignore" not in option_exclude:
        option_exclude += ("subprocess_ignore",)
    elif "ignore" not in option_exclude:
        option_exclude += ("ignore",)

    option_exclude += ("python3_ignore",)
    option_exclude += ("SDL2_ignore",)

    main_dir, test_subdir, fake_test_subdir = prepare_test_env()

    ###########################################################################
    # Compile a list of test modules. If fake, then compile list of fake
    # xxxx_test.py from run_tests__tests

    TEST_MODULE_RE = re.compile(r"^(.+_test)\.py$")

    test_mods_pkg_name = test_pkg_name

    working_dir_temp = tempfile.mkdtemp()

    if option_fake is not None:
        test_mods_pkg_name = ".".join(
            [test_mods_pkg_name, "run_tests__tests", option_fake]
        )
        test_subdir = os.path.join(fake_test_subdir, option_fake)
        working_dir = test_subdir
    else:
        working_dir = working_dir_temp

    # Added in because some machines will need os.environ else there will be
    # false failures in subprocess mode. Same issue as python2.6. Needs some
    # env vars.

    test_env = os.environ

    fmt1 = "%s.%%s" % test_mods_pkg_name
    fmt2 = "%s.%%s_test" % test_mods_pkg_name
    if args:
        test_modules = [m.endswith("_test") and (fmt1 % m) or (fmt2 % m) for m in args]
    else:
        test_modules = []
        for f in sorted(os.listdir(test_subdir)):
            for match in TEST_MODULE_RE.findall(f):
                test_modules.append(fmt1 % (match,))

    ###########################################################################
    # Remove modules to be excluded.

    tmp = test_modules
    test_modules = []
    for name in tmp:
        tag_module_name = f"{name[0:-5]}_tags"
        try:
            tag_module = import_submodule(tag_module_name)
        except ImportError:
            test_modules.append(name)
        else:
            try:
                tags = tag_module.__tags__
            except AttributeError:
                print(f"{tag_module_name} has no tags: ignoring")
                test_modules.append(name)
            else:
                for tag in tags:
                    if tag in option_exclude:
                        print(f"skipping {name} (tag '{tag}')")
                        break
                else:
                    test_modules.append(name)
    del tmp, tag_module_name, name

    ###########################################################################
    # Meta results

    results = {}
    meta_results = {"__meta__": {}}
    meta = meta_results["__meta__"]

    ###########################################################################
    # Randomization

    if option_randomize or option_seed is not None:
        if option_seed is None:
            option_seed = time.time()
        meta["random_seed"] = option_seed
        print(f"\nRANDOM SEED USED: {option_seed}\n")
        random.seed(option_seed)
        random.shuffle(test_modules)

    ###########################################################################
    # Single process mode

    if not option_usesubprocess:
        options["exclude"] = option_exclude
        t = time.time()
        for module in test_modules:
            results.update(run_test(module, **options))
        t = time.time() - t

    ###########################################################################
    # Subprocess mode
    #

    else:
        if is_pygame_pkg:
            from pygame.tests.test_utils.async_sub import proc_in_time_or_kill
        else:
            from test.test_utils.async_sub import proc_in_time_or_kill

        pass_on_args = ["--exclude", ",".join(option_exclude)]
        for field in ["randomize", "incomplete", "unbuffered", "verbosity"]:
            if kwds.get(field, False):
                pass_on_args.append("--" + field)

        def sub_test(module):
            print(f"loading {module}")

            cmd = [option_python, "-m", test_runner_mod, module] + pass_on_args

            return (
                module,
                (cmd, test_env, working_dir),
                proc_in_time_or_kill(
                    cmd, option_time_out, env=test_env, wd=working_dir
                ),
            )

        if option_multi_thread > 1:

            def tmap(f, args):
                return pygame.threads.tmap(
                    f, args, stop_on_error=False, num_workers=option_multi_thread
                )

        else:
            tmap = map

        t = time.time()

        for module, cmd, (return_code, raw_return) in tmap(sub_test, test_modules):
            test_file = f"{os.path.join(test_subdir, module)}.py"
            cmd, test_env, working_dir = cmd

            test_results = get_test_results(raw_return)
            if test_results:
                results.update(test_results)
            else:
                results[module] = {}

            results[module].update(
                dict(
                    return_code=return_code,
                    raw_return=raw_return,
                    cmd=cmd,
                    test_file=test_file,
                    test_env=test_env,
                    working_dir=working_dir,
                    module=module,
                )
            )

        t = time.time() - t

    ###########################################################################
    # Output Results
    #

    untrusty_total, combined = combine_results(results, t)
    total, n_errors, n_failures = count_results(results)

    meta["total_tests"] = total
    meta["combined"] = combined
    meta["total_errors"] = n_errors
    meta["total_failures"] = n_failures
    results.update(meta_results)

    if not option_usesubprocess and total != untrusty_total:
        raise AssertionError(
            "Something went wrong in the Test Machinery:\n"
            "total: %d != untrusty_total: %d" % (total, untrusty_total)
        )

    if not option_dump:
        print(combined)
    else:
        print(TEST_RESULTS_START)
        print(pformat(results))

    if option_file is not None:
        results_file = open(option_file, "w")
        try:
            results_file.write(pformat(results))
        finally:
            results_file.close()

    shutil.rmtree(working_dir_temp)

    return total, n_errors + n_failures


def count_results(results):
    total = errors = failures = 0
    for result in results.values():
        if result.get("return_code", 0):
            total += 1
            errors += 1
        else:
            total += result["num_tests"]
            errors += result["num_errors"]
            failures += result["num_failures"]

    return total, errors, failures


def run_and_exit(*args, **kwargs):
    """Run the tests, and if there are failures, exit with a return code of 1.

    This is needed for various buildbots to recognise that the tests have
    failed.
    """
    total, fails = run(*args, **kwargs)
    if fails:
        sys.exit(1)
    sys.exit(0)
