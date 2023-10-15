################################################################################

import subprocess, os, sys, re, difflib

################################################################################

IGNORE = (".svn", "infinite_loop")
NORMALIZERS = (
    (r"Ran (\d+) tests in (\d+\.\d+)s", "Ran \\1 tests in X.XXXs"),
    (r'File ".*?([^/\\.]+\.py)"', 'File "\\1"'),
)

################################################################################


def norm_result(result):
    "normalize differences, such as timing between output"
    for normalizer, replacement in NORMALIZERS:
        if hasattr(normalizer, "__call__"):
            result = normalizer(result)
        else:
            result = re.sub(normalizer, replacement, result)

    return result


def call_proc(cmd, cd=None):
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=cd,
        universal_newlines=True,
    )
    if proc.wait():
        print(f"{cmd} {proc.wait()}")
        raise Exception(proc.stdout.read())

    return proc.stdout.read()


################################################################################

unnormed_diff = "-u" in sys.argv
verbose = "-v" in sys.argv or unnormed_diff
if "-h" in sys.argv or "--help" in sys.argv:
    sys.exit(
        "\nCOMPARES OUTPUT OF SINGLE VS SUBPROCESS MODE OF RUN_TESTS.PY\n\n"
        "-v, to output diffs even on success\n"
        "-u, to output diffs of unnormalized tests\n\n"
        "Each line of a Differ delta begins with a two-letter code:\n\n"
        "    '- '    line unique to sequence 1\n"
        "    '+ '    line unique to sequence 2\n"
        "    '  '    line common to both sequences\n"
        "    '? '    line not present in either input sequence\n"
    )

main_dir = os.path.split(os.path.abspath(sys.argv[0]))[0]
trunk_dir = os.path.normpath(os.path.join(main_dir, "../../"))

test_suite_dirs = [
    x
    for x in os.listdir(main_dir)
    if os.path.isdir(os.path.join(main_dir, x)) and x not in IGNORE
]


################################################################################


def assert_on_results(suite, single, sub):
    test = globals().get(f"{suite}_test")
    if hasattr(test, "__call_"):
        test(suite, single, sub)
        print(f"assertions on {suite} OK")


# Don't modify tests in suites below. These assertions are in place to make sure
# that tests are actually being ran


def all_ok_test(suite, *args):
    for results in args:
        assert "Ran 36 tests" in results  # some tests are running
        assert "OK" in results  # OK


def failures1_test(suite, *args):
    for results in args:
        assert "FAILED (failures=2)" in results
        assert "Ran 18 tests" in results


################################################################################
# Test that output is the same in single process and subprocess modes
#

base_cmd = [sys.executable, "run_tests.py", "-i"]

cmd = base_cmd + ["-n", "-f"]
sub_cmd = base_cmd + ["-f"]
time_out_cmd = base_cmd + ["-t", "4", "-f", "infinite_loop"]

passes = 0
failed = False

for suite in test_suite_dirs:
    single = call_proc(cmd + [suite], trunk_dir)
    subs = call_proc(sub_cmd + [suite], trunk_dir)

    normed_single, normed_subs = map(norm_result, (single, subs))

    failed = normed_single != normed_subs
    if failed:
        print(f"{suite} suite comparison FAILED\n")
    else:
        passes += 1
        print(f"{suite} suite comparison OK")

    assert_on_results(suite, single, subs)

    if verbose or failed:
        print("difflib.Differ().compare(single, suprocessed):\n")
        print(
            "".join(
                list(
                    difflib.Differ().compare(
                        (unnormed_diff and single or normed_single).splitlines(1),
                        (unnormed_diff and subs or normed_subs).splitlines(1),
                    )
                )
            )
        )

sys.stdout.write("infinite_loop suite (subprocess mode timeout) ")
loop_test = call_proc(time_out_cmd, trunk_dir)
assert "successfully terminated" in loop_test
passes += 1
print("OK")

print(f"\n{passes}/{len(test_suite_dirs) + 1} suites pass")

print("\n-h for help")

################################################################################
