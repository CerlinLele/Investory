from enum import Enum


class InvestoryAction(str, Enum):
    ASK_FOR_MISSING_INPUT = "ask_for_missing_input"
    REFUSE_AND_REDIRECT = "refuse_and_redirect"
    EXECUTE_LEARNING_TASK = "execute_learning_task"
    CALL_TOOL = "call_tool"
    FINALIZE = "finalize"
