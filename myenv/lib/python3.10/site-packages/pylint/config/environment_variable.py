# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

import warnings

from pylint.config.find_default_config_files import find_pylintrc

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    PYLINTRC = find_pylintrc()
