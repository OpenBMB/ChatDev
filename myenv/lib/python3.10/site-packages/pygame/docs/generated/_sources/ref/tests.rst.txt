.. include:: common.txt

:mod:`pygame.tests`
===================

.. module:: pygame.tests
   :synopsis: Pygame unit test suite package

| :sl:`Pygame unit test suite package`

A quick way to run the test suite package from the command line is to import
the go submodule with the Python -m option:

::

  python -m pygame.tests [<test options>]

Command line option --help displays a usage message. Available options
correspond to the :func:`pygame.tests.run` arguments.

The xxxx_test submodules of the tests package are unit test suites for
individual parts of pygame. Each can also be run as a main program. This is
useful if the test, such as cdrom_test, is interactive.

For pygame development the test suite can be run from a pygame distribution
root directory. Program ``run_tests.py`` is provided for convenience, though
test/go.py can be run directly.

Module level tags control which modules are included in a unit test run. Tags
are assigned to a unit test module with a corresponding <name>_tags.py module.
The tags module has the global __tags__, a list of tag names. For example,
``cdrom_test.py`` has a tag file ``cdrom_tags.py`` containing a tags list that
has the 'interactive' string. The 'interactive' tag indicates ``cdrom_test.py``
expects user input. It is excluded from a ``run_tests.py`` or
``pygame.tests.go`` run. 

Two other tags that are excluded are 'ignore' and 'subprocess_ignore'. These
two tags indicate unit tests that will not run on a particular platform, or
for which no corresponding pygame module is available.

The test runner will list each excluded module along with the tag responsible.

.. function:: run

   | :sl:`Run the pygame unit test suite`
   | :sg:`run(*args, **kwds) -> tuple`

   Positional arguments (optional):

   ::

       The names of tests to include. If omitted then all tests are run. Test names
       need not include the trailing '_test'.

   Keyword arguments:

   ::

       incomplete - fail incomplete tests (default False)
       nosubprocess - run all test suites in the current process
                      (default False, use separate subprocesses)
       dump - dump failures/errors as dict ready to eval (default False)
       file - if provided, the name of a file into which to dump failures/errors
       timings - if provided, the number of times to run each individual test to
                 get an average run time (default is run each test once)
       exclude - A list of TAG names to exclude from the run
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
              pygame tests
       python - the path to a python executable to run subprocessed tests
                (default sys.executable)

   Return value:

   ::

       A tuple of total number of tests run, dictionary of error information.
       The dictionary is empty if no errors were recorded.

   By default individual test modules are run in separate subprocesses. This
   recreates normal pygame usage where ``pygame.init()`` and ``pygame.quit()``
   are called only once per program execution, and avoids unfortunate
   interactions between test modules. 
   
   A time limit is placed on test execution ensuring that any frozen tests
   processes are killed when their time allotment is expired. Use the single
   process option if threading is not working properly or if tests are taking
   too long. It is not guaranteed that all tests will pass in single process
   mode.

   Tests are run in a randomized order if the randomize argument is True or a
   seed argument is provided. If no seed integer is provided then the system
   time is used for the randomization seed value.

   Individual test modules may have a __tags__ attribute, a list of tag strings
   used to selectively omit modules from a run. By default only 'interactive'
   modules such as cdrom_test are ignored. An interactive module must be run
   from the console as a Python program.

   This function can only be called once per Python session. It is not
   reentrant.

   .. ## pygame.tests.run ##

.. ## pygame.tests ##
