import pytest

from investory.agent_core.actions.executors import (
    AskMissingFieldsExecutor,
    RefuseInvestmentAdviceExecutor,
    RunTaskModelExecutor,
    RunToolExecutor,
)
from investory.agent_core.actions.router import ActionRouter, ActionRoutingError
from investory.agent_core.contracts.action_contract import ActionCall


def _call(action: str) -> ActionCall:
    return ActionCall.model_construct(
        action=action,
        task_name="instrument_brief",
        params={},
        decision_reason="test decision",
        request_id=None,
    )


def test_router_finds_ask_missing_fields_executor():
    executor = ActionRouter().route(_call("ask_missing_fields"))

    assert isinstance(executor, AskMissingFieldsExecutor)


def test_router_finds_run_task_model_executor():
    executor = ActionRouter().route(_call("run_task_model"))

    assert isinstance(executor, RunTaskModelExecutor)


def test_router_finds_run_tool_executor():
    executor = ActionRouter().route(_call("run_tool"))

    assert isinstance(executor, RunToolExecutor)


def test_router_finds_refuse_investment_advice_executor():
    executor = ActionRouter().route(_call("refuse_investment_advice"))

    assert isinstance(executor, RefuseInvestmentAdviceExecutor)


def test_router_rejects_unregistered_action():
    with pytest.raises(ActionRoutingError, match="No executor registered"):
        ActionRouter(executors={}).route(_call("unknown_action"))
