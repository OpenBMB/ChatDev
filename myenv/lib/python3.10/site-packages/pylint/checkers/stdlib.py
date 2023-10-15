# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

"""Checkers for various standard library functions."""

from __future__ import annotations

import sys
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, Dict, Set, Tuple

import astroid
from astroid import nodes, util
from astroid.typing import InferenceResult

from pylint import interfaces
from pylint.checkers import BaseChecker, DeprecatedMixin, utils
from pylint.interfaces import INFERENCE
from pylint.typing import MessageDefinitionTuple

if TYPE_CHECKING:
    from pylint.lint import PyLinter

DeprecationDict = Dict[Tuple[int, int, int], Set[str]]

OPEN_FILES_MODE = ("open", "file")
OPEN_FILES_FUNCS = OPEN_FILES_MODE + ("read_text", "write_text")
UNITTEST_CASE = "unittest.case"
THREADING_THREAD = "threading.Thread"
COPY_COPY = "copy.copy"
OS_ENVIRON = "os._Environ"
ENV_GETTERS = ("os.getenv",)
SUBPROCESS_POPEN = "subprocess.Popen"
SUBPROCESS_RUN = "subprocess.run"
OPEN_MODULE = {"_io", "pathlib"}
DEBUG_BREAKPOINTS = ("builtins.breakpoint", "sys.breakpointhook", "pdb.set_trace")
LRU_CACHE = {
    "functools.lru_cache",  # Inferred for @lru_cache
    "functools._lru_cache_wrapper.wrapper",  # Inferred for @lru_cache() on >= Python 3.8
    "functools.lru_cache.decorating_function",  # Inferred for @lru_cache() on <= Python 3.7
}
NON_INSTANCE_METHODS = {"builtins.staticmethod", "builtins.classmethod"}


# For modules, see ImportsChecker

DEPRECATED_ARGUMENTS: dict[
    tuple[int, int, int], dict[str, tuple[tuple[int | None, str], ...]]
] = {
    (0, 0, 0): {
        "int": ((None, "x"),),
        "bool": ((None, "x"),),
        "float": ((None, "x"),),
    },
    (3, 8, 0): {
        "asyncio.tasks.sleep": ((None, "loop"),),
        "asyncio.tasks.gather": ((None, "loop"),),
        "asyncio.tasks.shield": ((None, "loop"),),
        "asyncio.tasks.wait_for": ((None, "loop"),),
        "asyncio.tasks.wait": ((None, "loop"),),
        "asyncio.tasks.as_completed": ((None, "loop"),),
        "asyncio.subprocess.create_subprocess_exec": ((None, "loop"),),
        "asyncio.subprocess.create_subprocess_shell": ((4, "loop"),),
        "gettext.translation": ((5, "codeset"),),
        "gettext.install": ((2, "codeset"),),
        "functools.partialmethod": ((None, "func"),),
        "weakref.finalize": ((None, "func"), (None, "obj")),
        "profile.Profile.runcall": ((None, "func"),),
        "cProfile.Profile.runcall": ((None, "func"),),
        "bdb.Bdb.runcall": ((None, "func"),),
        "trace.Trace.runfunc": ((None, "func"),),
        "curses.wrapper": ((None, "func"),),
        "unittest.case.TestCase.addCleanup": ((None, "function"),),
        "concurrent.futures.thread.ThreadPoolExecutor.submit": ((None, "fn"),),
        "concurrent.futures.process.ProcessPoolExecutor.submit": ((None, "fn"),),
        "contextlib._BaseExitStack.callback": ((None, "callback"),),
        "contextlib.AsyncExitStack.push_async_callback": ((None, "callback"),),
        "multiprocessing.managers.Server.create": ((None, "c"), (None, "typeid")),
        "multiprocessing.managers.SharedMemoryServer.create": (
            (None, "c"),
            (None, "typeid"),
        ),
    },
    (3, 9, 0): {"random.Random.shuffle": ((1, "random"),)},
}

DEPRECATED_DECORATORS: DeprecationDict = {
    (3, 8, 0): {"asyncio.coroutine"},
    (3, 3, 0): {
        "abc.abstractclassmethod",
        "abc.abstractstaticmethod",
        "abc.abstractproperty",
    },
    (3, 4, 0): {"importlib.util.module_for_loader"},
}


DEPRECATED_METHODS: dict[int, DeprecationDict] = {
    0: {
        (0, 0, 0): {
            "cgi.parse_qs",
            "cgi.parse_qsl",
            "ctypes.c_buffer",
            "distutils.command.register.register.check_metadata",
            "distutils.command.sdist.sdist.check_metadata",
            "tkinter.Misc.tk_menuBar",
            "tkinter.Menu.tk_bindForTraversal",
        }
    },
    2: {
        (2, 6, 0): {
            "commands.getstatus",
            "os.popen2",
            "os.popen3",
            "os.popen4",
            "macostools.touched",
        },
        (2, 7, 0): {
            "unittest.case.TestCase.assertEquals",
            "unittest.case.TestCase.assertNotEquals",
            "unittest.case.TestCase.assertAlmostEquals",
            "unittest.case.TestCase.assertNotAlmostEquals",
            "unittest.case.TestCase.assert_",
            "xml.etree.ElementTree.Element.getchildren",
            "xml.etree.ElementTree.Element.getiterator",
            "xml.etree.ElementTree.XMLParser.getiterator",
            "xml.etree.ElementTree.XMLParser.doctype",
        },
    },
    3: {
        (3, 0, 0): {
            "inspect.getargspec",
            "failUnlessEqual",
            "assertEquals",
            "failIfEqual",
            "assertNotEquals",
            "failUnlessAlmostEqual",
            "assertAlmostEquals",
            "failIfAlmostEqual",
            "assertNotAlmostEquals",
            "failUnless",
            "assert_",
            "failUnlessRaises",
            "failIf",
            "assertRaisesRegexp",
            "assertRegexpMatches",
            "assertNotRegexpMatches",
        },
        (3, 1, 0): {
            "base64.encodestring",
            "base64.decodestring",
            "ntpath.splitunc",
            "os.path.splitunc",
            "os.stat_float_times",
            "turtle.RawTurtle.settiltangle",
        },
        (3, 2, 0): {
            "cgi.escape",
            "configparser.RawConfigParser.readfp",
            "xml.etree.ElementTree.Element.getchildren",
            "xml.etree.ElementTree.Element.getiterator",
            "xml.etree.ElementTree.XMLParser.getiterator",
            "xml.etree.ElementTree.XMLParser.doctype",
        },
        (3, 3, 0): {
            "inspect.getmoduleinfo",
            "logging.warn",
            "logging.Logger.warn",
            "logging.LoggerAdapter.warn",
            "nntplib._NNTPBase.xpath",
            "platform.popen",
            "sqlite3.OptimizedUnicode",
            "time.clock",
        },
        (3, 4, 0): {
            "importlib.find_loader",
            "importlib.abc.Loader.load_module",
            "importlib.abc.Loader.module_repr",
            "importlib.abc.PathEntryFinder.find_loader",
            "importlib.abc.PathEntryFinder.find_module",
            "plistlib.readPlist",
            "plistlib.writePlist",
            "plistlib.readPlistFromBytes",
            "plistlib.writePlistToBytes",
        },
        (3, 4, 4): {"asyncio.tasks.async"},
        (3, 5, 0): {
            "fractions.gcd",
            "inspect.formatargspec",
            "inspect.getcallargs",
            "platform.linux_distribution",
            "platform.dist",
        },
        (3, 6, 0): {
            "importlib._bootstrap_external.FileLoader.load_module",
            "_ssl.RAND_pseudo_bytes",
        },
        (3, 7, 0): {
            "sys.set_coroutine_wrapper",
            "sys.get_coroutine_wrapper",
            "aifc.openfp",
            "threading.Thread.isAlive",
            "asyncio.Task.current_task",
            "asyncio.Task.all_task",
            "locale.format",
            "ssl.wrap_socket",
            "ssl.match_hostname",
            "sunau.openfp",
            "wave.openfp",
        },
        (3, 8, 0): {
            "gettext.lgettext",
            "gettext.ldgettext",
            "gettext.lngettext",
            "gettext.ldngettext",
            "gettext.bind_textdomain_codeset",
            "gettext.NullTranslations.output_charset",
            "gettext.NullTranslations.set_output_charset",
            "threading.Thread.isAlive",
        },
        (3, 9, 0): {
            "binascii.b2a_hqx",
            "binascii.a2b_hqx",
            "binascii.rlecode_hqx",
            "binascii.rledecode_hqx",
        },
        (3, 10, 0): {
            "_sqlite3.enable_shared_cache",
            "importlib.abc.Finder.find_module",
            "pathlib.Path.link_to",
            "zipimport.zipimporter.load_module",
            "zipimport.zipimporter.find_module",
            "zipimport.zipimporter.find_loader",
            "threading.currentThread",
            "threading.activeCount",
            "threading.Condition.notifyAll",
            "threading.Event.isSet",
            "threading.Thread.setName",
            "threading.Thread.getName",
            "threading.Thread.isDaemon",
            "threading.Thread.setDaemon",
            "cgi.log",
        },
        (3, 11, 0): {
            "locale.getdefaultlocale",
            "locale.resetlocale",
            "re.template",
            "unittest.findTestCases",
            "unittest.makeSuite",
            "unittest.getTestCaseNames",
            "unittest.TestLoader.loadTestsFromModule",
            "unittest.TestLoader.loadTestsFromTestCase",
            "unittest.TestLoader.getTestCaseNames",
        },
    },
}


DEPRECATED_CLASSES: dict[tuple[int, int, int], dict[str, set[str]]] = {
    (3, 2, 0): {
        "configparser": {
            "LegacyInterpolation",
            "SafeConfigParser",
        },
    },
    (3, 3, 0): {
        "importlib.abc": {
            "Finder",
        },
        "pkgutil": {
            "ImpImporter",
            "ImpLoader",
        },
        "collections": {
            "Awaitable",
            "Coroutine",
            "AsyncIterable",
            "AsyncIterator",
            "AsyncGenerator",
            "Hashable",
            "Iterable",
            "Iterator",
            "Generator",
            "Reversible",
            "Sized",
            "Container",
            "Callable",
            "Collection",
            "Set",
            "MutableSet",
            "Mapping",
            "MutableMapping",
            "MappingView",
            "KeysView",
            "ItemsView",
            "ValuesView",
            "Sequence",
            "MutableSequence",
            "ByteString",
        },
    },
    (3, 9, 0): {
        "smtpd": {
            "MailmanProxy",
        }
    },
    (3, 11, 0): {
        "typing": {
            "Text",
        },
        "webbrowser": {
            "MacOSX",
        },
    },
}


def _check_mode_str(mode: Any) -> bool:
    # check type
    if not isinstance(mode, str):
        return False
    # check syntax
    modes = set(mode)
    _mode = "rwatb+Ux"
    creating = "x" in modes
    if modes - set(_mode) or len(mode) > len(modes):
        return False
    # check logic
    reading = "r" in modes
    writing = "w" in modes
    appending = "a" in modes
    text = "t" in modes
    binary = "b" in modes
    if "U" in modes:
        if writing or appending or creating:
            return False
        reading = True
    if text and binary:
        return False
    total = reading + writing + appending + creating
    if total > 1:
        return False
    if not (reading or writing or appending or creating):
        return False
    return True


class StdlibChecker(DeprecatedMixin, BaseChecker):
    name = "stdlib"

    msgs: dict[str, MessageDefinitionTuple] = {
        **DeprecatedMixin.DEPRECATED_METHOD_MESSAGE,
        **DeprecatedMixin.DEPRECATED_ARGUMENT_MESSAGE,
        **DeprecatedMixin.DEPRECATED_CLASS_MESSAGE,
        **DeprecatedMixin.DEPRECATED_DECORATOR_MESSAGE,
        "W1501": (
            '"%s" is not a valid mode for open.',
            "bad-open-mode",
            "Python supports: r, w, a[, x] modes with b, +, "
            "and U (only with r) options. "
            "See https://docs.python.org/3/library/functions.html#open",
        ),
        "W1502": (
            "Using datetime.time in a boolean context.",
            "boolean-datetime",
            "Using datetime.time in a boolean context can hide "
            "subtle bugs when the time they represent matches "
            "midnight UTC. This behaviour was fixed in Python 3.5. "
            "See https://bugs.python.org/issue13936 for reference.",
            {"maxversion": (3, 5)},
        ),
        "W1503": (
            "Redundant use of %s with constant value %r",
            "redundant-unittest-assert",
            "The first argument of assertTrue and assertFalse is "
            "a condition. If a constant is passed as parameter, that "
            "condition will be always true. In this case a warning "
            "should be emitted.",
        ),
        "W1506": (
            "threading.Thread needs the target function",
            "bad-thread-instantiation",
            "The warning is emitted when a threading.Thread class "
            "is instantiated without the target function being passed as a kwarg or as a second argument. "
            "By default, the first parameter is the group param, not the target param.",
        ),
        "W1507": (
            "Using copy.copy(os.environ). Use os.environ.copy() instead.",
            "shallow-copy-environ",
            "os.environ is not a dict object but proxy object, so "
            "shallow copy has still effects on original object. "
            "See https://bugs.python.org/issue15373 for reference.",
        ),
        "E1507": (
            "%s does not support %s type argument",
            "invalid-envvar-value",
            "Env manipulation functions support only string type arguments. "
            "See https://docs.python.org/3/library/os.html#os.getenv.",
        ),
        "E1519": (
            "singledispatch decorator should not be used with methods, "
            "use singledispatchmethod instead.",
            "singledispatch-method",
            "singledispatch should decorate functions and not class/instance methods. "
            "Use singledispatchmethod for those cases.",
        ),
        "E1520": (
            "singledispatchmethod decorator should not be used with functions, "
            "use singledispatch instead.",
            "singledispatchmethod-function",
            "singledispatchmethod should decorate class/instance methods and not functions. "
            "Use singledispatch for those cases.",
        ),
        "W1508": (
            "%s default type is %s. Expected str or None.",
            "invalid-envvar-default",
            "Env manipulation functions return None or str values. "
            "Supplying anything different as a default may cause bugs. "
            "See https://docs.python.org/3/library/os.html#os.getenv.",
        ),
        "W1509": (
            "Using preexec_fn keyword which may be unsafe in the presence "
            "of threads",
            "subprocess-popen-preexec-fn",
            "The preexec_fn parameter is not safe to use in the presence "
            "of threads in your application. The child process could "
            "deadlock before exec is called. If you must use it, keep it "
            "trivial! Minimize the number of libraries you call into. "
            "See https://docs.python.org/3/library/subprocess.html#popen-constructor",
        ),
        "W1510": (
            "'subprocess.run' used without explicitly defining the value for 'check'.",
            "subprocess-run-check",
            "The ``check`` keyword  is set to False by default. It means the process "
            "launched by ``subprocess.run`` can exit with a non-zero exit code and "
            "fail silently. It's better to set it explicitly to make clear what the "
            "error-handling behavior is.",
        ),
        "W1514": (
            "Using open without explicitly specifying an encoding",
            "unspecified-encoding",
            "It is better to specify an encoding when opening documents. "
            "Using the system default implicitly can create problems on other operating systems. "
            "See https://peps.python.org/pep-0597/",
        ),
        "W1515": (
            "Leaving functions creating breakpoints in production code is not recommended",
            "forgotten-debug-statement",
            "Calls to breakpoint(), sys.breakpointhook() and pdb.set_trace() should be removed "
            "from code that is not actively being debugged.",
        ),
        "W1518": (
            "'lru_cache(maxsize=None)' or 'cache' will keep all method args alive indefinitely, including 'self'",
            "method-cache-max-size-none",
            "By decorating a method with lru_cache or cache the 'self' argument will be linked to "
            "the function and therefore never garbage collected. Unless your instance "
            "will never need to be garbage collected (singleton) it is recommended to refactor "
            "code to avoid this pattern or add a maxsize to the cache. "
            "The default value for maxsize is 128.",
            {
                "old_names": [
                    ("W1516", "lru-cache-decorating-method"),
                    ("W1517", "cache-max-size-none"),
                ]
            },
        ),
    }

    def __init__(self, linter: PyLinter) -> None:
        BaseChecker.__init__(self, linter)
        self._deprecated_methods: set[str] = set()
        self._deprecated_arguments: dict[str, tuple[tuple[int | None, str], ...]] = {}
        self._deprecated_classes: dict[str, set[str]] = {}
        self._deprecated_decorators: set[str] = set()

        for since_vers, func_list in DEPRECATED_METHODS[sys.version_info[0]].items():
            if since_vers <= sys.version_info:
                self._deprecated_methods.update(func_list)
        for since_vers, args_list in DEPRECATED_ARGUMENTS.items():
            if since_vers <= sys.version_info:
                self._deprecated_arguments.update(args_list)
        for since_vers, class_list in DEPRECATED_CLASSES.items():
            if since_vers <= sys.version_info:
                self._deprecated_classes.update(class_list)
        for since_vers, decorator_list in DEPRECATED_DECORATORS.items():
            if since_vers <= sys.version_info:
                self._deprecated_decorators.update(decorator_list)
        # Modules are checked by the ImportsChecker, because the list is
        # synced with the config argument deprecated-modules

    def _check_bad_thread_instantiation(self, node: nodes.Call) -> None:
        func_kwargs = {key.arg for key in node.keywords}
        if "target" in func_kwargs:
            return

        if len(node.args) < 2 and (not node.kwargs or "target" not in func_kwargs):
            self.add_message(
                "bad-thread-instantiation", node=node, confidence=interfaces.HIGH
            )

    def _check_for_preexec_fn_in_popen(self, node: nodes.Call) -> None:
        if node.keywords:
            for keyword in node.keywords:
                if keyword.arg == "preexec_fn":
                    self.add_message("subprocess-popen-preexec-fn", node=node)

    def _check_for_check_kw_in_run(self, node: nodes.Call) -> None:
        kwargs = {keyword.arg for keyword in (node.keywords or ())}
        if "check" not in kwargs:
            self.add_message("subprocess-run-check", node=node, confidence=INFERENCE)

    def _check_shallow_copy_environ(self, node: nodes.Call) -> None:
        arg = utils.get_argument_from_call(node, position=0)
        try:
            inferred_args = arg.inferred()
        except astroid.InferenceError:
            return
        for inferred in inferred_args:
            if inferred.qname() == OS_ENVIRON:
                self.add_message("shallow-copy-environ", node=node)
                break

    @utils.only_required_for_messages(
        "bad-open-mode",
        "redundant-unittest-assert",
        "deprecated-method",
        "deprecated-argument",
        "bad-thread-instantiation",
        "shallow-copy-environ",
        "invalid-envvar-value",
        "invalid-envvar-default",
        "subprocess-popen-preexec-fn",
        "subprocess-run-check",
        "deprecated-class",
        "unspecified-encoding",
        "forgotten-debug-statement",
    )
    def visit_call(self, node: nodes.Call) -> None:
        """Visit a Call node."""
        self.check_deprecated_class_in_call(node)
        for inferred in utils.infer_all(node.func):
            if isinstance(inferred, util.UninferableBase):
                continue
            if inferred.root().name in OPEN_MODULE:
                open_func_name: str | None = None
                if isinstance(node.func, nodes.Name):
                    open_func_name = node.func.name
                if isinstance(node.func, nodes.Attribute):
                    open_func_name = node.func.attrname
                if open_func_name in OPEN_FILES_FUNCS:
                    self._check_open_call(node, inferred.root().name, open_func_name)
            elif inferred.root().name == UNITTEST_CASE:
                self._check_redundant_assert(node, inferred)
            elif isinstance(inferred, nodes.ClassDef):
                if inferred.qname() == THREADING_THREAD:
                    self._check_bad_thread_instantiation(node)
                elif inferred.qname() == SUBPROCESS_POPEN:
                    self._check_for_preexec_fn_in_popen(node)
            elif isinstance(inferred, nodes.FunctionDef):
                name = inferred.qname()
                if name == COPY_COPY:
                    self._check_shallow_copy_environ(node)
                elif name in ENV_GETTERS:
                    self._check_env_function(node, inferred)
                elif name == SUBPROCESS_RUN:
                    self._check_for_check_kw_in_run(node)
                elif name in DEBUG_BREAKPOINTS:
                    self.add_message("forgotten-debug-statement", node=node)
            self.check_deprecated_method(node, inferred)

    @utils.only_required_for_messages("boolean-datetime")
    def visit_unaryop(self, node: nodes.UnaryOp) -> None:
        if node.op == "not":
            self._check_datetime(node.operand)

    @utils.only_required_for_messages("boolean-datetime")
    def visit_if(self, node: nodes.If) -> None:
        self._check_datetime(node.test)

    @utils.only_required_for_messages("boolean-datetime")
    def visit_ifexp(self, node: nodes.IfExp) -> None:
        self._check_datetime(node.test)

    @utils.only_required_for_messages("boolean-datetime")
    def visit_boolop(self, node: nodes.BoolOp) -> None:
        for value in node.values:
            self._check_datetime(value)

    @utils.only_required_for_messages(
        "method-cache-max-size-none",
        "singledispatch-method",
        "singledispatchmethod-function",
    )
    def visit_functiondef(self, node: nodes.FunctionDef) -> None:
        if node.decorators and isinstance(node.parent, nodes.ClassDef):
            self._check_lru_cache_decorators(node)
            self._check_dispatch_decorators(node)

    def _check_lru_cache_decorators(self, node: nodes.FunctionDef) -> None:
        """Check if instance methods are decorated with functools.lru_cache."""
        if any(utils.is_enum(ancestor) for ancestor in node.parent.ancestors()):
            # method of class inheriting from Enum is exempt from this check.
            return

        lru_cache_nodes: list[nodes.NodeNG] = []
        for d_node in node.decorators.nodes:
            # pylint: disable = too-many-try-statements
            try:
                for infered_node in d_node.infer():
                    q_name = infered_node.qname()
                    if q_name in NON_INSTANCE_METHODS:
                        return

                    # Check if there is a maxsize argument set to None in the call
                    if q_name in LRU_CACHE and isinstance(d_node, nodes.Call):
                        try:
                            arg = utils.get_argument_from_call(
                                d_node, position=0, keyword="maxsize"
                            )
                        except utils.NoSuchArgumentError:
                            break

                        if not isinstance(arg, nodes.Const) or arg.value is not None:
                            break

                        lru_cache_nodes.append(d_node)
                        break

                    if q_name == "functools.cache":
                        lru_cache_nodes.append(d_node)
                        break
            except astroid.InferenceError:
                pass
        for lru_cache_node in lru_cache_nodes:
            self.add_message(
                "method-cache-max-size-none",
                node=lru_cache_node,
                confidence=interfaces.INFERENCE,
            )

    def _check_dispatch_decorators(self, node: nodes.FunctionDef) -> None:
        decorators_map: dict[str, tuple[nodes.NodeNG, interfaces.Confidence]] = {}

        for decorator in node.decorators.nodes:
            if isinstance(decorator, nodes.Name) and decorator.name:
                decorators_map[decorator.name] = (decorator, interfaces.HIGH)
            elif utils.is_registered_in_singledispatch_function(node):
                decorators_map["singledispatch"] = (decorator, interfaces.INFERENCE)
            elif utils.is_registered_in_singledispatchmethod_function(node):
                decorators_map["singledispatchmethod"] = (
                    decorator,
                    interfaces.INFERENCE,
                )

        if "singledispatch" in decorators_map and "classmethod" in decorators_map:
            self.add_message(
                "singledispatch-method",
                node=decorators_map["singledispatch"][0],
                confidence=decorators_map["singledispatch"][1],
            )
        elif (
            "singledispatchmethod" in decorators_map
            and "staticmethod" in decorators_map
        ):
            self.add_message(
                "singledispatchmethod-function",
                node=decorators_map["singledispatchmethod"][0],
                confidence=decorators_map["singledispatchmethod"][1],
            )

    def _check_redundant_assert(self, node: nodes.Call, infer: InferenceResult) -> None:
        if (
            isinstance(infer, astroid.BoundMethod)
            and node.args
            and isinstance(node.args[0], nodes.Const)
            and infer.name in {"assertTrue", "assertFalse"}
        ):
            self.add_message(
                "redundant-unittest-assert",
                args=(infer.name, node.args[0].value),
                node=node,
            )

    def _check_datetime(self, node: nodes.NodeNG) -> None:
        """Check that a datetime was inferred, if so, emit boolean-datetime warning."""
        try:
            inferred = next(node.infer())
        except astroid.InferenceError:
            return
        if (
            isinstance(inferred, astroid.Instance)
            and inferred.qname() == "datetime.time"
        ):
            self.add_message("boolean-datetime", node=node)

    def _check_open_call(
        self, node: nodes.Call, open_module: str, func_name: str
    ) -> None:
        """Various checks for an open call."""
        mode_arg = None
        try:
            if open_module == "_io":
                mode_arg = utils.get_argument_from_call(
                    node, position=1, keyword="mode"
                )
            elif open_module == "pathlib":
                mode_arg = utils.get_argument_from_call(
                    node, position=0, keyword="mode"
                )
        except utils.NoSuchArgumentError:
            pass

        if mode_arg:
            mode_arg = utils.safe_infer(mode_arg)

            if (
                func_name in OPEN_FILES_MODE
                and isinstance(mode_arg, nodes.Const)
                and not _check_mode_str(mode_arg.value)
            ):
                self.add_message(
                    "bad-open-mode",
                    node=node,
                    args=mode_arg.value or str(mode_arg.value),
                )

        if (
            not mode_arg
            or isinstance(mode_arg, nodes.Const)
            and (not mode_arg.value or "b" not in str(mode_arg.value))
        ):
            encoding_arg = None
            try:
                if open_module == "pathlib":
                    if node.func.attrname == "read_text":
                        encoding_arg = utils.get_argument_from_call(
                            node, position=0, keyword="encoding"
                        )
                    elif node.func.attrname == "write_text":
                        encoding_arg = utils.get_argument_from_call(
                            node, position=1, keyword="encoding"
                        )
                    else:
                        encoding_arg = utils.get_argument_from_call(
                            node, position=2, keyword="encoding"
                        )
                else:
                    encoding_arg = utils.get_argument_from_call(
                        node, position=3, keyword="encoding"
                    )
            except utils.NoSuchArgumentError:
                self.add_message("unspecified-encoding", node=node)

            if encoding_arg:
                encoding_arg = utils.safe_infer(encoding_arg)

                if isinstance(encoding_arg, nodes.Const) and encoding_arg.value is None:
                    self.add_message("unspecified-encoding", node=node)

    def _check_env_function(self, node: nodes.Call, infer: nodes.FunctionDef) -> None:
        env_name_kwarg = "key"
        env_value_kwarg = "default"
        if node.keywords:
            kwargs = {keyword.arg: keyword.value for keyword in node.keywords}
        else:
            kwargs = None
        if node.args:
            env_name_arg = node.args[0]
        elif kwargs and env_name_kwarg in kwargs:
            env_name_arg = kwargs[env_name_kwarg]
        else:
            env_name_arg = None

        if env_name_arg:
            self._check_invalid_envvar_value(
                node=node,
                message="invalid-envvar-value",
                call_arg=utils.safe_infer(env_name_arg),
                infer=infer,
                allow_none=False,
            )

        if len(node.args) == 2:
            env_value_arg = node.args[1]
        elif kwargs and env_value_kwarg in kwargs:
            env_value_arg = kwargs[env_value_kwarg]
        else:
            env_value_arg = None

        if env_value_arg:
            self._check_invalid_envvar_value(
                node=node,
                infer=infer,
                message="invalid-envvar-default",
                call_arg=utils.safe_infer(env_value_arg),
                allow_none=True,
            )

    def _check_invalid_envvar_value(
        self,
        node: nodes.Call,
        infer: nodes.FunctionDef,
        message: str,
        call_arg: InferenceResult | None,
        allow_none: bool,
    ) -> None:
        if call_arg is None or isinstance(call_arg, util.UninferableBase):
            return

        name = infer.qname()
        if isinstance(call_arg, nodes.Const):
            emit = False
            if call_arg.value is None:
                emit = not allow_none
            elif not isinstance(call_arg.value, str):
                emit = True
            if emit:
                self.add_message(message, node=node, args=(name, call_arg.pytype()))
        else:
            self.add_message(message, node=node, args=(name, call_arg.pytype()))

    def deprecated_methods(self) -> set[str]:
        return self._deprecated_methods

    def deprecated_arguments(self, method: str) -> tuple[tuple[int | None, str], ...]:
        return self._deprecated_arguments.get(method, ())

    def deprecated_classes(self, module: str) -> Iterable[str]:
        return self._deprecated_classes.get(module, ())

    def deprecated_decorators(self) -> Iterable[str]:
        return self._deprecated_decorators


def register(linter: PyLinter) -> None:
    linter.register_checker(StdlibChecker(linter))
