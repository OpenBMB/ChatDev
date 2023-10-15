import inspect
import random
import re
import unittest

try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

from . import import_submodule


class PygameTestLoader(unittest.TestLoader):
    def __init__(
        self, randomize_tests=False, include_incomplete=False, exclude=("interactive",)
    ):
        super().__init__()
        self.randomize_tests = randomize_tests

        if exclude is None:
            self.exclude = set()
        else:
            self.exclude = set(exclude)

        if include_incomplete:
            self.testMethodPrefix = ("test", "todo_")

    def getTestCaseNames(self, testCaseClass):
        res = []
        for name in super().getTestCaseNames(testCaseClass):
            tags = get_tags(testCaseClass, getattr(testCaseClass, name))
            if self.exclude.isdisjoint(tags):
                res.append(name)

        if self.randomize_tests:
            random.shuffle(res)

        return res


# Exclude by tags:

TAGS_RE = re.compile(r"\|[tT]ags:(-?[ a-zA-Z,0-9_\n]+)\|", re.M)


class TestTags:
    def __init__(self):
        self.memoized = {}
        self.parent_modules = {}

    def get_parent_module(self, class_):
        if class_ not in self.parent_modules:
            self.parent_modules[class_] = import_submodule(class_.__module__)
        return self.parent_modules[class_]

    def __call__(self, parent_class, meth):
        key = (parent_class, meth.__name__)
        if key not in self.memoized:
            parent_module = self.get_parent_module(parent_class)

            module_tags = getattr(parent_module, "__tags__", [])
            class_tags = getattr(parent_class, "__tags__", [])

            tags = TAGS_RE.search(inspect.getdoc(meth) or "")
            if tags:
                test_tags = [t.strip() for t in tags.group(1).split(",")]
            else:
                test_tags = []

            combined = set()
            for tags in (module_tags, class_tags, test_tags):
                if not tags:
                    continue

                add = {t for t in tags if not t.startswith("-")}
                remove = {t[1:] for t in tags if t not in add}

                if add:
                    combined.update(add)
                if remove:
                    combined.difference_update(remove)

            self.memoized[key] = combined

        return self.memoized[key]


get_tags = TestTags()
