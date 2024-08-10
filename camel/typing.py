from enum import Enum
from camel.config_loader import config_loader, ModelType

# The ModelType enum is now dynamically created in ConfigLoader

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
