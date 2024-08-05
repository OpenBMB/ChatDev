# =========== Copyright 2023 @ CAMEL-AI.org. All Rights Reserved. ===========
# Licensed under the Apache License, Version 2.0 (the “License”);
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an “AS IS” BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# =========== Copyright 2023 @ CAMEL-AI.org. All Rights Reserved. ==============
#
# File: camel/typing.py
# Description: Enumerations for model, task, role, and phase types.
# 
# ==============================================================================


from enum import Enum

# Enumerations are used here for several reasons:
# 1. They provide a set of named constants, improving code readability and maintainability.
# 2. They help prevent errors by restricting values to a predefined set.
# 3. They make the code more self-documenting, as the names of the enum members describe their purpose.
# 4. They can be easily extended or modified without changing the underlying logic of the code.


class ModelType(Enum):
    """
    Enumeration of different AI model types.

    Using an enum for model types ensures that only valid model names are used
    throughout the codebase, reducing the risk of typos or invalid model references.
    """

    GPT_3_5_TURBO = "gpt-3.5-turbo-16k-0613"
    GPT_3_5_TURBO_NEW = "gpt-3.5-turbo-16k"
    GPT_4 = "gpt-4"
    GPT_4_32k = "gpt-4-32k"
    GPT_4_TURBO = "gpt-4-turbo"
    GPT_4_TURBO_V = "gpt-4-turbo"
    GPT_4O = "gpt-4o"
    GTP_4O_MINI = "gpt-4o-mini"
    STUB = "stub"

    @property
    def value_for_tiktoken(self):
        """
        Returns the value to be used for tiktoken, using a default for STUB.
        This method demonstrates how enums can encapsulate behavior related to their values.
        """
        return self.value if self.name != "STUB" else "gpt-4o-mini"


class TaskType(Enum):
    """
    Enumeration of different task types.

    Using an enum for task types allows for easy categorization and filtering of tasks,
    and ensures that all parts of the system use consistent task type identifiers.
    """

    AI_SOCIETY = "ai_society"
    CODE = "code"
    MISALIGNMENT = "misalignment"
    TRANSLATION = "translation"
    EVALUATION = "evaluation"
    SOLUTION_EXTRACTION = "solution_extraction"
    STARTR_TEAM = "startr_team"
    DEFAULT = "default"


class RoleType(Enum):
    """
    Enumeration of different role types, including general and Startr.Team specific roles.

    An enum for roles helps in access control, task assignment, and workflow management
    by providing a standardized set of roles that can be easily referenced and validated.
    """

    ASSISTANT = "assistant"
    USER = "user"
    CRITIC = "critic"
    EMBODIMENT = "embodiment"
    DEFAULT = "default"
    STARTR_TEAM = "AgentTech"
    STARTR_TEAM_COUNSELOR = "counselor"
    STARTR_TEAM_CEO = "chief executive officer (CEO)"
    STARTR_TEAM_CHRO = "chief human resource officer (CHRO)"
    STARTR_TEAM_CPO = "chief product officer (CPO)"
    STARTR_TEAM_CTO = "chief technology officer (CTO)"
    STARTR_TEAM_PROGRAMMER = "programmer"
    STARTR_TEAM_REVIEWER = "code reviewer"
    STARTR_TEAM_TESTER = "software test engineer"
    STARTR_TEAM_CCO = "chief creative officer (CCO)"


class PhaseType(Enum):
    """
    Enumeration of different phases in a development or task process.

    Using an enum for phases allows for clear tracking of the current state of a project,
    enables phase-specific behavior, and facilitates workflow management and reporting.
    """

    REFLECTION = "reflection"
    RECRUITING_CHRO = "recruiting CHRO"
    RECRUITING_CPO = "recruiting CPO"
    RECRUITING_CTO = "recruiting CTO"
    DEMAND_ANALYSIS = "demand analysis"
    CHOOSING_LANGUAGE = "choosing language"
    RECRUITING_PROGRAMMER = "recruiting programmer"
    RECRUITING_REVIEWER = "recruiting reviewer"
    RECRUITING_TESTER = "recruiting software test engineer"
    RECRUITING_CCO = "recruiting chief creative officer"
    CODING = "coding"
    CODING_COMPLETION = "coding completion"
    CODING_AUTOMODE = "coding auto mode"
    REVIEWING_COMMENT = "review comment"
    REVIEWING_MODIFICATION = "code modification after reviewing"
    ERROR_SUMMARY = "error summary"
    MODIFICATION = "code modification"
    ART_ELEMENT_ABSTRACTION = "art element abstraction"
    ART_ELEMENT_INTEGRATION = "art element integration"
    CREATING_ENVIRONMENT_DOCUMENT = "environment document"
    CREATING_USER_MANUAL = "user manual"


# Exports all the enum classes
# Using __all__ with enums makes it clear which types are intended to be used by other modules,
# and allows for easy importing of all relevant types in one line.
__all__ = ["TaskType", "RoleType", "ModelType", "PhaseType"]
