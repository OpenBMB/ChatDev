# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

from pylint import checkers
from pylint.lint import PyLinter
from pylint.testutils.reporter_for_tests import GenericTestReporter


def create_test_linter() -> PyLinter:
    test_reporter = GenericTestReporter()
    linter_ = PyLinter()
    linter_.set_reporter(test_reporter)
    linter_.config.persistent = 0
    checkers.initialize(linter_)
    return linter_


# Can't be renamed to a constant (easily), it breaks countless tests
linter = create_test_linter()
